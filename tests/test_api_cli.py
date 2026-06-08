import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_evidence_vault.api import collect_vault, load_manifest, verify_manifest
from agent_evidence_vault.cli import main


def make_delivery(root: Path, include_risk=False):
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    evidence = root / "evidence"
    evidence.mkdir()
    (evidence / "commands.jsonl").write_text('{"name":"cmd","exit_code":0}\n', encoding="utf-8")
    (evidence / "tests.jsonl").write_text('{"name":"tests","status":"passed"}\n', encoding="utf-8")
    (evidence / "acceptance.txt").write_text("name: accepted\nstatus: passed\n", encoding="utf-8")
    if include_risk:
        (evidence / "risks.jsonl").write_text('{"name":"risk","severity":"critical","status":"open"}\n', encoding="utf-8")
    return evidence


class ApiCliTests(unittest.TestCase):
    def test_collect_vault_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = make_delivery(root)
            result = collect_vault(root, evidence, root / "vault")
            self.assertTrue(result.gate_passed)
            self.assertEqual(result.exit_code, 0)
            self.assertTrue((root / "vault" / "manifest.json").is_file())

    def test_collect_vault_fails_on_blocking_risk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = make_delivery(root, include_risk=True)
            result = collect_vault(root, evidence, root / "vault")
            self.assertFalse(result.gate_passed)
            self.assertEqual(result.exit_code, 1)

    def test_collect_vault_missing_required_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            result = collect_vault(root, evidence, root / "vault")
            self.assertFalse(result.gate_passed)

    def test_load_manifest_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = make_delivery(root)
            collect_vault(root, evidence, root / "vault")
            manifest = load_manifest(root / "vault" / "manifest.json")
            self.assertEqual(manifest.schema_version, "aev.manifest.v1")

    def test_verify_manifest_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = make_delivery(root)
            collect_vault(root, evidence, root / "vault")
            result = verify_manifest(root / "vault" / "manifest.json", root)
            self.assertTrue(result.gate_passed)

    def test_verify_manifest_detects_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = make_delivery(root)
            collect_vault(root, evidence, root / "vault")
            (root / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
            result = verify_manifest(root / "vault" / "manifest.json", root)
            self.assertFalse(result.gate_passed)
            self.assertEqual(result.exit_code, 2)

    def test_cli_collect_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = make_delivery(root)
            code = main(["collect", "--root", str(root), "--evidence", str(evidence), "--out", str(root / "vault"), "--quiet"])
            self.assertEqual(code, 0)

    def test_cli_collect_returns_one_when_gate_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = make_delivery(root, include_risk=True)
            code = main(["collect", "--root", str(root), "--evidence", str(evidence), "--out", str(root / "vault"), "--quiet"])
            self.assertEqual(code, 1)

    def test_cli_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = make_delivery(root)
            collect_vault(root, evidence, root / "vault")
            code = main(["check", "--manifest", str(root / "vault" / "manifest.json"), "--root", str(root)])
            self.assertEqual(code, 0)

    def test_cli_check_writes_junit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = make_delivery(root)
            collect_vault(root, evidence, root / "vault")
            junit = root / "verify.xml"
            code = main(["check", "--manifest", str(root / "vault" / "manifest.json"), "--root", str(root), "--junit", str(junit)])
            self.assertEqual(code, 0)
            self.assertTrue(junit.is_file())

    def test_cli_score_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = make_delivery(root)
            collect_vault(root, evidence, root / "vault")
            code = main(["score", "--manifest", str(root / "vault" / "manifest.json"), "--json"])
            self.assertEqual(code, 0)

    def test_cli_score_fails_for_failed_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = make_delivery(root, include_risk=True)
            collect_vault(root, evidence, root / "vault")
            code = main(["score", "--manifest", str(root / "vault" / "manifest.json")])
            self.assertEqual(code, 1)

    def test_cli_validate_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.json"
            config.write_text('{"minimum_score": 50}', encoding="utf-8")
            self.assertEqual(main(["validate-config", "--config", str(config)]), 0)

    def test_cli_bad_config_returns_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.json"
            config.write_text('{"minimum_score": 500}', encoding="utf-8")
            self.assertEqual(main(["validate-config", "--config", str(config)]), 2)

    def test_module_invocation_help(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        proc = subprocess.run(
            [sys.executable, "-m", "agent_evidence_vault", "--version"],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("aev", proc.stdout)

    def test_manifest_json_has_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = make_delivery(root)
            collect_vault(root, evidence, root / "vault")
            data = json.loads((root / "vault" / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(data["files"])

    def test_cli_collect_attestation_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = make_delivery(root)
            code = main(
                [
                    "collect",
                    "--root",
                    str(root),
                    "--evidence",
                    str(evidence),
                    "--out",
                    str(root / "vault"),
                    "--format",
                    "attestation",
                    "--quiet",
                ]
            )
            self.assertEqual(code, 0)
            payload = json.loads((root / "vault" / "attestation.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["_type"], "https://in-toto.io/Statement/v1")
            self.assertEqual(payload["predicate"]["gate"], "PASS")


if __name__ == "__main__":
    unittest.main()
