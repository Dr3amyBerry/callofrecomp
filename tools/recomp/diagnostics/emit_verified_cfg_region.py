"""Emit OFF-by-default CoDSP 1.5 CFG helper only after independent x86 proof.

Requires an audited PE, pinned p-code/Ghidra body-map and original-x86 proof
including five RAM-alias scenarios. The derived .c is never tracked by Git.
No runtime, Android build or generated chunk is modified by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from cfg_region_lab import select_block,generate_runtime_region_c
from pcode2c import parse
from diagnostics.analyze_cfg_regions import verify_inputs
from diagnostics.verify_x86_prefix_oracle import (
    OracleError,require_private_path,require_original_fingerprints
)
EXPECTED_OUT=ROOT/"recomp_out/codsp_cfg14_geom_41c017.c"
SCHEMA="phase14c-real-original-x86-exact-RAM-oracle-v1"


def validate_proof(report:dict,pe_hash:str,pcode_hash:str,map_hash:str)->None:
    if (report.get("schema")!=SCHEMA or
        report.get("source_sha256")!=pe_hash or
        report.get("pcode_sha256")!=pcode_hash or
        report.get("map_sha256")!=map_hash or
        report.get("original_start_pc")!="0x0041c017" or
        report.get("original_exit_pc")!="0x00523cd9" or
        report.get("original_x86_instructions")!=29 or
        report.get("memory_model")!="EXACT guest 32-bit addresses, 24 MiB mapped; no modulo" or
        report.get("all_passed") is not True or
        report.get("cases",0)<40):
        raise OracleError("No valid original x86 exact-address region proof")
    scenarios=report.get("tested_scenarios",{})
    if set(scenarios)!={"0","1","2","3","4"}:
        raise OracleError("all 5 original memory scenarios required")
    for key,details in scenarios.items():
        if (details.get("cases",0)<8 or
            details.get("guest_pc_and_GPR_and_5_EFLAGS_and_full_R_and_full_RAM_matched") is not True):
            raise OracleError("insufficient matching original x86 memory-alias cases")
    if not any(scenarios[str(key)].get("read_after_write_alias_cases",0)>=8
               for key in (1,4)):
        raise OracleError("no independent read-after-write alias evidence")


def emit_private(out:Path,source:str) -> tuple[str,bool]:
    if out.resolve()!=EXPECTED_OUT.resolve():
        raise OracleError("output must be EXACT recomp_out/codsp_cfg14_geom_41c017.c")
    folder=EXPECTED_OUT.parent.resolve(strict=True)
    if not folder.is_relative_to(ROOT.resolve()):
        raise OracleError("output folder outside verified repo")
    cmd=subprocess.run(["git","check-ignore","-q",str(out)],cwd=ROOT,
                       capture_output=True)
    if cmd.returncode!=0:
        raise OracleError("derived CoDSP source would be tracked by Git; refuse")
    data=source.encode("utf-8")
    sha=hashlib.sha256(data).hexdigest()
    if out.exists():
        if out.read_bytes()!=data:
            raise OracleError("private region C already exists with DIFFERENT bytes")
        return sha,False
    with out.open("xb") as stream:
        stream.write(data)
    return sha,True


def main(argv:list[str]|None=None)->int:
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pe",type=Path,required=True)
    ap.add_argument("--proof",type=Path,required=True,
                    help="private summary.json from x86 original 40+ tests")
    ap.add_argument("--out",type=Path,default=EXPECTED_OUT)
    args=ap.parse_args(argv)
    try:
        require_private_path(args.pe,ROOT/".local/private")
        proof=args.proof.resolve(strict=True)
        if not proof.is_relative_to((ROOT/".local/profiles").resolve()):
            raise OracleError("original-x86 proof must remain private")
        pe_hash=hashlib.sha256(args.pe.read_bytes()).hexdigest()
        pcode=ROOT/"recomp_out/codsp.pcode"
        pcode_hash=hashlib.sha256(pcode.read_bytes()).hexdigest()
        require_original_fingerprints(pe_hash,pcode_hash)
        mapping=ROOT/"recomp_out/codsp_function_map_v2.json"
        p_hash,m_hash=verify_inputs(pcode,mapping)
        report=json.loads(proof.read_text(encoding="utf-8"))
        validate_proof(report,pe_hash,p_hash,m_hash)
        insns,_u,_f=parse(pcode)
        body_map=json.loads(mapping.read_text(encoding="utf-8"))
        block=select_block(insns,body_map,0x0041B8F0,0x0041C017)
        source,chosen=generate_runtime_region_c(block,cache_count=5)
        hash_value,created=emit_private(args.out,source)
        print("CFG14_RUNTIME_HELPER_EMITTED",
              "fields",len(chosen),"sha256",hash_value,
              "created",created,"path",args.out,flush=True)
        return 0
    except (ValueError,OSError,OracleError,RuntimeError) as exc:
        print("CFG14_RUNTIME_HELPER_REFUSED",exc,file=sys.stderr,flush=True)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
