"""
benchmarks/bench.py
Simple timing benchmark for the toon pipeline.

Run with:
    python benchmarks/bench.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

SAMPLES = {
    "short_text": "Build a FastAPI authentication service with JWT and OAuth2.",
    "medium_json": json.dumps({
        "task": "auth_service",
        "stack": "fastapi",
        "features": ["jwt", "oauth2", "refresh_tokens", "rate_limiting"],
        "description": "Stateless authentication microservice for enterprise SaaS platform",
        "dependencies": ["python-jose", "passlib", "sqlalchemy", "redis"],
        "endpoints": ["/auth/login", "/auth/refresh", "/auth/logout", "/auth/me"],
    }),
    "large_yaml_like": "\n".join(
        [f"module_{i}: description of module {i}" for i in range(100)]
    ),
}

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generator.toon_generator import generate
from src.parser.input_parser import parse_text
from src.parser.normalizer import normalize
from src.validator.toon_validator import validate

ITERATIONS = 200


def bench(name: str, text: str) -> None:
    start = time.perf_counter()
    for _ in range(ITERATIONS):
        parsed = parse_text(text)
        doc = normalize(parsed)
        toon = generate(doc)
        validate(toon)
    elapsed = time.perf_counter() - start
    per_call = elapsed / ITERATIONS * 1000
    print(f"  {name:<20} {per_call:.3f} ms/call  ({ITERATIONS} iterations)")


def main() -> None:
    print(f"\ntoon-cli benchmark ({ITERATIONS} iterations each)\n")
    for name, sample in SAMPLES.items():
        bench(name, sample)
    print()


if __name__ == "__main__":
    main()
