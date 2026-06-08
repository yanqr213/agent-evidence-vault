"""Evidence completeness and CI gate checks."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from .models import CheckResult, EvidenceItem, FileRecord
from .utils import sha256_file


def check_required_evidence(evidence: Sequence[EvidenceItem], required: Iterable[str]) -> List[CheckResult]:
    categories = {item.category for item in evidence}
    results: List[CheckResult] = []
    for category in required:
        if category in categories:
            results.append(CheckResult(f"required:{category}", "passed", f"Found {category} evidence.", "medium"))
        else:
            results.append(CheckResult(f"required:{category}", "failed", f"Missing required {category} evidence.", "high"))
    return results


def check_failed_tests(evidence: Sequence[EvidenceItem]) -> List[CheckResult]:
    failed = [item for item in evidence if item.category in {"tests", "commands", "ci", "acceptance"} and item.status == "failed"]
    if not failed:
        return [CheckResult("evidence:no_failed_runs", "passed", "No failed command/test/CI/acceptance evidence.", "high")]
    names = ", ".join(item.name for item in failed[:5])
    return [CheckResult("evidence:no_failed_runs", "failed", f"Failed evidence present: {names}", "high")]


def check_open_risks(evidence: Sequence[EvidenceItem], fail_on: Iterable[str]) -> List[CheckResult]:
    fail_on_set = {item.lower() for item in fail_on}
    blocking = []
    informational = []
    for item in evidence:
        if item.category != "risks" or item.status != "open":
            continue
        severity = str(item.data.get("severity", "medium")).lower()
        if severity in fail_on_set:
            blocking.append(item)
        else:
            informational.append(item)
    if blocking:
        names = ", ".join(item.name for item in blocking[:5])
        return [CheckResult("risks:no_blocking_open", "failed", f"Blocking open risks: {names}", "critical")]
    if informational:
        return [CheckResult("risks:no_blocking_open", "passed", f"Open non-blocking risks: {len(informational)}.", "medium")]
    return [CheckResult("risks:no_blocking_open", "passed", "No open risks.", "critical")]


def check_score(score: int, minimum: int) -> CheckResult:
    if score >= minimum:
        return CheckResult("score:minimum", "passed", f"Score {score} meets minimum {minimum}.", "high")
    return CheckResult("score:minimum", "failed", f"Score {score} is below minimum {minimum}.", "high")


def build_checks(evidence: Sequence[EvidenceItem], config: Dict[str, object], provisional_score: int) -> List[CheckResult]:
    checks: List[CheckResult] = []
    checks.extend(check_required_evidence(evidence, config.get("required_evidence", [])))  # type: ignore[arg-type]
    checks.extend(check_failed_tests(evidence))
    checks.extend(check_open_risks(evidence, config.get("fail_on_open_risks", [])))  # type: ignore[arg-type]
    checks.append(check_score(provisional_score, int(config.get("minimum_score", 70))))
    return checks


def gate_passed(checks: Sequence[CheckResult]) -> bool:
    return all(check.status == "passed" for check in checks)


def verify_file_hashes(root: Path, files: Sequence[FileRecord]) -> List[CheckResult]:
    results: List[CheckResult] = []
    for record in files:
        path = root / record.path
        if not path.is_file():
            results.append(CheckResult(f"integrity:{record.path}", "failed", "File is missing.", "critical"))
            continue
        actual = sha256_file(path)
        if actual != record.sha256:
            results.append(CheckResult(f"integrity:{record.path}", "failed", "SHA256 mismatch.", "critical"))
        else:
            results.append(CheckResult(f"integrity:{record.path}", "passed", "SHA256 matches.", "low"))
    return results

