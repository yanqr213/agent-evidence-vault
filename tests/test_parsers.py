import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_evidence_vault.parsers import (
    discover_evidence_files,
    first_str,
    infer_status,
    normalize_status,
    parse_evidence_dir,
    parse_json,
    parse_jsonl,
    parse_records,
    parse_text_blocks,
    record_to_evidence,
)


class ParserTests(unittest.TestCase):
    def test_normalize_status_pass_alias(self):
        self.assertEqual(normalize_status("ok"), "passed")

    def test_normalize_status_fail_alias(self):
        self.assertEqual(normalize_status("FAIL"), "failed")

    def test_normalize_status_empty(self):
        self.assertEqual(normalize_status(" "), "unknown")

    def test_first_str_uses_first_present(self):
        self.assertEqual(first_str({"id": "a"}, ["name", "id"], "x"), "a")

    def test_first_str_default(self):
        self.assertEqual(first_str({}, ["name"], "x"), "x")

    def test_infer_command_status_passed(self):
        self.assertEqual(infer_status("commands", {"exit_code": 0}), "passed")

    def test_infer_command_status_failed(self):
        self.assertEqual(infer_status("commands", {"exit_code": 2}), "failed")

    def test_infer_risk_open(self):
        self.assertEqual(infer_status("risks", {}), "open")

    def test_parse_jsonl_skips_blank_and_comment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "commands.jsonl"
            path.write_text('\n# hi\n{"name":"a"}\n', encoding="utf-8")
            self.assertEqual(parse_jsonl(path), [{"name": "a"}])

    def test_parse_jsonl_rejects_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "commands.jsonl"
            path.write_text("{bad}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                parse_jsonl(path)

    def test_parse_jsonl_rejects_non_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "commands.jsonl"
            path.write_text("[1]\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                parse_jsonl(path)

    def test_parse_json_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tests.json"
            path.write_text('{"name":"one"}', encoding="utf-8")
            self.assertEqual(parse_json(path), [{"name": "one"}])

    def test_parse_json_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tests.json"
            path.write_text('{"items":[{"name":"one"}]}', encoding="utf-8")
            self.assertEqual(parse_json(path), [{"name": "one"}])

    def test_parse_json_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tests.json"
            path.write_text('[{"name":"one"}]', encoding="utf-8")
            self.assertEqual(parse_json(path), [{"name": "one"}])

    def test_parse_json_rejects_scalar(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tests.json"
            path.write_text('"x"', encoding="utf-8")
            with self.assertRaises(ValueError):
                parse_json(path)

    def test_parse_json_rejects_non_object_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tests.json"
            path.write_text('[1]', encoding="utf-8")
            with self.assertRaises(ValueError):
                parse_json(path)

    def test_parse_text_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "acceptance.txt"
            path.write_text("name: one\nstatus: passed\n\nloose note\n", encoding="utf-8")
            records = parse_text_blocks(path)
            self.assertEqual(records[0]["name"], "one")
            self.assertEqual(records[1]["note"], "loose note")

    def test_parse_records_dispatch_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "commands.jsonl"
            path.write_text('{"name":"a"}\n', encoding="utf-8")
            self.assertEqual(parse_records(path)[0]["name"], "a")

    def test_parse_records_rejects_unknown_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "commands.csv"
            path.write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                parse_records(path)

    def test_record_to_evidence(self):
        item = record_to_evidence("commands", Path("commands.jsonl"), {"command": "python", "exit_code": 0})
        self.assertEqual(item.name, "python")
        self.assertEqual(item.status, "passed")

    def test_discover_missing_dir_returns_categories(self):
        found = discover_evidence_files(Path("does-not-exist"))
        self.assertIn("commands", found)

    def test_parse_evidence_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            (evidence / "commands.jsonl").write_text('{"name":"cmd","status":"passed"}\n', encoding="utf-8")
            items = parse_evidence_dir(evidence)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].category, "commands")


if __name__ == "__main__":
    unittest.main()
