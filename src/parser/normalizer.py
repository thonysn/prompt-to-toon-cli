"""
src/parser/normalizer.py
Normalizes heterogeneous parsed inputs into a canonical SemanticDoc.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .input_parser import ParsedInput


@dataclass
class SemanticDoc:
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    sections: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    raw_text: str = ""
    source_fmt: str = "text"


# Ordered by priority — first match wins as @task
_TITLE_KEYS = (
    "title", "name", "task", "subject", "id",
    "project", "service", "module", "component",
)

# Regex for semi-technical KEY: value blocks (ALL_CAPS or TitleCase single word)
_KV_LINE = re.compile(r"^([A-Z][A-Z0-9_]{1,29}|[A-Z][a-z]\w{1,28})\s*:\s*(.*)")


def normalize(parsed: ParsedInput) -> SemanticDoc:
    doc = SemanticDoc(source_fmt=parsed.fmt, raw_text=parsed.raw)
    if parsed.fmt == "text":
        return _normalize_text(parsed.raw, doc)
    if isinstance(parsed.data, dict):
        return _normalize_dict(parsed.data, doc)
    if isinstance(parsed.data, list):
        return _normalize_list(parsed.data, doc)
    return _normalize_text(str(parsed.data), doc)


def _normalize_text(text: str, doc: SemanticDoc) -> SemanticDoc:
    # Try semi-technical KEY: value detection before falling back to free text
    kv = _parse_kv_block(text)
    if kv:
        return _normalize_dict(kv, doc)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        doc.title = _extract_title(lines[0])
        doc.description = " ".join(lines[1:4]) if len(lines) > 1 else ""
    doc.tags = _extract_tags(text)
    doc.sections = _extract_key_phrases(text)
    return doc


def _normalize_dict(data: dict[str, Any], doc: SemanticDoc) -> SemanticDoc:
    # Unwrap single-key nested dicts (common in XML: {"root": {...content...}})
    if len(data) == 1:
        only_key, only_val = next(iter(data.items()))
        if isinstance(only_val, dict):
            inner = _normalize_dict(only_val, doc)
            if not inner.title:
                inner.title = str(only_key)
            return inner

    title_key: str | None = None
    for key in _TITLE_KEYS:
        # Only accept scalar values as title source
        if key in data and isinstance(data[key], (str, int, float)):
            doc.title = str(data[key])
            title_key = key
            break
    for key in ("description", "summary", "content", "body", "text", "goal"):
        if key in data:
            doc.description = _to_str(data[key])
            break
    for key in ("tags", "keywords", "labels", "features", "topics"):
        if key in data:
            val = data[key]
            if isinstance(val, list):
                doc.tags = [str(v) for v in val]
            elif isinstance(val, str):
                doc.tags = [t.strip() for t in re.split(r"[,;\s]+", val) if t.strip()]
            break
    skip = {
        "title", "name", "description", "summary", "body", "text",
        "tags", "keywords", "labels", "features", "topics", "goal", "content",
    }
    # Prevent the field used as title from being re-emitted as a directive
    if title_key:
        skip = skip | {title_key}
    doc.metadata = {k: str(v) for k, v in data.items()
                    if isinstance(v, str) and k not in skip}
    raw_sections = {k: v for k, v in data.items() if k not in skip}
    # Unwrap {"child_tag": [items]} → [items] (XML repeated-element pattern)
    doc.sections = {
        k: (next(iter(v.values())) if isinstance(v, dict) and len(v) == 1
            and isinstance(next(iter(v.values())), list) else v)
        for k, v in raw_sections.items()
    }
    if not doc.title and doc.raw_text:
        first = (doc.raw_text.splitlines() or [""])[0]
        candidate = _extract_title(first)
        if any(c.isalnum() for c in candidate):  # only use if it yields a meaningful slug
            doc.title = candidate
    return doc


def _normalize_list(data: list[Any], doc: SemanticDoc) -> SemanticDoc:
    doc.sections["items"] = data
    if data and isinstance(data[0], str):
        doc.title = data[0]
        doc.description = " ".join(str(d) for d in data[1:3])
    return doc


def _parse_kv_block(text: str) -> dict[str, Any] | None:
    """Detect ALL_CAPS or TitleCase KEY: value blocks (semi-technical format).

    Returns a dict if at least 2 KV pairs are found, otherwise None.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    result: dict[str, Any] = {}
    current: str | None = None
    for line in lines:
        m = _KV_LINE.match(line)
        if m:
            key = m.group(1).strip().lower()
            val = m.group(2).strip()
            if val:
                result[key] = val
                current = None
            else:
                result[key] = []
                current = key
        elif current is not None and re.match(r"^[-*+]\s+", line):
            result[current].append(re.sub(r"^[-*+]\s+", "", line))
        elif line and not line[0].isspace():
            current = None  # non-bullet top-level line ends current section
    return result if len(result) >= 2 else None


def _extract_title(text: str) -> str:
    text = re.sub(r"^#+\s*", "", text).strip()
    return text[:120]


def _extract_tags(text: str) -> list[str]:
    hashtags = re.findall(r"#([A-Za-z]\w+)", text)
    caps = re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", text)
    return list(dict.fromkeys(hashtags + caps))[:20]


def _extract_key_phrases(text: str) -> dict[str, Any]:
    sections: dict[str, Any] = {}
    current: str | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.endswith(":") and len(line) < 50:
            current = line[:-1].lower().replace(" ", "_")
            sections[current] = []
        elif current and (line.startswith("-") or line.startswith("*")):
            sections[current].append(line.lstrip("-* "))
        elif current and isinstance(sections[current], list) and not sections[current]:
            sections[current].append(line)
    return sections


def _to_str(val: Any) -> str:
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return " ".join(str(v) for v in val)
    return str(val)
