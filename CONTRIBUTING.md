# Contributing

Contributions are welcome! Here's how to get started.

## Setup

```bash
git clone https://github.com/yourusername/prompt-to-toon-cli
cd prompt-to-toon-cli
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest --cov=src --cov-report=term-missing
```

## Code Style

We use `ruff` for linting and formatting:

```bash
ruff check src tests
ruff format src tests
```

## Pull Request Guidelines

1. Fork the repository and create a feature branch
2. Add tests for any new functionality
3. Ensure all tests pass and coverage stays above 90%
4. Update documentation if you change CLI behavior
5. Keep PRs focused — one feature or fix per PR

## Adding a New Input Format

1. Add detection logic in `src/parser/input_parser.py` (`_detect_format_by_content`)
2. Add a parser case in `_parse_raw`
3. Add normalization logic in `src/parser/normalizer.py` if needed
4. Add an example file in `examples/`
5. Add test cases in `tests/test_toon.py`

## Architecture Overview

```
input → parse_file/parse_text/parse_stdin
      → ParsedInput (raw + fmt + data)
      → normalize()
      → SemanticDoc (title, description, tags, sections, metadata)
      → generate()
      → .toon string
      → validate()
      → write()
      → .toon file on disk
```
