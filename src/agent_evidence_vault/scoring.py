"""Risk and evidence scoring."""

from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List

from .models import CheckResult, EvidenceItem

SEVERITY_WEIGHT = {"low": 3, "medium": 8, "high": 18, "critical": 35}
FAILED_STATUS = {"failed", "error"}
PASS_STATUS = {"passed", "mitigated", "skipped"}


def summarize_evidence(evidence: Iterable[EvidenceItem]) -> Dict[str, object]:
    items = list(evidence)
    by_category = Counter(item.category for item in items)
    by_status = Counter(item.status for item in items)
    return {
        "evidence_count": len(items),
        "by_category": dict(sorted(by_category.items())),
        "by_status": dict(sorted(by_status.items())),
        "open_risk_count": sum(1 for item in items if item.category == "risks" and item.status == "open"),
        "failed_count": sum(1 for item in items if item.status in FAILED_STATUS),
    }


def risk_penalty(evidence: Iterable[EvidenceItem]) -> int:
    penalty = 0
    for item in evidence:
        if item.category != "risks" or item.status != "open":
            continue
        severity = str(item.data.get("severity", "medium")).lower()
        penalty += SEVERITY_WEIGHT.get(severity, SEVERITY_WEIGHT["medium"])
    return penalty


def failed_evidence_penalty(evidence: Iterable[EvidenceItem]) -> int:
    return sum(10 for item in evidence if item.status in FAILED_STATUS and item.category != "risks")


def check_penalty(checks: Iterable[CheckResult]) -> int:
    weights = {"low": 5, "medium": 10, "high": 20, "critical": 35}
    return sum(weights.get(check.severity, 10) for check in checks if check.status == "failed")


def compute_score(evidence: List[EvidenceItem], checks: List[CheckResult]) -> int:
    score = 100
    score -= risk_penalty(evidence)
    score -= failed_evidence_penalty(evidence)
    score -= check_penalty(checks)
    if not evidence:
        score -= 30
    return max(0, min(100, score))

