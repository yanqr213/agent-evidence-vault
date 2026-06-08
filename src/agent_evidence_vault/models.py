"""Dataclasses used by the vault engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FileRecord:
    path: str
    size: int
    sha256: str
    kind: str
    evidence_category: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "size": self.size,
            "sha256": self.sha256,
            "kind": self.kind,
            "evidence_category": self.evidence_category,
        }


@dataclass
class EvidenceItem:
    category: str
    name: str
    status: str = "unknown"
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "name": self.name,
            "status": self.status,
            "source": self.source,
            "data": self.data,
        }


@dataclass
class CheckResult:
    id: str
    status: str
    message: str
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class VaultManifest:
    schema_version: str
    generated_at: str
    root: str
    config: Dict[str, Any]
    files: List[FileRecord]
    evidence: List[EvidenceItem]
    checks: List[CheckResult]
    score: int
    summary: Dict[str, Any]
    tool: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "root": self.root,
            "config": self.config,
            "files": [record.to_dict() for record in self.files],
            "evidence": [item.to_dict() for item in self.evidence],
            "checks": [check.to_dict() for check in self.checks],
            "score": self.score,
            "summary": self.summary,
            "tool": self.tool,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VaultManifest":
        return cls(
            schema_version=str(data.get("schema_version", "")),
            generated_at=str(data.get("generated_at", "")),
            root=str(data.get("root", "")),
            config=dict(data.get("config", {})),
            files=[FileRecord(**item) for item in data.get("files", [])],
            evidence=[
                EvidenceItem(
                    category=str(item.get("category", "")),
                    name=str(item.get("name", "")),
                    status=str(item.get("status", "unknown")),
                    source=str(item.get("source", "")),
                    data=dict(item.get("data", {})),
                )
                for item in data.get("evidence", [])
            ],
            checks=[
                CheckResult(
                    id=str(item.get("id", "")),
                    status=str(item.get("status", "")),
                    message=str(item.get("message", "")),
                    severity=str(item.get("severity", "medium")),
                )
                for item in data.get("checks", [])
            ],
            score=int(data.get("score", 0)),
            summary=dict(data.get("summary", {})),
            tool=dict(data.get("tool", {})),
        )


@dataclass
class CollectionResult:
    manifest: VaultManifest
    output_files: Dict[str, str]
    exit_code: int
    gate_passed: bool
    message: Optional[str] = None

