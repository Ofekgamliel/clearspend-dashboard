from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from clearspend.database.settings import DatabaseBackend


@dataclass(frozen=True)
class ImportMetadataPolicy:
    """Persistence policy for metadata that is not needed for financial reads."""

    preserve_full_source_path: bool
    preserve_error_message: bool
    preserve_source_payload: bool

    def source_path(self, path: Path, original_name: str) -> str:
        return str(path) if self.preserve_full_source_path else original_name

    def error_message(self, message: str) -> Optional[str]:
        return message if self.preserve_error_message else None

    def source_payload(self, payload: Any) -> Any:
        return payload if self.preserve_source_payload else None


SQLITE_IMPORT_METADATA_POLICY = ImportMetadataPolicy(
    preserve_full_source_path=True,
    preserve_error_message=True,
    preserve_source_payload=True,
)

POSTGRESQL_IMPORT_METADATA_POLICY = ImportMetadataPolicy(
    preserve_full_source_path=False,
    preserve_error_message=False,
    preserve_source_payload=False,
)


def metadata_policy_for_backend(backend: DatabaseBackend) -> ImportMetadataPolicy:
    if backend is DatabaseBackend.POSTGRESQL:
        return POSTGRESQL_IMPORT_METADATA_POLICY
    return SQLITE_IMPORT_METADATA_POLICY
