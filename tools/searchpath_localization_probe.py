#!/usr/bin/env python3
"""Recover the CoD 1.5 SP localization table and linked-list node evidence.

Evidence is pinned to the original PE32 executable and SHA-256 fingerprints.
This is static analysis, not an executable compatible game filesystem.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from pe_inspect import PEFile, PEFormatError

BASELINE_SHA256 = "c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47"
LANGUAGE_TABLE_VA = 0x00564B08
LANGUAGE_TABLE_COUNT = 14
LANGUAGE_RECORD_BYTES = 8

# Reference points are matched by a strict binary fingerprint, not names alone.
EVIDENCE_REGIONS = (
    ("archive_classification", 0x00424BC0, 34,
     "14e4f51bc1efce63b13db0c372f297652484df44d6cc84e5e2afc83b7cb88795"),
    ("archive_node_creation", 0x00424D25, 77,
     "5bd04e1121de925d81b2ecaab58aece490d37276486e0abc5cac935c2c179ca4"),
    ("directory_node_creation", 0x00425029, 135,
     "99f01e527ccf63037a860c2348048e717b43d34077e0aa7acb5f842fb1d906ee"),
    ("directory_conflict_checks", 0x00424F25, 82,
     "1bd20f060293a90be12e10fd887cc420450d6e94586e6e78dcb1cb5587f8b1ba"),
    ("language_index_matching", 0x00424C02, 134,
     "15df6aad1c515b45566a45c7c4adc591f7dce8cda666bce4c531c7408efb7776"),
)

PREFIX_VAS = {
    "localized_prefix": 0x00558014,
    "sp_prefix": 0x00558024,
    "mp_prefix": 0x00558010,
    "zz_prefix": 0x0055800C,
}


def va_bytes(pe: PEFile, va: int, size: int) -> bytes:
    if size <= 0 or va < pe.image_base:
        raise PEFormatError("invalid virtual address window")
    offset = pe.rva_to_offset(va - pe.image_base)
    if offset + size > len(pe.data):
        raise PEFormatError("truncated virtual address window")
    return pe.data[offset:offset + size]


def languages_from_pe(pe: PEFile) -> list[dict]:
    result = []
    seen = set()
    for index in range(LANGUAGE_TABLE_COUNT):
        va = LANGUAGE_TABLE_VA + index * LANGUAGE_RECORD_BYTES
        string_va, trailing_dword = struct.unpack("<II", va_bytes(pe, va, 8))
        if string_va == 0 or trailing_dword != 0:
            raise PEFormatError(f"unexpected static language table slot {index}")
        label = pe.c_string_at_rva(string_va - pe.image_base, max_len=48)
        if not re.fullmatch(r"[a-z]{2,24}", label) or label in seen:
            raise PEFormatError(f"invalid/duplicate language label at slot {index}")
        seen.add(label)
        result.append({"index": index, "language": label, "string_va": f"0x{string_va:08X}"})
    return result


def classify_pkg_name(name: str, language_to_index: dict[str, int]) -> dict:
    """Candidate *filename* metadata only, not final FS mount priority."""
    basename = name.replace("\\", "/").split("/")[-1].lower()
    localized = re.fullmatch(r"localized_([a-z]+)_pak([0-9a-z]+)\.pk3", basename)
    if localized:
        language, suffix = localized.groups()
        if language in language_to_index:
            return {"name": name, "kind": "localized_candidate", "language": language,
                    "language_index": language_to_index[language], "pak_suffix": suffix}
        return {"name": name, "kind": "unknown_language_candidate", "language": language}
    ordinary = re.fullmatch(r"pak([0-9a-z]+)\.pk3", basename)
    if ordinary:
        return {"name": name, "kind": "plain_candidate", "pak_suffix": ordinary.group(1)}
    return {"name": name, "kind": "unclassified"}


def analyze(path: Path, names: list[str] | None = None) -> dict:
    pe = PEFile(path)
    digest = hashlib.sha256(pe.data).hexdigest()
    if digest != BASELINE_SHA256:
        raise PEFormatError("CoD PC 1.5 SP executable SHA-256 mismatch")
    languages = languages_from_pe(pe)
    prefix_values = {
        name: pe.c_string_at_rva(va - pe.image_base, max_len=32)
        for name, va in PREFIX_VAS.items()
    }
    if prefix_values != {
        "localized_prefix": "localized_", "sp_prefix": "sp_",
        "mp_prefix": "mp_", "zz_prefix": "zz_",
    }:
        raise PEFormatError("unexpected PK3 filename prefix constants")
    evidence = []
    for label, va, length, expected in EVIDENCE_REGIONS:
        actual = hashlib.sha256(va_bytes(pe, va, length)).hexdigest()
        if actual != expected:
            raise PEFormatError(f"function fingerprint mismatch: {label}")
        evidence.append({"label": label, "va": f"0x{va:08X}",
                         "bytes": length, "sha256": actual})
    language_to_index = {x["language"]: x["index"] for x in languages}
    return {
        "schema_version": 1,
        "binary": path.name,
        "sha256": digest,
        "language_table_va": f"0x{LANGUAGE_TABLE_VA:08X}",
        "language_count": len(languages),
        "languages": languages,
        "filename_prefixes": prefix_values,
        "searchpath_node": {
            "next_pointer_offset": 0,
            "package_object_pointer_offset": 4,
            "directory_object_pointer_offset": 8,
            "localized_flag_offset": 12,
            "language_index_offset": 16,
            "head_pointer_va": "0x013F9E3C",
            "node_size_bytes": 20,
            "confidence": "matched: constructor stores and localization diagnostics; no full mount priority claim",
        },
        "fingerprints": evidence,
        "filename_candidates": [classify_pkg_name(n, language_to_index) for n in (names or [])],
        "remaining_unknowns": [
            "runtime language selection and fallbacks",
            "complete directory/PK3 startup ordering and loose-file precedence",
            "exact prefix handling for multiplayer vs single-player patch assets",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path, help="original CoD 1.5 single-player PE")
    parser.add_argument("--pk3-name", action="append", default=[], help="an installed PK3 basename; may repeat")
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()
    try:
        report = analyze(args.exe, args.pk3_name)
    except (OSError, ValueError, struct.error) as exc:
        parser.error(str(exc))
    output = json.dumps(report, indent=2) + "\n"
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
