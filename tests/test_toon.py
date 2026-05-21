"""
tests/test_toon.py
Full test suite for toon-cli (stdlib unittest, no pytest required).
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generator.toon_generator import _safe_value, _slug, generate
from src.parser.input_parser import parse_file, parse_text
from src.parser.normalizer import SemanticDoc, normalize
from src.validator.toon_validator import validate
from src.writer.file_writer import _sanitize_output_path, write


# ===========================================================================
# Parser
# ===========================================================================

class TestParseText(unittest.TestCase):
    def test_json_detection(self):
        p = parse_text('{"task": "auth", "stack": "fastapi"}')
        self.assertEqual(p.fmt, "json")
        self.assertEqual(p.data["task"], "auth")

    def test_yaml_detection(self):
        p = parse_text("task: auth\nstack: fastapi\n")
        self.assertEqual(p.fmt, "yaml")
        self.assertEqual(p.data["task"], "auth")

    def test_markdown_detection(self):
        p = parse_text("# My Service\n\n- feature one\n- feature two\n")
        self.assertEqual(p.fmt, "markdown")

    def test_plaintext_fallback(self):
        p = parse_text("Create a FastAPI auth service with JWT.")
        self.assertEqual(p.fmt, "text")

    def test_xml_detection(self):
        p = parse_text("<project><name>MyApp</name></project>")
        self.assertEqual(p.fmt, "xml")
        self.assertIn("project", p.data)

    def test_empty_string_is_text(self):
        p = parse_text("")
        self.assertEqual(p.fmt, "text")


class TestParseFile(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def test_json_file(self):
        f = self.tmp / "spec.json"
        f.write_text('{"task": "demo", "version": "1.0"}')
        p = parse_file(f)
        self.assertEqual(p.fmt, "json")
        self.assertEqual(p.data["task"], "demo")

    def test_yaml_file(self):
        f = self.tmp / "spec.yaml"
        f.write_text("task: demo\nstack: python\n")
        p = parse_file(f)
        self.assertEqual(p.fmt, "yaml")

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            parse_file(self.tmp / "nope.json")

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            parse_file(Path("/etc/passwd"))

    def test_large_file_rejected(self):
        f = self.tmp / "big.txt"
        f.write_bytes(b"x" * (11 * 1024 * 1024))
        with self.assertRaises(ValueError):
            parse_file(f)


# ===========================================================================
# Normalizer
# ===========================================================================

class TestNormalize(unittest.TestCase):
    def test_dict_with_title(self):
        from src.parser.input_parser import ParsedInput
        p = ParsedInput(raw='{}', fmt="json", data={"task": "auth", "stack": "fastapi"})
        doc = normalize(p)
        self.assertEqual(doc.title, "auth")

    def test_text_extracts_title(self):
        p = parse_text("Build an OAuth2 service for enterprise clients.")
        doc = normalize(p)
        self.assertTrue(doc.title)

    def test_tags_extracted(self):
        p = parse_text('{"tags": ["jwt", "oauth2", "fastapi"], "name": "auth"}')
        doc = normalize(p)
        self.assertIn("jwt", doc.tags)

    def test_list_input(self):
        from src.parser.input_parser import ParsedInput
        p = ParsedInput(raw="[]", fmt="json", data=["auth_service", "jwt", "postgres"])
        doc = normalize(p)
        self.assertIn("items", doc.sections)


# ===========================================================================
# Generator
# ===========================================================================

class TestSlug(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_slug("My Task"), "my_task")

    def test_special_chars(self):
        self.assertEqual(_slug("hello-world!"), "hello_world")

    def test_long_slug_truncated(self):
        self.assertLessEqual(len(_slug("a" * 100)), 48)

    def test_empty_string(self):
        self.assertEqual(_slug(""), "")


class TestSafeValue(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(_safe_value("hello\n  world"), "hello world")

    def test_truncates_long(self):
        self.assertLessEqual(len(_safe_value("x" * 300)), 200)

    def test_short_passthrough(self):
        self.assertEqual(_safe_value("hello"), "hello")


class TestGenerate(unittest.TestCase):
    def _doc(self, **kwargs):
        return SemanticDoc(**kwargs)

    def test_basic_output(self):
        doc = self._doc(title="Auth Service", description="JWT-based auth")
        out = generate(doc)
        self.assertIn("@task auth_service", out)
        self.assertIn("@desc", out)

    def test_tags_line(self):
        doc = self._doc(title="Demo", tags=["jwt", "oauth2"])
        out = generate(doc)
        self.assertIn("@tags jwt oauth2", out)

    def test_compact_no_double_blank(self):
        doc = self._doc(title="Demo", description="desc", tags=["a", "b"])
        out = generate(doc, compact=True)
        self.assertNotIn("\n\n", out)

    def test_pretty_has_comment(self):
        doc = self._doc(title="Demo")
        out = generate(doc, pretty=True)
        self.assertIn("#", out)

    def test_sections_list(self):
        doc = self._doc(title="Demo", sections={"features": ["jwt", "oauth2"]})
        out = generate(doc)
        self.assertIn("@features", out)

    def test_sections_dict(self):
        doc = self._doc(title="Demo", sections={"config": {"port": "8080"}})
        out = generate(doc)
        self.assertIn("@port 8080", out)


# ===========================================================================
# Validator
# ===========================================================================

class TestValidate(unittest.TestCase):
    def test_valid_document(self):
        result = validate("@task auth_service\n@stack fastapi\n@desc JWT auth\n")
        self.assertTrue(result.valid)
        self.assertEqual(result.directive_count, 3)

    def test_empty_document(self):
        result = validate("")
        self.assertFalse(result.valid)

    def test_malformed_directive(self):
        result = validate("@TASK broken\n")
        self.assertFalse(result.valid)

    def test_duplicate_directive_warns(self):
        result = validate("@task a\n@task b\n")
        self.assertTrue(any("duplicate" in w for w in result.warnings))

    def test_no_task_warns(self):
        result = validate("@stack fastapi\n@desc some desc\n")
        self.assertTrue(result.valid)
        self.assertTrue(any("task" in w or "name" in w for w in result.warnings))

    def test_comment_lines_ok(self):
        self.assertTrue(validate("# comment\n@task demo\n").valid)

    def test_indent_items_ok(self):
        self.assertTrue(validate("@task demo\n@features\n  - jwt\n  - oauth2\n").valid)


# ===========================================================================
# Writer
# ===========================================================================

class TestWriter(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def test_writes_file(self):
        out = self.tmp / "out.toon"
        write("@task demo\n", out)
        self.assertEqual(out.read_text(), "@task demo\n")

    def test_creates_parent_dirs(self):
        out = self.tmp / "nested" / "dir" / "out.toon"
        write("@task demo\n", out)
        self.assertTrue(out.exists())

    def test_sensitive_path_rejected(self):
        with self.assertRaises(ValueError):
            _sanitize_output_path(Path("/etc/toon.toon"))

    def test_overwrites_existing(self):
        out = self.tmp / "out.toon"
        out.write_text("old")
        write("@task new\n", out)
        self.assertEqual(out.read_text(), "@task new\n")


# ===========================================================================
# End-to-end
# ===========================================================================

class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def test_json_to_toon(self):
        f = self.tmp / "spec.json"
        f.write_text(json.dumps({
            "task": "auth_service", "stack": "fastapi",
            "features": ["jwt", "oauth2", "refresh_tokens"],
        }))
        parsed = parse_file(f)
        doc = normalize(parsed)
        toon = generate(doc, pretty=True)
        result = validate(toon)
        self.assertTrue(result.valid)
        self.assertIn("@task", toon)

    def test_yaml_to_toon(self):
        f = self.tmp / "spec.yaml"
        f.write_text(yaml.dump({
            "name": "data_pipeline",
            "description": "ETL for warehouse",
            "tags": ["etl", "airflow", "postgres"],
        }))
        parsed = parse_file(f)
        toon = generate(normalize(parsed))
        self.assertTrue(validate(toon).valid)

    def test_natural_language_to_toon(self):
        parsed = parse_text("Build a recommendation engine using collaborative filtering.")
        toon = generate(normalize(parsed))
        self.assertTrue(validate(toon).valid)
        self.assertIn("@task", toon)

    def test_markdown_to_toon(self):
        f = self.tmp / "spec.md"
        f.write_text("# Chat Service\n\nReal-time messaging backend.\n\n## Features\n- websockets\n- redis\n")
        toon = generate(normalize(parse_file(f)), pretty=True)
        self.assertTrue(validate(toon).valid)

    def test_compact_smaller_than_pretty(self):
        parsed = parse_text("A microservice for user authentication with JWT.")
        doc = normalize(parsed)
        self.assertLessEqual(len(generate(doc, compact=True)), len(generate(doc, pretty=True)))

    def test_xml_to_toon(self):
        f = self.tmp / "spec.xml"
        f.write_text("<project><name>MyAPI</name><stack>fastapi</stack></project>")
        toon = generate(normalize(parse_file(f)))
        self.assertTrue(validate(toon).valid)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestSecurityFixes(unittest.TestCase):
    def test_xml_deep_nesting_rejected(self):
        deep = "<a>" * 60 + "x" + "</a>" * 60
        p = parse_text(deep)
        self.assertEqual(p.fmt, "text")  # falls back safely, no crash

    def test_xml_entity_declaration_rejected(self):
        malicious = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY lol "lol">]><x>&lol;</x>'
        p = parse_text(malicious)
        self.assertIsNotNone(p)  # no uncaught exception

    def test_xml_normal_still_works(self):
        p = parse_text("<project><name>MyApp</name></project>")
        self.assertEqual(p.fmt, "xml")
        self.assertIn("project", p.data)

    def test_yaml_safe_load_blocks_exec(self):
        evil = "!!python/object/apply:os.system ['echo pwned']"
        p = parse_text(evil)
        self.assertIsNotNone(p)  # falls back to text, no execution
