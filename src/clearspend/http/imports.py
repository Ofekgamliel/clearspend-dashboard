from __future__ import annotations

import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import MutableMapping, Sequence

from clearspend.http.multipart import UploadedFile
from clearspend.staging.analysis import analyze_staged_files
from clearspend.staging.service import commit_staged_statement


StagedImportStore = MutableMapping[str, dict]


def _persist_upload(upload_dir: Path, item: UploadedFile) -> tuple[str, Path]:
    filename = Path(item.filename or "statement").name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
    with tempfile.NamedTemporaryFile(
        dir=upload_dir,
        suffix=f"-{safe_name}",
        delete=False,
    ) as output:
        while True:
            chunk = item.file.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
        return filename, Path(output.name)


def process_import_uploads(
    database: Path,
    staged_imports: StagedImportStore,
    items: Sequence[UploadedFile],
) -> tuple[dict, int]:
    """Persist and analyze exactly one statement without changing live data."""
    if len(items) != 1:
        return {"error": "Import exactly one XLSX or PDF file at a time"}, 400
    item = items[0]
    filename = Path(item.filename or "statement").name
    extension = Path(filename).suffix.lower()
    if extension not in {".xlsx", ".pdf"}:
        return {"error": "Use one XLSX or PDF statement"}, 400

    batch_id = uuid.uuid4().hex
    upload_dir = database.parent / "staging"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename, upload_path = _persist_upload(upload_dir, item)
    staged_uploads = [{"filename": filename, "path": upload_path}]
    try:
        analysis = analyze_staged_files(
            database,
            [(item["filename"], item["path"]) for item in staged_uploads],
        )
    except Exception as error:
        upload_path.unlink(missing_ok=True)
        return {"error": str(error)}, 400
    staged_imports[batch_id] = {
        "uploads": staged_uploads,
        "created_at": datetime.now().isoformat(),
    }
    analysis["batch_id"] = batch_id
    analysis["upload_errors"] = []
    return analysis, 200


def commit_staged_import(
    database: Path,
    staged_imports: StagedImportStore,
    payload: dict,
) -> tuple[dict, int]:
    """Validate and commit a staged import session, then remove its temporary files."""
    batch_id = str(payload.get("batch_id", ""))
    batch = staged_imports.get(batch_id)
    if not batch:
        raise ValueError("Staged import was not found or the server was restarted")
    if len(batch.get("uploads", [])) != 1:
        raise ValueError("Exactly one staged statement is required for import")
    decisions = payload.get("decisions", [])
    if not isinstance(decisions, list):
        raise ValueError("Decisions must be a list")
    duplicate_decisions = payload.get("duplicate_decisions", [])
    if not isinstance(duplicate_decisions, list):
        raise ValueError("Duplicate decisions must be a list")
    reconciled_files = payload.get("reconciled_files", [])
    if not isinstance(reconciled_files, list):
        raise ValueError("Reconciled files must be a list")
    analysis = analyze_staged_files(
        database,
        [(item["filename"], item["path"]) for item in batch["uploads"]],
    )
    required_reconciliation = {
        item["filename"]
        for item in analysis["files"]
        if item["kind"] == "statement"
        and item["status"] == "ready"
        and item["reconciliation"]["status"] in {"manual_required", "mismatch"}
    }
    missing_reconciliation = required_reconciliation - {
        str(item) for item in reconciled_files
    }
    if missing_reconciliation:
        missing = ", ".join(sorted(missing_reconciliation))
        raise ValueError(f"Confirm the statement total before importing: {missing}")
    result = commit_staged_statement(
        database,
        batch,
        decisions,
        duplicate_decisions,
        analysis,
    )
    for item in batch["uploads"]:
        item["path"].unlink(missing_ok=True)
    staged_imports.pop(batch_id, None)
    return result, 200


def cancel_staged_import(
    staged_imports: StagedImportStore,
    payload: dict,
) -> tuple[dict, int]:
    """Discard one staged session and remove its temporary statement copies."""
    batch_id = str(payload.get("batch_id", ""))
    if not batch_id:
        raise ValueError("A staged import id is required")
    batch = staged_imports.pop(batch_id, None)
    if not batch:
        return {"status": "discarded", "removed": False}, 200
    for item in batch.get("uploads", []):
        item["path"].unlink(missing_ok=True)
    return {"status": "discarded", "removed": True}, 200
