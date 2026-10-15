#!/usr/bin/env python3
"""Archive a conservative batch of private, legacy, unreferenced Python scripts.

Requires fresh private preflight manifests produced by the audit scripts.
Does not execute legacy scripts or touch binaries, build trees or live studies.
Every original SHA and destination is recorded for safe restore. Dry-run default.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / ".local" / "profiles"
CATALOG = ROOT / ".local" / "catalog"
PREFLIGHT = CATALOG / "script_move_preflight.json"
DEEP = CATALOG / "script_move_preflight_deep.json"
NESTED = CATALOG / "nested_script_references.json"
MANIFEST = CATALOG / "archived_legacy_scripts_2026-10-15.json"
PREFIX = ".local/profiles/"
CANDIDATE = re.compile(r"^(add_|fix_|phase[0-9]+[a-z]?_|tecno_live_screenshot\.py$|tecno_screen_small\.py$)", re.I)
MAX_AGE_HOURS = 12


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def label(name: str) -> str:
    if name.startswith("tecno_"):
        return "tecno"
    if name.startswith("phase14"):
        return "cfg-phase14"
    if re.match(r"phase[0-9]+[a-z]?_", name):
        return "cpu-phases"
    if name.startswith(("add_", "fix_")):
        return "oneoff-edits"
    return "misc"


def proposed(limit: int, now: float | None = None) -> list[dict]:
    if not (1 <= limit <= 150):
        raise ValueError("Batch size must be between 1 and 150")
    now = time.time() if now is None else now
    audit = json.loads(PREFLIGHT.read_text(encoding="utf8"))
    deep = json.loads(DEEP.read_text(encoding="utf8"))
    metadata = {x["path"]: x for x in audit["scripts"]}
    eligible = {path for path, _ in deep["candidates"]}
    refs = deep["references"]
    nested_refs = json.loads(NESTED.read_text(encoding="utf8"))
    ordered = sorted(eligible, key=lambda p: (
        0 if Path(p).name in {"tecno_live_screenshot.py", "tecno_screen_small.py"} else 1,
        Path(p).name
    ))
    out = []
    for rel in ordered:
        if not rel.startswith(PREFIX):
            continue
        old = ROOT / rel
        if old.parent != PROFILE or not old.is_file() or old.is_symlink():
            continue
        name = old.name
        if not CANDIDATE.match(name):
            continue
        if refs.get(name) or nested_refs.get(name):
            continue
        stat = old.stat()
        if now - stat.st_mtime < MAX_AGE_HOURS * 3600:
            continue
        expected = metadata.get(rel)
        if not expected or expected["bytes"] != stat.st_size:
            continue
        # Rehash all selected bytes and require the exact preflight digest.
        sha = digest(old)
        if sha != expected["sha256"]:
            continue
        # 'Deep' preflight already rejects '__file__' and imports from siblings.
        destination = PROFILE / "history" / "scripts" / label(name) / name
        if destination.exists() or destination.is_symlink():
            continue
        out.append({"old": rel,
                    "new": destination.relative_to(ROOT).as_posix(),
                    "sha256": sha, "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns})
        if len(out) >= limit:
            break
    return out


def apply(moves: list[dict]) -> None:
    if MANIFEST.exists():
        raise RuntimeError("Manifest exists; use --restore or explicitly review it, never overwrite")
    # Validate all before moving any source.
    for item in moves:
        src, dst = ROOT / item["old"], ROOT / item["new"]
        if dst.exists() or src.stat().st_mtime_ns != item["mtime_ns"] or digest(src) != item["sha256"]:
            raise RuntimeError("Evidence changed during preflight: " + item["old"])
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"schema": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                                    "description": "Conservative historical scripts; see tools/organize_legacy_scripts.py",
                                    "moves": moves}, ensure_ascii=False, indent=2), encoding="utf8")
    moved = 0
    for item in moves:
        src, dst = ROOT / item["old"], ROOT / item["new"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        if digest(dst) != item["sha256"]:
            raise RuntimeError("Moved file hash changed: " + item["new"])
        moved += 1
    print(json.dumps({"archived": moved, "manifest": MANIFEST.relative_to(ROOT).as_posix()}))


def restore() -> None:
    moves = json.loads(MANIFEST.read_text(encoding="utf8"))["moves"]
    restored = 0
    for item in moves:
        src, dst = ROOT / item["old"], ROOT / item["new"]
        if src.is_file() and not dst.exists():
            # This entry was not moved, or was already restored.
            continue
        if src.exists() or not dst.is_file() or digest(dst) != item["sha256"]:
            raise RuntimeError("Unsafe restore: " + item["old"])
        src.parent.mkdir(parents=True, exist_ok=True)
        dst.rename(src)
        if digest(src) != item["sha256"]:
            raise RuntimeError("Restored file hash changed: " + item["old"])
        restored += 1
    print(json.dumps({"restored": restored, "manifest_kept": True}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        if args.apply and args.restore:
            raise ValueError("Choose either --apply or --restore")
        if args.restore:
            restore()
            return 0
        moves = proposed(args.batch_size)
        if args.apply:
            apply(moves)
        else:
            counts = {}
            for item in moves:
                tag = Path(item["new"]).parent.name
                counts[tag] = counts.get(tag, 0) + 1
            print(json.dumps({"mode": "dry-run", "batch": len(moves),
                              "total_bytes": sum(x["bytes"] for x in moves),
                              "categories": counts, "first_ten": moves[:10]},
                             ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
