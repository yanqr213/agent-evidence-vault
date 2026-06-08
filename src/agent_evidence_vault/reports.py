"""Markdown, JSON, and JUnit report rendering."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Dict, Iterable, List

from .models import CheckResult, VaultManifest
from .utils import write_json, write_text_lf


def write_reports(manifest: VaultManifest, out_dir: Path, formats: Iterable[str]) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: Dict[str, str] = {}
    requested = set(formats)
    if "all" in requested:
        requested = {"json", "markdown", "junit"}
    if "json" in requested:
        path = out_dir / "manifest.json"
        write_json(path, manifest.to_dict())
        outputs["json"] = str(path)
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

