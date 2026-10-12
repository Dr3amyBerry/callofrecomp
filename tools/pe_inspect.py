#!/usr/bin/env python3
"""Minimal dependency-free PE32 static inspector.

Designed for reproducible analysis of legacy Windows x86 executables used by the
recompilation project. It intentionally does not modify input files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

MACHINE_NAMES = {
    0x014C: "i386",
    0x8664: "amd64",
    0x01C0: "arm",
    0xAA64: "arm64",
}
SUBSYSTEM_NAMES = {
    1: "native",
    2: "windows_gui",
    3: "windows_cui",
    7: "posix_cui",
    9: "windows_ce_gui",
    10: "efi_application",
    14: "xbox",
}


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
        span = max(self.virtual_size, self.raw_size)
        return self.virtual_address <= rva < self.virtual_address + span


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
        if pe_off + 24 > len(self.data) or self.data[pe_off:pe_off + 4] != b"PE\0\0":
            raise PEFormatError("missing PE signature")

        coff = pe_off + 4
        self.machine = self._u16(coff)
        self.number_of_sections = self._u16(coff + 2)
        self.timestamp = self._u32(coff + 4)
        self.optional_size = self._u16(coff + 16)
        self.characteristics = self._u16(coff + 18)

        opt = coff + 20
        magic = self._u16(opt)
        if magic != 0x10B:
            raise PEFormatError(f"only PE32 is supported for now (magic=0x{magic:04x})")
        self.magic = magic
        self.entry_rva = self._u32(opt + 16)
        self.base_of_code = self._u32(opt + 20)
        self.base_of_data = self._u32(opt + 24)
        self.image_base = self._u32(opt + 28)
        self.section_alignment = self._u32(opt + 32)
        self.file_alignment = self._u32(opt + 36)
        self.size_of_image = self._u32(opt + 56)
        self.size_of_headers = self._u32(opt + 60)
        self.subsystem = self._u16(opt + 68)
        self.dll_characteristics = self._u16(opt + 70)
        self.number_of_rva_and_sizes = self._u32(opt + 92)

        dd = opt + 96
        self.data_directories: list[tuple[int, int]] = []
        for i in range(min(self.number_of_rva_and_sizes, 16)):
            rva, size = struct.unpack_from("<II", self.data, dd + i * 8)
            self.data_directories.append((rva, size))

        section_off = opt + self.optional_size
        self.sections: list[Section] = []
        for i in range(self.number_of_sections):
            off = section_off + i * 40
            if off + 40 > len(self.data):
                raise PEFormatError("truncated section table")
            name_raw, vsize, vaddr, raw_size, raw_off, _, _, _, _, chars = struct.unpack_from(
                "<8sIIIIIIHHI", self.data, off
            )
            name = name_raw.split(b"\0", 1)[0].decode("ascii", errors="replace")
            self.sections.append(Section(name, vsize, vaddr, raw_size, raw_off, chars))

    def rva_to_offset(self, rva: int) -> int:
        if rva < self.size_of_headers:
            return rva
        for section in self.sections:
            if section.contains_rva(rva):
                delta = rva - section.virtual_address
                if delta >= section.raw_size:
                    raise PEFormatError(f"RVA 0x{rva:x} points into unbacked virtual data")
                return section.raw_offset + delta
        raise PEFormatError(f"RVA 0x{rva:x} is not mapped by a section")

    def c_string_at_rva(self, rva: int, max_len: int = 4096) -> str:
        off = self.rva_to_offset(rva)
        end = self.data.find(b"\0", off, min(len(self.data), off + max_len))
        if end < 0:
            end = min(len(self.data), off + max_len)
        return self.data[off:end].decode("ascii", errors="replace")

    def _directory(self, index: int) -> tuple[int, int]:
        if index >= len(self.data_directories):
            return (0, 0)
        return self.data_directories[index]

    def imports(self) -> list[dict]:
        import_rva, import_size = self._directory(1)
        if not import_rva or not import_size:
            return []
        off = self.rva_to_offset(import_rva)
        result: list[dict] = []
        max_desc = max(1, import_size // 20 + 8)
        for _ in range(max_desc):
            if off + 20 > len(self.data):
                break
            original_first_thunk, ts, fwd, name_rva, first_thunk = struct.unpack_from("<IIIII", self.data, off)
            off += 20
            if not any((original_first_thunk, ts, fwd, name_rva, first_thunk)):
                break
            dll_name = self.c_string_at_rva(name_rva)
            thunk_rva = original_first_thunk or first_thunk
            functions = []
            try:
                thunk_off = self.rva_to_offset(thunk_rva)
                for idx in range(65536):
                    if thunk_off + idx * 4 + 4 > len(self.data):
                        break
                    value = self._u32(thunk_off + idx * 4)
                    if value == 0:
                        break
                    iat_rva = first_thunk + idx * 4
                    location = {
                        "iat_rva": iat_rva,
                        "iat_va": self.image_base + iat_rva,
                    }
                    if value & 0x80000000:
                        functions.append({"ordinal": value & 0xFFFF, **location})
                    else:
                        hint_name_off = self.rva_to_offset(value)
                        hint = self._u16(hint_name_off)
                        end = self.data.find(b"\0", hint_name_off + 2)
                        if end < 0:
                            break
                        name = self.data[hint_name_off + 2:end].decode("ascii", errors="replace")
                        functions.append({"name": name, "hint": hint, **location})
            except PEFormatError:
                pass
            result.append({
                "dll": dll_name,
                "lookup_table_rva": thunk_rva,
                "iat_rva": first_thunk,
                "iat_va": self.image_base + first_thunk,
                "functions": functions,
            })
        return result

    def exports(self) -> list[dict]:
        export_rva, export_size = self._directory(0)
        if not export_rva or not export_size:
            return []
        off = self.rva_to_offset(export_rva)
        if off + 40 > len(self.data):
            return []
        (
            _chars, _ts, _major, _minor, _name_rva, ordinal_base,
            num_functions, num_names, funcs_rva, names_rva, ordinals_rva,
        ) = struct.unpack_from("<IIHHIIIIIII", self.data, off)
        funcs_off = self.rva_to_offset(funcs_rva)
        names_off = self.rva_to_offset(names_rva)
        ords_off = self.rva_to_offset(ordinals_rva)
        names_by_index: dict[int, str] = {}
        for i in range(num_names):
            name_rva = self._u32(names_off + i * 4)
            function_index = self._u16(ords_off + i * 2)
            names_by_index[function_index] = self.c_string_at_rva(name_rva)
        exports = []
        for i in range(num_functions):
            function_rva = self._u32(funcs_off + i * 4)
            if function_rva == 0:
                continue
            exports.append({
                "ordinal": ordinal_base + i,
                "name": names_by_index.get(i),
                "rva": function_rva,
                "va": self.image_base + function_rva,
            })
        return exports

    def ascii_strings(self, min_length: int = 6) -> Iterable[tuple[int, str]]:
        start = None
        for i, b in enumerate(self.data):
            printable = 32 <= b <= 126 or b in (9,)
            if printable and start is None:
                start = i
            elif not printable and start is not None:
                if i - start >= min_length:
                    yield start, self.data[start:i].decode("ascii", errors="replace")
                start = None
        if start is not None and len(self.data) - start >= min_length:
            yield start, self.data[start:].decode("ascii", errors="replace")

    def report(self, string_min_length: int | None = None) -> dict:
        sha256 = hashlib.sha256(self.data).hexdigest()
        report = {
            "path": str(self.path),
            "name": self.path.name,
            "size_bytes": len(self.data),
            "sha256": sha256,
            "format": "PE32",
            "machine": {"value": self.machine, "name": MACHINE_NAMES.get(self.machine, "unknown")},
            "timestamp": {
                "unix": self.timestamp,
                "utc": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            },
            "characteristics": self.characteristics,
            "is_dll": bool(self.characteristics & 0x2000),
            "entry_point": {"rva": self.entry_rva, "va": self.image_base + self.entry_rva},
            "image_base": self.image_base,
            "size_of_image": self.size_of_image,
            "subsystem": {"value": self.subsystem, "name": SUBSYSTEM_NAMES.get(self.subsystem, "unknown")},
            "section_alignment": self.section_alignment,
            "file_alignment": self.file_alignment,
            "sections": [
                {
                    "name": s.name,
                    "virtual_address": s.virtual_address,
                    "virtual_size": s.virtual_size,
                    "raw_offset": s.raw_offset,
                    "raw_size": s.raw_size,
                    "characteristics": s.characteristics,
                }
                for s in self.sections
            ],
            "imports": self.imports(),
            "exports": self.exports(),
        }
        if string_min_length is not None:
            strings = list(self.ascii_strings(string_min_length))
            report["ascii_strings"] = [{"file_offset": off, "value": value} for off, value in strings]
        return report


def compact_text(report: dict) -> str:
    lines = [
        f"{report['name']}: {report['format']} {report['machine']['name']}",
        f"  size: {report['size_bytes']} bytes",
        f"  sha256: {report['sha256']}",
        f"  timestamp: {report['timestamp']['utc']}",
        f"  image base: 0x{report['image_base']:08x}",
        f"  entry: RVA 0x{report['entry_point']['rva']:08x} / VA 0x{report['entry_point']['va']:08x}",
        f"  subsystem: {report['subsystem']['name']}",
        "  sections: " + ", ".join(s["name"] for s in report["sections"]),
    ]
    if report["exports"]:
        lines.append("  exports: " + ", ".join(e["name"] or f"ord{e['ordinal']}" for e in report["exports"]))
    lines.append("  imports:")
    for item in report["imports"]:
        lines.append(f"    - {item['dll']}: {len(item['functions'])} symbols")
    return "\n".join(lines)



def default_objdump() -> str:
    """Return a runnable objdump: $CODRECOMP_OBJDUMP, GNU objdump, then llvm-objdump.

    On Windows, extension-less wrapper scripts (e.g. llvm-mingw's ``objdump``)
    are found by ``shutil.which`` but cannot be spawned by ``subprocess``.
    """
    import os
    import shutil
    if os.getenv('CODRECOMP_OBJDUMP'):
        return os.environ['CODRECOMP_OBJDUMP']
    for name in ('objdump', 'llvm-objdump'):
        found = shutil.which(name)
        if found and (os.name != 'nt' or found.lower().endswith('.exe')):
            return found
    return 'objdump'

def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect legacy PE32 binaries without modifying them")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path, help="write full JSON report")
    parser.add_argument("--strings", type=int, metavar="MIN", help="include ASCII strings of at least MIN bytes in JSON")
    args = parser.parse_args()

    reports = []
    for path in args.files:
        try:
            report = PEFile(path).report(args.strings)
        except (OSError, PEFormatError, struct.error) as exc:
            parser.error(f"{path}: {exc}")
        reports.append(report)
        print(compact_text(report))

    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps({"schema_version": 1, "binaries": reports}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
