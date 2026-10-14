#!/usr/bin/env bash
# Build the pinned upstream ANGLE Android debug-driver APK in an isolated Linux workspace.
# This does not install or enable ANGLE on any device.
set -euo pipefail

ANGLE_COMMIT="43140711d13063716fd32a15de829885d0bce469"
ANGLE_UPSTREAM="https://chromium.googlesource.com/angle/angle.git"
DEPOT_UPSTREAM="https://chromium.googlesource.com/chromium/tools/depot_tools.git"

if [[ "$(uname -s)" != Linux ]]; then
  echo "ERROR: ANGLE Android upstream requires a Linux build host" >&2
  exit 2
fi
for binary in git python3 bash; do
  command -v "$binary" >/dev/null || { echo "Missing: $binary" >&2; exit 2; }
done
WORK_ROOT="${1:?Pass a dedicated build directory OUTSIDE the game source tree}"
mkdir -p "$WORK_ROOT"
WORK_ROOT="$(cd "$WORK_ROOT" && pwd -P)"
if [[ -e "$WORK_ROOT/.gclient" && ! -f "$WORK_ROOT/.angle-pinned-build" ]]; then
  echo "Refusing to use an unrelated gclient workspace: $WORK_ROOT" >&2
  exit 2
fi
if [[ ! -f "$WORK_ROOT/.angle-pinned-build" ]]; then
  if [[ -n "$(ls -A "$WORK_ROOT")" ]]; then
    echo "Refusing to overwrite a nonempty workspace: $WORK_ROOT" >&2
    exit 2
  fi
  printf '%s\n' "$ANGLE_COMMIT" > "$WORK_ROOT/.angle-pinned-build"
fi
if [[ "$(cat "$WORK_ROOT/.angle-pinned-build")" != "$ANGLE_COMMIT" ]]; then
  echo "Pinned revision mismatch in build workspace" >&2
  exit 2
fi
cd "$WORK_ROOT"
if [[ ! -d depot_tools/.git ]]; then
  git clone --depth 1 "$DEPOT_UPSTREAM" depot_tools
fi
export PATH="$WORK_ROOT/depot_tools:$PATH"
# gclient and GN are supplied by depot_tools. No globally installed toolchain.
if [[ ! -f .gclient ]]; then
  gclient config --name angle "$ANGLE_UPSTREAM"
  printf "\ntarget_os = ['android']\n" >> .gclient
fi
gclient sync --revision "angle@$ANGLE_COMMIT" --nohooks
if [[ "$(git -C angle rev-parse HEAD)" != "$ANGLE_COMMIT" ]]; then
  echo "ANGLE checkout is NOT the requested commit" >&2
  exit 3
fi
git -C angle fsck --no-reflogs
# Install Linux build dependencies BEFORE running hooks that need them.
if [[ "${ANGLE_INSTALL_BUILD_DEPS:-0}" == 1 ]]; then
  command -v sudo >/dev/null || { echo "sudo missing for build dependencies" >&2; exit 2; }
  (cd angle && sudo ./build/install-build-deps.sh)
fi
# The upstream project fetches Android-specific build tools in its hooks.
gclient runhooks
cd angle
mkdir -p out/Android
cat > out/Android/args.gn <<'GN'
target_os = "android"
target_cpu = "x64"
arm_control_flow_integrity = "none"
angle_enable_vulkan = true
is_component_build = false
is_debug = false
angle_assert_always_on = false
use_remoteexec = false
GN
gn gen out/Android
autoninja -C out/Android angle_apks
APK="out/Android/apks/AngleLibraries.apk"
test -s "$APK" || { echo "ANGLE APK was not built" >&2; exit 4; }
python3 - "$APK" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    names = [n.lower() for n in z.namelist() if n.startswith("lib/x86_64/")]
    assert any("libegl" in n and n.endswith(".so") for n in names), "No x86_64 EGL library"
    assert any("libglesv2" in n and n.endswith(".so") for n in names), "No x86_64 GLESv2 library"
print("x86_64 EGL and GLESv2 ELF entries found; APK still requires signature and package verification.")
PY
(cd out/Android/apks && sha256sum AngleLibraries.apk > AngleLibraries.apk.sha256)
printf 'ANGLE_COMMIT=%s\n' "$ANGLE_COMMIT" > out/Android/apks/ANGLE_PROVENANCE.txt
printf 'ANGLE_TREE=%s\n' "$(git rev-parse HEAD^{tree})" >> out/Android/apks/ANGLE_PROVENANCE.txt
printf 'DEPOT_TOOLS_COMMIT=%s\n' "$(git -C "$WORK_ROOT/depot_tools" rev-parse HEAD)" >> out/Android/apks/ANGLE_PROVENANCE.txt
echo "Build complete. Verify signature/package and real Vulkan use before gameplay A/B."
echo "$WORK_ROOT/angle/$APK"
