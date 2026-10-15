"""Phase14B: verified, byte-granular read-only original-function state contract.

No native code generated; output is private (ignored .local/profiles).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from pcode2c import parse
from region_state_contract import region_contract
from diagnostics.analyze_cfg_regions import (
    validate_paths,verify_inputs,HOT_FUNCTIONS
)


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pcode",type=Path,default=ROOT/"recomp_out/codsp.pcode")
    parser.add_argument("--map",type=Path,default=ROOT/"recomp_out/codsp_function_map_v2.json")
    parser.add_argument("--entry",action="append",type=lambda x:int(x,0),
                        help="original Ghidra F entry, repeatable; defaults to 7 hot bodies")
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        validate_paths(args.pcode,args.map,args.out,ROOT)
        p_sha,m_sha=verify_inputs(args.pcode,args.map)
        insns,_,_=parse(args.pcode)
        mapping=json.loads(args.map.read_text(encoding="utf-8"))
        selected=tuple(args.entry) if args.entry else HOT_FUNCTIONS
        if len(set(selected))!=len(selected):
            raise ValueError("Duplicate function requested")
        output=[region_contract(insns,mapping,entry) for entry in selected]
        report={
            "schema":"phase14b-per-byte-architectural-contract-v1",
            "verified_sha":{"pcode":p_sha,"ghidra_v2":m_sha},
            "interpretation":"CONSERVATIVE MAY/MUST, not an x86 state oracle or performance result",
            "function_count":len(output),
            "functions":output,
            "all_device_code_unchanged":True,
        }
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with args.out.open("x",encoding="utf-8",newline="\n") as f:
            json.dump(report,f,indent=2,sort_keys=True)
            f.write("\n")
        for obj in output:
            print("STATE_CONTRACT",obj["entry_va"],"insns",obj["instruction_count"],
                  "blocks",obj["block_count"],"R_may_read",obj["may_read_arch_bytes"],
                  "R_may_write",obj["may_write_arch_bytes"],
                  "guest_barriers",obj["hazards"],flush=True)
        print("REPORT",args.out,flush=True)
        return 0
    except (ValueError,OSError) as exc:
        parser.error(str(exc))


if __name__=="__main__":
    raise SystemExit(main())
