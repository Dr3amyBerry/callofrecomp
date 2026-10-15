#!/usr/bin/env python3
"""Reusable, read-only TECNO/WSA profile evidence tools.

Consolidates only *generalizable capabilities* of three historical, pinned
scripts: phase15_compare_capture_hashes, phase15_inventory_existing_perf, and
phase15_two_session_check. Does not execute any archived historical script.
Use the versioned tool with explicit relative inputs rather than cloning
fixed-date experiment scripts. No FPS is inferred from sample counts.

Examples:
 python tools/recomp/diagnostics/profile_evidence.py inventory --root .local/profiles
 python tools/recomp/diagnostics/profile_evidence.py hash --root .local/profiles --files a.perf.data b.json
 python tools/recomp/diagnostics/profile_evidence.py hash --root .local/profiles --files a.perf.data --output runs/shared/DATE/SESSION/metrics/sha.json
 python tools/recomp/diagnostics/profile_evidence.py verify --root .local/profiles --manifest runs/shared/DATE/SESSION/metrics/sha.json
 python tools/recomp/diagnostics/profile_evidence.py metadata --root .local/profiles --files a.json b.json --require-same-build
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / ".local/profiles"
INVENTORY_EXT = {".data", ".json", ".log", ".txt", ".so", ".md", ".csv", ".perf"}
INVENTORY_TOKENS = ("tecno", "simpleperf", "perf", "profile", "cpu", "libmain", "hot")
META_FIELDS = ("utc", "created_utc", "status", "warning", "total_cpu_samples",
               "libmain_cpu_samples", "installed_unstripped_build_id",
               "elapsed_seconds", "duration_requested_sec", "package")


class EvidenceError(ValueError):
    pass


def root_dir(value: str | Path) -> Path:
    root = Path(value).resolve()
    if not root.is_dir():
        raise EvidenceError("Evidence root is not a directory: " + str(value))
    return root


def safe_file(root: Path, relative: str) -> Path:
    path = Path(relative)
    if not relative or path.is_absolute() or path.drive or ".." in path.parts:
        raise EvidenceError("Only relative paths inside --root are supported: " + relative)
    if any(part in ("", ".") for part in path.parts) or ":" in relative:
        raise EvidenceError("Invalid relative file path: " + relative)
    target = root / path
    if not target.is_file() or target.is_symlink():
        raise EvidenceError("Evidence file missing or symlink: " + relative)
    canonical = target.resolve()
    if not canonical.is_relative_to(root):
        raise EvidenceError("Evidence file escapes root: " + relative)
    return canonical


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_files(root: Path, names: list[str]) -> dict:
    if not names or len(names) > 500:
        raise EvidenceError("Provide 1..500 file names")
    if len(names) != len(set(names)):
        raise EvidenceError("Repeated file name in capture set")
    results = []
    for name in names:
        path = safe_file(root, name)
        results.append({"path": path.relative_to(root).as_posix(),
                        "size_bytes": path.stat().st_size, "sha256": sha256(path)})
    return {"schema": 1, "kind": "profile_evidence_hashes", "files": results}


def save_hashes(root: Path, relative: str, doc: dict) -> None:
    path = Path(relative)
    if not relative or path.is_absolute() or path.drive or ".." in path.parts:
        raise EvidenceError("Invalid output path")
    # Use the same per-session private workspace conventions as local_workspace.
    if len(path.parts) < 5 or path.parts[0] != "runs" or "metrics" not in path.parts[:-1]:
        raise EvidenceError("Save hashes only in runs/.../metrics/... under evidence root")
    target = (root / path).resolve()
    if not target.is_relative_to(root) or not target.parent.is_dir():
        raise EvidenceError("Output must be inside an existing run metrics directory")
    if target.suffix.lower() != ".json":
        raise EvidenceError("Output filename must be .json")
    with target.open("x", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")


def verify_hashes(root: Path, manifest: str) -> dict:
    source = safe_file(root, manifest)
    if source.stat().st_size > 2_000_000:
        raise EvidenceError("Fingerprint manifest exceeds 2MB")
    doc = json.loads(source.read_text(encoding="utf-8"))
    if doc.get("schema") != 1 or doc.get("kind") != "profile_evidence_hashes":
        raise EvidenceError("Unsupported fingerprint schema or kind")
    entries = doc.get("files")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 500:
        raise EvidenceError("Invalid fingerprint manifest file list")
    names = [x.get("path") if isinstance(x, dict) else None for x in entries]
    if any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
        raise EvidenceError("Missing/duplicate fingerprint file paths")
    checks = []
    for entry in entries:
        target = safe_file(root, entry["path"])
        expected_hash = entry.get("sha256")
        expected_size = entry.get("size_bytes")
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise EvidenceError("Invalid SHA256 for " + entry["path"])
        if type(expected_size) is not int or expected_size < 0:
            raise EvidenceError("Invalid size for " + entry["path"])
        actual_size = target.stat().st_size
        actual_hash = sha256(target)
        checks.append({"path": entry["path"], "ok":
                       (expected_hash == actual_hash and expected_size == actual_size)})
    return {"status": "pass" if all(x["ok"] for x in checks) else "fail",
            "count": len(checks), "verified": sum(x["ok"] for x in checks),
            "checks": checks}


def inventory(root: Path, *, limit: int = 150, max_bytes: int = 350 * 1024 * 1024,
              token: str = "") -> dict:
    if not 1 <= limit <= 2000 or max_bytes < 0 or max_bytes > 2**44:
        raise EvidenceError("Bad inventory limits")
    items = []
    skipped_symlinks = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        keep = []
        for name in sorted(dirs):
            child = base / name
            if child.is_symlink() or os.path.isjunction(child):
                skipped_symlinks += 1
            elif name not in {"__pycache__", "CMakeFiles", "angle-research", "mesa-zink"}:
                keep.append(name)
        dirs[:] = keep
        for name in files:
            path = base / name
            if path.is_symlink():
                skipped_symlinks += 1
                continue
            if path.suffix.lower() not in INVENTORY_EXT:
                continue
            low_name = name.lower()
            if token and token.lower() not in low_name:
                continue
            if not token and not any(t in low_name for t in INVENTORY_TOKENS):
                continue
            st = path.stat()
            if st.st_size > max_bytes:
                continue
            items.append({"path": path.relative_to(root).as_posix(),
                          "size_bytes": st.st_size})
    items.sort(key=lambda x: x["path"])
    return {"count": len(items), "results": items[:limit],
            "truncated": len(items) > limit, "ignored_symlinks": skipped_symlinks}


def metadata(root: Path, names: list[str], *, require_same_build: bool = False,
             require_complete: bool = False) -> dict:
    if not 1 <= len(names) <= 100 or len(names) != len(set(names)):
        raise EvidenceError("Provide 1..100 distinct JSON file names")
    results, ids = [], []
    for name in names:
        path = safe_file(root, name)
        if path.suffix.lower() != ".json" or path.stat().st_size > 5_000_000:
            raise EvidenceError("Metadata must be JSON smaller than 5MB: " + name)
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise EvidenceError("Metadata root must be an object: " + name)
        fields = {key: raw[key] for key in META_FIELDS if key in raw
                  and isinstance(raw[key], (str, int, float, bool, type(None)))}
        resolved = raw.get("resolved_guest")
        if isinstance(resolved, dict):
            fields["resolved_native_samples_total"] = resolved.get("native_samples_total")
            fields["resolved_unique_body_samples"] = resolved.get("unique_ghidra_body_samples")
        build = fields.get("installed_unstripped_build_id")
        if require_same_build:
            if not isinstance(build, str) or not re.fullmatch(r"[0-9a-fA-F]{8,128}", build):
                raise EvidenceError("Build ID missing or invalid: " + name)
            ids.append(build.lower())
        if require_complete and fields.get("status") != "complete":
            raise EvidenceError("Capture incomplete or status missing: " + name)
        results.append({"path": path.relative_to(root).as_posix(), "fields": fields})
    if require_same_build and len(set(ids)) != 1:
        raise EvidenceError("Installed/unstripped Build IDs differ across sessions")
    return {"count": len(results), "same_build_id": (ids[0] if ids else None),
            "metadata": results,
            "caution": "CPU samples/metadata do not establish game FPS"}


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__.splitlines()[1].strip())
    subs = cli.add_subparsers(dest="command", required=True)
    inv = subs.add_parser("inventory")
    inv.add_argument("--root", default=str(DEFAULT_ROOT))
    inv.add_argument("--limit", type=int, default=150)
    inv.add_argument("--max-bytes", type=int, default=350 * 1024 * 1024)
    inv.add_argument("--name-contains", default="")
    hasher = subs.add_parser("hash")
    hasher.add_argument("--root", default=str(DEFAULT_ROOT))
    hasher.add_argument("--files", nargs="+", required=True)
    hasher.add_argument("--output", help="new JSON under existing runs/.../metrics/")
    ver = subs.add_parser("verify")
    ver.add_argument("--root", default=str(DEFAULT_ROOT))
    ver.add_argument("--manifest", required=True)
    meta = subs.add_parser("metadata")
    meta.add_argument("--root", default=str(DEFAULT_ROOT))
    meta.add_argument("--files", nargs="+", required=True)
    meta.add_argument("--require-same-build", action="store_true")
    meta.add_argument("--require-complete", action="store_true")
    args = cli.parse_args(argv)
    try:
        root = root_dir(args.root)
        if args.command == "inventory":
            result = inventory(root, limit=args.limit, max_bytes=args.max_bytes,
                               token=args.name_contains)
        elif args.command == "hash":
            result = hash_files(root, args.files)
            if args.output:
                save_hashes(root, args.output, result)
        elif args.command == "verify":
            result = verify_hashes(root, args.manifest)
        else:
            result = metadata(root, args.files,
                              require_same_build=args.require_same_build,
                              require_complete=args.require_complete)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("status") == "fail" else 0
    except (EvidenceError, OSError, ValueError, json.JSONDecodeError) as error:
        print("PROFILE_EVIDENCE_ERROR:", error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
