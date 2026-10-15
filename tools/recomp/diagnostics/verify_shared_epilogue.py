#!/usr/bin/env python3
"""Audit CoDSP 1.5 shared function epilogue without changing guest execution.

The geometry body at 0x0041B8F0 has three external JMP exits to a separate
Ghidra function at 0x00523CD9. This tool pins direct source edges, checks
independently decoded original PE control flow and classifies the shared tail
as mandatory guest code (comparison, conditional branch, RET, failure JMP).

This is STATIC proof of targets only: the security-check hypothesis must not
be mistaken for a complete x86 state oracle. Full input/output state, stack,
flags, memory aliasing and guest return addresses remain observable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from pcode2c import parse
from region_cfg import micro_exits, extract_function, CFGError
from diagnostics.analyze_cfg_regions import verify_inputs
from diagnostics.verify_cfg_against_x86 import (
    _verify_paths,
)

GEOMETRY_ENTRY=0x0041B8F0
SHARED_ENTRY=0x00523CD9
GEOMETRY_JMPS=(0x0041C012,0x0041C07A,0x0041C090)
TAIL_JCC=0x00523CDF
TAIL_RET=0x00523CE1
TAIL_FAILURE_JMP=0x00523CE2
FAILURE_TARGET=0x00523CA8
COOKIE_GLOBAL_ADDRESS=0x00563940


def assert_direct_control(ops: list, next_pc: int, kind: str, target: int|None) -> None:
    """Fail closed on wrong, missing or extra micro-CFG edges."""
    if not ops:
        raise CFGError("No p-code at shared control boundary")
    exits,issues=micro_exits(ops,next_pc)
    actual={(exit.kind,exit.target) for exit in exits}
    if kind=="conditional_taken":
        expected={(kind,target),("fallthrough",next_pc)}
    else:
        expected={(kind,target)}
    if actual!=expected or issues:
        raise CFGError("Shared tail has mismatched original p-code control flow")


def verify_epilogue_contract(instructions: list, mapping: dict,
                             x86_decode) -> dict:
    """Validate all private original guest PCs and independent x86 class/edges."""
    body,_,_=extract_function(instructions,mapping,GEOMETRY_ENTRY)
    allowed={pc for pc,_size,_ops in body}
    by_pc={pc:(size,ops) for pc,size,ops in instructions}
    if SHARED_ENTRY in allowed or not any(
            item["entry_va"]==f"0x{SHARED_ENTRY:08x}" and item["entry_in_translation"]
            for item in mapping["functions"]):
        raise CFGError("Shared exit must be distinct verified Ghidra function entry")
    for pc in GEOMETRY_JMPS:
        if pc not in allowed or pc not in by_pc:
            raise CFGError("Expected geometry external JMP absent")
        size,ops=by_pc[pc]
        assert_direct_control(ops,pc+size,"direct_jump",SHARED_ENTRY)
        decoded=x86_decode(pc,size)
        if (decoded.control!="direct_jump" or decoded.target!=SHARED_ENTRY
                or decoded.size!=size):
            raise CFGError("Original x86 geometry JMP differs from Ghidra p-code")
    for pc,kind,target in (
            (TAIL_JCC,"conditional_taken",TAIL_FAILURE_JMP),
            (TAIL_RET,"dynamic_return",None),
            (TAIL_FAILURE_JMP,"direct_jump",FAILURE_TARGET)):
        if pc not in by_pc:
            raise CFGError("Shared epilogue guest PC absent")
        size,ops=by_pc[pc]
        assert_direct_control(ops,pc+size,kind,target)
        decoded=x86_decode(pc,size)
        expected_control={"conditional_taken":"conditional",
                          "dynamic_return":"return",
                          "direct_jump":"direct_jump"}[kind]
        if (decoded.control!=expected_control or decoded.target!=target
                or decoded.size!=size):
            raise CFGError("Original x86 shared epilogue differs from p-code")
    # The initial CMP has no transfer; x86 must explicitly read ECX and the
    # memory address containing the check value, not a synthetic NOP.
    pc=SHARED_ENTRY
    if pc not in by_pc:
        raise CFGError("Shared entry CMP not translated")
    size,ops=by_pc[pc]
    assert_direct_control(ops,pc+size,"fallthrough",TAIL_JCC)
    decoded=x86_decode(pc,size)
    if decoded.control!="normal" or decoded.size!=size:
        raise CFGError("Shared exit CMP must be ordinary x86 instruction")
    # Comparand operands themselves must be checked using Capstone detail
    # by caller; this pure control graph proof never claims memory equality.
    return {
        "schema":"phase14-original-shared-epilogue-contract-v1",
        "geometry_entry":f"0x{GEOMETRY_ENTRY:08x}",
        "external_jumps":[f"0x{pc:08x}" for pc in GEOMETRY_JMPS],
        "shared_entry":f"0x{SHARED_ENTRY:08x}",
        "shared_entry_is_own_function":True,
        "success_control":"CMP at entry, conditional JNE to failure, RET on equal",
        "return_exit":f"0x{TAIL_RET:08x}",
        "failure_branch":f"0x{TAIL_FAILURE_JMP:08x}",
        "failure_destination":f"0x{FAILURE_TARGET:08x}",
        "hypothesis":"stack/security cookie check; not yet proven complete",
        "must_preserve_shared_tail":True,
        "safe_to_inline_or_omit":False,
        "has_full_state_oracle":False,
    }


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pe",required=True,type=Path)
    parser.add_argument("--pcode",type=Path,default=ROOT/"recomp_out/codsp.pcode")
    parser.add_argument("--map",type=Path,default=ROOT/"recomp_out/codsp_function_map_v2.json")
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        _verify_paths(args.pe,args.pcode,args.map,args.out)
        verify_inputs(args.pcode,args.map)
        insns,_,_=parse(args.pcode)
        mapping=json.loads(args.map.read_text(encoding="utf-8"))
        import pefile
        from capstone import Cs,CS_ARCH_X86,CS_MODE_32
        from capstone.x86_const import X86_OP_REG,X86_OP_MEM
        # Decode every CHECKED original instruction, including CMP operands.
        pe=pefile.PE(str(args.pe),fast_load=True)
        if pe.OPTIONAL_HEADER.ImageBase!=0x400000:
            raise ValueError("Unexpected original CoDSP x86 image base")
        capstone=Cs(CS_ARCH_X86,CS_MODE_32)
        capstone.detail=True
        from diagnostics.verify_cfg_against_x86 import X86Instruction
        from capstone import CS_GRP_JUMP,CS_GRP_RET
        from capstone.x86_const import X86_OP_IMM
        def decode(pc,size):
            data=pe.get_data(pc-0x400000,size)
            code=list(capstone.disasm(data,pc,count=1)) if len(data)==size else []
            if len(code)!=1 or code[0].size!=size:
                raise CFGError("Original PE instruction boundaries differ")
            ins=code[0]
            if ins.group(CS_GRP_RET):
                kind,target="return",None
            elif ins.group(CS_GRP_JUMP):
                if ins.operands and ins.operands[0].type==X86_OP_IMM:
                    target=int(ins.operands[0].imm)&0xffffffff
                    kind="direct_jump" if ins.mnemonic=="jmp" else "conditional"
                else:
                    kind,target="indirect_jump",None
            else:
                kind,target="normal",None
            return X86Instruction(pc,size,kind,target)
        # Check exact CMP operands: ECX vs [0x00563940].
        cmp_raw=pe.get_data(SHARED_ENTRY-0x400000,TAIL_JCC-SHARED_ENTRY)
        cmp_decode=list(capstone.disasm(cmp_raw,SHARED_ENTRY,count=1))
        if len(cmp_decode)!=1 or cmp_decode[0].mnemonic!="cmp":
            raise CFGError("Original shared entry not a CMP")
        left,right=cmp_decode[0].operands
        from capstone.x86_const import X86_REG_ECX
        if (left.type!=X86_OP_REG or left.reg!=X86_REG_ECX or
            right.type!=X86_OP_MEM or right.mem.disp!=COOKIE_GLOBAL_ADDRESS):
            raise CFGError("Shared CMP operands disagree with checked x86 instructions")
        contract=verify_epilogue_contract(insns,mapping,decode)
        contract.update({
            "source_pe_sha256":hashlib.sha256(args.pe.read_bytes()).hexdigest(),
            "cookie_global_reference":f"0x{COOKIE_GLOBAL_ADDRESS:08x}",
            "independent_original_x86_decode":True,
            "read_only":True,
        })
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with args.out.open("x",encoding="utf-8",newline="\n") as sink:
            json.dump(contract,sink,indent=2,sort_keys=True)
            sink.write("\n")
        print("SHARED_EXIT_VERIFIED",contract["geometry_entry"],
              "sources",len(GEOMETRY_JMPS),"to",contract["shared_entry"],
              "failure",contract["failure_destination"],
              "success_return",contract["return_exit"],flush=True)
        return 0
    except (OSError,ValueError,ImportError,CFGError) as error:
        parser.error(str(error))


if __name__=="__main__":
    raise SystemExit(main())
