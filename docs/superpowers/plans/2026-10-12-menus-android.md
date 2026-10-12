# Menus and Android implementation plan

> Use superpowers:executing-plans to implement this plan task by task.

**Goal:** restore original menu transitions and produce an installable ARM64 APK.
**Architecture:** reuse original UI, SDL2 platform services and GL4ES desktop-GL
compatibility. A small Android launcher owns data import and touch controls.
**Tech stack:** C, Java, Android SDK/NDK, CMake, SDL2 2.32.10, pinned GL4ES.
**Spec:** ../specs/2026-10-12-menus-android-design.md

## Constraints and review focus

- Commit/push main after verified phases; original inputs/generated C stay ignored.
- APK includes no original PE files or PK3 data; require user-provided installation.
- Input from UI threads is queued, never calls guest code; release controls on cancel.
- Separate imported files from saves; incomplete imports must not enable play.
- Check real WSA execution and state limitations of WSA's ARM64 translation.

## Tasks

- [x] Recover cleanup entry 0x0047EEE0 through the existing verified-entry exporter;
  regenerate private C, rebuild changed objects and exercise menu transitions.
- [x] Add an Android CMake host for all four modules, SDL2 and GL4ES; cross-compile
  real ARM64 shared libraries, keeping dependency sources outside the tracked tree.
- [x] Implement Android launcher/import, SDL activity and cancellable touch input.
  Add synthetic input tests for absolute menu positions and held-button release.
- [x] Add a reproducible SDK packaging/signing script and build the APK. Verify
  ARM64 ELF entries, APK signature and alignment with installed SDK tools.
- [x] Install on WSA, supply private original files, capture logs/screenshots and
  exercise original menus and mission loading. Resolve observed failures.
- [x] Run desktop regressions, update verified progress, commit/push and check CI.

## Execution record

- Cleanup additionally required the original audio shutdown thunk 0x0051A430
  and two registered RET destructors 0x00532010/20. Export: 333,208 instructions;
  actual desktop common/menu initialization and Quit exit 0.
- Input normalization and a 400-event burst have regression coverage; 12/12
  CTests pass. Commit 11c3133, GitHub CI 38271741631 success.
- Reviewer caught SDL's implicit argv[0], incompatible imports and launcher
  rotation during import. Arguments now start at installation path; SHA-256
  checks reject wrong binaries and accept the private baseline; launcher handles
  configuration changes without starting a second worker.
- Local SDK packaging is used to avoid unnecessary Gradle/AGP dependencies.
  WSA is verified as the Microsoft process serving the local loopback endpoint;
  private installation data transfer completed after destination verification.
- Shutdown sources were promoted after the initial compile and the changed ARM64
  objects rebuilt. APK signature, ELF/ZIP alignment and WSA installation pass.
- Real WSA SAF import passes baseline validation. ARM64 reaches common init but
  has no first frame; native x86-64 optimized comparison is in progress. Removing
  outlined SDL atomics did not resolve this, so the experiment was removed.
- Native x86-64 reaches the visible original Spanish menu and original Camp
  Toccoa training. Verified Options/back/new-game direct touches, training load,
  joystick/look, and pause with controls hidden. ARM64 phone testing remains open.
- User selected RetroTouch's FPS controls. Integrated the actual pinned AAR with
  a CoD-owned bridge and independent show/hide toggle. Added Java cancellation
  and stick-direction regressions to CI; batched absolute movement has a tested
  red/green regression in the runtime smoke. Windows menu +quit still exits 0.
- Commit 18efb50 pushed to main; GitHub CI 38303531640 passed, including the new
  Java touch tests. Follow-up training inspection identified required prone/lean
  controls; added these and objectives, with a separate red/green input test and
  both ABI packages rebuilt. Native WSA final gameplay is the device checkpoint;
  a physical ARM64 run and completing every training objective remain open.
