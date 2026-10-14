#!/usr/bin/env python3
"""Read-only inventory/backup and later equality check for private WSA game saves.

Only accesses files/profile/main/save of the installed DEBUGGABLE test app.
Does NOT restore, delete, edit, or export any commercial game files into git.
Backups must stay under ignored .local/profiles and be kept private.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import subprocess
from pathlib import Path, PurePosixPath

SERIAL = "127.0.0.1:58526"
PACKAGE = "org.callofrecomp"
SAVE_ROOT = "files/profile/main/save"


class SaveGuardError(RuntimeError):
    pass


def adb_bytes(*args: str) -> bytes:
    result = subprocess.run(
        ["adb", "-s", SERIAL, *args], capture_output=True, timeout=45,
        check=False,
    )
    if result.returncode:
        raise SaveGuardError(
            f"ADB failed ({result.returncode}) for {args[:3]}: "
            + result.stderr.decode("utf-8", "replace")[:250])
    return result.stdout


def valid_save_path(path: str) -> str:
    if not path or "\x00" in path or "\r" in path or "\n" in path:
        raise SaveGuardError("Invalid save filename")
    raw = PurePosixPath(path)
    root = PurePosixPath(SAVE_ROOT)
    if raw.is_absolute() or ".." in raw.parts or posixpath.normpath(path) != path:
        raise SaveGuardError("Unexpected path or traversal")
    try:
        relative = raw.relative_to(root)
    except ValueError as ex:
        raise SaveGuardError("File is outside save folder") from ex
    if relative == PurePosixPath(".") or any(p.startswith(".") for p in relative.parts):
        raise SaveGuardError("Hidden or root save path not allowed")
    return relative.as_posix()


def collect_saves() -> dict[str, bytes]:
    abi = adb_bytes("shell", "getprop", "ro.product.cpu.abi").decode().strip()
    device = adb_bytes("shell", "getprop", "ro.product.device").decode().strip()
    if (abi, device) != ("x86_64", "windows_x86_64"):
        raise SaveGuardError("Only the audited WSA x86_64 may be inspected")
    listing = adb_bytes(
        "shell", "run-as", PACKAGE, "find", SAVE_ROOT, "-type", "f"
    ).decode("utf-8").splitlines()
    if not listing:
        raise SaveGuardError("No existing saves: refuse an empty backup")
    values = {}
    for path in listing:
        key = valid_save_path(path)
        if key in values:
            raise SaveGuardError("Duplicate save path")
        values[key] = adb_bytes("exec-out", "run-as", PACKAGE, "cat", path)
    return values


def manifest(saves: dict[str, bytes]) -> dict:
    return {"package": PACKAGE, "serial": SERIAL,
            "save_root": SAVE_ROOT,
            "files": {k: {"sha256": hashlib.sha256(v).hexdigest(),
                          "bytes": len(v)} for k, v in sorted(saves.items())}}


def private_output_dir(path: Path) -> None:
    # The program works only within ignored working-tree profiles.
    target = path.resolve()
    allowed = (Path.cwd() / ".local/profiles").resolve()
    if not target.is_relative_to(allowed) or target == allowed:
        raise SaveGuardError("Backup destination must be under ignored .local/profiles/")


def make_backup(folder: Path) -> dict:
    private_output_dir(folder)
    if folder.exists():
        raise SaveGuardError("Refusing to overwrite an existing backup directory")
    saves = collect_saves()
    folder.mkdir(parents=True, exist_ok=False)
    for name, content in saves.items():
        dest = folder / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    meta = manifest(saves)
    (folder / "manifest.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def verify_backup(folder: Path) -> dict:
    private_output_dir(folder)
    meta_path = folder / "manifest.json"
    if not meta_path.is_file():
        raise SaveGuardError("Missing immutable local backup manifest")
    expected = json.loads(meta_path.read_text(encoding="utf-8"))
    current = manifest(collect_saves())
    # Check that the local backup has not been changed too.
    for name, fingerprint in expected["files"].items():
        backup_file = folder / valid_save_path(SAVE_ROOT + "/" + name)
        if not backup_file.is_file():
            raise SaveGuardError("Missing backup file: " + name)
        b = backup_file.read_bytes()
        if (hashlib.sha256(b).hexdigest(), len(b)) != (
                fingerprint["sha256"], fingerprint["bytes"]):
            raise SaveGuardError("Local backup damaged: " + name)
    return {"unchanged": current == expected,
            "expected": expected["files"], "current": current["files"],
            "backup_intact": True, "automatic_restore_performed": False}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("operation", choices=("backup", "verify"))
    ap.add_argument("--dir", type=Path, required=True)
    args = ap.parse_args()
    try:
        result = (make_backup(args.dir) if args.operation == "backup"
                  else verify_backup(args.dir))
    except (OSError, ValueError, subprocess.TimeoutExpired, SaveGuardError) as ex:
        print(json.dumps({"error": str(ex)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if args.operation == "backup" or result["unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
