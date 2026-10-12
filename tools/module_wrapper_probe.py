#!/usr/bin/env python3
"""Recover direct module syscall-wrapper argument origins from a native CoD SP DLL.

Only handles the narrow assembly shapes observed near dllEntry: PUSH,
MOV (register/reg or register/ESP stack slot), CALL [callback], stack
cleanup, RET and alignment. Unknown operations fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

from pe_inspect import PEFile, PEFormatError, default_objdump

INSN_RE = re.compile(r'^\s*([a-fA-F0-9]+):\s+(?:[a-fA-F0-9]{2}\s+)+\s*([a-z][a-z0-9]*)\s*(.*?)\s*$')
ESP_REF = re.compile(r'^DWORD PTR \[esp(?:\s*\+\s*0x([0-9a-f]+))?\]$', re.IGNORECASE)
REGS = ('eax', 'ecx', 'edx', 'ebx', 'esi', 'edi')


def decode_instructions(text: str, start: int, stop: int) -> list[dict]:
    decoded = []
    for line in text.splitlines():
        match = INSN_RE.match(line)
        if not match:
            continue
        va, op, operands = int(match[1], 16), match[2].lower(), match[3].strip().lower()
        if start <= va < stop:
            decoded.append({'va': va, 'opcode': op, 'operands': operands})
    return decoded


def origin_for_stack(offset: int) -> str:
    if offset == 0:
        return 'caller_return_address'
    if offset > 0 and offset % 4 == 0:
        return f'stack_arg_{offset // 4 - 1}'
    return f'unknown_stack_offset_{offset}'


def recover_push_provenance(instructions: list[dict], callback_va: int, syscall_id: int) -> dict:
    """Symbolically track the limited wrapper instructions until the syscall call."""
    registers = {reg: reg for reg in REGS}
    esp = 0  # Relative to stack pointer on wrapper entry.
    stack = {}
    for insn in instructions:
        op = insn['opcode']
        args = [part.strip() for part in insn['operands'].split(',', 1)]
        if op == 'push' and len(args) == 1:
            if args[0] in registers:
                origin = registers[args[0]]
            else:
                try:
                    origin = f'constant_{int(args[0], 0)}'
                except ValueError:
                    origin = 'unknown_' + args[0]
            esp -= 4
            stack[esp] = origin
        elif op == 'mov' and len(args) == 2 and args[0] in registers:
            if args[1] in registers:
                registers[args[0]] = registers[args[1]]
            else:
                match = ESP_REF.fullmatch(args[1])
                if match:
                    address = esp + (int(match[1], 16) if match[1] else 0)
                    registers[args[0]] = stack.get(address, origin_for_stack(address))
                else:
                    registers[args[0]] = 'unknown_' + args[1]
        elif op == 'call' and f'0x{callback_va:x}' in insn['operands']:
            if stack.get(esp) != f'constant_{syscall_id}':
                raise ValueError('expected syscall ID at stack top')
            arguments = []
            slot = esp + 4
            while slot < 0:
                arguments.append(stack.get(slot, origin_for_stack(slot)))
                slot += 4
            return {
                'callback_call_va': insn['va'],
                'command_id': syscall_id,
                'argument_origins': arguments,
                'argument_words_pushed': len(arguments),
                'provenance': 'register/stack values at wrapper entry; not a C function signature',
            }
        elif op not in ('ret', 'nop', 'add', 'pop'):
            raise ValueError(f'unsupported wrapper instruction {op} {insn["operands"]}')
    raise ValueError('callback call not found')


def recover_wrapper_start(pe: PEFile, call_offset: int, lookback: int = 64) -> int:
    """Find the candidate start after the preceding RET and NOP padding."""
    start = max(0, call_offset - lookback)
    last_ret = pe.data[start:call_offset].rfind(b'\xc3')
    if last_ret < 0:
        raise ValueError('previous RET not found; boundary unknown')
    offset = start + last_ret + 1
    while offset < call_offset and pe.data[offset] in (0x90, 0xCC):
        offset += 1
    if offset >= call_offset:
        raise ValueError('empty wrapper prefix')
    return offset


def inspect(pe: PEFile, wanted: list[int], window: int = 1024,
            objdump: str | None = None) -> dict:
    objdump = objdump or default_objdump()
    exports = {item['name']: item for item in pe.exports()}
    entry = exports.get('dllEntry')
    if entry is None:
        raise PEFormatError('dllEntry export not found')
    start_off = pe.rva_to_offset(entry['rva'])
    prefix = pe.data[start_off:start_off + 20]
    marker_index = prefix.find(b'\xa3')
    if marker_index < 0 or marker_index + 5 > len(prefix):
        raise PEFormatError('dllEntry callback slot not recognized')
    callback_va = struct.unpack_from('<I', prefix, marker_index + 1)[0]
    marker = b'\xff\x15' + struct.pack('<I', callback_va)
    start_va = entry['va'] + 20
    stop_va = entry['va'] + window
    cases = []

    for command in wanted:
        candidates = []
        for section in pe.sections:
            if not section.characteristics & 0x20000000:
                continue
            va_start = max(start_va, pe.image_base + section.virtual_address)
            va_stop = min(stop_va, pe.image_base + section.virtual_address + section.raw_size)
            if va_stop <= va_start:
                continue
            begin = pe.rva_to_offset(va_start - pe.image_base)
            end = pe.rva_to_offset(va_stop - 1 - pe.image_base) + 1
            buf = pe.data[begin:end]
            for i in range(2, len(buf) - len(marker) + 1):
                if buf[i:i + 6] != marker:
                    continue
                match_imm8 = 0 <= command < 128 and buf[i - 2] == 0x6A and buf[i - 1] == command
                match_imm32 = i >= 5 and buf[i - 5] == 0x68 and struct.unpack_from('<I', buf, i - 4)[0] == command
                if match_imm8 or match_imm32:
                    candidates.append((begin + i, va_start + i))
        if len(candidates) != 1:
            raise ValueError(f'expected one canonical wrapper for ID {command}, found {len(candidates)}')
        call_off, call_va = candidates[0]
        wrapper_off = recover_wrapper_start(pe, call_off)
        wrapper_va = call_va - (call_off - wrapper_off)
        stop = call_va + len(marker)
        result = subprocess.run(
            [objdump, '-d', '-M', 'intel',
             f'--start-address=0x{wrapper_va:x}', f'--stop-address=0x{stop:x}',
             str(pe.path)],
            check=True, capture_output=True, text=True,
        )
        instructions = decode_instructions(result.stdout, wrapper_va, stop)
        details = recover_push_provenance(instructions, callback_va, command)
        if pe.data[call_off:call_off + 6] != marker:
            raise PEFormatError('callback call bytes changed')
        cases.append({
            'id': command, 'wrapper_va': wrapper_va,
            'wrapper_rva': wrapper_va - pe.image_base, **details,
        })

    return {
        'schema_version': 1, 'binary': pe.path.name,
        'sha256': hashlib.sha256(pe.data).hexdigest(),
        'dllEntry_va': entry['va'], 'callback_slot_va': callback_va,
        'wrapper_span_bytes': window, 'cases': cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Trace native game syscall wrapper argument origins')
    parser.add_argument('module', type=Path)
    parser.add_argument('--ids', required=True, help='comma-separated syscall IDs')
    parser.add_argument('--wrapper-span', type=int, default=1024)
    parser.add_argument('--objdump', default=None)
    parser.add_argument('--require-sha256', help='refuse input if SHA-256 does not match')
    parser.add_argument('--json', dest='json_path', type=Path)
    args = parser.parse_args()
    try:
        ids = [int(item.strip(), 0) for item in args.ids.split(',') if item.strip()]
        if not ids or len(set(ids)) != len(ids) or args.wrapper_span < 32:
            raise ValueError('empty/duplicate IDs or wrapper-span too small')
        pe = PEFile(args.module)
        actual_hash = hashlib.sha256(pe.data).hexdigest()
        if args.require_sha256 and actual_hash.lower() != args.require_sha256.lower():
            raise ValueError('input SHA-256 does not match requested baseline')
        report = inspect(pe, ids, args.wrapper_span, args.objdump)
    except (OSError, ValueError, PEFormatError, subprocess.CalledProcessError, struct.error) as exc:
        parser.error(str(exc))
    for case in report['cases']:
        print(f"{case['id']:3} wrapper 0x{case['wrapper_va']:08x}: {case['argument_origins']}")
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
