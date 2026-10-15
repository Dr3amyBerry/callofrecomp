#!/usr/bin/env python3
"""Archive retired build outputs without touching active junctions, generated C or saves."""
from pathlib import Path
import os, json, hashlib, argparse, datetime, subprocess

ROOT=Path(__file__).resolve().parents[1]
MOVES={
    ".local/builds/phase14d_cfg_off":".local/builds/history/cfg14/phase14d_cfg_off",
    ".local/builds/phase14d_cfg_off_v3":".local/builds/history/cfg14/phase14d_cfg_off_v3",
    ".local/builds/phase14d_cfg_on_v3":".local/builds/history/cfg14/phase14d_cfg_on_v3",
    ".local/builds/phase14e_expected_unsafe_cfg_rejection":".local/builds/history/cfg14/phase14e_expected_unsafe_cfg_rejection",
    "recomp_out/release-v0.2.0":".local/builds/history/releases/v0.2.0",
    "recomp_out/release-v0.2.1":".local/builds/history/releases/v0.2.1",
    "recomp_out/release-v0.2.2":".local/builds/history/releases/v0.2.2",
}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    moves=[];hashes=[]
    for src,dst in MOVES.items():
        a,b=ROOT/src,ROOT/dst
        if b.exists() and not a.exists():continue  # already archived safely
        if not a.is_dir() or os.path.isjunction(a) or a.is_symlink() or b.exists():
            raise RuntimeError(f"Unexpected archive source/destination: {src} -> {dst}")
        moves.append((src,dst))
        if src.startswith("recomp_out/release"):
            for file in sorted(a.iterdir()):
                if not file.is_file():raise RuntimeError("Release has unexpected subdirectory: "+str(file))
                digest=hashlib.sha256(file.read_bytes()).hexdigest() if file.stat().st_size<2_000_000 else "(large APK: use SHA256SUMS and manifest)"
                hashes.append({"path":src+"/"+file.name,"bytes":file.stat().st_size,"sha256_if_small":digest})
    plan={"date":"2026-10-15","mode":"apply" if args.apply else "dry_run","moves":moves,"release_files":hashes,
        "do_not_move":[".local/builds/build-* (active CMake/Android, including junctions)","build-retrotouch (physical third-party tree with reverse junction)","recomp_out (active generated recompilation sources)","recomp_out/release-v0.2.3 (latest known published snapshot)","profiles and A/B worktrees with exact paths"]}
    out=ROOT/".local/catalog/archived_builds_2026-10-15.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    if moves or not out.exists():
        out.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding="utf-8")
    if args.apply:
        for src,dst in moves:
            target=ROOT/dst;target.parent.mkdir(parents=True,exist_ok=True)
            (ROOT/src).rename(target)
        for src,dst in moves:
            if not (ROOT/dst).exists() or (ROOT/src).exists():raise RuntimeError("Archive relocation failed: "+src)
    print(json.dumps({"mode":plan["mode"],"moved":len(moves) if args.apply else 0,"planned":len(moves),"paths":[x[0] for x in moves]},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
