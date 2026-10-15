#!/usr/bin/env python3
"""Read-only validation of private artifacts, archives, and profile organization.

Never executes experimental scripts or hashes large APK assets. Provides a
bounded JSON report under ignored .local/catalog when requested.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import warnings

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
PROFILES = LOCAL / "profiles"
CATALOG = LOCAL / "catalog"
EXPECTED = {"captures", "logs", "metrics", "scripts", "builds", "reports", "raw"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_move_manifest(path: Path, field: str) -> tuple[dict, list[str]]:
    if not path.exists():
        return {"status": "absent", "count": 0}, []
    doc = json.loads(path.read_text(encoding="utf8"))
    errors = []
    moved, total = 0, 0
    for item in doc[field]:
        if isinstance(item, dict):
            src = ROOT / item["old"]
            dst = ROOT / item["new"]
        else:
            src, dst = ROOT / item[0], ROOT / item[1]
        total += 1
        # Historic build manifests may describe moves as strings, and are
        # verified only by path; hashing multi-GB binary trees is unnecessary.
        if src.exists() and not dst.exists():
            errors.append("Archive item still at source: " + str(src.relative_to(ROOT)))
            continue
        if src.exists() or not dst.exists():
            errors.append("Missing/ambiguous archive: " + str(dst.relative_to(ROOT)))
            continue
        if isinstance(item, dict):
            if not dst.is_file() or dst.stat().st_size != item["bytes"]:
                errors.append("Archived size mismatch: " + str(dst.relative_to(ROOT)))
                continue
            if sha256(dst) != item["sha256"]:
                errors.append("Archived SHA mismatch: " + str(dst.relative_to(ROOT)))
                continue
        moved += 1
    return {"status": "complete" if not errors else "incomplete",
            "count": total, "verified": moved}, errors


def verify_runs() -> tuple[dict, list[str]]:
    base = PROFILES / "runs"
    errors = []
    counts = Counter()
    if not base.exists():
        return {"runs": 0, "status": "not-created"}, []
    for path in base.rglob("session.json"):
        if path.is_symlink():
            errors.append("Symlink session metadata: " + str(path))
            continue
        try:
            data = json.loads(path.read_text(encoding="utf8"))
            for sub in EXPECTED:
                if not (path.parent / sub).is_dir():
                    errors.append("Missing run folder: " + str(path.parent / sub))
            if not data.get("created_utc") or not data.get("target") or not data.get("study"):
                errors.append("Incomplete run metadata: " + str(path))
            counts[data.get("target", "unknown")] += 1
        except (ValueError, OSError):
            errors.append("Invalid session JSON: " + str(path))
    return {"runs": sum(counts.values()), "by_target": dict(counts)}, errors


def verify_scripts() -> tuple[dict, list[str]]:
    paths = []
    excluded = {"__pycache__", ".git", "angle-research", "mesa-zink",
                "node_modules", "CMakeFiles", ".venv"}
    # Include nested WSA/TECNO studies, archived scripts and small private
    # catalog tools. Do not recurse into .local/builds, APKs or dependencies.
    for base, children_to_skip in (
        (PROFILES, excluded),
        (LOCAL, excluded | {"profiles", "builds", "private", "dependencies",
                            "references", "releases", "downloads", "toolchains",
                            "wsa-ab"}),
    ):
        for here, dirs, filenames in os.walk(base, followlinks=False):
            parent = Path(here)
            dirs[:] = [name for name in dirs if name not in children_to_skip
                       and not (parent / name).is_symlink()
                       and not os.path.isjunction(parent / name)]
            for name in filenames:
                p = parent / name
                if p.suffix.lower() == ".py" and p.is_file() and not p.is_symlink():
                    paths.append(p)
    paths = sorted(set(paths))
    bad = []
    hashes = defaultdict(list)
    counts = Counter()
    for p in paths:
        try:
            data = p.read_bytes()
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=SyntaxWarning)
                ast.parse(data.decode("utf-8-sig"), filename=str(p))
            counts["valid"] += 1
            hashes[hashlib.sha256(data).hexdigest()].append(p.relative_to(ROOT).as_posix())
        except (UnicodeError, SyntaxError, OSError) as err:
            bad.append({"path": p.relative_to(ROOT).as_posix(),
                        "detail": str(err)[:180]})
    duplicates = [x for x in hashes.values() if len(x) > 1]
    return {"inspected": len(paths), "valid_ast": counts["valid"],
            "legacy_parse_errors": bad, "exact_duplicate_groups": duplicates,
            "loose_profile_scripts": len(list(PROFILES.glob("*.py"))),
            "archived_scripts": len(list((PROFILES / "history" / "scripts").rglob("*.py")))}, []


def verify_index() -> tuple[dict, list[str]]:
    path = CATALOG / "profiles_index.json"
    if not path.exists():
        return {"status": "index-missing"}, ["Profiles index missing: tools/local_workspace.py refresh"]
    doc = json.loads(path.read_text(encoding="utf8"))
    paths = {x["path"] for x in doc["files"]}
    errors = []
    archive = CATALOG / "archived_legacy_scripts_2026-10-15.json"
    if archive.exists():
        for item in json.loads(archive.read_text(encoding="utf8"))["moves"]:
            if item["new"] not in paths:
                errors.append("Archived script missing from index: " + item["new"])
            if item["old"] in paths:
                errors.append("Stale source in index: " + item["old"])
    return {"indexed": doc.get("count"), "current_paths": len(paths),
            "last_updated_utc": doc.get("indexed_utc")}, errors


def verify_git_privacy() -> tuple[dict, list[str]]:
    cp = subprocess.run(["git", "ls-files", "--", ".local"],
                        cwd=ROOT, capture_output=True, text=True, check=False)
    if cp.returncode:
        return {"status": "git-unavailable"}, []
    paths = [line for line in cp.stdout.splitlines() if line.strip()]
    return {"tracked_private_paths": len(paths)}, (
        ["Unexpected private files tracked by Git: " + ", ".join(paths[:5])] if paths else []
    )


def report() -> dict:
    checked = {}
    errors = []
    for label, func in (
        ("historic_scripts", lambda: verify_move_manifest(CATALOG / "archived_legacy_scripts_2026-10-15.json", "moves")),
        ("historic_screenshots", lambda: verify_move_manifest(CATALOG / "archived_loose_captures_2026-10-15.json", "entries")),
        ("historic_builds", lambda: verify_move_manifest(CATALOG / "archived_builds_2026-10-15.json", "moves")),
        ("session_layout", verify_runs),
        ("python_legacy", verify_scripts),
        ("search_index", verify_index),
        ("private_git_safety", verify_git_privacy),
    ):
        value, found = func()
        checked[label] = value
        errors.extend(found)
    legacy_issues = checked.get("python_legacy", {}).get("legacy_parse_errors", [])
    warnings_list = [
        "Legacy Python syntax error (not executed): " + x["path"]
        for x in legacy_issues
    ]
    status = "fail" if errors else ("pass_with_warnings" if warnings_list else "pass")
    return {"checked_utc": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "errors": errors,
            "warnings": warnings_list,
            "checks": checked}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--save", action="store_true", help="Write report only under private catalog")
    args = p.parse_args(argv)
    result = report()
    if args.save:
        CATALOG.mkdir(parents=True, exist_ok=True)
        outfile = CATALOG / "verification_report.json"
        outfile.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
