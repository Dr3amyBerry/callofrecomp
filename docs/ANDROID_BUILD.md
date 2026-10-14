# Android build

The Android host runs the four statically recompiled modules, SDL2 2.32.10 and
GL4ES. The launcher imports a user-provided Call of Duty 1.5 installation, then
starts the original game UI. Imported data lives in external app-specific storage;
writable profiles live in internal app storage. The APK contains no original PE/PK3 assets.

## Build prerequisites

- Export/generate all four private modules under `recomp_out` first (see
  `tools/recomp/build_engine.py` and the verified export-entry ledger).
- Python 3, Git, CMake/Ninja, JDK 17 or newer.
- Android SDK platform 35, current build-tools supporting `zipalign -P 16`, and
  an Android NDK with ARM64 support. Local development uses NDK 30.0.16248370.

```powershell
python tools/recomp/build_android.py --sdk "$env:ANDROID_HOME" --java "$env:JAVA_HOME" --jobs 2
```

The builder fetches the exact SDL2, GL4ES and RetroTouch revisions in its source,
builds ARM64 shared libraries for API 26+, compiles the SDL and application Java
sources, and produces `recomp_out/callofrecomp-arm64-debug.apk`. It checks the APK
signature and 16-KiB native-library ZIP alignment. Builds and the local debug
signing key remain ignored by Git. `--package-only` packages existing native
libraries without compiling them again. The debug APK is a private development
artifact, with a development signing certificate and a debuggable manifest.
`--abi x86_64` builds `recomp_out/callofrecomp-x86_64-debug.apk` for native WSA
testing. Both variants share the local signing key so reinstalling preserves data.
`--recomp-opt 0` is a slow diagnostic build; keep the default `1` for normal use.
The builder strips packaged copies while retaining generated-code line tables
and runtime debug information in the native build, and checks
both ELF LOAD segments and APK ZIP alignment at 16 KiB.

Regenerate private C with the current `pcode2c.py` to enable instruction-local
temporaries. It proves initialization through relative branches and loops before
using compact local byte storage; an unproven module is rejected.
`--global-temporaries` generates the previous form for diagnostic comparisons.
If unique inputs can cross instructions or modules, regenerate all linked modules
with that option; mixing global readers and local writers would lose their values.
The generator change does not optimize already generated C automatically.

For a diagnostic **private APK** (without altering the regular default),
build with `--gl-profile` and/or `--cpu-profile`:

```powershell
python tools/recomp/build_android.py --sdk "$env:ANDROID_HOME" --java "$env:JAVA_HOME" --gl-profile --cpu-profile
```

Both options are OFF unless explicitly given. They only change small runtime
sources, not the massive private recompilation units.

Guest OpenGL call diagnostics are **compiled out by default**. To test, configure
Android CMake with `-DCODRECOMP_GL_PROFILING=ON`, rebuild the native runtime,
and place a `gl_stats` marker alongside the existing `frame_stats` marker in
the app's private profile directory (`files/profile/gl_stats`). Every five
seconds the log prints `gl profile:` with counts of guest bridge draws, index
or vertex quantities, texture calls, buffer uploads and lock/unlock calls.
The counts are **not GLES draw calls, GPU time, bytes uploaded by GL4ES, or
CPU percentages**. Remove the marker for normal diagnostic APK play; ship
regular release builds with the CMake option OFF.

Sampled thread CPU diagnostics require configuring Android CMake with
`-DCODRECOMP_CPU_PROFILING=ON` and creating `files/profile/cpu_stats` inside the
app's private data. Normal builds compile out the sampling path. The log lists
chunk candidates every five seconds; timings include measurement overhead and
nested calls and must not be interpreted as precise CPU percentages.

SDL2: <https://github.com/libsdl-org/SDL> (zlib license).
GL4ES: <https://github.com/ptitSeb/gl4es> (MIT license).
RetroTouch: <https://github.com/Andiweli/RetroTouch> (MIT license), 1.0.0-beta.4
AAR at commit `cdc01db0a6d6f9acaef72d7c496f5929b1bc3b8b`. The builder uses its
classes.jar directly rather than copying the library implementation into the app.
The upstream licenses are retained in the local dependency source trees.

## Install and play

```powershell
adb connect 127.0.0.1:58526
adb -s 127.0.0.1:58526 install -r recomp_out/callofrecomp-x86_64-debug.apk
adb -s 127.0.0.1:58526 shell am start -n org.callofrecomp/.LauncherActivity
```

Use **Elegir carpeta del juego** to select the original PC installation root:
`CoDSP.exe`, `gamex86.dll`, `cgamex86.dll`, `uix86.dll`, and `main/*.pk3`.
Only those files are imported. Imports are staged before replacing the active
installation, so an incomplete import does not activate partial game data.
The four binary SHA-256 hashes must match `analysis/baselines/cod1_sp_pc_1_5.json`;
other executable/DLL versions are rejected. PK3 content may include localization.

**Jugar** starts the engine and its original campaign/options/load UI. Touch menus directly.
The initial language follows available imported localization packs, preferring the
device language when available; a Spanish-only installation starts in Spanish.
Use the x86-64 APK on WSA; use the ARM64 APK on an ARM64 Android phone.
For training, choose **Nueva Partida**, then **Regular** or **Novato**. The original
menu starts `training` (Campamento Toccoa), before the campaign missions.
Use **CONTROLES** after entering the level: left stick moves, drag the free area
to look, and the labelled buttons fire, aim, reload, use, jump, crouch and switch
weapon. TUMBARSE, INCL. IZQ./DER. and OBJETIVOS cover the training's remaining
keyboard actions, including the barbed-wire section. **OCULTAR** removes the
overlay so menus and briefings accept direct taps.
**MENÚ** sends Escape and hides the controls for the original pause menu. Tap
**Volver a la Partida**, then **CONTROLES**, to resume touch gameplay. RetroTouch's
settings icon opens its layout editor; SAVE retains position/size/opacity changes.
Touch cancellation, focus loss and backgrounding release held controls.
Menu taps first update the original UI cursor, then activate after a rendered
frame; this preserves the original engine's relative/recentered mouse behavior.
Keyboard/mouse input also passes through SDL.

**Ver registro** displays the last 32 KB of `profile/codrecomp.log` after exiting
the game. Profiles and saves are not replaced when importing installation data.

## Validation scope

WSA is a local Android test environment. It reports ARM64 compatibility, but
executes ARM64 libraries through its native bridge on this x86-64 PC. WSA tests
therefore do not establish performance on a physical ARM64 Android device.
The launcher, real SAF import, compatible-binary checks and signed ARM64 APK
installation have been exercised on WSA. The ARM64 engine reaches common
initialization and parses original menus but has not produced a first frame there;
Native x86-64 WSA now displays the original Spanish menus, opens Options by
direct touch, loads the original training briefing and enters the Camp Toccoa
3D world. Relative look, joystick movement and pause/hide have been exercised.
This verifies that native WSA path, not physical ARM64 performance or completion
of every training objective. ADB screencap may return black while WSA's desktop
window visibly renders; validation also used window captures.
ELF/ZIP alignment alone does not establish full 16-KiB host-page compatibility;
the guest memory allocator currently tracks and protects 4-KiB pages.

### Per-call GL4ES/GLES CPU timing (diagnostic APK only)

Build a private diagnostic APK using `python tools/recomp/build_android.py
--abi x86_64 --gl-time-profile` (or `--abi arm64-v8a`), then create the
`files/profile/gl_time` marker in the application's private files directory.
After restarting, the runtime prints one `gl cpu:` line approximately every
five seconds. It lists inclusive **thread CPU microseconds** and call counts
spent by the guest OpenGL bridge in draw functions, texture binding/upload,
array-pointer setup, lock/unlock, state changes and VBO handling.

This measures CPU time inside the host GL4ES/GLES entry points, **not GPU
execution time or time spent in the recompilated guest renderer itself**.
CPU microseconds across sampled function calls are normalized against the
number of native frames in each reporting window. Timer overhead distorts
instrumented FPS; use a noninstrumented APK for any A/B comparison.

Compile with `CODRECOMP_GL_TIMING=OFF` (default) for production. The marker
cannot activate any timing hooks in a normal APK, and no per-call clocks
or counters remain in release object code. This is independent of
`--gl-profile`, which only counts requested calls.
