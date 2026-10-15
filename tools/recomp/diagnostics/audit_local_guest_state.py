#!/usr/bin/env python3
"""Audit exact exported ELF symbol delta from the opt-in local guest state map.

For WSA/ARM64 local R/MEM/U/PC experiments: require those four global OBJECT
symbols to disappear from .dynsym and all other defined exports to retain
name/type/binding/visibility/size. Addresses may legitimately move at link.
No FPS, binary80 or guest-RAM equivalence is inferred from an ELF export audit.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess

GUEST_OBJECTS=frozenset(("R","MEM","U","PC"))
SYMBOL=re.compile(
    r"^\s*\d+:\s+[0-9a-fA-F]+\s+\d+\s+\w+\s+\w+\s+\w+\s+\S+\s+\S+")


class ExportAuditError(ValueError):
    pass


def parse_dynamic_exports(text: str) -> dict[str, tuple[str,str,str,int]]:
    found={}
    for line in text.splitlines():
        if not SYMBOL.match(line):
            continue
        parts=line.split(None,7)
        if len(parts)!=8:
            raise ExportAuditError("Malformed .dynsym line")
        index, addr, size, typ, binding, visibility, ndx, name=parts
        if ndx=="UND" or name=="":
            continue
        try:
            count=int(size)
        except ValueError as exc:
            raise ExportAuditError("Invalid dynsym size") from exc
        if name in found:
            raise ExportAuditError("Duplicate defined exported symbol: "+name)
        found[name]=(typ,binding,visibility,count)
    if not found:
        raise ExportAuditError("No defined exports found; expected Android libmain")
    return found


def compare_exports(a: dict, b: dict) -> dict:
    missing=sorted(set(a)-set(b))
    added=sorted(set(b)-set(a))
    modified=sorted(x for x in a.keys() & b.keys() if a[x]!=b[x])
    wrong_targets=sorted(x for x in GUEST_OBJECTS
                         if x not in a or a[x][0:3]!=("OBJECT","GLOBAL","DEFAULT"))
    extras=sorted(set(missing)-GUEST_OBJECTS)
    missing_targets=sorted(GUEST_OBJECTS-set(missing))
    verified=(not added and not modified and not wrong_targets and
              not extras and not missing_targets)
    return {
        "status":"pass" if verified else "fail",
        "baseline_defined_exports":len(a),
        "candidate_defined_exports":len(b),
        "expected_removed":sorted(GUEST_OBJECTS),
        "actually_removed":missing,
        "unexpected_removed":extras,
        "unexpected_added":added,
        "modified_export_contracts":modified,
        "missing_protected_removals":missing_targets,
        "invalid_baseline_guest_objects":wrong_targets,
        "unchanged_other_exports":len(set(a) & set(b))-len(modified),
        "warning":"Only the dynamic exported symbol ABI is audited, not guest behavior or FPS",
    }


def read_exports(readelf:Path, binary:Path)->dict:
    if not readelf.is_file() or not binary.is_file():
        raise ExportAuditError("readelf and both ELF files must exist")
    out=subprocess.run([str(readelf),"--dyn-syms","--wide",str(binary)],
                       capture_output=True,text=True,timeout=90,check=True)
    if "Symbol table '.dynsym'" not in out.stdout:
        raise ExportAuditError("Not a readable dynamic symbol table")
    return parse_dynamic_exports(out.stdout)


def main(argv=None)->int:
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--readelf",type=Path,required=True)
    ap.add_argument("--baseline",type=Path,required=True)
    ap.add_argument("--candidate",type=Path,required=True)
    args=ap.parse_args(argv)
    try:
        result=compare_exports(read_exports(args.readelf,args.baseline),
                               read_exports(args.readelf,args.candidate))
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0 if result["status"]=="pass" else 1
    except (OSError,subprocess.CalledProcessError,ExportAuditError) as exc:
        ap.exit(2,"LOCAL_GUEST_EXPORT_AUDIT_ERROR: "+str(exc)+"\n")


if __name__=="__main__":
    raise SystemExit(main())
