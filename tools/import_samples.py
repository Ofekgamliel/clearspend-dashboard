#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from clearspend.import_engine import import_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Import supported statement samples into the local ClearSpend database")
    parser.add_argument("sample_dir", type=Path)
    parser.add_argument("--database", type=Path, default=PROJECT_ROOT / "data" / "clearspend.db")
    args = parser.parse_args()
    paths = sorted(
        path for path in args.sample_dir.resolve().iterdir()
        if path.suffix.lower() in {".xlsx", ".pdf"}
    )
    print(json.dumps(import_paths(args.database, paths), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
