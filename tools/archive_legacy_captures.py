#!/usr/bin/env python3
"""Archive only verified-unused loose historic WSA PNG screenshots.

Does NOT move active A/B directories, APK, saves, or profiling scripts.
Dry-run by default. --restore uses the SHA manifest to reverse changes.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import time

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / ".local" / "profiles"
OUT = PROFILES / "history" / "wsa_20261013" / "captures"
MANIFEST = ROOT / ".local" / "catalog" / "archived_loose_captures_2026-10-15.json"
PATTERN = re.compile(r"^wsa_[a-z0-9_]+_(briefing|gameplay|menu)\.png$", re.I)


def relevant_texts():
    for parent in (ROOT / "docs", ROOT / "tools", ROOT / "tests"):
        if not parent.exists():
            continue
        for p in parent.rglob("*"):
            if p.suffix.lower() in {".md", ".py", ".ps1", ".json", ".yml", ".yaml"} and p.is_file() and p.stat().st_size < 1_000_000:
                yield p
    for p in PROFILES.glob("*.py"):
        if p.is_file() and p.stat().st_size < 1_000_000:
            yield p


def referenced_names(names):
    refs = {}
    names = set(names)
    for p in relevant_texts():
        try:
            content = p.read_text(encoding="utf8", errors="replace")
        except OSError:
            continue
        for name in names:
            if name in content:
                refs.setdefault(name, []).append(str(p.relative_to(ROOT)))
    return refs


def sha(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def plan():
    now = time.time()
    files = [p for p in PROFILES.glob("*.png") if p.is_file() and not p.is_symlink()
             and PATTERN.fullmatch(p.name) and now - p.stat().st_mtime > 6*3600]
    refs = referenced_names(p.name for p in files)
    entries = []
    for p in files:
        if p.name in refs:
            continue
        group = "vbo" if "_vbo_" in p.name else "other_ab"
        dest = OUT / group / p.name
        if dest.exists():
            continue
        st = p.stat()
        entries.append({"old": p.relative_to(ROOT).as_posix(),
                        "new": dest.relative_to(ROOT).as_posix(),
                        "bytes": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": sha(p)})
    return {"schema": 1, "entries": entries, "skipped_referenced": refs,
            "scope": "Only loose historical wsa_*.png; never active study folders."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if args.apply and args.restore:
        parser.error("--apply and --restore are mutually exclusive")
    if args.restore:
        data = json.loads(MANIFEST.read_text(encoding="utf8"))
        restored = 0
        for entry in data["entries"]:
            old, new = ROOT / entry["old"], ROOT / entry["new"]
            if not new.exists() or old.exists():
                raise RuntimeError("Unsafe restore destination/source: "+entry["old"])
            if sha(new) != entry["sha256"]:
                raise RuntimeError("Archive hash changed: "+str(new))
            old.parent.mkdir(parents=True, exist_ok=True)
            new.rename(old)
            restored += 1
        print(json.dumps({"restored": restored}))
        return
    data = plan()
    if args.apply:
        if MANIFEST.exists():
            raise RuntimeError("Existing archive manifest; use --restore instead of overwriting")
        # Verify metadata twice to avoid moving files a concurrent agent is changing.
        for entry in data["entries"]:
            src = ROOT / entry["old"]
            st = src.stat()
            if st.st_mtime_ns != entry["mtime_ns"] or st.st_size != entry["bytes"]:
                raise RuntimeError("Concurrent change detected: "+entry["old"])
            if (ROOT / entry["new"]).exists():
                raise RuntimeError("Destination exists: "+entry["new"])
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8")
        try:
            for entry in data["entries"]:
                dest = ROOT / entry["new"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                (ROOT / entry["old"]).rename(dest)
                if sha(dest) != entry["sha256"]:
                    raise RuntimeError("Moved file hash mismatch: "+str(dest))
        except BaseException:
            print("PARTIAL MOVE: inspect manifest, do not delete either location")
            raise
    print(json.dumps({"mode": "applied" if args.apply else "preview",
                      "candidates": len(data["entries"]),
                      "skipped_referenced": data["skipped_referenced"],
                      "destination": OUT.relative_to(ROOT).as_posix()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
