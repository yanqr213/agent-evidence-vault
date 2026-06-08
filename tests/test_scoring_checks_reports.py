import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_evidence_vault.checks import (
    build_checks,
    check_failed_tests,
    check_open_risks,
    check_required_evidence,
    check_score,
    gate_passed,
    verify_file_hashes,
)
from agent_evidence_vault.models import CheckResult, EvidenceItem, FileRecord, VaultManifest
from agent_evidence_vault.reports import escape_pipe, render_junit, render_markdown, write_reports
from agent_evidence_vault.scoring import compute_score, failed_evidence_penalty, risk_penalty, summarize_evidence
from agent_evidence_vault.utils import sha256_file, utc_now_iso


def item(category, name="x", status="passed", **data):
    return EvidenceItem(category=category, name=name, status=status, source="source", data=data)


def manifest(checks=None, evidence=None):
    evidence = evidence or [item("commands"), item("tests"), item("acceptance")]
    checks = checks if checks is not None else [CheckResult("ok", "passed", "fine", "low")]
    return VaultManifest(
        schema_version="test",
        generated_at=utc_now_iso(),
        root="/tmp/root",
        config={},
        files=[],
        evidence=evidence,
        checks=checks,
        score=compute_score(evidence, checks),
        summary=summarize_evidence(evidence),
        tool={"name": "test", "version": "0"},
    )


class ScoringChecksReportsTests(unittest.TestCase):
    def test_summarize_counts(self):
        summary = summarize_evidence([item("commands"), item("risks", status="open")])
        self.assertEqual(summary["evidence_count"], 2)
        self.assertEqual(summary["open_risk_count"], 1)

    def test_risk_penalty_critical(self):
        self.assertEqual(risk_penalty([item("risks", status="open", severity="critical")]), 35)

    def test_risk_penalty_unknown_defaults_medium(self):
        self.assertEqual(risk_penalty([item("risks", status="open", severity="weird")]), 8)

    def test_closed_risk_no_penalty(self):
        self.assertEqual(risk_penalty([item("risks", status="mitigated", severity="critical")]), 0)

    def test_failed_evidence_penalty(self):
        self.assertEqual(failed_evidence_penalty([item("tests", status="failed")]), 10)

    def test_failed_risk_not_failed_evidence_penalty(self):
        self.assertEqual(failed_evidence_penalty([item("risks", status="failed")]), 0)

    def test_compute_score_empty_penalty(self):
        self.assertEqual(compute_score([], []), 70)

    def test_compute_score_clamped_zero(self):
        evidence = [item("risks", status="open", severity="critical") for _ in range(10)]
        self.assertEqual(compute_score(evidence, []), 0)

    def test_check_required_pass_and_fail(self):
        checks = check_required_evidence([item("commands")], ["commands", "tests"])
        self.assertEqual([check.status for check in checks], ["passed", "failed"])

    def test_check_failed_tests_passes(self):
        self.assertEqual(check_failed_tests([item("tests")])[0].status, "passed")

    def test_check_failed_tests_fails(self):
        self.assertEqual(check_failed_tests([item("tests", status="failed")])[0].status, "failed")

    def test_check_open_risks_blocking(self):
        checks = check_open_risks([item("risks", status="open", severity="critical")], ["critical"])
        self.assertEqual(checks[0].status, "failed")

    def test_check_open_risks_non_blocking(self):
        checks = check_open_risks([item("risks", status="open", severity="low")], ["critical"])
        self.assertEqual(checks[0].status, "passed")

    def test_check_open_risks_none(self):
        self.assertEqual(check_open_risks([], ["critical"])[0].status, "passed")

    def test_check_score_pass(self):
        self.assertEqual(check_score(80, 70).status, "passed")

    def test_check_score_fail(self):
        self.assertEqual(check_score(60, 70).status, "failed")

    def test_build_checks_contains_score(self):
        checks = build_checks([item("commands"), item("tests"), item("acceptance")], {"required_evidence": ["commands"], "fail_on_open_risks": [], "minimum_score": 1}, 100)
        self.assertTrue(any(check.id == "score:minimum" for check in checks))

    def test_gate_passed_true(self):
        self.assertTrue(gate_passed([CheckResult("a", "passed", "ok")]))

    def test_gate_passed_false(self):
        self.assertFalse(gate_passed([CheckResult("a", "failed", "bad")]))

    def test_verify_file_hashes_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "a.txt"
            path.write_text("a", encoding="utf-8")
            record = FileRecord("a.txt", 1, sha256_file(path), "text", "changes")
            self.assertEqual(verify_file_hashes(root, [record])[0].status, "passed")

    def test_verify_file_hashes_missing(self):
        record = FileRecord("missing.txt", 0, "x", "text", "changes")
        self.assertEqual(verify_file_hashes(Path("."), [record])[0].status, "failed")

    def test_verify_file_hashes_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "a.txt"
            path.write_text("a", encoding="utf-8")
            record = FileRecord("a.txt", 1, "0" * 64, "text", "changes")
            self.assertEqual(verify_file_hashes(root, [record])[0].status, "failed")

    def test_escape_pipe(self):
        self.assertEqual(escape_pipe("a|b"), "a\\|b")

    def test_render_markdown_contains_score(self):
        self.assertIn("Score", render_markdown(manifest()))

    def test_render_markdown_contains_failure_gate(self):
        md = render_markdown(manifest(checks=[CheckResult("bad", "failed", "bad")]))
        self.assertIn("FAIL", md)

    def test_render_junit_has_testsuite(self):
        self.assertIn("<testsuite", render_junit(manifest()))

    def test_render_junit_failure(self):
        xml = render_junit(manifest(checks=[CheckResult("bad", "failed", "bad", "critical")]))
        self.assertIn("<failure", xml)

    def test_write_reports_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = write_reports(manifest(), Path(tmp), ["all"])
            self.assertIn("json", outputs)
            self.assertIn("markdown", outputs)
            self.assertIn("junit", outputs)

    def test_write_reports_json_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = write_reports(manifest(), Path(tmp), ["json"])
            data = json.loads(Path(outputs["json"]).read_text(encoding="utf-8"))
            self.assertIn("score", data)


if __name__ == "__main__":
    unittest.main()
