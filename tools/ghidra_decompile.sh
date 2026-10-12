#!/usr/bin/env sh
# Batch-decompile the original SP binaries with Ghidra headless.
# Usage: GHIDRA_HOME=/path/to/ghidra tools/ghidra_decompile.sh <originals_dir> [out_dir] [binaries...]
# Output (decomp/ by default) is derived from proprietary code and is git-ignored.
set -eu

: "${GHIDRA_HOME:?set GHIDRA_HOME to the Ghidra install directory}"
ORIG="${1:?originals directory required}"
OUT="${2:-decomp}"
shift 2 2>/dev/null || shift $#
BINS="${*:-CoDSP.exe gamex86.dll cgamex86.dll uix86.dll}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJ="$ROOT/ghidra_projects"
mkdir -p "$PROJ" "$OUT"
OUT_ABS="$(cd "$OUT" && pwd)"

HEADLESS="$GHIDRA_HOME/support/analyzeHeadless"
[ -x "$HEADLESS" ] || HEADLESS="$GHIDRA_HOME/support/analyzeHeadless.bat"

for b in $BINS; do
  echo "== $b"
  "$HEADLESS" "$PROJ" codrecomp -overwrite \
    -import "$ORIG/$b" \
    -scriptPath "$ROOT/tools/ghidra" \
    -postScript ExportDecomp.java "$OUT_ABS" \
    -log "$OUT_ABS/$b.ghidra.log" 2>&1 | grep -E "codrecomp:|ERROR" || true
done
