"""
src/validator/toon_validator.py
Validates a .toon document string for structural correctness.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

VALID_DIRECTIVE = re.compile(r"^@[a-z][a-z0-9_]{0,47}(\s.*)?$")
COMMENT_LINE = re.compile(r"^\s*#.*$")
INDENT_ITEM = re.compile(r"^\s+-\s+.+$")
BLANK_LINE = re.compile(r"^\s*$")


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    directive_count: int = 0

    def __str__(self) -> str:
        status = "✓ valid" if self.valid else "✗ invalid"
        parts = [f"{status} — {self.directive_count} directives"]
        for e in self.errors:
            parts.append(f"  ERROR: {e}")
        for w in self.warnings:
            parts.append(f"  WARN:  {w}")
        return "\n".join(parts)


def validate(toon_text: str) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    directive_count = 0
    seen: set[str] = set()

    if not toon_text.strip():
        return ValidationResult(valid=False, errors=["Document is empty"])

    for lineno, line in enumerate(toon_text.splitlines(), start=1):
        if BLANK_LINE.match(line) or COMMENT_LINE.match(line) or INDENT_ITEM.match(line):
            continue
        if not line.startswith("@"):
            errors.append(f"Line {lineno}: unexpected content: {line!r}")
            continue
        if not VALID_DIRECTIVE.match(line):
            errors.append(f"Line {lineno}: malformed directive: {line!r}")
            continue
        name = line.split()[0][1:]
        directive_count += 1
        if name in seen:
            warnings.append(f"Line {lineno}: duplicate directive @{name}")
        seen.add(name)

    if directive_count == 0:
        errors.append("No directives found")
    if "task" not in seen and "name" not in seen:
        warnings.append("Consider adding a @task or @name directive")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        directive_count=directive_count,
    )
