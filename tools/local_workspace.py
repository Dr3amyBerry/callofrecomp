#!/usr/bin/env python3
"""Private workspace session and script registry for CallofRecomp.

Never follows junctions, never scans downloaded third-party repos, never deletes
historical data. Other agents may write concurrently: index is advisory only.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
PROFILES = LOCAL / "profiles"
INDEX = LOCAL / "catalog" / "profiles_index.json"
DIRS = ("captures", "logs", "metrics", "scripts", "builds", "reports", "raw")
TARGETS = ("wsa", "tecno", "arm64-offline", "shared")
SKIP = frozenset((".git", ".venv", "__pycache__", "node_modules", "angle-research",
                  "mesa-zink", "CMakeFiles", "build", "Testing"))
EXT_KIND = {".py": "script", ".ps1": "script", ".bat": "script",
            ".sh": "script", ".cmd": "script", ".png": "capture",
            ".jpg": "capture", ".jpeg": "capture", ".webp": "capture",
            ".gif": "capture", ".log": "log", ".json": "data",
            ".apk": "build", ".so": "build", ".exe": "build",
            ".md": "document"}
SAFE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,49}$")
SUFFIXES = (".py", ".ps1", ".bat", ".sh", ".cmd")


def check_slug(s: str) -> str:
    if not SAFE.fullmatch(s):
        raise ValueError("Use 1-50 lowercase letters, digits, '_' or '-' (no paths)")
    return s


def safe_path(path: Path, home: Path) -> bool:
    try:
        path.resolve().relative_to(home.resolve())
        return True
    except ValueError:
        return False


def current_sha() -> str:
    cp = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                        capture_output=True, text=True, check=False)
    return cp.stdout.strip() if cp.returncode == 0 else "unknown"


def create_run(target: str, slug: str, agent: str = "chatgpt-mcp",
               now: datetime | None = None) -> Path:
    if target not in TARGETS:
        raise ValueError("Unknown target")
    check_slug(slug)
    check_slug(agent)
    now = now or datetime.now(timezone.utc)
    parent = PROFILES / "runs" / target / now.strftime("%Y-%m-%d") / slug
    parent.mkdir(parents=True, exist_ok=True)
    for number in range(100):
        run = parent / (now.strftime("%Y%m%dT%H%M%SZ") + f"-{os.getpid()}-{number:02d}")
        try:
            run.mkdir(exist_ok=False)
            break
        except FileExistsError:
            continue
    else:
        raise RuntimeError("Could not allocate a unique run")
    for sub in DIRS:
        (run / sub).mkdir()
    identity = {
        "schema": 1,
        "created_utc": now.isoformat(),
        "target": target,
        "study": slug,
        "agent": agent,
        "git_head_at_start": current_sha(),
        "status": "in_progress",
        "note": "Place exact APK/ELF IDs, graphics preset and A/B labels in reports."
    }
    (run / "session.json").write_text(json.dumps(identity, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    return run


def entries(base: Path, exclude: set[str] | None = None):
    if not base.exists():
        return
    exclude = exclude or set()
    for here, children, names in os.walk(base, followlinks=False):
        parent = Path(here)
        children[:] = sorted(c for c in children if c not in SKIP and c not in exclude
                             and not (parent / c).is_symlink()
                             and not os.path.isjunction(parent / c))
        for name in sorted(names):
            p = parent / name
            try:
                if p.is_symlink() or not p.is_file():
                    continue
                st = p.stat()
            except OSError:
                continue
            yield p, st


def index_files() -> dict:
    files = []
    for base in (PROFILES, LOCAL / "scripts", ROOT / "tools"):
        if not base.exists():
            continue
        for p, st in entries(base, {"__pycache__"}):
            if base == ROOT / "tools" and p.suffix.lower() not in SUFFIXES:
                continue
            if base == PROFILES and p.parts[-2:] == ("catalog", "profiles_index.json"):
                continue
            rel = p.relative_to(ROOT).as_posix()
            ext = p.suffix.lower()
            files.append({"path": rel, "size": st.st_size, "modified_ns": st.st_mtime_ns,
                          "kind": EXT_KIND.get(ext, "other"),
                          "zone": (p.relative_to(base).parts[0] if len(p.relative_to(base).parts) > 1 else "loose")})
    return {"schema": 1, "indexed_utc": datetime.now(timezone.utc).isoformat(),
            "count": len(files), "files": files,
            "ignored": sorted(SKIP)}


def save_index(data: dict, path: Path | None = None) -> None:
    path = path or INDEX
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement prevents readers observing a partially written index.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                     prefix=".profiles-", suffix=".tmp",
                                     dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def candidates(query: str, data: dict, kind: str | None = None, limit: int = 20):
    if not query.strip():
        raise ValueError("Search term required")
    aliases = {"screenshot": "capture", "screenshots": "capture", "captura": "capture",
               "capturas": "capture", "foto": "capture", "pantalla": "capture",
               "screens": "capture", "fps": "frame", "medicion": "profile"}
    terms = re.findall(r"[a-z0-9]+", query.lower())
    expanded = [t for term in terms for t in {term, aliases.get(term, term)}]
    ranked = []
    for item in data["files"]:
        if kind and item["kind"] != kind:
            continue
        path = item["path"]
        name = Path(path).name.lower()
        p = path.lower()
        hits = sum(1 for t in expanded if t in p)
        if not hits:
            continue
        canonical = p.startswith("tools/")
        score = hits * 10 + (25 if name.startswith(query.lower()) else 0)
        if kind == "script" and canonical:
            score += 15
        if name == query.lower():
            score += 60
        ranked.append((score, item))
    ranked.sort(key=lambda row: (-row[0], row[1]["path"]))
    return [item for _, item in ranked[:limit]]


def exact_script_duplicates():
    groups = {}
    for base in (PROFILES, LOCAL / "scripts", ROOT / "tools"):
        for p, _ in entries(base) or ():
            if p.suffix.lower() not in SUFFIXES:
                continue
            try:
                if p.stat().st_size > 2_000_000:
                    continue
                digest = hashlib.sha256(p.read_bytes()).hexdigest()
            except OSError:
                continue
            groups.setdefault(digest, []).append(p.relative_to(ROOT).as_posix())
    return [paths for paths in groups.values() if len(paths) > 1]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("new-run", help="Create a unique immutable-by-default study folder")
    run.add_argument("--target", required=True, choices=TARGETS)
    run.add_argument("--slug", required=True)
    run.add_argument("--agent", default="chatgpt-mcp")
    sub.add_parser("refresh", help="Regenerate indexed metadata (not binary contents)")
    find = sub.add_parser("find", help="Search the compact catalog instead of scanning recursively")
    find.add_argument("query")
    find.add_argument("--kind", choices=sorted(set(EXT_KIND.values())))
    find.add_argument("--limit", type=int, default=20)
    sub.add_parser("duplicates", help="Find byte-identical scripts without deleting anything")
    args = parser.parse_args(argv)
    try:
        if args.action == "new-run":
            print(create_run(args.target, args.slug, args.agent).relative_to(ROOT).as_posix())
        elif args.action == "refresh":
            data = index_files()
            save_index(data)
            by_kind = Counter(item["kind"] for item in data["files"])
            print(json.dumps({"indexed": data["count"], "by_kind": dict(by_kind),
                              "index": INDEX.relative_to(ROOT).as_posix()}))
        elif args.action == "find":
            if not 1 <= args.limit <= 100:
                raise ValueError("limit must be 1..100")
            if not INDEX.is_file():
                save_index(index_files())
            data = json.loads(INDEX.read_text(encoding="utf-8"))
            print(json.dumps({"indexed_utc": data["indexed_utc"],
                              "matches": candidates(args.query, data, args.kind, args.limit)},
                             ensure_ascii=False, indent=2))
        elif args.action == "duplicates":
            print(json.dumps({"exact_script_groups": exact_script_duplicates()},
                             ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError, OSError) as e:
        print("ERROR:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
