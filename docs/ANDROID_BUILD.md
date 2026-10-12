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

The builder fetches the exact SDL2 and GL4ES revisions recorded in its source,
builds ARM64 shared libraries for API 26+, compiles the SDL and application Java
sources, and produces `recomp_out/callofrecomp-arm64-debug.apk`. It checks the APK
signature and 16-KiB native-library ZIP alignment. Builds and the local debug
signing key remain ignored by Git. `--package-only` packages existing native
libraries without compiling them again. The debug APK is a private development
artifact, with a development signing certificate and a debuggable manifest.
`--abi x86_64` builds `recomp_out/callofrecomp-x86_64-debug.apk` for native WSA
testing. Both variants share the local signing key so reinstalling preserves data.
`--recomp-opt 0` is a slow diagnostic build; keep the default `1` for normal use.
The builder strips packaged copies while retaining native-build symbols and checks
both ELF LOAD segments and APK ZIP alignment at 16 KiB.

SDL2: <https://github.com/libsdl-org/SDL> (zlib license).
GL4ES: <https://github.com/ptitSeb/gl4es> (MIT license).
The upstream licenses are retained in the local dependency source trees.

## Install and play

```powershell
adb connect 127.0.0.1:58526
adb -s 127.0.0.1:58526 install -r recomp_out/callofrecomp-arm64-debug.apk
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
Use **CONTROLES** after entering a mission: left stick moves, drag the free area
to look, and the labelled buttons fire, aim, reload, use, jump, crouch and switch
weapon. **MENÚ / PAUSA** sends Escape and returns to direct menu input.
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
Android gameplay is not yet verified. Native x86-64 comparison is in progress.
ELF/ZIP alignment alone does not establish full 16-KiB host-page compatibility;
the guest memory allocator currently tracks and protects 4-KiB pages.
