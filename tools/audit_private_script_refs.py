#!/usr/bin/env python3
"""Safe static preflight for a *new* private script archive batch.

Searches first-party source and private historical code but never executes it.
Records hashes and references. Avoids build trees, vendor dumps and binaries.
An unreferenced script is a *candidate*, not proof of independence.
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
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".local"
PROFILE = PRIVATE / "profiles"
CATALOG = PRIVATE / "catalog"
PRUNE = {".git", "__pycache__", "node_modules", ".venv", "venv",
         "angle-research", "mesa-zink", "CMakeFiles", "builds",
         "private", "dependencies", "references", "toolchains", "downloads",
         "releases", "wsa-ab"}
EXTS = {".py", ".md", ".ps1", ".sh", ".bat", ".cmd", ".json", ".yml",
        ".yaml", ".txt", ".c", ".h", ".cpp"}
MAX_BYTES = 600_000
CANDIDATE = re.compile(r"^(add_|fix_|phase[0-9]+[a-z]?_)", re.I)


def walk_sources(parent: Path):
    if not parent.is_dir():
        return
    for current, dirs, files in os.walk(parent, followlinks=False):
        here = Path(current)
        dirs[:] = [x for x in sorted(dirs)
                   if x not in PRUNE and not (here / x).is_symlink()
                   and not os.path.isjunction(here / x)]
        for file in sorted(files):
            p = here / file
            if p.suffix.lower() not in EXTS or p.is_symlink():
                continue
            try:
                if p.stat().st_size <= MAX_BYTES:
                    yield p
            except OSError:
                continue


def source_paths():
    found = set()
    for parent in (PROFILE, PRIVATE / "scripts",
                   ROOT / "tools", ROOT / "tests", ROOT / "docs",
                   ROOT / "analysis", ROOT / ".github"):
        for path in walk_sources(parent):
            found.add(path)
    # Index/catalog JSON and Markdown contain *every* known script name.
    # They are discovery data, NOT execution dependencies. Scan only helper
    # source in this directory or every candidate would falsely look used.
    for path in (PRIVATE / "catalog").glob("*.py"):
        if path.is_file() and not path.is_symlink():
            found.add(path)
    for path in PRIVATE.glob("*.py"):
        if path.is_file():
            found.add(path)
    for path in (ROOT / "AGENTS.md", ROOT / "README.md", ROOT / "PROGRESS.md"):
        if path.is_file():
            found.add(path)
    return sorted(found)


def digest(raw: bytes):
    return hashlib.sha256(raw).hexdigest()


def find_references(texts: list[tuple[str, str]], candidate_names: set[str]):
    """Index known script basenames using a single regex, not O(N*M) scans."""
    if not candidate_names:
        return {}
    pattern = re.compile(r"(?<![A-Za-z0-9_])(" +
                         "|".join(re.escape(name) for name in
                                  sorted(candidate_names, key=len, reverse=True)) +
                         r")(?![A-Za-z0-9_])")
    refs = defaultdict(set)
    for origin, body in texts:
        for match in pattern.finditer(body):
            name = match.group(1)
            # Self reference is not an external dependency.
            if origin != ".local/profiles/" + name:
                refs[name].add(origin)
    return {name: sorted(paths) for name, paths in refs.items()}


def analyze(batch_id: int, now: float | None = None) -> dict:
    if not 2 <= batch_id <= 999:
        raise ValueError("Only second and later batches are supported by this preflight")
    now = time.time() if now is None else now
    baseline = []
    for p in sorted(PROFILE.glob("*.py")):
        if p.is_file() and not p.is_symlink():
            st = p.stat()
            baseline.append((p, st, p.read_bytes()))
    candidate_names = {p.name for p, _, _ in baseline}
    texts = []
    for p in source_paths():
        try:
            content = p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        texts.append((p.relative_to(ROOT).as_posix(), content))
    references = find_references(texts, candidate_names)
    rows, candidates, reasons = [], [], Counter()
    for p, st, raw in baseline:
        rel = p.relative_to(ROOT).as_posix()
        try:
            source = raw.decode("utf-8-sig")
            ast_tree = ast.parse(source)
            valid = True
            error = None
        except (UnicodeError, SyntaxError) as e:
            valid = False
            error = str(e)[:180]
            ast_tree = None
            source = raw.decode("utf-8", errors="replace")
        imports = set()
        if ast_tree:
            for n in ast.walk(ast_tree):
                if isinstance(n, ast.Import):
                    imports.update(x.name.split(".")[0] for x in n.names)
                elif isinstance(n, ast.ImportFrom) and n.module:
                    imports.add(n.module.split(".")[0])
        sibling = sorted(i for i in imports if i + ".py" in candidate_names)
        why = []
        if not CANDIDATE.match(p.name):
            why.append("outside_archive_family")
        if now - st.st_mtime <= 12 * 3600:
            why.append("recent")
        if not valid:
            why.append("invalid_syntax")
        if "__file__" in source:
            why.append("relative_to_script")
        if sibling:
            why.append("sibling_imports")
        if references.get(p.name):
            why.append("named_reference")
        # Do not archive files that are themselves likely active script hosts.
        if len(raw) > 100_000:
            why.append("large_script")
        row = {"path": rel, "bytes": st.st_size, "mtime_ns": st.st_mtime_ns,
               "sha256": digest(raw), "ast_ok": valid, "error": error,
               "references": references.get(p.name, []), "sibling_imports": sibling,
               "reasons": why}
        rows.append(row)
        if not why:
            candidates.append(dict(row))
        else:
            reasons.update(why)
    return {
        "schema": 2, "batch_id": batch_id,
        "scanned_utc": datetime.now(timezone.utc).isoformat(),
        "scanned_epoch": now,
        "root": ".local/profiles", "no_execution": True,
        "files_scanned": len(texts), "scripts_inspected": len(rows),
        "candidate_count": len(candidates),
        "blocked_reasons": dict(reasons),
        "scripts": rows, "candidates": candidates
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", type=int, default=2)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = analyze(args.batch_id)
        dest = CATALOG / f"script_preflight_batch{args.batch_id:02d}.json"
        if args.write:
            CATALOG.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(json.dumps({
            "batch_id": report["batch_id"], "sources_scanned": report["files_scanned"],
            "scripts_inspected": report["scripts_inspected"],
            "candidates": report["candidate_count"],
            "excluded_reasons": report["blocked_reasons"],
            "saved": str(dest.relative_to(ROOT)) if args.write else None
        }, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as e:
        print("ERROR:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
