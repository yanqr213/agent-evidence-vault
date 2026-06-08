"""Markdown, JSON, JUnit, and attestation report rendering."""

from __future__ import annotations

import html
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .models import CheckResult, VaultManifest
from .utils import write_json, write_text_lf


def write_reports(manifest: VaultManifest, out_dir: Path, formats: Iterable[str]) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: Dict[str, str] = {}
    requested = set(formats)
    if "all" in requested:
        requested = {"json", "markdown", "junit", "attestation"}
    if "json" in requested:
        path = out_dir / "manifest.json"
        write_json(path, manifest.to_dict())
        outputs["json"] = str(path)
    if "attestation" in requested:
        path = out_dir / "attestation.json"
        write_json(path, render_attestation(manifest))
        outputs["attestation"] = str(path)
    if "markdown" in requested or "md" in requested:
        path = out_dir / "report.md"
        write_text_lf(path, render_markdown(manifest))
        outputs["markdown"] = str(path)
    if "junit" in requested:
        path = out_dir / "junit.xml"
        write_text_lf(path, render_junit(manifest))
        outputs["junit"] = str(path)
    return outputs


def render_markdown(manifest: VaultManifest) -> str:
    failed_checks = [check for check in manifest.checks if check.status != "passed"]
    lines: List[str] = [
        "# Agent Evidence Vault Report",
        "",
        f"- Schema: `{manifest.schema_version}`",
        f"- Generated at: `{manifest.generated_at}`",
        f"- Root: `{manifest.root}`",
        f"- Score: **{manifest.score}/100**",
        f"- Gate: **{'PASS' if not failed_checks else 'FAIL'}**",
        "",
        "## Summary",
        "",
        f"- Files scanned: {len(manifest.files)}",
        f"- Evidence items: {manifest.summary.get('evidence_count', 0)}",
        f"- Failed evidence: {manifest.summary.get('failed_count', 0)}",
        f"- Open risks: {manifest.summary.get('open_risk_count', 0)}",
        "",
        "## Checks",
        "",
        "| Status | Check | Severity | Message |",
        "| --- | --- | --- | --- |",
    ]
    for check in manifest.checks:
        lines.append(f"| {check.status} | `{check.id}` | {check.severity} | {escape_pipe(check.message)} |")
    lines.extend(["", "## Evidence", "", "| Category | Status | Name | Source |", "| --- | --- | --- | --- |"])
    for item in manifest.evidence:
        lines.append(f"| {item.category} | {item.status} | {escape_pipe(item.name)} | `{item.source}` |")
    lines.extend(["", "## Files", "", "| Path | Kind | Category | Size | SHA256 |", "| --- | --- | --- | ---: | --- |"])
    for file_record in manifest.files:
        lines.append(
            f"| `{file_record.path}` | {file_record.kind} | {file_record.evidence_category} | "
            f"{file_record.size} | `{file_record.sha256}` |"
        )
    lines.append("")
    return "\n".join(lines)


def render_attestation(manifest: VaultManifest) -> Dict[str, Any]:
    failed_checks = [check for check in manifest.checks if check.status != "passed"]
    evidence_by_category: Dict[str, int] = {}
    evidence_by_status: Dict[str, int] = {}
    for item in manifest.evidence:
        evidence_by_category[item.category] = evidence_by_category.get(item.category, 0) + 1
        evidence_by_status[item.status] = evidence_by_status.get(item.status, 0) + 1
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": file_record.path,
                "digest": {"sha256": file_record.sha256},
                "size": file_record.size,
                "kind": file_record.kind,
                "evidence_category": file_record.evidence_category,
            }
            for file_record in manifest.files
        ],
        "predicateType": "https://github.com/yanqr213/agent-evidence-vault/attestation/v1",
        "predicate": {
            "schema_version": manifest.schema_version,
            "generated_at": manifest.generated_at,
            "root": manifest.root,
            "tool": manifest.tool,
            "manifest_sha256": canonical_manifest_sha256(manifest),
            "gate": "PASS" if not failed_checks else "FAIL",
            "score": manifest.score,
            "summary": manifest.summary,
            "evidence_by_category": evidence_by_category,
            "evidence_by_status": evidence_by_status,
            "checks": [check.to_dict() for check in manifest.checks],
            "failed_checks": [check.to_dict() for check in failed_checks],
        },
    }


def canonical_manifest_sha256(manifest: VaultManifest) -> str:
    payload = json.dumps(manifest.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def escape_pipe(value: str) -> str:
    return str(value).replace("|", "\\|")


def render_junit(manifest: VaultManifest) -> str:
    checks = manifest.checks
    failures = [check for check in checks if check.status != "passed"]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuite name="agent-evidence-vault" tests="{len(checks)}" failures="{len(failures)}">',
    ]
    for check in checks:
        lines.append(f'  <testcase classname="agent_evidence_vault" name="{html.escape(check.id)}">')
        if check.status != "passed":
            lines.append(
                f'    <failure message="{html.escape(check.message)}" type="{html.escape(check.severity)}">'
                f"{html.escape(check.message)}</failure>"
            )
        lines.append("  </testcase>")
    lines.append("</testsuite>")
    return "\n".join(lines) + "\n"

