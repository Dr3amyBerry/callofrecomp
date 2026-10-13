# Android performance profiles

Select the graphics profile in the launcher before starting the game. Choices
persist independently of campaign saves. Balanced is the default; Android devices
reporting low-RAM capability default to Light. All retain the 60 FPS ceiling.

| Profile | Maximum landscape render buffer | Graphics tradeoff |
| --- | --- | --- |
| Balanced | 1280×720 | Reduced texture/LOD cost, dynamic lights and shadows off |
| Light | 960×540 | Further texture/LOD reduction, simple sky, detail textures off |
| High | Native viewport | Restores the profile-controlled visual settings |

Both render dimensions share a scale factor, rounded down to even pixels.
Wider phones retain their aspect ratio; smaller displays are not upscaled.
For a 1920×1080 viewport, Balanced rasterizes about 44% as many pixels and Light
25%. These are pixel counts, not measured FPS improvements.

The SurfaceView stays full size while its EGL backing buffer uses a fixed size,
through Android's [SurfaceHolder.setFixedSize API](https://developer.android.com/reference/android/view/SurfaceHolder#setFixedSize(int,%20int)).
The original engine receives those buffer dimensions and a matching custom
aspect/FOV. RetroTouch and menu overlays stay at view resolution; fallback SDL
touch coordinates are transformed from view pixels to buffer pixels. Changing
profiles requires restarting the game. The initial landscape view chooses the
buffer; live desktop-window resizing is not a dynamic-resolution system.

Android pacing sleeps during the final fractional interval to reduce polling.
Audio mixing evaluates its rate ratio once per voice per output buffer. Neither
change alters objective scripts or simulation timing. Automated budget tests and
build/regression checks do not establish performance or presentation on a real
phone; manual checks remain with the user in flash mode.
