#!/usr/bin/env sh
# End-to-end static recompilation check for one original SP module:
#   Ghidra p-code export -> pcode2c.py -> clang -> run -> diff against the real DLL.
# Usage: GHIDRA_HOME=... tools/recomp/run_module.sh <originals_dir> <module> [out_dir]
# Needs a Ghidra project containing <module>.dll (created by tools/ghidra_decompile.sh),
# a 64-bit clang and an i686-w64-mingw32 clang for the native reference host.
set -eu
: "${GHIDRA_HOME:?set GHIDRA_HOME}"
ORIG="$1"; M="$2"; OUT="${3:-recomp_out}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
HEADLESS="$GHIDRA_HOME/support/analyzeHeadless"
[ -x "$HEADLESS" ] || HEADLESS="$GHIDRA_HOME/support/analyzeHeadless.bat"

"$HEADLESS" "$ROOT/ghidra_projects" codrecomp -process "$M.dll" -noanalysis \
  -scriptPath "$ROOT/tools/ghidra" -postScript ExportPcode.java "$OUT/$M.pcode" | grep "codrecomp:"
python "$ROOT/tools/recomp/pcode2c.py" "$OUT/$M.pcode" "$ORIG/$M.dll" -o "$OUT/${M}_recomp.c"
clang -O1 -w -I"$ROOT/tools/recomp" -c "$OUT/${M}_recomp.c" -o "$OUT/${M}_recomp.o"
clang -O1 -w -I"$ROOT/tools/recomp" -o "$OUT/${M}_host.exe" "$ROOT/tools/recomp/recomp_host.c" "$OUT/${M}_recomp.o"
i686-w64-mingw32-clang -O1 -I"$ROOT/tools/recomp" -o "$OUT/native_host.exe" "$ROOT/tools/recomp/native_host.c"

"$OUT/native_host.exe" "$ORIG/$M.dll" > "$OUT/$M.native.trace" || true
"$OUT/${M}_host.exe" "$ORIG/$M.dll" > "$OUT/$M.recomp.trace" || true
python "$ROOT/tools/recomp/compare_traces.py" "$OUT/$M.native.trace" "$OUT/$M.recomp.trace"
