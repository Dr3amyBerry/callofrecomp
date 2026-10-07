#!/usr/bin/env python3
"""Inventory Quake/CoD PK3 archives without extracting their contents."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from zipfile import BadZipFile, ZipFile


def inspect_pk3(path: Path, include_files: bool = False) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    with ZipFile(path) as zf:
        entries = [i for i in zf.infolist() if not i.is_dir()]
        extensions = Counter((Path(i.filename).suffix.lower() or "<none>") for i in entries)
        top_dirs = Counter((i.filename.split("/", 1)[0] if "/" in i.filename else "<root>") for i in entries)
        report = {
            "name": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": digest.hexdigest(),
            "entry_count": len(entries),
            "compressed_bytes": sum(i.compress_size for i in entries),
            "uncompressed_bytes": sum(i.file_size for i in entries),
            "extensions": dict(extensions.most_common()),
            "top_level": dict(top_dirs.most_common()),
        }
        if include_files:
            report["files"] = [
                {"path": i.filename, "size": i.file_size, "compressed_size": i.compress_size, "crc32": f"{i.CRC:08x}"}
                for i in entries
            ]
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory PK3/ZIP archives without extracting them")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--include-files", action="store_true")
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()
    reports = []
    for path in args.files:
        try:
            report = inspect_pk3(path, args.include_files)
        except (OSError, BadZipFile) as exc:
            parser.error(f"{path}: {exc}")
        reports.append(report)
        print(f"{path.name}: {report['entry_count']} files, {report['uncompressed_bytes']} bytes uncompressed")
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps({"schema_version": 1, "archives": reports}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
