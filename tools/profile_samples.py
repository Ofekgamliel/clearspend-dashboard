#!/usr/bin/env python3
"""Read-only profiler for ClearSpend sample files.

The profiler intentionally uses only Python's standard library so the first
inspection can run before the application dependencies are installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


@dataclass
class SheetProfile:
    name: str
    rows: int
    columns: int
    header_row: int | None
    headers: list[str]
    nonempty_by_column: dict[str, int]
    types_by_column: dict[str, dict[str, int]]
    sample_values_by_column: dict[str, list[str]]


@dataclass
class FileProfile:
    path: str
    extension: str
    size: int
    sha256: str
    semantic_hash: str | None
    sheets: list[SheetProfile]
    notes: list[str]


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def column_name(reference: str) -> str:
    match = re.match(r"([A-Z]+)", reference)
    return match.group(1) if match else reference


def parse_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(node.text or "" for node in item.iter(f"{MAIN}t")) for item in root]


def workbook_sheets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"].lstrip("/")
        for rel in rels.findall(f"{PKG_REL}Relationship")
    }
    result: list[tuple[str, str]] = []
    for sheet in workbook.findall(f".//{MAIN}sheet"):
        target = targets[sheet.attrib[f"{REL}id"]]
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        result.append((sheet.attrib["name"], target))
    return result


def excel_date(value: str) -> str:
    try:
        number = float(value)
    except ValueError:
        return value
    base = datetime(1899, 12, 30)
    return (base + timedelta(days=number)).isoformat(sep=" ", timespec="seconds")


def date_style_ids(archive: zipfile.ZipFile) -> set[int]:
    try:
        root = ET.fromstring(archive.read("xl/styles.xml"))
    except KeyError:
        return set()
    custom_formats = {
        int(item.attrib["numFmtId"]): item.attrib.get("formatCode", "")
        for item in root.findall(f".//{MAIN}numFmt")
    }
    built_in_dates = set(range(14, 23)) | {45, 46, 47}
    result: set[int] = set()
    cell_xfs = root.find(f"{MAIN}cellXfs")
    if cell_xfs is None:
        return result
    for index, xf in enumerate(cell_xfs):
        format_id = int(xf.attrib.get("numFmtId", "0"))
        code = custom_formats.get(format_id, "").lower()
        is_custom_date = bool(re.search(r"(^|[^\\])[dmyhs]", code))
        if format_id in built_in_dates or is_custom_date:
            result.add(index)
    return result


def cell_value(cell: ET.Element, shared: list[str], dates: set[int]) -> Any:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{MAIN}t"))
    value_node = cell.find(f"{MAIN}v")
    if value_node is None or value_node.text is None:
        return None
    raw = value_node.text
    if kind == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            return raw
    if kind == "b":
        return raw == "1"
    if int(cell.attrib.get("s", "0")) in dates:
        return excel_date(raw)
    try:
        number = float(raw)
        return int(number) if number.is_integer() else number
    except ValueError:
        return raw


def read_xlsx(path: Path) -> list[tuple[str, list[dict[str, Any]]]]:
    with zipfile.ZipFile(path) as archive:
        shared = parse_shared_strings(archive)
        dates = date_style_ids(archive)
        result = []
        for name, target in workbook_sheets(archive):
            root = ET.fromstring(archive.read(target))
            rows: list[dict[str, Any]] = []
            for row in root.findall(f".//{MAIN}row"):
                values: dict[str, Any] = {}
                for cell in row.findall(f"{MAIN}c"):
                    values[column_name(cell.attrib.get("r", ""))] = cell_value(cell, shared, dates)
                rows.append(values)
            result.append((name, rows))
        return result


def value_kind(value: Any) -> str:
    if value is None or value == "":
        return "empty"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    text = str(value)
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return "date"
    return "text"


def choose_header(rows: list[dict[str, Any]]) -> int | None:
    best_index = None
    best_score = 0
    for index, row in enumerate(rows[:25]):
        populated = [value for value in row.values() if value not in (None, "")]
        strings = sum(isinstance(value, str) for value in populated)
        score = len(populated) + strings * 2
        if len(populated) >= 2 and score > best_score:
            best_score = score
            best_index = index
    return best_index


def profile_sheet(name: str, rows: list[dict[str, Any]]) -> SheetProfile:
    columns = sorted({column for row in rows for column in row}, key=lambda col: (len(col), col))
    header_index = choose_header(rows)
    header = rows[header_index] if header_index is not None else {}
    headers = [str(header.get(column, "")).strip() for column in columns]
    data_rows = rows[header_index + 1 :] if header_index is not None else rows
    counts: dict[str, int] = {}
    types: dict[str, dict[str, int]] = {}
    samples: dict[str, list[str]] = {}
    for column, label in zip(columns, headers):
        key = label or column
        values = [row.get(column) for row in data_rows if row.get(column) not in (None, "")]
        counts[key] = len(values)
        types[key] = dict(Counter(value_kind(value) for value in values))
        seen: list[str] = []
        for value in values:
            rendered = str(value).strip()
            if rendered and rendered not in seen:
                seen.append(rendered)
            if len(seen) == 4:
                break
        samples[key] = seen
    return SheetProfile(
        name=name,
        rows=len(rows),
        columns=len(columns),
        header_row=header_index + 1 if header_index is not None else None,
        headers=headers,
        nonempty_by_column=counts,
        types_by_column=types,
        sample_values_by_column=samples,
    )


def semantic_numbers_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with zipfile.ZipFile(path) as archive:
        table_members = sorted(
            name for name in archive.namelist() if name.startswith("Index/Tables/Tile-") and name.endswith(".iwa")
        )
        for name in table_members:
            digest.update(archive.read(name))
    return digest.hexdigest()


def profile_file(path: Path, root: Path) -> FileProfile:
    extension = path.suffix.lower()
    sheets: list[SheetProfile] = []
    notes: list[str] = []
    semantic_hash = None
    if extension == ".xlsx":
        try:
            sheets = [profile_sheet(name, rows) for name, rows in read_xlsx(path)]
        except Exception as error:  # keep profiling other samples
            notes.append(f"XLSX parsing failed: {type(error).__name__}: {error}")
    elif extension == ".numbers":
        semantic_hash = semantic_numbers_hash(path)
        notes.append("Apple Numbers package: table payload fingerprinted; conversion is required for row-level profiling.")
    elif extension == ".pdf":
        notes.append("PDF statement: text extraction/OCR adapter is required for row-level profiling.")
    else:
        notes.append("Unsupported sample format.")
    return FileProfile(
        path=str(path.relative_to(root)),
        extension=extension,
        size=path.stat().st_size,
        sha256=sha256_path(path),
        semantic_hash=semantic_hash,
        sheets=sheets,
        notes=notes,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sample_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sample_dir = args.sample_dir.resolve()
    profiles = [profile_file(path, sample_dir.parent) for path in sorted(sample_dir.iterdir()) if path.is_file()]
    payload = {"generated_at": datetime.now().astimezone().isoformat(), "files": [asdict(item) for item in profiles]}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
