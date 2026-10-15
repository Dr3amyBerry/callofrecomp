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
inside the Compass, Cursorhints, stance, tankstatus **and Health** menu
sections. The Health cross, backing strip and fill are compensated together,
without changing the health value. Vertical coordinates, textures, original
owner-draw callbacks, weapon displays, buttons, menus, controls and all
3D drawing remain intact. The compass layers, needle and pointer surfaces are
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
  posture/prompt icons, correctly aligned health bar, fail-closed unfamiliar
  HUD, ZIP indices containing duplicate entries, untouched source PK3
  and cleanup at 4:3.
- Full local regression: **94 Python unit tests passed (4 skipped), 26/26 CTest passed**, and the signed Android ARM64 APK installed and loaded the original saved training mission. The regular APK has **zero embedded commercial PK3/PE/DLL resources**.
- The pre-existing experimental CoDSP x87 fast path remains opt-in in
  the Android native build. This is a **visual correction**. No claim
  of increased FPS or achievement of the 60 FPS spawn target is made.

## Scope and limits

This fixes the identified square 2D HUD decorations and the health strip
without changing the ammo bars, menu backgrounds, fonts
or every original 2D effect. It has been validated on the installed
Spanish-language CoD 1.5 HUD; other radically changed modded HUD
scripts may be deliberately skipped. The renderer and original
custom-aspect camera remain unchanged.

**Outstanding separate performance goal:** 60 sustained FPS at the
initial spawn on the TECNO CK6n; the previously measured fast-path
improvement (21.45 → 25.65 FPS, +19.58%) is retained.

## Follow-up: dynamic friend, tank and objective markers (2026-10-14)

The prior aspect correction restored the circular compass artwork, but
green ally indicators could still extend beyond its edge. The original
cgamex86.dll version 1.5 computes pointer positions in native guest code
using a separate **43.75 virtual-unit radius**, not just ui/hud.menu.

Private P-code and Ghidra analysis identified the specific original callers
for friend pointers, tank markers, objective markers and objective pulses.
No proprietary guest modules, source dumps, original PK3 assets, P-code
records or address sidecars are committed.

**New implementation:** tools/recomp/runtime/compass_markers.h provides
pure layout math and strict argument validation. The Android-only path in
tools/recomp/runtime/guest.c adjusts temporary render-call arguments only
for the verified original cgame pointer calls. android/native_host.c enables
this projection only when the matching generated HUD overlay exists and
the EGL surface is wider than 4:3.

The original virtual compass is 160x160. At 1280x576, its effective
horizontal factor is (4/3) / (1280/576) = **0.60**. Marker width and X
distance to the circle center are scaled consistently, retaining the
heading. A pointer placed exactly at the old 43.75-radius rim would have
part of its icon outside the circle. For markers that would extend
beyond the edge, the maximum center radius is bounded to
43.75 * HUD_zoom - marker_height/2 - 1.5. Inner markers keep their
original distance from the center and all retain their angular direction.

Only the compass's selected 2D sprite geometry is modified: the real
3D widescreen FOV, NPC and objective world coordinates, rotation, game
simulation, menus, health bars and original game assets remain intact.
In 4:3 or without the private overlay, the native hook does nothing.
Malformed/nonfinite marker geometry is rejected.

**Evidence, not assumptions:**

- TECNO CK6n physical Android ARM64 device: 1280x576 panorama with about
  108.87 degrees of horizontal FOV preserved.
- Native log shows marker correction actually activated for green friends
  and objective pulse in the saved training scene. Screenshots confirmed
  green markers remained inside the circular rim after radial limiting.
- Dynamic tank and main objective-star callsite support was added using
  source-verified addresses and synthetic geometry tests, but those
  specific mission contexts have **not** been visually exercised.
- **94 Python tests passed (4 skipped), 27/27 host CTest passed**, including
  the new compass_markers_smoke. Signed ARM64 APK installed successfully;
  earlier experimental x87 performance optimization was kept.
- 30 stable gameplay summary windows on the corrected build: median
  **25.75 FPS**, median **37.525 ms CPU/frame**. Earlier A/B/A x87 build
  yielded ~25.65 FPS. This does not establish a new FPS improvement;
  the **60 FPS sustained training-spawn target remains open**.

The previously installed APK was backed up privately before the tests.
No commercial resources or save games were published or replaced.

## Follow-up: health strip and genuinely round objective stars (2026-10-14)

The original Health menu defined a medical cross at 12×12, a backing
strip at 130×12 and a filled strip at 128×10, all in virtual 640×480.
In widescreen 1280×576, the renderer widened those horizontally by
2.0 while Y used 1.2. The newer Java HUD overlay scales the X offsets
and widths of **all three Health children**, retains their respective Y
and height, and moves the zero-width parent to keep the health strip's
original right edge at virtual X=631. Health percentages and owner-draw
logic are unchanged. For an unfamiliar custom Health layout, this specific
fix fails closed rather than corrupting an unrelated widget.

The gold ring and star were **not** fixed by the earlier marker hook.
Private original p-code shows that `0x3001ceda` is the return from the
preceding **0x4a color syscall**. The actual 0x4b objective sprite draw
is the CALLIND at guest `0x3001cf3a`, returning to `0x3001cf40`.
The cgame callback points into the original **recompiled CoDSP guest
motor**, not normally the host thunk dispatch, so the old thunk-only
hook did not fire. The corrected hook identifies that exact call at
the callback's entry, with guest return, opcode, loaded module and
widescreen overlay guards. It does not affect other HUD components.

Unlike ally and pulse draw helpers, the objective sprite's 0x4b call
already receives X/Y/width/height in **physical pixel units**. The
new `compass_marker_project_pixels()` restores 640×480 virtual units
using the cgame's own X/Y scale floats (2.0 and 1.2 on the TECNO),
performs the previous X-aspect and perimeter correction, and rescales
to pixels. Without this conversion, the sprite appears stretched even
when the compass backing is circular.

### Observed result

- Physical TECNO CK6n with previously saved training game: the direct
  star draw was logged, transforming **64.0×38.4 → 38.4×38.4**
  physical pixels; actual yellow-ring bounding box in the 2400×1080
  screen capture measured **29×29 pixels**. This validates roundness
  of the visible objective indicator, not merely mathematical tests.
- The right-side health bar appears shorter and proportionate, with
  medical cross and background aligned at the same right margin.
- Exact aspect 1280×576 and panoramic camera/FOV were unchanged.
- Regression completed: **94 Python unit tests passed (4 skipped)**,
  **27/27 CTest**; signed ARM64 Android APK installed. The previously
  working opt-in x87 path is still included; all proprietary game
  resources, profiles and APK backup remain local/ignored.
- The **60 FPS sustained training-spawn target remains open**.
  This HUD work was not a controlled FPS-optimization A/B/A trial.
  Dynamic tank markers and additional campaign scenarios remain
  separate visual-verification items.
