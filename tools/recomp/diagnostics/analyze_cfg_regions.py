"""Audit original CoDSP regions without exposing proprietary instructions.

CLI requires the exact audited CoDSP 1.5 p-code and Ghidra v2 body map.
Reports go only to ignored .local/profiles and never overwrite a prior run.
This is structural discovery, NOT a transformed build or an x86 oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/recomp"))
from pcode2c import parse  # noqa: E402
from region_cfg import recover_function_cfg  # noqa: E402

PCODE_SHA256 = "36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e"
MAP_SHA256 = "f6d56b4d167df2fb66a9f18ff8624e6b48fd363eadcbd05e62fa2598cd03ab4c"
HOT_FUNCTIONS = (
    0x0041B8F0, 0x004196F0,
    0x0047BD40,
    0x004D8280, 0x004D94C0, 0x004D8420, 0x004D6BC0,
)


def validate_paths(pcode: Path, mapping: Path, output: Path, root: Path) -> None:
    """Reject untrusted version, nonprivate output and all overwrites."""
    work = root.resolve()
    raw = (work / "recomp_out").resolve()
    private = (work / ".local/profiles").resolve()
    a = pcode.resolve(strict=True)
    b = mapping.resolve(strict=True)
    out = output.resolve()
    if (not a.is_relative_to(raw) or not b.is_relative_to(raw) or
            not out.is_relative_to(private) or out == private or out.exists() or
            out in (a, b)):
        raise ValueError("Inputs must be under recomp_out; new output inside .local/profiles")
    if a.name != "codsp.pcode" or b.name != "codsp_function_map_v2.json":
        raise ValueError("Only audited CoDSP 1.5 original inputs are supported")


def sha256_file(file: Path) -> str:
    with file.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def verify_inputs(pcode: Path, mapping: Path) -> tuple[str, str]:
    p_sha = sha256_file(pcode)
    m_sha = sha256_file(mapping)
    if p_sha != PCODE_SHA256:
        raise ValueError("CoDSP p-code SHA-256 mismatch; no CFG report created")
    if m_sha != MAP_SHA256:
        raise ValueError("Ghidra v2 function body-map SHA-256 mismatch")
    return p_sha, m_sha


def build_report(insns: list, mapping: dict, entries: tuple[int, ...],
                 p_sha: str, m_sha: str) -> dict:
    if mapping.get("module", "").lower() != "codsp.exe" or mapping.get("schema_version") != 2:
        raise ValueError("Need CoDSP Ghidra B body-map schema v2")
    if mapping.get("instruction_count") != len(insns):
        raise ValueError("Map instruction count differs from the raw p-code")
    if len(set(entries)) != len(entries):
        raise ValueError("Duplicate requested entry")
    if not entries:
        raise ValueError("Select at least one function")
    functions = [recover_function_cfg(insns, mapping, va) for va in entries]
    return {
        "schema": "callofrecomp-phase14-cfg-v1",
        "pcode_sha256": p_sha,
        "function_map_v2_sha256": m_sha,
        "module": "codsp",
        "source_kind": "original_Ghidra_pcode_B_ranges",
        "semantics": "read_only_structural_cfg_not_x86_oracle",
        "partitions_untouched": True,
        "functions": functions,
        "summary": [
            {"entry": f["entry_va"],
             "insns": f["instruction_count"], "blocks": f["block_count"],
             "external_edges": len(f["outgoing_external_edges"]),
             "dynamic_exits": len(f["dynamic_exit_edges"]),
             "known_external_entries": f["hazards"].get("known_external_direct_entries", 0),
             "missing_pcode": f["hazards"].get("missing_pcode", 0),
             "direct_reachable": f["direct_reachable_instructions"],
             "may_return_reachable": f["may_return_reachable_instructions"]}
            for f in functions
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pcode", type=Path, default=ROOT / "recomp_out/codsp.pcode")
    parser.add_argument("--map", type=Path, default=ROOT / "recomp_out/codsp_function_map_v2.json")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--entry", action="append", type=lambda x: int(x, 0),
                        help="Select one original Ghidra function entry (repeatable); default 7 hotspots")
    args = parser.parse_args(argv)
    try:
        validate_paths(args.pcode, args.map, args.out, ROOT)
        sha_a, sha_b = verify_inputs(args.pcode, args.map)
        mapping = json.loads(args.map.read_text(encoding="utf-8"))
        insns, _, _ = parse(args.pcode)
        report = build_report(insns, mapping,
                              tuple(args.entry) if args.entry else HOT_FUNCTIONS,
                              sha_a, sha_b)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive create protects earlier evidence if another process races us.
        with args.out.open("x", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, indent=2, sort_keys=True)
            f.write("\n")
    except (ValueError, OSError, KeyError, StopIteration) as error:
        parser.error(str(error))
    for item in report["summary"]:
        print("CFG", item["entry"], "instructions", item["insns"],
              "blocks", item["blocks"],
              "indirect", item["dynamic_exits"],
              "unknown_pcode", item["missing_pcode"],
              "known_external_entries", item["known_external_entries"])
    print("PHASE14_CFG_REPORT", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
