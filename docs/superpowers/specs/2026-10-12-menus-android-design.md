# Original menus and Android build

The user requests the original menus and an Android build after confirming PC
mission 1 and smooth aiming. Existing authorization covers implementation and
commit/push to main. WSA is connected at 127.0.0.1:58526, Android 13, and supports
arm64-v8a. No original assets or generated module sources enter Git or the APK.

Restore original cleanup callbacks needed to leave a mission, then verify the
original main menu, options, pause and return-to-menu paths in the desktop host.
Reuse the original UI module and PK3 menus rather than reconstructing their layout.

The Android APK contains SDL2, GL4ES and ARM64 versions of the four recompiled
modules. SDL creates a GLES2 context; GL4ES supplies desktop compatibility entry
points. Guest Win32 services continue to use the existing portable runtime.
The launcher imports user-owned original binaries and main/*.pk3 through Android's
folder picker into the app's writable storage, without broad storage permission.
Saved games and configuration occupy a separate writable profile directory.

Touch menus map absolute normalized coordinates to guest client coordinates.
An on-screen control overlay provides movement, look, attack, aim, reload, use,
jump, crouch and pause. A visible control-mode toggle permits original menus and
briefings to use direct touch. Touch input enters SDL's event queue; Android UI
threads never execute guest code. Mouse/keyboard desktop input remains supported.

Build using the installed NDK and SDK command-line tools. Dependencies are pinned
and fetched into ignored build directories. APK signing uses an ignored local
debug keystore. Record compilation, APK signature and native alignment checks,
then install and inspect startup, menus, input and logs on WSA. WSA validation
does not establish performance on a physical ARM64 phone.
