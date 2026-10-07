#!/usr/bin/env python3
"""Recover the legacy module dispatch/syscall ABI using narrow x86 patterns.

This is deliberately a *probe*, not a general x86 disassembler. It extracts two
high-value structures that are stable in the supplied CoD 1.5 modules:

1. vmMain's indexed jump table (``jmp [eax*4+table]``), and
2. syscall wrapper call sites that indirect through the callback installed by
   ``dllEntry``.

Every result is address-based evidence; semantic names are assigned separately.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from pe_inspect import PEFile, PEFormatError


def _read_u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def find_export(pe: PEFile, name: str) -> dict:
    for item in pe.exports():
        if item.get("name") == name:
            return item
    raise PEFormatError(f"required export {name!r} not found")


def recover_dllentry_callback(pe: PEFile) -> dict:
    exp = find_export(pe, "dllEntry")
    off = pe.rva_to_offset(exp["rva"])
    window = pe.data[off:off + 32]

    # Supplied modules use MOV moffs32,EAX (A3 <abs32>) after loading arg0.
    idx = window.find(b"\xA3")
    if idx < 0 or idx + 5 > len(window):
        raise PEFormatError("dllEntry callback store (A3 <abs32>) not found")
    callback_va = _read_u32(window, idx + 1)
    callback_rva = callback_va - pe.image_base
    return {
        "dllentry_rva": exp["rva"],
        "dllentry_va": exp["va"],
        "callback_slot_va": callback_va,
        "callback_slot_rva": callback_rva,
    }


def _find_dispatch_limit(prefix: bytes) -> int | None:
    # Prefer the last CMP EAX,imm8 before the indirect jump.
    last = None
    for i in range(max(0, len(prefix) - 32), len(prefix) - 2):
        if prefix[i:i + 2] == b"\x83\xF8":
            last = prefix[i + 2]
    if last is not None:
        return last
    # Alternate encoding CMP EAX,imm32.
    for i in range(max(0, len(prefix) - 32), len(prefix) - 4):
        if prefix[i] == 0x3D:
            last = _read_u32(prefix, i + 1)
    return last


def recover_vm_dispatch(pe: PEFile) -> dict:
    exp = find_export(pe, "vmMain")
    off = pe.rva_to_offset(exp["rva"])
    window = pe.data[off:off + 128]

    # FF 24 85 imm32 == jmp dword ptr [eax*4 + imm32]
    marker = b"\xFF\x24\x85"
    j = window.find(marker)
    if j < 0 or j + 7 > len(window):
        raise PEFormatError("vmMain indexed jump table pattern not found")
    table_va = _read_u32(window, j + 3)
    table_rva = table_va - pe.image_base
    max_command = _find_dispatch_limit(window[:j])
    if max_command is None or max_command > 4096:
        raise PEFormatError("vmMain command upper bound not found")

    table_off = pe.rva_to_offset(table_rva)
    entries = []
    for command in range(max_command + 1):
        target_va = _read_u32(pe.data, table_off + command * 4)
        target_rva = target_va - pe.image_base
        entries.append({
            "command": command,
            "target_va": target_va,
            "target_rva": target_rva,
        })
    return {
        "vmmain_rva": exp["rva"],
        "vmmain_va": exp["va"],
        "jump_table_va": table_va,
        "jump_table_rva": table_rva,
        "max_command": max_command,
        "entries": entries,
    }


def recover_syscall_sites(pe: PEFile, callback_slot_va: int, max_command_id: int = 1024) -> dict:
    # Find executable sections. IMAGE_SCN_MEM_EXECUTE = 0x20000000.
    sites = []
    call_pattern = b"\xFF\x15" + struct.pack("<I", callback_slot_va)

    for section in pe.sections:
        if not (section.characteristics & 0x20000000):
            continue
        raw = pe.data[section.raw_offset:section.raw_offset + section.raw_size]
        cursor = 0
        while True:
            idx = raw.find(call_pattern, cursor)
            if idx < 0:
                break
            call_file_off = section.raw_offset + idx
            call_rva = section.virtual_address + idx
            command = None
            command_encoding = None

            # The command is the argument pushed immediately before the indirect
            # call in these wrappers. Support PUSH imm8 and PUSH imm32.
            if idx >= 2 and raw[idx - 2] == 0x6A:
                imm = raw[idx - 1]
                command = imm if imm < 0x80 else imm - 0x100
                command_encoding = "push_imm8"
            elif idx >= 5 and raw[idx - 5] == 0x68:
                command = struct.unpack_from("<i", raw, idx - 4)[0]
                command_encoding = "push_imm32"

            if command is not None and not (0 <= command <= max_command_id):
                command = None
                command_encoding = None

            sites.append({
                "call_rva": call_rva,
                "call_va": pe.image_base + call_rva,
                "file_offset": call_file_off,
                "command": command,
                "command_encoding": command_encoding,
            })
            cursor = idx + len(call_pattern)

    commands: dict[int, list[int]] = {}
    unresolved = []
    for site in sites:
        if site["command"] is None:
            unresolved.append(site["call_rva"])
        else:
            commands.setdefault(site["command"], []).append(site["call_rva"])

    return {
        "indirect_call_count": len(sites),
        "resolved_command_count": len(commands),
        "max_command_id": max_command_id,
        "commands": [
            {"command": cmd, "call_rvas": rvas}
            for cmd, rvas in sorted(commands.items())
        ],
        "unresolved_call_rvas": unresolved,
        "sites": sites,
    }


def analyze(path: Path) -> dict:
    pe = PEFile(path)
    callback = recover_dllentry_callback(pe)
    dispatch = recover_vm_dispatch(pe)
    syscalls = recover_syscall_sites(pe, callback["callback_slot_va"])
    return {
        "name": path.name,
        "image_base": pe.image_base,
        "callback": callback,
        "vm_dispatch": dispatch,
        "syscalls": syscalls,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe CoD-style vmMain/dllEntry x86 module ABI")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    reports = []
    for path in args.files:
        try:
            report = analyze(path)
        except (OSError, PEFormatError, struct.error) as exc:
            parser.error(f"{path}: {exc}")
        reports.append(report)
        print(
            f"{path.name}: vm commands 0..{report['vm_dispatch']['max_command']} "
            f"({len(report['vm_dispatch']['entries'])} entries), "
            f"syscall commands recovered={report['syscalls']['resolved_command_count']} "
            f"from {report['syscalls']['indirect_call_count']} indirect calls"
        )

    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps({"schema_version": 1, "modules": reports}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
