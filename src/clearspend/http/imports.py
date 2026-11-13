from __future__ import annotations

import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import MutableMapping, Sequence

from clearspend.http.multipart import UploadedFile
from clearspend.import_engine import ImportDatabase
from clearspend.staging.analysis import analyze_staged_files
from clearspend.staging.service import commit_staged_batch


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
    *,
    staged: bool,
) -> tuple[dict, int]:
    """Persist uploaded files and either analyze them or import them directly."""
    results: list[dict] = []
    batch_id = uuid.uuid4().hex
    upload_dir = database.parent / ("staging" if staged else "uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    staged_uploads: list[dict] = []
    for item in items:
        filename = Path(item.filename or "statement").name
        extension = Path(filename).suffix.lower()
        if extension not in {".xlsx", ".pdf"}:
            results.append({
                "filename": filename,
                "status": "unsupported",
                "error": "Use XLSX or PDF",
            })
            continue
        filename, upload_path = _persist_upload(upload_dir, item)
        if staged:
            staged_uploads.append({"filename": filename, "path": upload_path})
            continue
        importer = ImportDatabase(database)
        try:
            try:
                result = importer.import_file(upload_path)
                if result.get("import_id"):
                    table = "income_imports" if result.get("kind") == "income" else "imports"
                    importer.connection.execute(
                        f"UPDATE {table} SET original_name = ? WHERE id = ?",
                        (filename, result["import_id"]),
                    )
                    importer.connection.commit()
            except Exception as error:
                upload_path.unlink(missing_ok=True)
                result = {"status": "error", "error": str(error)}
        finally:
            importer.close()
        result["filename"] = filename
        if result["status"] in {"duplicate_file", "duplicate_content"}:
            upload_path.unlink(missing_ok=True)
        results.append(result)
    if not staged:
        return {"results": results}, 200
    try:
        analysis = analyze_staged_files(
            database,
            [(item["filename"], item["path"]) for item in staged_uploads],
        )
    except Exception as error:
        for item in staged_uploads:
            item["path"].unlink(missing_ok=True)
        return {"error": str(error), "results": results}, 400
    staged_imports[batch_id] = {
        "uploads": staged_uploads,
        "created_at": datetime.now().isoformat(),
    }
    analysis["batch_id"] = batch_id
    analysis["upload_errors"] = results
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
    result = commit_staged_batch(
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
