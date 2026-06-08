"""Configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from .utils import coerce_list, read_json

DEFAULT_CONFIG: Dict[str, Any] = {
    "required_evidence": ["commands", "tests", "acceptance"],
    "fail_on_open_risks": ["critical"],
    "minimum_score": 70,
    "include": ["**/*"],
    "exclude": [
        ".git/**",
        ".hg/**",
        ".svn/**",
        "__pycache__/**",
        "*.pyc",
        "vault/**",
        "dist/**",
        "build/**",
    ],
    "max_file_bytes": 10 * 1024 * 1024,
}

KNOWN_CATEGORIES = {
    "commands",
    "tests",
    "ci",
    "risks",
    "acceptance",
    "review_notes",
    "screenshots",
    "logs",
    "changes",
}

SEVERITIES = {"low", "medium", "high", "critical"}


def load_config(path: Path | None = None, overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    if path:
        loaded = read_json(path)
        config.update(loaded)
    if overrides:
        config.update({key: value for key, value in overrides.items() if value is not None})
    errors = validate_config(config)
    if errors:
        raise ValueError("; ".join(errors))
    return config


def validate_config(config: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    try:
        required = coerce_list(config.get("required_evidence"), "required_evidence")
        unknown = sorted(set(required) - KNOWN_CATEGORIES)
        if unknown:
            errors.append("required_evidence contains unknown categories: " + ", ".join(unknown))
    except ValueError as exc:
        errors.append(str(exc))

    try:
        severities = coerce_list(config.get("fail_on_open_risks"), "fail_on_open_risks")
        unknown_severities = sorted(set(severities) - SEVERITIES)
        if unknown_severities:
            errors.append("fail_on_open_risks contains unknown severities: " + ", ".join(unknown_severities))
    except ValueError as exc:
        errors.append(str(exc))

    for key in ("include", "exclude"):
        try:
            coerce_list(config.get(key), key)
        except ValueError as exc:
            errors.append(str(exc))

    score = config.get("minimum_score")
    if not isinstance(score, int) or score < 0 or score > 100:
        errors.append("minimum_score must be an integer from 0 to 100")

    max_file_bytes = config.get("max_file_bytes")
    if not isinstance(max_file_bytes, int) or max_file_bytes < 1:
        errors.append("max_file_bytes must be a positive integer")

    return errors


def explain_config(config: Dict[str, Any]) -> List[Tuple[str, str]]:
    return [
        ("required_evidence", ", ".join(config["required_evidence"])),
        ("fail_on_open_risks", ", ".join(config["fail_on_open_risks"])),
        ("minimum_score", str(config["minimum_score"])),
        ("include", ", ".join(config["include"])),
        ("exclude", ", ".join(config["exclude"])),
        ("max_file_bytes", str(config["max_file_bytes"])),
    ]

