"""
src/parser/input_parser.py
Detects input format and normalizes content to a plain dict or string.
Supports: natural language, JSON, YAML, Markdown, XML, plain text.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ParsedInput:
    raw: str
    fmt: str   # "json" | "yaml" | "xml" | "markdown" | "text"
    data: Any  # dict | list | str


# ---------------------------------------------------------------------------

def parse_file(path: Path) -> ParsedInput:
    _validate_path(path)
    raw = path.read_text(encoding="utf-8")
    fmt = _detect_format_by_extension(path.suffix.lower(), raw)
    return _parse_raw(raw, fmt)


def parse_text(text: str) -> ParsedInput:
    text = text.strip()
    fmt = _detect_format_by_content(text)
    return _parse_raw(text, fmt)


def parse_stdin() -> ParsedInput:
    return parse_text(sys.stdin.read())


# ---------------------------------------------------------------------------

def _validate_path(path: Path) -> None:
    resolved = path.resolve()
    sensitive = ["/etc", "/proc", "/sys"]
    for s in sensitive:
        if str(resolved).startswith(s):
            raise ValueError(f"Refusing to read from sensitive path: {resolved}")
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Not a regular file: {path}")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Input file exceeds 10 MB limit")


def _detect_format_by_extension(ext: str, raw: str) -> str:
    ext_map = {
        ".json": "json", ".yaml": "yaml", ".yml": "yaml",
        ".xml": "xml", ".md": "markdown", ".markdown": "markdown",
        ".txt": "text", ".toon": "text",
    }
    return ext_map.get(ext) or _detect_format_by_content(raw)


def _detect_format_by_content(text: str) -> str:
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            json.loads(text)
            return "json"
        except json.JSONDecodeError:
            pass
    if re.match(r"^\s*<\?xml|^\s*<[a-zA-Z]", stripped):
        return "xml"
    if re.search(r"^[a-zA-Z_][a-zA-Z0-9_]*\s*:", text, re.MULTILINE):
        try:
            parsed = yaml.safe_load(text)
            if isinstance(parsed, dict):
                return "yaml"
        except yaml.YAMLError:
            pass
    if re.search(r"^#{1,6}\s+\S|^\*\*|^-\s+\S", text, re.MULTILINE):
        return "markdown"
    return "text"


def _parse_raw(raw: str, fmt: str) -> ParsedInput:
    try:
        if fmt == "json":
            return ParsedInput(raw=raw, fmt=fmt, data=json.loads(raw))
        elif fmt == "yaml":
            loaded = yaml.safe_load(raw)
            data = loaded if isinstance(loaded, (dict, list)) else str(loaded)
            return ParsedInput(raw=raw, fmt=fmt, data=data)
        elif fmt == "xml":
            return ParsedInput(raw=raw, fmt=fmt, data=_xml_to_dict(raw))
        elif fmt == "markdown":
            return ParsedInput(raw=raw, fmt=fmt, data=_markdown_to_dict(raw))
        else:
            return ParsedInput(raw=raw, fmt="text", data=raw)
    except MemoryError:
        raise ValueError("Input is too large or too complex to parse safely")
    except Exception:
        return ParsedInput(raw=raw, fmt="text", data=raw)


def _xml_to_dict(text: str) -> dict[str, Any]:
    import xml.etree.ElementTree as ET
    import xml.parsers.expat as expat

    def _safe_parse(raw: str) -> ET.Element:
        builder = ET.TreeBuilder()
        p = expat.ParserCreate()

        def _reject_entity_decl(name, *args):
            raise ET.ParseError(f"XML entity declarations are not allowed: {name}")

        p.EntityDeclHandler = _reject_entity_decl
        p.ExternalEntityRefHandler = lambda *_: 0
        p.StartElementHandler = builder.start
        p.EndElementHandler = builder.end
        p.CharacterDataHandler = builder.data

        try:
            p.Parse(raw, True)
        except expat.ExpatError as exc:
            raise ET.ParseError(str(exc)) from exc

        return builder.close()

    def _elem(el: ET.Element, depth: int = 0) -> Any:
        if depth > 50:
            raise ValueError("XML structure too deeply nested (max depth: 50)")
        children = list(el)
        if not children:
            return (el.text or "").strip()
        r: dict[str, Any] = {}
        for c in children:
            val = _elem(c, depth + 1)
            if c.tag in r:
                if not isinstance(r[c.tag], list):
                    r[c.tag] = [r[c.tag]]
                r[c.tag].append(val)
            else:
                r[c.tag] = val
        return r

    root = _safe_parse(text)
    return {root.tag: _elem(root)}


def _markdown_to_dict(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current: str | None = None
    lines = text.splitlines()
    i = 0
    code_blocks: list[str] = []
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            block: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            code_blocks.append("\n".join(block).strip())
            i += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading:
            current = heading.group(2).strip().lower().replace(" ", "_")
            result[current] = []
            i += 1
            continue
        bullet = re.match(r"^[-*+]\s+(.*)", line)
        if bullet:
            item = bullet.group(1).strip()
            if current and isinstance(result.get(current), list):
                result[current].append(item)
            i += 1
            continue
        if current and line.strip():
            if isinstance(result.get(current), list) and not result[current]:
                result[current] = line.strip()
            elif isinstance(result.get(current), str):
                result[current] += " " + line.strip()
        i += 1
    if code_blocks:
        result["code_blocks"] = code_blocks
    if not result:
        result["content"] = text
    return result
