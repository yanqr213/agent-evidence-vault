"""High-level collection and verification API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Optional

from . import __version__
from .checks import build_checks, gate_passed, verify_file_hashes
from .config import load_config
from .models import CollectionResult, VaultManifest
from .parsers import parse_evidence_dir
from .reports import write_reports
from .scanner import scan_files
from .scoring import compute_score, summarize_evidence
from .utils import read_json, utc_now_iso

SCHEMA_VERSION = "aev.manifest.v1"


def collect_vault(
    root: str | Path,
    evidence_dir: str | Path | None = None,
    out_dir: str | Path = "vault",
    config_path: str | Path | None = None,
    formats: Iterable[str] = ("all",),
    overrides: Optional[Dict[str, object]] = None,
) -> CollectionResult:
    root_path = Path(root).resolve()
    evidence_path = Path(evidence_dir).resolve() if evidence_dir else root_path / "evidence"
    output_path = Path(out_dir).resolve()
    config = load_config(Path(config_path).resolve() if config_path else None, overrides)
    files = scan_files(root_path, config)
    evidence = parse_evidence_dir(evidence_path)

    provisional_checks = build_checks(evidence, config, 100)
    provisional_score = compute_score(evidence, provisional_checks)
    checks = build_checks(evidence, config, provisional_score)
    score = compute_score(evidence, checks)
    checks = build_checks(evidence, config, score)

    manifest = VaultManifest(
        schema_version=SCHEMA_VERSION,
        generated_at=utc_now_iso(),
        root=str(root_path),
        config=config,
        files=files,
        evidence=evidence,
        checks=checks,
        score=score,
        summary=summarize_evidence(evidence),
        tool={"name": "agent-evidence-vault", "version": __version__},
    )
    outputs = write_reports(manifest, output_path, formats)
    passed = gate_passed(checks)
    return CollectionResult(manifest=manifest, output_files=outputs, exit_code=0 if passed else 1, gate_passed=passed)


def load_manifest(path: str | Path) -> VaultManifest:
    return VaultManifest.from_dict(read_json(Path(path)))


def verify_manifest(manifest_path: str | Path, root: str | Path | None = None) -> CollectionResult:
    manifest = load_manifest(manifest_path)
    root_path = Path(root).resolve() if root else Path(manifest.root).resolve()
    checks = verify_file_hashes(root_path, manifest.files)
    passed = gate_passed(checks)
    verified = VaultManifest(
        schema_version=manifest.schema_version,
        generated_at=utc_now_iso(),
        root=str(root_path),
        config=manifest.config,
        files=manifest.files,
        evidence=manifest.evidence,
        checks=checks,
        score=100 if passed else 0,
        summary=dict(manifest.summary),
        tool=manifest.tool,
    )
    return CollectionResult(manifest=verified, output_files={}, exit_code=0 if passed else 2, gate_passed=passed)

