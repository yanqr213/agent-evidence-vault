"""Evidence input parsers for JSON, JSONL, and simple text blocks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .models import EvidenceItem

SUPPORTED_EVIDENCE_FILES = {
    "commands": ["commands.jsonl", "commands.json", "commands.txt"],
    "tests": ["tests.jsonl", "tests.json", "tests.txt"],
    "ci": ["ci.jsonl", "ci.json", "ci.txt"],
    "risks": ["risks.jsonl", "risks.json", "risks.txt"],
    "acceptance": ["acceptance.jsonl", "acceptance.json", "acceptance.txt"],
    "review_notes": ["review_notes.jsonl", "review_notes.json", "review_notes.txt"],
}


def discover_evidence_files(evidence_dir: Path) -> Dict[str, List[Path]]:
    found: Dict[str, List[Path]] = {key: [] for key in SUPPORTED_EVIDENCE_FILES}
    if not evidence_dir.exists():
        return found
    for category, names in SUPPORTED_EVIDENCE_FILES.items():
        for name in names:
            path = evidence_dir / name
            if path.is_file():
                found[category].append(path)
    return found


def parse_evidence_dir(evidence_dir: Path) -> List[EvidenceItem]:
    items: List[EvidenceItem] = []
    for category, paths in discover_evidence_files(evidence_dir).items():
        for path in paths:
            for raw in parse_records(path):
                items.append(record_to_evidence(category, path, raw))
    return items


def parse_records(path: Path) -> List[Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return parse_jsonl(path)
    if suffix == ".json":
        return parse_json(path)
    if suffix == ".txt":
        return parse_text_blocks(path)
    raise ValueError(f"Unsupported evidence file type: {path}")


def parse_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{index}: invalid JSONL: {exc.msg}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{index}: JSONL record must be an object")
            records.append(value)
    return records


def parse_json(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if isinstance(value, dict):
        if isinstance(value.get("items"), list):
            values = value["items"]
        else:
            values = [value]
    elif isinstance(value, list):
        values = value
    else:
        raise ValueError(f"{path}: JSON evidence must be an object or list")
    if not all(isinstance(item, dict) for item in values):
        raise ValueError(f"{path}: JSON evidence items must be objects")
    return list(values)


def parse_text_blocks(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    blocks = [block for block in text.split("\n\n") if block.strip()]
    records: List[Dict[str, Any]] = []
    for block in blocks:
        record: Dict[str, Any] = {}
        loose_lines: List[str] = []
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                record[key] = value.strip()
            else:
                loose_lines.append(stripped)
        if loose_lines:
            record.setdefault("note", "\n".join(loose_lines))
        if record:
            records.append(record)
    return records


def record_to_evidence(category: str, path: Path, record: Dict[str, Any]) -> EvidenceItem:
    name = first_str(record, ["name", "id", "command", "title", "criterion", "url"], default="unnamed")
    status = normalize_status(first_str(record, ["status", "result", "outcome"], default=infer_status(category, record)))
    return EvidenceItem(category=category, name=name, status=status, source=path.as_posix(), data=dict(record))


def first_str(record: Dict[str, Any], keys: Iterable[str], default: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def infer_status(category: str, record: Dict[str, Any]) -> str:
    if category == "commands":
        exit_code = record.get("exit_code")
        if exit_code is not None:
            return "passed" if str(exit_code) == "0" else "failed"
    if category == "risks":
        return str(record.get("state", record.get("status", "open")))
    return "unknown"


def normalize_status(status: str) -> str:
    lowered = status.strip().lower()
    aliases = {
        "ok": "passed",
        "pass": "passed",
        "success": "passed",
        "successful": "passed",
        "fail": "failed",
        "failure": "failed",
        "error": "failed",
        "pending": "pending",
        "todo": "pending",
        "skipped": "skipped",
        "skip": "skipped",
        "mitigated": "mitigated",
        "closed": "mitigated",
        "open": "open",
    }
    return aliases.get(lowered, lowered or "unknown")

