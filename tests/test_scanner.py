import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_evidence_vault.scanner import (
    classify_evidence_category,
    classify_kind,
    scan_files,
    should_include,
)


class ScannerTests(unittest.TestCase):
    def test_classify_markdown(self):
        self.assertEqual(classify_kind(Path("README.md")), "markdown")

    def test_classify_python(self):
        self.assertEqual(classify_kind(Path("app.py")), "python")

    def test_classify_jsonl(self):
        self.assertEqual(classify_kind(Path("commands.jsonl")), "jsonl")

    def test_classify_image(self):
        self.assertEqual(classify_kind(Path("shot.png")), "image")

    def test_classify_archive(self):
        self.assertEqual(classify_kind(Path("bundle.zip")), "archive")

    def test_classify_pdf(self):
        self.assertEqual(classify_kind(Path("report.pdf")), "pdf")

    def test_classify_unknown_without_suffix(self):
        self.assertEqual(classify_kind(Path("Makefile")), "unknown")

    def test_category_commands(self):
        self.assertEqual(classify_evidence_category("evidence/commands.jsonl", "jsonl"), "commands")

    def test_category_tests(self):
        self.assertEqual(classify_evidence_category("reports/test-results.txt", "text"), "tests")

    def test_category_screenshot_from_kind(self):
        self.assertEqual(classify_evidence_category("assets/a.png", "image"), "screenshots")

    def test_category_log_from_kind(self):
        self.assertEqual(classify_evidence_category("run.out", "log"), "logs")

    def test_category_default_changes(self):
        self.assertEqual(classify_evidence_category("src/app.py", "python"), "changes")

    def test_should_include_true(self):
        self.assertTrue(should_include("src/app.py", ["**/*"], []))

    def test_should_include_root_file_with_globstar(self):
        self.assertTrue(should_include("app.py", ["**/*"], []))

    def test_should_include_false_by_exclude(self):
        self.assertFalse(should_include("vault/manifest.json", ["**/*"], ["vault/**"]))

    def test_scan_files_records_hash_and_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            records = scan_files(root, {"include": ["**/*"], "exclude": [], "max_file_bytes": 999})
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].path, "src/app.py")
            self.assertEqual(len(records[0].sha256), 64)

    def test_scan_files_respects_max_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "big.txt").write_text("hello", encoding="utf-8")
            records = scan_files(root, {"include": ["**/*"], "exclude": [], "max_file_bytes": 2})
            self.assertEqual(records, [])

    def test_scan_files_respects_exclude(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "vault").mkdir()
            (root / "vault" / "manifest.json").write_text("{}", encoding="utf-8")
            records = scan_files(root, {"include": ["**/*"], "exclude": ["vault/**"], "max_file_bytes": 999})
            self.assertEqual(records, [])

    def test_scan_files_includes_root_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
            records = scan_files(root, {"include": ["**/*"], "exclude": [], "max_file_bytes": 999})
            self.assertEqual(records[0].path, "app.py")


if __name__ == "__main__":
    unittest.main()
