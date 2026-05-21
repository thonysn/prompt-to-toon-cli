"""
src/writer/file_writer.py
Safely writes .toon content to disk.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write(content: str, output: Path) -> Path:
    """Atomically write content to output path with a safe temp-file swap."""
    output = _sanitize_output_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: write to a temp file in the same dir, then rename
    fd, tmp_path = tempfile.mkstemp(dir=output.parent, suffix=".toon.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        Path(tmp_path).replace(output)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return output


def derive_output_path(input_path: Path | None, text_mode: bool) -> Path:
    """Choose a default output path when --output is not specified."""
    if input_path:
        return input_path.with_suffix(".toon")
    return Path("output.toon")


def _sanitize_output_path(path: Path) -> Path:
    resolved = path.resolve()
    # Refuse writes to sensitive system directories
    sensitive = ["/etc", "/proc", "/sys", "/bin", "/usr/bin"]
    for s in sensitive:
        if str(resolved).startswith(s):
            raise ValueError(f"Refusing to write to sensitive path: {resolved}")
    return path
