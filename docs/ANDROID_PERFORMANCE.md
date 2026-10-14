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

## WSA x86_64 A/B and writable overlay microbenchmark (2026-10-13)

Recompiled `9147588` as an x86_64 WSA APK from an isolated, clean worktree.
The comparison used the same imported installation and saved training mission
at Camp Toccoa, the same view and Balanced graphics settings. For each APK,
we captured **60 one-second `frame stats:` summary windows** after
`CL_InitCGame`, without touching the controls during collection.

| Engine measure | Previous WSA APK | `9147588` |
| --- | ---: | ---: |
| Median FPS across summary windows | 54.5 | 54.5 |
| Median per-window averaged frame time | 18.36 ms | 18.34 ms |
| p95 of per-window averaged frame time | 20.187 ms | 20.119 ms |
| Median thread CPU time per-window average | 17.920 ms | 17.855 ms |
| `CL_InitCGame` (one load only) | 7.07 s | 6.71 s |

These are **percentiles of one-second averages**, not frame percentiles.
No significant FPS benefit was demonstrated for the GL pointer bridge fix or
the binary-search OpenGL name lookup on this scene. The initial 44.3 FPS
reference was measured elsewhere in the level and cannot be compared.

The writable overlay's first-write path previously called `fgetc/fputc` once
per byte to copy an original file. The buffered replacement uses a 16-KiB
scratch array and rejects/removes partial copies on read/write/close errors.
A synthetic 16-MiB Windows host microbenchmark (five alternating trials per
implementation, high-resolution wall timer) measured **291.540 ms median**
byte-by-byte versus **11.919 ms median** buffered (24.46x). This applies
only to this copying operation, **not** general map loading, game FPS or
Android device storage performance. The original immutable PK3 files are read
via the separate existing path.

WSA exposes x86_64 and a Windows-provided OpenGL ES translator. Real ARM64
GPU/driver results must be measured separately before shipping a performance
claim or enabling additional guest OpenGL extensions.

## Opt-in GL call accounting in a WSA training scene

Using the diagnostic x86_64 APK built with CODRECOMP_GL_PROFILING=ON and the
private gl_stats marker, one stable five-second interval of the Camp Toccoa
entrance rendered **274 frames**. The game's requests to the OpenGL bridge were:

| Operation | Five-second window | Average per native frame |
| --- | ---: | ---: |
| glDrawElements | 9,590 | 35 |
| glDrawRangeElements | 18,632 | 68 |
| All indexed draws | 28,222 | 103 |
| glBindTexture | 31,784 | 116 |
| glActiveTexture / glActiveTextureARB | 11,234 | 41 |
| glLockArrays / glUnlockArrays pairs | 8,494 | 31 |
| Requested index count | 42,018,996 | 153,354 |
| Guest glBindBufferARB operations | 0 | 0 |

These are **guest bridge invocation counts**, not GLES-level draw counts, time
spent in GL4ES, GPU time or triangle counts. No guest VBO use was observed in
this interval; GL4ES can independently use internal VBOs. The large number of
indexed draws and locks makes GL4ES array-conversion and batch handling a
priority for controlled tests. The profiling build is not the normal APK.

## A/B de GL4ES con VBO interno modo 2 y modo 3 en WSA (2026-10-13)

Tras medir 103 llamadas indexadas del motor y 31 pares glLockArrays /
glUnlockArrays por cuadro, se probaron de manera aislada dos ajustes
opcionales de GL4ES: LIBGL_USEVBO=2 y LIBGL_USEVBO=3. Cada APK se compiló en
un worktree de experimentación, sin alterar el código publicado. El punto
fue el mismo training guardado, vista inicial estática y perfil Equilibrado.

| Métrica (60 ventanas de un segundo) | VBO normal 1 | VBO 3 | VBO 2 |
| --- | ---: | ---: | ---: |
| Mediana FPS de promedios por ventana | 54.50 | 51.55 | 49.25 |
| Mediana tiempo medio del cuadro | 18.34 ms | 19.39 ms | 20.305 ms |
| Mediana CPU de hilo | 17.855 ms | 19.35 ms | 20.29 ms |
| FPS respecto al normal | referencia | -5.4% | -9.6% |

Los resultados son de UNA ejecución por variante (60 ventanas por
ejecución): una regresión reproducible en esa escena, no una conclusión
universal sobre todos los dispositivos. Ambos modos mostraron visualmente
la misma escena inicial, pero eso no es validación exhaustiva gráfica ni
de jugabilidad. No se introduce ninguno en main. La APK normal se reinstaló,
su SHA-256 se comparó con la copia sin instrumentación y se confirmó que no
incluye la variable experimental LIBGL_USEVBO. Se conservaron los guardados.

Próxima hipótesis: medir trabajo real dentro de GL4ES (transformaciones,
copias de índices y llamadas a GLES) para reducir el coste de la vía
actual sin exponer extensiones guest que puedan cambiar el render.

## Guest dispatcher: adjacent-page fast path (2026-10-14)

The dispatcher index stores the last recompiled chunk intersecting each 4-KiB
page. An exact-range check for the previous chunk now precedes the binary-search
fallback. It avoids a binary search for a frequent shared-page case while
retaining the original lookup for gaps, three-or-more shared chunks, and
other addresses. The smoke fixture checks hundreds of colliding boundaries,
page holes, high addresses, and rebuild/unload behavior.

A Windows x86_64 synthetic microbenchmark of 32,768,000 lookups over 512
adjacent chunks reported roughly **152 ms before versus 41 ms after** in seven
runs per method, with the same checksum. This is an optimization of that
lookup operation, **not a demonstrated FPS improvement**. In a separate
60-window WSA comparison at the training entrance, median FPS was 52.7 before
and 52.15 after; the differences are too small and noisy to claim a frame-rate
benefit. We retain the narrowly beneficial hot path without changing GL4ES,
game simulation, or the code-generator's default chunk partitioning.

The function-aligned chunks experiment compiled and loaded correctly, but
measured 52.1 FPS and 19.135 ms median engine thread time compared with 52.7 FPS
and 18.865 ms in the baseline. This experimental generator remains private
and is **not enabled by default**.
