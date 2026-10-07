#!/usr/bin/env python3
"""Recover the engine <-> native VM boundary from CoDSP.exe.

The probe is intentionally address/evidence oriented. It does not assign
semantic names to command or syscall IDs. For a known binary baseline it:

* finds direct calls to the engine VM_Call wrapper,
* classifies calls by the VM handle loaded into EAX,
* recovers immediate command IDs when they are the final pushed argument, and
* recovers the jump table used by each module-to-engine syscall callback.

This lets later analysis map both sides of the ABI without guessing names.
"""
from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path


class PEFormatError(ValueError):
    pass


@dataclass(frozen=True)
class Section:
    name: str
    virtual_size: int
    virtual_address: int
    raw_size: int
    raw_offset: int
    characteristics: int

    def contains_rva(self, rva: int) -> bool:
        return self.virtual_address <= rva < self.virtual_address + max(
            self.virtual_size, self.raw_size
        )


class PEFile:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        self._parse_headers()

    def _u16(self, off: int) -> int:
        return struct.unpack_from("<H", self.data, off)[0]

    def _u32(self, off: int) -> int:
        return struct.unpack_from("<I", self.data, off)[0]

    def _parse_headers(self) -> None:
        if len(self.data) < 0x40 or self.data[:2] != b"MZ":
            raise PEFormatError("missing DOS MZ header")
        pe_off = self._u32(0x3C)
        if self.data[pe_off : pe_off + 4] != b"PE\0\0":
            raise PEFormatError("missing PE signature")

        coff = pe_off + 4
        section_count = self._u16(coff + 2)
        optional_size = self._u16(coff + 16)
        opt = coff + 20
        if self._u16(opt) != 0x10B:
            raise PEFormatError("engine VM probe currently supports PE32 only")

        self.image_base = self._u32(opt + 28)
        self.size_of_headers = self._u32(opt + 60)

        section_off = opt + optional_size
        self.sections: list[Section] = []
        for i in range(section_count):
            off = section_off + i * 40
            if off + 40 > len(self.data):
                raise PEFormatError("truncated section table")
            name = (
                self.data[off : off + 8]
                .split(b"\0", 1)[0]
                .decode("ascii", errors="replace")
            )
            virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
                "<IIII", self.data, off + 8
            )
            characteristics = self._u32(off + 36)
            self.sections.append(
                Section(
                    name,
                    virtual_size,
                    virtual_address,
                    raw_size,
                    raw_offset,
                    characteristics,
                )
            )

    def rva_to_offset(self, rva: int) -> int:
        if rva < self.size_of_headers:
            return rva
        for section in self.sections:
            if section.contains_rva(rva):
                delta = rva - section.virtual_address
                if delta >= section.raw_size:
                    raise PEFormatError(
                        f"RVA 0x{rva:x} points into unbacked virtual data"
                    )
                return section.raw_offset + delta
        raise PEFormatError(f"RVA 0x{rva:x} is not mapped")

    def va_to_offset(self, va: int) -> int:
        return self.rva_to_offset(va - self.image_base)

    def executable_sections(self) -> list[Section]:
        # IMAGE_SCN_MEM_EXECUTE
        return [s for s in self.sections if s.characteristics & 0x20000000]


def parse_named_addresses(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"expected name=address, got {value!r}")
        name, address = value.split("=", 1)
        out[name] = int(address, 0)
    return out


def find_direct_calls(pe: PEFile, target_va: int) -> list[tuple[int, int, int]]:
    """Return (file_offset, RVA, VA) for x86 E8 rel32 calls to target_va."""
    calls: list[tuple[int, int, int]] = []
    for section in pe.executable_sections():
        raw = pe.data[section.raw_offset : section.raw_offset + section.raw_size]
        for index in range(0, max(0, len(raw) - 5)):
            if raw[index] != 0xE8:
                continue
            rel = struct.unpack_from("<i", raw, index + 1)[0]
            call_rva = section.virtual_address + index
            call_va = pe.image_base + call_rva
            if call_va + 5 + rel == target_va:
                calls.append((section.raw_offset + index, call_rva, call_va))
    return calls


def recover_immediate_command(pe: PEFile, call_offset: int) -> tuple[int | None, str | None]:
    """Recover the final PUSH immediate immediately before VM_Call."""
    if call_offset >= 2 and pe.data[call_offset - 2] == 0x6A:
        return pe.data[call_offset - 1], "push_imm8"
    if call_offset >= 5 and pe.data[call_offset - 5] == 0x68:
        return struct.unpack_from("<I", pe.data, call_offset - 4)[0], "push_imm32"
    return None, None


def classify_vm_handle(
    pe: PEFile,
    call_offset: int,
    handle_slots: dict[str, int],
    window: int = 64,
) -> tuple[int | None, str | None, int | None]:
    """Find the nearest MOV EAX,[absolute] that references a known VM handle."""
    start = max(0, call_offset - window)
    data = pe.data[start:call_offset]
    candidates: list[tuple[int, str, int]] = []

    for name, slot_va in handle_slots.items():
        address = struct.pack("<I", slot_va)
        # A1 moffs32 and 8B 05 abs32 both load a dword into EAX.
        for pattern in (b"\xA1" + address, b"\x8B\x05" + address):
            index = data.rfind(pattern)
            if index >= 0:
                candidates.append((start + index, name, slot_va))

    if not candidates:
        return None, None, None
    return max(candidates, key=lambda item: item[0])


def recover_syscall_dispatch(pe: PEFile, callback_va: int) -> dict:
    """Recover CMP max + JMP [eax*4+table] dispatcher metadata."""
    callback_offset = pe.va_to_offset(callback_va)
    window = pe.data[callback_offset : callback_offset + 160]

    max_id: int | None = None
    for index in range(min(96, max(0, len(window) - 2))):
        if window[index : index + 2] == b"\x83\xF8":
            max_id = window[index + 2]
            break
        if window[index] == 0x3D and index + 5 <= len(window):
            max_id = struct.unpack_from("<I", window, index + 1)[0]
            break

    marker = b"\xFF\x24\x85"  # jmp dword ptr [eax*4 + imm32]
    jump_index = window.find(marker)
    if max_id is None or jump_index < 0 or jump_index + 7 > len(window):
        raise PEFormatError(
            f"indexed syscall dispatcher not found at VA 0x{callback_va:08x}"
        )

    table_va = struct.unpack_from("<I", window, jump_index + 3)[0]
    table_offset = pe.va_to_offset(table_va)
    targets = struct.unpack_from(
        "<" + "I" * (max_id + 1), pe.data, table_offset
    )

    entries = [
        {
            "id": syscall_id,
            "target_va": target_va,
            "target_rva": target_va - pe.image_base,
        }
        for syscall_id, target_va in enumerate(targets)
    ]

    return {
        "callback_va": callback_va,
        "callback_rva": callback_va - pe.image_base,
        "max_id": max_id,
        "entry_count": len(entries),
        "unique_target_count": len(set(targets)),
        "jump_table_va": table_va,
        "jump_table_rva": table_va - pe.image_base,
        "entries": entries,
    }


def analyze(
    path: Path,
    vm_call_va: int,
    handle_slots: dict[str, int],
    callbacks: dict[str, int],
) -> dict:
    pe = PEFile(path)
    calls = []

    for call_offset, call_rva, call_va in find_direct_calls(pe, vm_call_va):
        command, encoding = recover_immediate_command(pe, call_offset)
        handle_offset, module_name, handle_slot = classify_vm_handle(
            pe, call_offset, handle_slots
        )
        calls.append(
            {
                "call_va": call_va,
                "call_rva": call_rva,
                "module": module_name,
                "handle_slot_va": handle_slot,
                "command": command,
                "command_encoding": encoding,
                "handle_load_distance": (
                    None
                    if handle_offset is None
                    else call_offset - handle_offset
                ),
            }
        )

    summary = {}
    for module_name in handle_slots:
        module_calls = [c for c in calls if c["module"] == module_name]
        commands = sorted(
            {c["command"] for c in module_calls if c["command"] is not None}
        )
        summary[module_name] = {
            "call_count": len(module_calls),
            "commands": commands,
            "command_count": len(commands),
            "unresolved_command_calls": sum(
                c["command"] is None for c in module_calls
            ),
        }

    return {
        "binary": path.name,
        "image_base": pe.image_base,
        "vm_call_va": vm_call_va,
        "vm_call_rva": vm_call_va - pe.image_base,
        "handle_slots": handle_slots,
        "engine_to_module": {
            "calls": calls,
            "summary": summary,
        },
        "module_to_engine": {
            name: recover_syscall_dispatch(pe, callback_va)
            for name, callback_va in callbacks.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recover the native VM boundary from the Call of Duty engine"
    )
    parser.add_argument("exe", type=Path)
    parser.add_argument(
        "--vm-call-va",
        required=True,
        type=lambda value: int(value, 0),
        help="VA of the engine VM_Call wrapper",
    )
    parser.add_argument(
        "--handle",
        action="append",
        default=[],
        metavar="NAME=VA",
        help="known engine global containing a VM handle; repeatable",
    )
    parser.add_argument(
        "--callback",
        action="append",
        default=[],
        metavar="NAME=VA",
        help="known module-to-engine syscall callback; repeatable",
    )
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    try:
        handles = parse_named_addresses(args.handle)
        callbacks = parse_named_addresses(args.callback)
        report = analyze(args.exe, args.vm_call_va, handles, callbacks)
    except (OSError, ValueError, PEFormatError, struct.error) as exc:
        parser.error(str(exc))

    for name, data in report["engine_to_module"]["summary"].items():
        print(
            f"{name}: {data['call_count']} VM calls, "
            f"{data['command_count']} immediate command IDs "
            f"{data['commands']}"
        )

    for name, data in report["module_to_engine"].items():
        print(
            f"{name}: syscall dispatcher 0..{data['max_id']} "
            f"({data['entry_count']} entries, "
            f"{data['unique_target_count']} unique targets)"
        )

    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(
            json.dumps({"schema_version": 1, **report}, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
