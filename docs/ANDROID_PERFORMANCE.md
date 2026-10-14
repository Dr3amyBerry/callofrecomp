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

## Native signed overflow and sign extension (2026-10-14)

Static p-code counts in the CoDSP renderer regions identify frequent
`INT_SCARRY`, `INT_SBORROW`, signed comparisons and `POPCOUNT`.
The signed-overflow helper now uses checked arithmetic
(`__builtin_add_overflow` / `__builtin_sub_overflow`) for native
1-, 2-, 4-, and 8-byte x86 widths, and defined unsigned sign-bit formulas
for other widths up to 16 bytes. This also fixes a demonstrated bug:
the previous signed-128-bit intermediate overflowed at width 16 and failed
a newly written correctness test.

The new host smoke test exhaustively checks 65,536 pairs at width one and
30,000 seeded random operand pairs for each width 1–16, plus edge cases,
against an independent wide reference. 23/23 CTest tests pass. The
Android AArch64 NDK compiler accepts the test source (not executed on a phone).

| Operation, Clang `-O1` | Previous ARM64 instructions | Updated |
| --- | ---: | ---: |
| 32-bit signed addition overflow | 3 | 3 |
| 32-bit signed subtraction overflow | 15 | 3 |
| 64-bit signed addition overflow | 11 | 3 |
| 64-bit signed subtraction overflow | 11 | 3 |

In a separate synthetic Windows host benchmark running four million combined
carry/borrow checks per trial, seven trials per width, the median execution
time was **26.826 → 12.421 ms at 32 bits** and
**27.672 → 12.213 ms at 64 bits** with identical checksums.
These are specific local-operation improvements, **not FPS, GPU, or
measured mobile performance**. The compiler already generated efficient
x86_64 instructions for normal 32-/64-bit sign-extension comparisons;
there is no independent sign-extension speed claim.

**Still to verify:** WSA's actual engine FPS / CPU per frame in the same saved
training scene, with profiling disabled, and the native ARM64 full library
build. Do not enable speculative GL4ES VBO modes or repartition generated
chunks on the basis of these microbenchmarks.

## WSA renderer GL bridge CPU timing (2026-10-14)

A separately compiled WSA x86_64 diagnostic APK, with
`CODRECOMP_GL_TIMING=ON` and the private `gl_time` marker, ran the
preserved Camp Toccoa training entrance in Balanced quality. Timings use
`CLOCK_THREAD_CPUTIME_ID` **only inside selected guest GL wrappers**
around GL4ES/GLES calls. A representative 272-native-frame reporting
window showed:

| Category | Inclusive CPU microseconds / 272 frames | Approx. CPU ms/frame |
| --- | ---: | ---: |
| DrawElements / DrawRangeElements / DrawArrays | 718,126 | **2.64** |
| GL render state changes | 27,934 | 0.103 |
| Vertex/color/normal/texture pointer setup | 24,080 | 0.089 |
| Bind / active texture calls | 11,881 | 0.044 |
| Lock/unlock arrays | 3,601 | 0.013 |
| Texture uploads and explicit guest buffers | 0 | 0 |

This sample had approximately 103 indexed draw requests per frame. The
instrumented engine-thread frame summary window median was around 18 ms.
Thus host draw calls are significant (~2.6 ms), but they do **not**
account for the rest of the engine's workload. That remainder contains
recompiled renderer, simulation, audio, event processing, and profiling
overhead: it is **incorrect** to assign all remaining time to the
renderer without additional native samples.

**Not measured:** real GPU execution time, wait on the GPU after submission,
internal GL4ES replays/draw call count, and actual ARM64 devices. Timer
overhead is nonzero, so instrumented FPS is not used for A/B evaluation.
No GL4ES VBO mode was enabled.

### Next targeted experiment: selective higher compiler optimization

The hottest previously sampled renderer guest chunks reside in the CoDSP
generated `p10` / `p11` translation units. The OFF-by-default Android
CMake option `CODRECOMP_RENDER_O2` / builder `--render-o2` tries
`-O2` only for these two sources, without changing source instructions,
drawing settings, shaders, or graphics buffers. Build both variants with
timing disabled, then compare the same WSA save and the same static view.
An older ARM64 `p10` compile produced about **4% more code bytes**
under `-O2`; this is **not evidence of faster execution**.

### WSA renderer p10/p11 selective -O2 A/B (2026-10-14)

Compiled a signed WSA x86_64 APK where only CoDSP p10/p11 use -O2
(Ninja compile flags checked); all other generated partitions still -O1.
Both A/B variants contain the same optimized signed-overflow arithmetic.
Used the same static saved Camp Toccoa training entrance, Balanced quality,
60 roughly one-second native engine summary windows for each, no profiling.

| Measure | Optimized arithmetic, normal -O1 | p10/p11 -O2 |
| --- | ---: | ---: |
| Median FPS across summary windows | 54.50 | 54.25 |
| Median engine thread CPU ms across windows | 17.75 | 17.79 |
| Median frame ms across windows | 18.36 | 18.43 |
| p95 of window-average frame ms | 19.52 | 19.871 |
| CL_InitCGame (one load each) | 6.75s | 6.76s |

No FPS benefit established. Keep selective O2 experimental and disabled by
default. These are NOT individual-frame percentiles or a real ARM64 result.

### WSA arithmetic hot-path A/B (2026-10-14)

Compared original normal APK vs optimized signed-overflow arithmetic:
60 roughly one-second summary windows, same save and Balanced quality.

| Measure | Previous APK | Optimized math |
| --- | ---: | ---: |
| Median FPS across summary windows | 54.55 | 54.50 |
| Median engine thread CPU ms | 17.70 | 17.75 |
| Median frame ms across windows | 18.335 | 18.360 |

No observable FPS benefit in this WSA scene, but the signed arithmetic
change is justified by operation-level microbenchmarks and a correctness
fix for 128-bit overflow. Tests were independent of visual output.

### ARM64 native normal build verification (2026-10-14)

Rebuilt Android AArch64 libmain.so from the updated C runtime with the
normal optimization and diagnostic configuration. The native library linked
successfully; ELF e_machine is EM_AARCH64 (183). Checked CMake cache flags:
CODRECOMP_GL_TIMING=OFF, CODRECOMP_GL_PROFILING=OFF,
CODRECOMP_CPU_PROFILING=OFF, and CODRECOMP_RENDER_O2=OFF.
Neither the GL CPU timing nor the GL guest-call profile format string is
present in the production native object. 24/24 host CTest cases pass.

A real ARM64 phone GPU and gameplay performance measurement is still
required. WSA x86_64 timing does not determine Mali/Adreno behavior.

## Original UI menu reload audit (2026-10-14)

The original engine's training transition performs a second renderer initialization
after `RE_Shutdown(0)` and `Hunk_Clear`, and then parses the UI menu files
again. This is **loading work**, not evidence that each menu is drawn twice
per gameplay frame. Two private WSA training logs independently show two
`R_Init` cycles and the **same 25 unique menu files parsed in both cycles**.
The reported menu-load groups sum to 951 + 1,040 ms in one capture and
1,496 + 1,516 ms in another. These are separate runs under different trial
conditions, so their totals must not be treated as controlled A/B speed gains.

Reproduce the noninvasive analysis on any existing local log:

```powershell
python tools/recomp/analyze_menu_reloads.py path/to/codrecomp.log --json
```

The tool groups `Parsing menu file` events per `R_Init`, totals only
`UI menu load time` markers associated with an actual parse group, and
counts repeated file paths between adjacent cycles. It never includes
private filenames or log content in its aggregate output. Synthetic Python
unit tests cover repeated reloads, orphan timing markers, and partial logs.

**Not fixed yet:** Skipping the second parse without proving allocator and
GL resource lifetime safety can create invalid pointers after `Hunk_Clear`.
Instrument/trace the original menu parser ownership and renderer resource
handles before attempting this; validate actual startup, level transition,
graphics restarts, menu interaction, and save reloads in isolated builds.
No renderer settings or stable APK behavior were changed by this audit.

### Follow-up: UI-module compiler experiment and CPU sampling

Controlled WSA startup tests (same installation and training transition)
measured two UI parse/reload passes per run. Aggregate engine-reported
menu loading time was **2,065 / 2,017 ms** using the normal `-O1` build,
versus **2,006 / 2,026 ms** using a private APK with **only the original
UI module** compiled with `-O2`. This is not a demonstrated improvement:
the small variation lies within the observed run-to-run spread, so the
experimental option was removed. All four runs reached `CL_InitCGame`
and parsed the same 25 menus in each initialization.

Separately, a guest-CPU-sampled run produced 2,435 ms total parse time;
the additional profiling overhead prevents direct comparison with normal
APKs. The top samples include generated engine chunks, so the cost
cannot safely be assigned entirely to UI-module compilation or filesystem
access. This does not demonstrate duplicate rendering per frame or an
in-game FPS improvement. The noninstrumented normal WSA APK and save were
restored.
