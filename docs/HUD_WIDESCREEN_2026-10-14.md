# Native panoramic camera with aspect-correct HUD (2026-10-14)

## Problem and confirmed baseline

The Android port's **3D projection is already genuine widescreen**, rather
than stretching a 4:3 screenshot. The original camera's 80° horizontal
field of view in 4:3 is converted to the device's actual viewport ratio
so the vertical view stays constant and the player sees more world left
and right. The original `r_customaspect`, `cg_fov` and custom dimensions
remain in use, without changes to the renderer's 3D projection.

On the physical TECNO CK6n / balanced graphics setting, the native log
confirmed approximately 1280×574 (ratio 2.22997) and horizontal
FOV 109.055°. After the automatic fix was installed the buffer was
1280×576 (ratio 2.22222) with horizontal FOV 108.867°.
The small buffer difference reflects Android layout dimensions, not a
change from native widescreen to stretched 4:3.

The **2D HUD** was different: the original `ui/hud.menu` places a 160×160
compass in virtual 640×480 units, and the wide viewport expands X more
than Y. As a result the compass, despite representing a circular asset,
appeared as a wide ellipse. Certain other 40×40 HUD icons suffered the
same issue.

## Implemented fix

`android/java/org/callofrecomp/HudWidescreen.java` runs during
`GameActivity.getArguments()`, before CoD's original file-system initializes.
It locates the **user's own installed** `ui/hud.menu` from a private PK3 and
generates a tiny overlay PK3 at:

`<app internal files>/profile/main/zzzz_codrecomp_hud_fix.pk3`

The patch changes only the relevant horizontal coordinates and sizes
inside the Compass, Cursorhints, stance and tankstatus menu sections.
Vertical coordinates, textures, ownermade HUD callbacks, health bars,
weapon displays, buttons, menus, control coordinates and all 3D drawing
remain intact. The compass layers, needle and pointer surfaces are
adjusted as one unit, preserving their alignment.

The formula is:

```text
horizontal_factor = (4/3) / (egl_width / egl_height)
corrected_width = original_virtual_width * horizontal_factor
corrected_x = original_x + (original_virtual_width - corrected_width) / 2
```

This centers each originally square decoration at its prior virtual
location while restoring a 1:1 physical pixel aspect. The compass
needle's local X offset and width are also corrected. At a 1280×576
buffer, the compass virtual width becomes 96 (from 160), with height
unchanged at 160. This yields a circular physical shape.

**Original installation and saves are untouched.** No commercial PK3,
HUD script, bitmap, executable, generated game code or private profile
is stored in Git or inside the public APK. The generated override is
replaced atomically on launch when the device/profile dimensions change
and removed if the viewport is 4:3 or the installed HUD layout is
unrecognized. When the source is absent, normal gameplay proceeds with
its original HUD.

## Compatibility with the original PK3 format

Android's standard `ZipFile` rejects some original 2003 ZIP indices
because of duplicate directory records (reproduced on the TECNO).
To avoid scanning or unpacking large archives, the patch reads just
the requested entry using a guarded ZIP32 central-directory reader.
It supports stored and raw-DEFLATE entries and checks entry bounds,
size caps, CRC32 and compression method. It skips malformed ZIP64 or
unsupported packages without rewriting them. A synthetic test uses
duplicated ZIP directory entries.

## Verification

- Real TECNO CK6n: manual private overlay loaded by FS_Startup, compass
  changed from an oval to a circular shape in the training scene while
  3D widescreen view and world proportions remained normal.
- Real TECNO CK6n: updated Android APK automatically generated its
  own 1.5-KiB private overlay from `localized_spanish_pak0.pk3`
  (**log: HUD aspect fix enabled at 1280x576**) after the manual overlay
  was explicitly removed. Native logs continued to report aspect and
  camera FOV correctly.
- Synthetic pure-Java ZIP/geometry tests verify 2.23:1 and 16:9
  compensation, all six compass layers, the compass needle, centered
  posture/prompt icons, untouched health bar, fail-closed unfamiliar
  HUD, ZIP indices containing duplicate entries, untouched source PK3
  and cleanup at 4:3.
- Full local regression: **94 Python unit tests passed (4 skipped), 26/26 CTest passed**, and the signed Android ARM64 APK installed and loaded the original saved training mission. The regular APK has **zero embedded commercial PK3/PE/DLL resources**.
- The pre-existing experimental CoDSP x87 fast path remains opt-in in
  the Android native build. This is a **visual correction**. No claim
  of increased FPS or achievement of the 60 FPS spawn target is made.

## Scope and limits

This fixes the identified square 2D HUD decorations without making
arbitrary changes to non-square life/ammo bars, menu backgrounds, fonts
or every original 2D effect. It has been validated on the installed
Spanish-language CoD 1.5 HUD; other radically changed modded HUD
scripts may be deliberately skipped. The renderer and original
custom-aspect camera remain unchanged.

**Outstanding separate performance goal:** 60 sustained FPS at the
initial spawn on the TECNO CK6n; the previously measured fast-path
improvement (21.45 → 25.65 FPS, +19.58%) is retained.
