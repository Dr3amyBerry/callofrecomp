"""Emit a closed, original-byte-checked x86_64 x87 region (private output)."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

REGS={'eax':0,'ecx':4,'edx':8,'esi':24,'edi':28}

def decode_region(code,start):
    from capstone import Cs,CS_ARCH_X86,CS_MODE_32
    from capstone.x86 import X86_OP_MEM
    decoder=Cs(CS_ARCH_X86,CS_MODE_32);decoder.detail=True
    result=[];position=start
    for ins in decoder.disasm(code,start):
        if ins.address!=position:raise ValueError('instruction gap')
        position+=ins.size
        if ins.mnemonic=='ret' and ins.bytes==b'\xc3':
            if not result or position!=start+len(code):raise ValueError('invalid return')
            return result,ins.address
        if len(ins.bytes)<2:raise ValueError('unsupported instruction')
        item={'pc':ins.address,'opcode':((ins.bytes[0]&7)<<8)|ins.bytes[1]}
        if ins.mnemonic=='faddp' and bytes(ins.bytes)==b'\xde\xc1':
            item.update(asm='faddp %st, %st(1)',reg=None,disp=0)
        elif ins.mnemonic in ('fld','fmul','fadd','fstp') and len(ins.operands)==1 and ins.operands[0].type==X86_OP_MEM:
            op=ins.operands[0];mem=op.mem;reg=ins.reg_name(mem.base)
            if op.size!=4 or reg not in REGS or mem.index or mem.segment or mem.disp<0:
                raise ValueError('unsupported memory operand')
            item.update(asm={'fld':'flds','fmul':'fmuls','fadd':'fadds','fstp':'fstps'}[ins.mnemonic],reg=reg,disp=mem.disp)
        else:raise ValueError('unsupported instruction')
        result.append(item)
    raise ValueError('missing return')

def emit_region(code,start):
    instructions,ret=decode_region(code,start)
    used=sorted({i['reg'] for i in instructions if i['reg']})
    last=next(i for i in reversed(instructions) if i['reg'])
    declarations='\n'.join(f'extern const char nx87_{start:x}_{i};' for i in range(len(instructions)))
    table=',\n'.join(f'{{(uintptr_t)&nx87_{start:x}_{n},0x{i["pc"]:x},0x{i["opcode"]:x}}}' for n,i in enumerate(instructions))
    loads='\n'.join(f'uint32_t {r}; memcpy(&{r},r+{REGS[r]},4);' for r in used)
    guards='\n'.join(f'if((uint64_t){r}+{max(i["disp"] for i in instructions if i["reg"]==r)}+4>UINT64_C(0x100000000)) return 0;' for r in used)
    operands=','.join(f'[{r}] "r"(memory+{r})' for r in used)
    lines=['fxsave64 %[host]','fninit','frstor %[input]']
    for n,i in enumerate(instructions):
        lines += [f'.global nx87_{start:x}_{n}',f'nx87_{start:x}_{n}:',
                  f'{i["asm"]} {i["disp"]}(%[{i["reg"]}])' if i['reg'] else i['asm'].replace('%','%%')]
    lines+=['fnsave %[output]','fxrstor64 %[host]']
    assembly='\n'.join('"'+line+'\\n\\t"' for line in lines)
    return f'''/* Generated privately from verified original bytes. */
#include "runtime/native_x87_bridge.h"
#include <stdio.h>
extern int guest_committed(uint32_t);
{declarations}
static const native_x87_instruction instructions[]={{ {table} }};
__attribute__((noinline,used)) int codsp_native_x87_region_try(
 uint8_t *r,uint8_t *memory,uint32_t *pc,uint16_t cs,uint16_t ds) {{
 static const uint8_t expected[]={{ {','.join(str(b) for b in code)} }};
 uint16_t cw;memcpy(&cw,r+0x10a0,2);
 static int inspected;if(!inspected){{inspected=1;
 printf("codrecomp: native x87 entry cw=%04x high_mem=%d high_code=%d committed=%d/%d\\n",cw,
 (uintptr_t)memory>UINT32_MAX,instructions[0].native_pc>UINT32_MAX,
 guest_committed(0x{start:x}),guest_committed(0x{start+len(code)-1:x}));}}
 if((uintptr_t)memory<=UINT32_MAX || instructions[0].native_pc<=UINT32_MAX) return 0;
 /* Hardware always reads reserved CW bit 6 as one. The current translator
  * stores 0x023f after FLDCW; accept that alias of architectural 0x027f. */
 if((cw&0x3f)!=0x3f || (cw&0x300)==0x100 || (cw&0xe080)) return 0;
 if(!guest_committed(0x{start:x}) || !guest_committed(0x{start+len(code)-1:x}) ||
    memcmp(memory+0x{start:x},expected,sizeof expected)) {{
 static int warned;if(!warned){{warned=1;puts("codrecomp: native x87 fallback code mismatch/unmapped");}}return 0;}}
 {loads}
 {guards}
 uint32_t esp;memcpy(&esp,r+0x10,4);if(esp>UINT32_MAX-3) return 0;
 native_x87_context context={{.memory_base=(uintptr_t)memory,.instructions=instructions,
 .count=sizeof instructions/sizeof *instructions,.code_selector=cs,.data_selector=ds}};
 x87_native_state_from_registers(&context.initial,r,cs,ds);
 uint16_t hardware_cw=cw|0x40;memcpy(context.initial.bytes,&hardware_cw,2);
 x87_native_state output;_Alignas(16) uint8_t host[512];
 native_x87_active=&context;atomic_signal_fence(memory_order_seq_cst);
 __asm__ volatile({assembly}
 : [host] "+m"(host),[output] "=m"(output)
 : [input] "m"(context.initial),{operands}
 : "memory","st","st(1)","st(2)","st(3)","st(4)","st(5)","st(6)","st(7)");
 atomic_signal_fence(memory_order_seq_cst);native_x87_active=NULL;
 x87_native_state_set_memory_metadata(&output,0x{last['pc']:x},{last['reg']}+{last['disp']},0x{last['opcode']:x},cs,ds);
 native_x87_finish_return(r,memory,&output,esp,0x{ret:x},pc);
 static int announced;if(!announced){{announced=1;puts("codrecomp: native x87 region accepted");}}
 return 1;
}}
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pe',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    if args.out.resolve().parent!=(root/'recomp_out').resolve():parser.error('output must be private recomp_out')
    data=args.pe.read_bytes();digest=hashlib.sha256(data).hexdigest()
    if digest!='c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47':parser.error('unverified original PE')
    sys.path.insert(0,str(root/'tools'))
    from pe_inspect import PEFile
    pe=PEFile(args.pe);offset=pe.rva_to_offset(0x5061b0-pe.image_base)
    code=data[offset:offset+150];instructions,ret=decode_region(code,0x5061b0)
    if len(instructions)!=57 or ret!=0x506245:parser.error('unexpected region')
    args.out.write_text(emit_region(code,0x5061b0),encoding='utf-8')
    args.out.with_suffix('.json').write_text(json.dumps({'pe_sha256':digest,'source_sha256':hashlib.sha256(args.out.read_bytes()).hexdigest(),'instructions':len(instructions)},indent=2))
    print('Emitted verified private native x87 region: 57 instructions')

if __name__=='__main__':main()
