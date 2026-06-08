"""Agent Evidence Vault public API."""

__version__ = "0.2.0"

from .api import collect_vault, load_manifest, verify_manifest
from .models import EvidenceItem, FileRecord, VaultManifest

__all__ = [
    "EvidenceItem",
    "FileRecord",
    "VaultManifest",
    "collect_vault",
    "load_manifest",
    "verify_manifest",
]
