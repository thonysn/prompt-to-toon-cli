# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✓         |

## Reporting a Vulnerability

Please report security vulnerabilities by opening a **private** GitHub Security Advisory rather than a public issue.

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

We aim to respond within 72 hours and patch critical issues within 7 days.

## Security Design

`toon` is designed with security as a first-class concern:

- **No shell execution** — no `subprocess`, `os.system`, or `eval` anywhere
- **No network access** — fully offline, no outbound connections
- **Path traversal prevention** — all file paths are validated and resolved before access
- **Input size limits** — files over 10 MB are rejected
- **Sensitive path protection** — reads/writes to `/etc`, `/proc`, `/sys`, `/bin` are refused
- **Atomic writes** — output files are written via temp-file + rename to prevent partial writes
- **Dependency minimalism** — only `typer`, `pydantic`, `PyYAML` as runtime deps
