#!/usr/bin/env python3
"""Save a real Android/WSA or Windows screenshot into a pre-created private run.

No hardcoded device serial, no base64 logs, no silent overwrite, no network.
Run: python tools/local_workspace.py new-run --target wsa --slug visual-check
Then: python tools/local_capture.py android --run .local/profiles/runs/... --serial SERIAL --name scene-a
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
try:
    from .local_workspace import ROOT, PROFILES, check_slug, safe_path
except ImportError:
    from local_workspace import ROOT, PROFILES, check_slug, safe_path


def capture_path(run: Path, name: str) -> Path:
    check_slug(name)
    if not run.is_dir() or not safe_path(run, PROFILES / "runs"):
        raise ValueError("The run must exist inside .local/profiles/runs/")
    if not (run / "session.json").is_file():
        raise ValueError("Run lacks session.json; create with tools/local_workspace.py")
    target = run / "captures" / (name + ".png")
    if not target.parent.is_dir() or target.is_symlink() or not safe_path(target, run):
        raise ValueError("Unsafe or missing captures folder")
    return target


def write_png(target: Path, content: bytes) -> None:
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Input is not a PNG capture")
    # Creation must fail instead of overwriting evidence in a concurrent run.
    with target.open("xb") as f:
        f.write(content)


def capture_android(serial: str, timeout: int = 30) -> bytes:
    if not serial or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", serial):
        raise ValueError("Explicit ADB serial required (run: adb devices)")
    cp = subprocess.run(["adb", "-s", serial, "exec-out", "screencap", "-p"],
                        timeout=timeout, capture_output=True, check=True)
    return cp.stdout


def capture_windows() -> bytes:
    if os.name != "nt":
        raise RuntimeError("Windows desktop capture requires a Windows session")
    from io import BytesIO
    try:
        from PIL import ImageGrab
    except ImportError as err:
        raise RuntimeError("Pillow is needed for Windows desktop capture") from err
    buf = BytesIO()
    ImageGrab.grab(all_screens=True).save(buf, format="PNG")
    return buf.getvalue()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", choices=("android", "windows"))
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--serial", help="Required for Android/WSA; never assume previous serial")
    args = p.parse_args(argv)
    try:
        output = capture_path(args.run, args.name)
        if output.exists():
            raise FileExistsError(output)
        if args.source == "android":
            data = capture_android(args.serial or "")
        else:
            if args.serial:
                raise ValueError("--serial only applies to Android")
            data = capture_windows()
        write_png(output, data)
        print(json.dumps({"path": output.relative_to(ROOT).as_posix(),
                          "bytes": len(data), "source": args.source}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
