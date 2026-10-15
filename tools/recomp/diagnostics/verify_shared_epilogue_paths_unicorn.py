#!/usr/bin/env python3
"""Original CoDSP x86 shared epilogue: independent Unicorn two-path oracle.

Executes CMP/JNE/RET for matching cookie and CMP/JNE/JMP for mismatched
cookie from ORIGINAL 1.5 PE bytes. Uses current pcode2c.Gen for comparison,
with exact guest addresses (no folded RAM) in ignored PRIVATE DLL output.

Fail branch is validated THROUGH jump to error-handler entry 0x00523CA8,
not through handler calls, exceptions or process termination.
"""
from __future__ import annotations
import argparse,ctypes,hashlib,json,random,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from pcode2c import parse,Gen,temporary_layout
from diagnostics.verify_x86_prefix_oracle import (
    OracleError,require_private_path,require_ignored_output,
    require_original_fingerprints,FLAG_BITS,REG_OFFSETS)
from diagnostics.verify_shared_epilogue import (
    SHARED_ENTRY,TAIL_JCC,TAIL_RET,TAIL_FAILURE_JMP,
    FAILURE_TARGET,COOKIE_GLOBAL_ADDRESS)
from diagnostics.benchmark_cfg_region import compile_host

PC_SUCCESS=0x00471230  # mapped sentinel, not executed
MEM_SIZE=0x600000
R_SIZE=0x2000
STACK=0x320000
INSN_PCS=(SHARED_ENTRY,TAIL_JCC,TAIL_RET,TAIL_FAILURE_JMP)
REG_NAMES=tuple(REG_OFFSETS)
EXPECTED_MNEMONICS=("cmp","jne","ret","jmp")
ERROR_SETUP_PCS=(0x00523CA8,0x00523CAA,0x00523CAF)
ERROR_SETUP_MNEMONICS=("push","push","call")
ERROR_CALL_TARGET=0x0051FF90

def verified_pcode(insns:list,pe_path:Path,*,follow_error_call:bool=False)->tuple[dict,dict]:
    import pefile
    from capstone import Cs,CS_ARCH_X86,CS_MODE_32
    by={pc:(size,ops) for pc,size,ops in insns}
    pe=pefile.PE(str(pe_path),fast_load=True)
    if pe.OPTIONAL_HEADER.ImageBase!=0x400000:
        raise OracleError("Unexpected original CoDSP PE base")
    cs=Cs(CS_ARCH_X86,CS_MODE_32)
    raw={}
    selected={}
    path_pcs=INSN_PCS+(ERROR_SETUP_PCS if follow_error_call else ())
    names=EXPECTED_MNEMONICS+(ERROR_SETUP_MNEMONICS if follow_error_call else ())
    for pc,name in zip(path_pcs,names):
        if pc not in by:raise OracleError("missing original Ghidra p-code for shared epilogue")
        size,ops=by[pc]
        body=pe.get_data(pc-0x400000,size)
        di=list(cs.disasm(body,pc,count=1))
        if len(di)!=1 or di[0].size!=size or di[0].mnemonic!=name:
            raise OracleError("original shared epilogue instruction differs from p-code")
        if not ops or temporary_layout(ops) is None:
            raise OracleError("unproven p-code unique temporary in shared epilogue")
        selected[pc]=(size,ops)
        raw[pc]=body
    if (int(list(cs.disasm(raw[TAIL_JCC],TAIL_JCC))[0].op_str,0)
            !=TAIL_FAILURE_JMP or
        int(list(cs.disasm(raw[TAIL_FAILURE_JMP],TAIL_FAILURE_JMP))[0].op_str,0)
            !=FAILURE_TARGET):
        raise OracleError("original error branch targets changed")
    if follow_error_call:
        direct=list(cs.disasm(raw[ERROR_SETUP_PCS[-1]],ERROR_SETUP_PCS[-1]))
        if len(direct)!=1 or int(direct[0].op_str,0)!=ERROR_CALL_TARGET:
            raise OracleError("error handler's first original call target changed")
    return selected,raw

def generate_private_epilogue(selected:dict,*,follow_error_call:bool=False)->str:
    lines=[
        "/* PRIVATE: ORIGINAL CoDSP 1.5-derived pcode. NEVER COMMIT. */",
        '#include "recomp_rt.h"',
        "uint8_t *MEM; uint8_t R[0x2000]; uint8_t U[0x400000];",
        "uint32_t PC; int recomp_miss;",
        "#if defined(_WIN32)",
        "#define EXPORTED __declspec(dllexport)",
        "#else",
        '#define EXPORTED __attribute__((visibility("default")))',
        "#endif",
        "EXPORTED uint32_t epilogue_pc(void){return PC;}",
        "EXPORTED void run_epilogue(uint8_t *regs, uint8_t *guest_memory) {",
        " MEM=guest_memory; memcpy(R,regs,0x2000); PC=0x523cd9u;",
        " goto p_523cd9;",
    ]
    g=Gen({})
    for pc in INSN_PCS+(ERROR_SETUP_PCS if follow_error_call else ()):
        ops=selected[pc][1]
        offsets=temporary_layout(ops)
        if offsets is None:raise OracleError("undefined shared-tail unique state")
        g.temp_offsets=offsets
        lines.append(f"p_{pc:x}: {{ uint8_t T[{max(1,len(offsets))}];")
        for mnemonic,out,inputs in ops:
            if (mnemonic in {"CALLIND","CALLOTHER","BRANCHIND"} or
                (mnemonic=="CALL" and pc!=ERROR_SETUP_PCS[-1])):
                raise OracleError("shared tail has unexpected opaque control")
            def jump(target):
                allowed=(TAIL_FAILURE_JMP,FAILURE_TARGET,ERROR_CALL_TARGET)
                if target[0]!="m" or target[1] not in allowed:
                    raise OracleError("unexpected original shared-tail jump target")
                if target[1]==TAIL_FAILURE_JMP:return f"goto p_{TAIL_FAILURE_JMP:x};"
                if target[1]==FAILURE_TARGET and follow_error_call:
                    return f"goto p_{FAILURE_TARGET:x};"
                return f"PC=0x{target[1]:x}u; goto finish;"
            stmt=g.op(mnemonic,out,inputs,jump,None)
            if "unsupported(" in stmt:raise OracleError("unsupported shared-tail p-code")
            lines.append(" "+stmt)
        lines.append("}")
        if pc==SHARED_ENTRY:lines.append(f"goto p_{TAIL_JCC:x};")
        elif pc==TAIL_JCC:lines.append(f"goto p_{TAIL_RET:x};")
        elif pc==TAIL_RET:lines.append("goto finish;") # Return uses goto dyn.
        elif pc==TAIL_FAILURE_JMP:lines.append("goto finish;")
        elif pc==ERROR_SETUP_PCS[0]:lines.append(f"goto p_{ERROR_SETUP_PCS[1]:x};")
        elif pc==ERROR_SETUP_PCS[1]:lines.append(f"goto p_{ERROR_SETUP_PCS[2]:x};")
        elif pc==ERROR_SETUP_PCS[2]:lines.append("goto finish;")
    if g.unsupported:raise OracleError("unsupported shared tail lowering")
    lines+=["dyn: goto finish;","finish: memcpy(regs,R,0x2000);","}"]
    return "\n".join(lines)+"\n"

def bits(flags,offset):
    for _name,(bit,slot) in FLAG_BITS.items():
        if slot==offset:return (flags>>bit)&1
    raise OracleError("unknown modeled flag")

def case_input(index:int,success:bool):
    rng=random.Random(0x523cd9 ^ (index*0x9e3779b1) ^ (0 if success else 0x1234))
    state=bytearray(rng.randbytes(R_SIZE))
    mem=bytearray(MEM_SIZE)
    stack=bytearray(rng.randbytes(0x180))
    memory_cookie=rng.getrandbits(32)
    if index%8==0:memory_cookie=0
    elif index%8==1:memory_cookie=0xffffffff
    elif index%8==2:memory_cookie=0x80000000
    elif index%8==3:memory_cookie=1
    ecx_value=(memory_cookie if success else memory_cookie ^ (1<<(index%32)))
    ret=PC_SUCCESS
    mem[STACK:STACK+len(stack)]=stack
    mem[STACK:STACK+4]=ret.to_bytes(4,"little")
    mem[COOKIE_GLOBAL_ADDRESS:COOKIE_GLOBAL_ADDRESS+4]=memory_cookie.to_bytes(4,"little")
    regs={name:rng.getrandbits(32) for name in REG_NAMES}
    regs["ESP"]=STACK
    regs["ECX"]=ecx_value
    for name,off in REG_OFFSETS.items():
        state[off:off+4]=regs[name].to_bytes(4,"little")
    # Never accidentally arm CPU single-step TF (bit 8), which raises #DB
    # after CMP and is unrelated to this bounded epilogue proof.
    modeled=sum(1<<bit for bit,_offset in FLAG_BITS.values())
    oldflags=2 | (rng.getrandbits(16) & (modeled | (1<<4)))
    for _name,(bit,off) in FLAG_BITS.items():
        state[off]=(oldflags>>bit)&1
    return bytes(state),bytes(mem),regs,oldflags

def verify_case(index:int,success:bool,lib,raw:dict,*,follow_error_call:bool=False)->dict:
    from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
    import unicorn.x86_const as X
    ids={
        "EAX":X.UC_X86_REG_EAX,"ECX":X.UC_X86_REG_ECX,
        "EDX":X.UC_X86_REG_EDX,"EBX":X.UC_X86_REG_EBX,
        "ESP":X.UC_X86_REG_ESP,"EBP":X.UC_X86_REG_EBP,
        "ESI":X.UC_X86_REG_ESI,"EDI":X.UC_X86_REG_EDI,
    }
    initial,mem,seed_regs,seedflags=case_input(index,success)
    uc=Uc(UC_ARCH_X86,UC_MODE_32)
    uc.mem_map(0x1000,MEM_SIZE-0x1000)
    for pc,body in raw.items():uc.mem_write(pc,body)
    uc.mem_write(STACK,mem[STACK:STACK+0x180])
    uc.mem_write(COOKIE_GLOBAL_ADDRESS,mem[COOKIE_GLOBAL_ADDRESS:COOKIE_GLOBAL_ADDRESS+4])
    for name,value in seed_regs.items():uc.reg_write(ids[name],value)
    uc.reg_write(X.UC_X86_REG_EFLAGS,seedflags)
    uc.reg_write(X.UC_X86_REG_EIP,SHARED_ENTRY)
    expected_end=PC_SUCCESS if success else (
        ERROR_CALL_TARGET if follow_error_call else FAILURE_TARGET)
    visited=[]
    def trace(cpu,pc,_size,_):
        visited.append(pc)
        if pc==expected_end:cpu.emu_stop()
    uc.hook_add(UC_HOOK_CODE,trace)
    try:uc.emu_start(SHARED_ENTRY,0,count=8,timeout=300000)
    except Exception as exc:
        raise OracleError(f"Original epilogue Unicorn trapped case={index} success={success}: {exc} "
                          f"visited={[hex(v) for v in visited]}, "
                          f"EIP=0x{uc.reg_read(X.UC_X86_REG_EIP):08x}, "
                          f"ESP=0x{uc.reg_read(X.UC_X86_REG_ESP):08x}, "
                          f"jnebytes={bytes(uc.mem_read(TAIL_JCC,2)).hex()}, "
                          f"retbytes={bytes(uc.mem_read(TAIL_RET,1)).hex()}, "
                          f"jbytes={bytes(uc.mem_read(TAIL_FAILURE_JMP,5)).hex()}") from exc
    expected_visited=(SHARED_ENTRY,TAIL_JCC,TAIL_RET,PC_SUCCESS) if success else (
        (SHARED_ENTRY,TAIL_JCC,TAIL_FAILURE_JMP,*ERROR_SETUP_PCS,ERROR_CALL_TARGET)
        if follow_error_call else
        (SHARED_ENTRY,TAIL_JCC,TAIL_FAILURE_JMP,FAILURE_TARGET))
    if tuple(visited)!=expected_visited or uc.reg_read(X.UC_X86_REG_EIP)!=expected_end:
        raise OracleError("Original epilogue exited unexpected x86 path")
    buf=ctypes.create_string_buffer(initial,R_SIZE)
    ram=ctypes.create_string_buffer(mem,MEM_SIZE)
    lib.run_epilogue(ctypes.cast(buf,ctypes.c_void_p),ctypes.cast(ram,ctypes.c_void_p))
    libpc=lib.epilogue_pc()
    if libpc!=expected_end:
        raise OracleError(f"Translator epilogue PC mismatch x86 in case {index}, success={success}")
    expected=bytearray(initial)
    for name,off in REG_OFFSETS.items():
        actual=uc.reg_read(ids[name])&0xffffffff
        expected[off:off+4]=actual.to_bytes(4,"little")
        if buf.raw[off:off+4]!=expected[off:off+4]:
            raise OracleError(f"Translator {name} differs at epilogue case {index}")
    finalflags=uc.reg_read(X.UC_X86_REG_EFLAGS)
    for _name,(bit,off) in FLAG_BITS.items():
        expected[off]=(finalflags>>bit)&1
        if buf.raw[off]!=expected[off]:
            raise OracleError(f"Translator {_name} differs at epilogue case {index}")
    # Ghidra emits RET's stack-loaded target into R+0x284 (guest EIP
    # shadow), then copies it into the dispatcher PC. This is an actual
    # architectural side effect of the p-code, not a stray write.
    if success:
        expected[0x284:0x288]=expected_end.to_bytes(4,"little")
    if buf.raw!=expected:
        offsets=[hex(i) for i,(a,b) in enumerate(zip(buf.raw,expected)) if a!=b]
        raise OracleError("Translator wrote unexpected R byte in epilogue at offsets "+str(offsets[:16]))
    # The short epilogue changes no memory. With follow_error_call the
    # ORIGINAL failure handler pushes two args + the first CALL return PC.
    expected_mem=bytearray(mem)
    if follow_error_call and not success:
        expected_mem[STACK-4:STACK]=(8).to_bytes(4,"little")
        expected_mem[STACK-8:STACK-4]=(0x00533B68).to_bytes(4,"little")
        expected_mem[STACK-12:STACK-8]=(0x00523CB4).to_bytes(4,"little")
    if ram.raw!=bytes(expected_mem):
        raise OracleError("Translated shared error-handler memory diverged")
    if bytes(uc.mem_read(STACK-16,0x190))!=bytes(expected_mem[STACK-16:STACK-16+0x190]):
        raise OracleError("Original epilogue/error handler mutated stack unexpectedly")
    if bytes(uc.mem_read(COOKIE_GLOBAL_ADDRESS,4))!=mem[COOKIE_GLOBAL_ADDRESS:COOKIE_GLOBAL_ADDRESS+4]:
        raise OracleError("Original epilogue mutated global cookie unexpectedly")
    expected_stack=STACK+(4 if success else (-12 if follow_error_call else 0))
    if uc.reg_read(X.UC_X86_REG_ESP)!=expected_stack:
        raise OracleError("Original x86 return/failure-call stack adjustment unexpected")
    # AF is intentionally NOT compared: old translator omits materialization.
    return {"branch":"return" if success else "failure_entry",
            "modeled_flags_equal":True,"gpr_R_RAM_PC_equal":True}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pe",required=True,type=Path)
    ap.add_argument("--pcode",type=Path,default=ROOT/"recomp_out/codsp.pcode")
    ap.add_argument("--output",required=True,type=Path)
    ap.add_argument("--cases-per-branch",type=int,default=128)
    ap.add_argument("--follow-error-first-call",action="store_true",
                    help="also execute original error handler PUSH/PUSH/CALL up to first call target")
    args=ap.parse_args(argv)
    if not 1<=args.cases_per_branch<=512:
        ap.error("--cases-per-branch range 1..512")
    try:
        require_private_path(args.pe,ROOT/".local/private")
        p_sha=hashlib.sha256(args.pcode.read_bytes()).hexdigest()
        pe_sha=hashlib.sha256(args.pe.read_bytes()).hexdigest()
        require_original_fingerprints(pe_sha,p_sha)
        require_ignored_output(args.output,ROOT)
        insns,_,_=parse(args.pcode)
        selected,raw=verified_pcode(insns,args.pe,
                                    follow_error_call=args.follow_error_first_call)
        args.output.mkdir(parents=True,exist_ok=False)
        private_source=args.output/"private_epilogue.c"
        private_dll=args.output/"private_epilogue.dll"
        private_source.write_text(generate_private_epilogue(
            selected,follow_error_call=args.follow_error_first_call),encoding="utf-8")
        compile_host(private_source,private_dll)
        lib=ctypes.CDLL(str(private_dll.resolve()))
        lib.run_epilogue.argtypes=(ctypes.c_void_p,ctypes.c_void_p)
        lib.run_epilogue.restype=None
        lib.epilogue_pc.argtypes=()
        lib.epilogue_pc.restype=ctypes.c_uint32
        counts={"return":0,"failure_entry":0}
        for success in (True,False):
            for index in range(args.cases_per_branch):
                result=verify_case(index,success,lib,raw,
                                   follow_error_call=args.follow_error_first_call)
                counts[result["branch"]]+=1
            print("SHARED_EPILOGUE_ORIGINAL_X86", "RETURN" if success else "FAILURE_ENTRY",
                  counts["return" if success else "failure_entry"],flush=True)
        result={
            "schema":"phase14-shared-tail-original-x86-branch-oracle-v1",
            "pe_sha256":pe_sha,"pcode_sha256":p_sha,
            "start":"0x00523cd9","success_return_target":f"0x{PC_SUCCESS:08x}",
            "failure_handler_entry":"0x00523ca8",
            "failure_path_stopped_at_first_external_call":args.follow_error_first_call,
            "failure_first_external_call_target":"0x0051ff90"
                 if args.follow_error_first_call else None,
            "branches_checked":counts,
            "checked":["8 GPR","5 modeled flags CF/PF/ZF/SF/OF",
                       "full 8192-byte R","6MiB guest RAM",
                       "stack","exact guest PC"],
            "AF_equivalence_checked":False,
            "failure_handler_body_executed":bool(args.follow_error_first_call),
            "failure_handler_full_execution_verified":False,
            "full_exception_semantics_checked":False,
            "all_checked_passed":True,
        }
        (args.output/"summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        return 0
    except (OracleError,OSError,ValueError,RuntimeError) as err:
        print("SHARED_EPILOGUE_X86_FAILED",err,file=sys.stderr,flush=True)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
