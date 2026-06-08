"""Filesystem scanning and file classification."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

from .models import FileRecord
from .utils import matches_any, normalize_relpath, sha256_file

TEXT_SUFFIXES = {
    ".md": "markdown",
    ".txt": "text",
    ".log": "log",
    ".json": "json",
    ".jsonl": "jsonl",
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
}

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

CATEGORY_HINTS = {
    "commands": ["command", "commands", "run", "terminal"],
    "tests": ["test", "tests", "pytest", "unittest", "junit"],
    "ci": ["ci", "workflow", "actions", "build"],
    "risks": ["risk", "risks", "threat"],
    "acceptance": ["acceptance", "criteria", "验收"],
    "review_notes": ["review", "notes", "pr"],
    "screenshots": ["screenshot", "screenshots", "screen"],
    "logs": ["log", "logs"],
    "changes": ["diff", "patch", "change", "changed"],
}


def classify_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return TEXT_SUFFIXES[suffix]
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in {".zip", ".tar", ".gz"}:
        return "archive"
    if suffix in {".pdf"}:
        return "pdf"
    return "binary" if suffix else "unknown"


def classify_evidence_category(relpath: str, kind: str) -> str:
    if kind == "image":
        return "screenshots"
    if kind == "log":
        return "logs"
    lowered = relpath.lower()
    for category, hints in CATEGORY_HINTS.items():
        if any(hint in lowered for hint in hints):
            return category
    return "changes"


def should_include(relpath: str, include: Iterable[str], exclude: Iterable[str]) -> bool:
    included = matches_any(relpath, include)
    excluded = matches_any(relpath, exclude)
    return included and not excluded


def scan_files(root: Path, config: Dict[str, object]) -> List[FileRecord]:
    include = list(config.get("include", ["**/*"]))  # type: ignore[arg-type]
    exclude = list(config.get("exclude", []))  # type: ignore[arg-type]
    max_file_bytes = int(config.get("max_file_bytes", 10 * 1024 * 1024))
    records: List[FileRecord] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relpath = normalize_relpath(path, root)
        if not should_include(relpath, include, exclude):
            continue
        size = path.stat().st_size
        if size > max_file_bytes:
            continue
        kind = classify_kind(path)
        records.append(
            FileRecord(
                path=relpath,
                size=size,
                sha256=sha256_file(path),
                kind=kind,
                evidence_category=classify_evidence_category(relpath, kind),
            )
        )
    return records
