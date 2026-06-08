import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_evidence_vault.config import DEFAULT_CONFIG, explain_config, load_config, validate_config


class ConfigTests(unittest.TestCase):
    def test_default_config_valid(self):
        self.assertEqual(validate_config(dict(DEFAULT_CONFIG)), [])

    def test_load_default_contains_required_evidence(self):
        config = load_config()
        self.assertIn("commands", config["required_evidence"])

    def test_override_minimum_score(self):
        config = load_config(overrides={"minimum_score": 88})
        self.assertEqual(config["minimum_score"], 88)

    def test_none_override_is_ignored(self):
        config = load_config(overrides={"minimum_score": None})
        self.assertEqual(config["minimum_score"], DEFAULT_CONFIG["minimum_score"])

    def test_invalid_required_type(self):
        errors = validate_config({"required_evidence": "commands", "fail_on_open_risks": [], "minimum_score": 70, "include": [], "exclude": [], "max_file_bytes": 1})
        self.assertTrue(any("required_evidence" in error for error in errors))

    def test_unknown_required_category(self):
        config = dict(DEFAULT_CONFIG)
        config["required_evidence"] = ["moon"]
        self.assertTrue(any("unknown categories" in error for error in validate_config(config)))

    def test_unknown_severity(self):
        config = dict(DEFAULT_CONFIG)
        config["fail_on_open_risks"] = ["urgent"]
        self.assertTrue(any("unknown severities" in error for error in validate_config(config)))

    def test_invalid_minimum_score_low(self):
        config = dict(DEFAULT_CONFIG)
        config["minimum_score"] = -1
        self.assertTrue(validate_config(config))

    def test_invalid_minimum_score_high(self):
        config = dict(DEFAULT_CONFIG)
        config["minimum_score"] = 101
        self.assertTrue(validate_config(config))

    def test_invalid_max_file_bytes(self):
        config = dict(DEFAULT_CONFIG)
        config["max_file_bytes"] = 0
        self.assertTrue(validate_config(config))

    def test_load_config_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text('{"minimum_score": 42}', encoding="utf-8")
            self.assertEqual(load_config(path)["minimum_score"], 42)

    def test_load_config_rejects_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text('{"minimum_score": "high"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)

    def test_explain_config_pairs(self):
        pairs = explain_config(load_config())
        keys = [key for key, _ in pairs]
        self.assertIn("minimum_score", keys)


if __name__ == "__main__":
    unittest.main()
