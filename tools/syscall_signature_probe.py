#!/usr/bin/env python3
"""Record direct stack-slot references and return shapes of syscall dispatcher cases.

Deliberately conservative: a referenced slot is not a complete function prototype,
and a preserved EAX does not prove a particular return value or type. All code is
static and original binaries are never modified.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

INSTRUCTION = re.compile(r'^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{2}\s+)+\s*(.*?)\s*$')
ARG_SLOT = re.compile(r'\[ebp\+0x([0-9a-fA-F]+)\]', re.IGNORECASE)


def parse_asm(disassembly: str, start: int, stop: int) -> dict:
    """Summarize *observed direct* slot references and final return shape."""
    instructions = []
    slots = set()
    for line in disassembly.splitlines():
        match = INSTRUCTION.match(line)
        if not match:
            continue
        va, asm = int(match.group(1), 16), match.group(2)
        if not (start <= va < stop) or not asm:
            continue
        bits = asm.split(None, 1)
        op = bits[0].lower()
        operands = bits[1].strip() if len(bits) > 1 else ''
        # [ebp+0] is the syscall *ID*, not the first user argument.
        for h in ARG_SLOT.findall(operands):
            offset = int(h, 16)
            if offset >= 4 and offset % 4 == 0:
                slots.add((offset - 4) // 4)
        instructions.append({'va': va, 'op': op, 'operands': operands})

    if not instructions:
        raise ValueError(f'no decoded instructions at 0x{start:x}')

    last = instructions[-1]
    if last['op'] == 'jmp':
        return_shape = 'tail_jump_delegated'
    elif last['op'].startswith('ret'):
        last_call = max((i for i, x in enumerate(instructions) if x['op'] == 'call'), default=-1)
        after_call = instructions[last_call + 1:]
        forced_zero = any(
            (x['op'] == 'xor' and x['operands'].replace(' ', '').lower() == 'eax,eax') or
            (x['op'] == 'mov' and x['operands'].replace(' ', '').lower() in ('eax,0x0', 'eax,0'))
            for x in after_call
        )
        return_shape = 'forced_zero_eax' if forced_zero else 'eax_not_forced_zero'
    else:
        return_shape = 'unknown_or_fallthrough'

    direct_indices = sorted(slots)
    return {
        'direct_arg_indices': direct_indices,
        'direct_arg_count_lower_bound': (max(direct_indices) + 1) if direct_indices else 0,
        'return_shape': return_shape,
        'last_instruction_va': last['va'],
        'last_instruction_op': last['op'],
        'decoded_instruction_count': len(instructions),
    }


def scan_case(exe: Path, start: int, stop: int, objdump: str = 'objdump') -> dict:
    proc = subprocess.run(
        [objdump, '-d', '-M', 'intel',
         f'--start-address=0x{start:x}', f'--stop-address=0x{stop:x}', str(exe)],
        capture_output=True, text=True, check=True,
    )
    return parse_asm(proc.stdout, start, stop)


def analyze(exe: Path, callback_va: int, start_id: int, end_id: int,
            max_handler_bytes: int = 192, objdump: str = 'objdump') -> dict:
    from syscall_handler_edges import analyze as edge_analyze

    report = edge_analyze(exe, callback_va, start_id, end_id,
                          max_handler_bytes=max_handler_bytes, objdump=objdump)
    cases = []
    cache = {}
    for handler in report['handlers']:
        start, stop = handler['entry_va'], handler['scan_end_va']
        key = (start, stop)
        if key not in cache:
            cache[key] = scan_case(exe, start, stop, objdump)
        cases.append({**handler, **cache[key]})
    return {
        'schema_version': 1,
        'binary': exe.name,
        'callback_va': callback_va,
        'ids': [start_id, end_id],
        'method': 'bounded x86 objdump instructions; no indirect argument inference',
        'return_shape_disclaimer': 'EAX observation only; not a C return type',
        'cases': cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Recover conservative ABI shapes of engine syscall cases')
    parser.add_argument('exe', type=Path)
    parser.add_argument('--callback-va', type=lambda x: int(x, 0), required=True)
    parser.add_argument('--start-id', type=int, required=True)
    parser.add_argument('--end-id', type=int, required=True)
    parser.add_argument('--max-handler-bytes', type=int, default=192)
    parser.add_argument('--objdump', default='objdump')
    parser.add_argument('--json', dest='json_path', type=Path)
    args = parser.parse_args()
    try:
        report = analyze(args.exe, args.callback_va, args.start_id,
                         args.end_id, args.max_handler_bytes, args.objdump)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    for item in report['cases']:
        args_txt = ','.join(str(x) for x in item['direct_arg_indices']) or '-'
        print(f"{item['id']:3} 0x{item['entry_va']:08x} direct-args=[{args_txt}] "
              f"return={item['return_shape']}")
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
