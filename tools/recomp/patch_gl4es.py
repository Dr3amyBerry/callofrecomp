#!/usr/bin/env python3
"""Apply the reviewed normalization patch to the pinned offline GL4ES checkout.

Only the exact upstream array.c or its exact patched form is accepted.
Other files are untouched. Revert using git apply --reverse with PATCH_FILE.
"""
import argparse
from pathlib import Path
import subprocess

PINNED_REVISION = 'ec16bedd8819c475326f4f1a3063772c6d986e06'
PATCH_FILE = Path(__file__).resolve().parent / 'patches/gl4es-array-normalization.patch'
TARGET = 'src/gl/array.c'


def git(root, *args, check=True, input=None):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, input=input)
    if check and result.returncode:
        raise RuntimeError(f'git {args[0]} failed: {result.stderr.decode(errors="replace").strip()}')
    return result


def optimized_source(source):
    for kind in ('us', 'ui'):
        anchor = f'    getminmax_indices_{kind}(indices, max, min, count);\n'.encode()
        if source.count(anchor) != 1:
            raise RuntimeError(f'Unexpected GL4ES normalization source ({kind})')
        source = source.replace(anchor, anchor + b'    if (count > 0 && *min == 0) return;\n')
    return source


def apply_patch(root):
    root = Path(root).resolve()
    revision = git(root, 'rev-parse', 'HEAD').stdout.decode().strip()
    if revision != PINNED_REVISION:
        raise RuntimeError(f'GL4ES HEAD must be {PINNED_REVISION}; found {revision}')
    original = git(root, 'show', f'HEAD:{TARGET}').stdout.replace(b'\r\n', b'\n')
    expected = optimized_source(original)
    raw = (root / TARGET).read_bytes()
    current = raw.replace(b'\r\n', b'\n')
    # Git for Windows may check out the upstream source and our patch as CRLF.
    # Match the target's line endings without changing its unrelated bytes.
    patch = PATCH_FILE.read_bytes().replace(b'\r\n', b'\n')
    if b'\r\n' in raw:
        patch = patch.replace(b'\n', b'\r\n')
    if current == expected:
        git(root, 'apply', '--reverse', '--check', '-', input=patch)
        return 'already applied'
    if current != original:
        raise RuntimeError('GL4ES array.c has unexpected changes; refusing to patch')
    git(root, 'apply', '--check', '-', input=patch)
    git(root, 'apply', '-', input=patch)
    actual = (root / TARGET).read_bytes().replace(b'\r\n', b'\n')
    if actual != expected:
        raise RuntimeError('GL4ES patch postcondition failed')
    git(root, 'apply', '--reverse', '--check', '-', input=patch)
    return 'applied'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path)
    args = parser.parse_args()
    try:
        print(f'GL4ES normalization patch: {apply_patch(args.checkout)}')
    except (RuntimeError, OSError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
