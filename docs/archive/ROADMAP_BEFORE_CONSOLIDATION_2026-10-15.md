> HISTÓRICO: copia anterior a la consolidación del 2026-10-15. El estado y las prioridades vigentes están en [PROJECT_STATUS.md](../PROJECT_STATUS.md).

# Recompilation roadmap

## Scope

Initial milestone: boot the Call of Duty 1.5 single-player code path on Android ARM64 using original user-supplied game data externally. Multiplayer and United Offensive remain later milestones.

## Comprobación independiente del FCOMP x87 y restricciones (2026-10-14)

- [x] Comparados C0/C1/C2/C3 entre instrucciones x86 originales `FLD`+`FCOMP` en Unicorn y `codsp_fcom_pop_float32` experimental compilado solo en DLL host.
- [x] **1.037/1.037 coincidencias** de bits de condición con 13 casos especiales y 1.024 finitos reproducibles. Prueba negativa C0 falló correctamente, seis tests offline.
- [ ] Mantener **FCOM rápido OFF** hasta modelar TOP, palabra de estado/control, excepciones, NaN y todas las salidas observables, después comparar ARM64 real en TECNO. **0/5**. [Informe](../CPU_PHASE2_FCOM_CONDITION_ORACLE_2026-10-14.md).

## Equivalencia x87 inicial: cinco instrucciones de coma flotante (2026-10-14)

- [x] Oráculo x87 de salida: Unicorn ejecuta `fld/fsub/fmul/fsub/fstp` del CoDSP original frente al C traducido por el generador real.
- [x] **1.024/1.024 resultados de memoria float32 coincidentes**, stack/operandos/registros generales y PC conservados; falla intencional en byte de salida detectada. Cinco tests sintéticos.
- [ ] Expandir estado `binary80`, palabras de control/status y FCOM con NaN/excepciones antes de aceptar optimizaciones. No hay resultado de FPS ni intento TECNO: **0/5**. [Informe](../CPU_PHASE2_X87_WINDOW_ORACLE_2026-10-14.md).

## Oráculo diferencial x86 independiente: primer bloque finalizado (2026-10-14)

- [x] Implementar ejecutor Unicorn para **bytes auténticos x86**, confrontar con p-code traducido mediante `pcode2c.Gen` compilado a DLL (fuentes privados solo bajo `.local`). Entrada validada por hashes PE/p-code, Capstone, tamaño y destino real de la primera bifurcación.
- [x] **20 instrucciones** de `0x0041B8F0–0x0041B940` verificadas en **1.024 estados** con 512 salidas por cada ruta; registros, EFLAGS disponibles, memoria y PC equivalentes. Prueba negativa de rama corrupta rechazada.
- [ ] Fase siguiente: estados x87 reales y ventanas flotantes, CFG y aliasing, oráculo completo; solo luego valorar optimización ARM64 con diffs de código máquina y teléfono TECNO. **0/5**. [Informe](../CPU_PHASE2_X86_PREFIX_ORACLE_2026-10-14.md).

## Fase 2 estructural: diagnóstico de una función caliente de ARM64 (2026-10-14)

- [x] Delimitada función CoDSP `0x0041B8F0` con 553 instrucciones, dos rangos Ghidra y 3.957 p-code; 1.789 `COPY`, 187 `LOAD`, 67 `STORE`. Es parte del chunk 19 con 12 entradas y su perfil de 100 sitios nativos es solo parcial.
- [x] Añadida herramienta de auditoría con validaciones conservadoras, más CTest de **20.000 estados sintéticos x87 de 80 bits**: reemplazar copias `rd/wr` por `memcpy` no redujo las **29 instrucciones ARM64** a `-O1` ni a `-O2`. **No habilitar esta transformación**.
- [ ] Seguir con oráculo independiente de un único grupo caliente (CFG, registros, flags, x87, memoria), comprobar cambio `.text` real y solo después medir en TECNO con A/B/A/B/A. Estrategia y contador **0/5** intactos. [Informe completo](../CPU_PHASE2_41B8F0_AUDIT_2026-10-14.md).

## Resultado de la validación gráfica 3D en WSA y decisión (2026-10-14)

- [x] Ejecutado **A1/B/A2 en la misma partida de Camp Toccoa**. A1 GL4ES 54,75 FPS; B ANGLE/Vulkan 55,15 FPS; A2 GL4ES 55,20 FPS de mediana. El p10 de B (47,6 FPS) fue inferior al de ambas referencias A, sin prueba estadística de regresión concluyente.
- [x] Verificación del renderer en ambos extremos de B por PID+Logcat Vulkan; screenshot de mundo y HUD compatible visualmente, SSIM 0,995943 frente a GL4ES en región estática. Guardados y APK estables comprobados tras rollback.
- [x] Herramientas `wsa_save_guard.py`, `capture_wsa_game_frames.py --backend`, `summarize_wsa_driver_ab.py` y tests para reproducibilidad y detección de falsos positivos.
- [ ] **No adoptar ANGLE**: sin ganancia de FPS demostrable en WSA. Volver a fase CPU ARM64, inspección y equivalencia de `0x0041B8F0` con dispositivo TECNO; evaluar GPU Mali si se habilita. Meta 60 FPS física; **0/5**. [Informe A/B/A](../ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md).

## Próxima etapa de ejecución — WSA 3D reproducible, A/B/A exploratorio (2026-10-14)

- [x] Documentado el [checkpoint integral](../PROJECT_STATUS_CHECKPOINT_2026-10-14.md) del port, perfiles ARM64 históricos, Vulkan propio, Zink, build ANGLE, verificaciones WSA, restauración y riesgos.
- [ ] Identificar de manera no destructiva la partida estable y una ruta reproducible para cargar la escena Camp Toccoa en WSA; **evitar reset de saves**.
- [ ] Capturar imagen real 3D/HUD con GL4ES (A) y ANGLE/Vulkan (B), restaurar y repetir A. Registrar shader warmup, glitches, fallos y carga de la escena.
- [ ] Capturar frametimes/FPS reales del juego con el mismo estado. Si las condiciones difieren, marcar **inconcluso**; nunca equiparar menú ni prototipo WSI con 3D/Camp Toccoa ni extrapolar WSA al TECNO.

## ANGLE Vulkan en juego real WSA, cierre de compatibilidad inicial (2026-10-14)

- [x] GitHub Actions Linux compiló el APK experimental x86_64 desde fuente oficial pinneada; SHA, ABI, EGL/GLES, paquete y firma Android verificados. Compilación real en **34m50s**.
- [x] En WSA, `GameActivity` de CallofRecomp cargó `org.chromium.angle` y reportó `Renderer (Vulkan 1.3.0 AMD Radeon)` en el **mismo PID**, durante la ventana registrada; el menú de Call of Duty se renderizó visiblemente y se cotejó con GL4ES nativo.
- [x] Tres ensayos aislados con rollback final sin errores. Fallos del detector (`JUGAR` allCaps y `ANGLE debug package enabled`) corregidos, nuevas pruebas de regresión incorporadas. Referencia A1 y settings restaurados.
- [ ] Siguiente: equivalencia **3D en Camp Toccoa**, captura reproducible y FPS A/B/A de CallofRecomp, no de menús ni prototipos. Solo luego contemplar soporte ARM64/Mali, sin cambiar GL4ES estable. **0/5**. [Informe real](../ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md).

## ANGLE: entrada optativa y verificable al juego (2026-10-14)

- [x] `angle_wsa_launcher.py` inspecciona accesibilidad y reconoce exactamente el botón habilitado `Jugar` de la APK de CallofRecomp; rechaza múltiples coincidencias, coordenadas inválidas y apps ajenas.
- [x] `--enter-game` solo se permite junto a `--execute`, tras la autenticación offline de la APK ANGLE; se confirma `GameActivity` reanudada o se considera error y se inicia rollback.
- [x] ANGLE sí fue ejecutado y verificado en GameActivity **en WSA**; pendientes gráficos 3D/FPS A/B/A. [Informe](../ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md). **0/5**.

## ANGLE: diagnóstico Logcat verificable por PID/época (2026-10-14)

- [x] Logs WSA reales en formato `-v epoch` contrastados: se acotan por hora Android y PID del proceso CallofRecomp; deben mostrar selección de paquete y Vulkan en esa misma ejecución.
- [x] Pruebas contra falsos positivos de Logcat viejo, PID distinto y texto sin formato. `LauncherActivity` requiere interacción en **Jugar** para crear el contexto GLES del juego, no se reportan FPS de pantalla inicial.
- [x] Verificado con APK ANGLE compilada desde upstream, selección real por paquete, Logcat Vulkan por PID/tiempo y rollback exitoso. [Informe](../ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md). **0/5**.

## ANGLE: ensayo reversible por aplicación WSA (2026-10-14)

- [x] `angle_wsa_trial.py`: preflight de solo lectura y protocolo explícito de instalación temporal tras verificar identidad/firma/ABI/SHA, selección de un único paquete, diagnóstico Logcat y rollback en `finally`.
- [x] Preflight WSA real sin modificaciones: aplicación depurable, juego detenido, no hay ANGLE instalado, opciones null, sin bloqueos. Ensayo con driver real todavía **pendiente**.
- [ ] Una vez termine el build Linux y el artefacto supere `verify_angle_apk.py`, ejecutar prueba puntual; confirmar qué renderer se cargó, restaurar y después planificar gameplay A/B/A. [Guía](../ANGLE_BUILD_PIPELINE_2026-10-14.md).

## Preparación de build ANGLE en Linux sin afectar Windows ni WSA (2026-10-14)

- [x] `tools/recomp/diagnostics/build_angle_android_linux.sh`: descarga oficial fijada, dependencias Chromium sincronizadas y compilación de `AngleLibraries.apk` x86_64/Vulkan bajo Linux; queda como receta, no se ha ejecutado.
- [x] Workflow `angle-manual-build.yml`: **ejecución manual exclusivamente**, sin push automático, permisos mínimos, artefacto APK y comprobante de procedencia. El disco/tiempo disponible en runners estándar no está garantizado.
- [x] `verify_angle_apk.py`: comprobación local de SHA-256, cabecera ELF x86_64 de EGL/GLESv2, package name mediante aapt y verificación de firma mediante apksigner. Validez de firma no equivale a firma oficial Google.
- [ ] Obtener binario compilado de forma real y ejecutar inspección estricta: [primer workflow Linux en marcha, run #38591658796](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38591658796), sin resultado final todavía. Posteriormente ensayo por aplicación en WSA con rollback y Logcat Vulkan, seguido de A/B/A. **0/5**. [Documentación](../ANGLE_BUILD_PIPELINE_2026-10-14.md).

## Evaluación ANGLE GLES2→Vulkan y preparación de prueba por aplicación (2026-10-14)

- [x] Descargado el snapshot oficial ANGLE: commit **43140711d13063716fd32a15de829885d0bce469**, árbol `06315a7275a6cc870b55e2e32c6eab165604357d`; integridad Git y concordancia con espejo verificados.
- [x] **GL4ES → ANGLE GLES2 → Vulkan** es un candidato que conserva GL4ES y el contexto SDL2; código upstream y documentación Android inspeccionados.
- [x] WSA x86_64 API33: app depurable iniciada por Java (SDLActivity) pero **paquete ANGLE ausente**. Las preferencias ANGLE no se modificaron. [Diagnóstico completo](../ANGLE_GLES_VULKAN_FEASIBILITY_2026-10-14.md).
- [ ] Compilar ANGLE para Android desde Linux con depot_tools, gclient, GN y Ninja; **no hay distro WSL ni herramientas GN disponibles en este PC**. Verificar la firma/origen y ABI de AngleLibraries.apk antes de probar.
- [ ] Probar ANGLE únicamente para `org.callofrecomp`, verificar backend Vulkan en Logcat, restaurar preferencias luego, y solo después realizar A/B/A en una escena real de gameplay. Sin FPS ni intento fallido contabilizado por la auditoría.

## Evaluación Mesa Zink 26.2.4 frente a GPU real WSA (2026-10-14)

- [x] Descargada fuente de Mesa 26.2.4 con SHA-256 oficial verificado, inspeccionada su implementación Gallium/Zink y perfil Vulkan `VP_ZINK_gl21_baseline`.
- [x] Censo Vulkan en WSA: AMD Radeon Vulkan 1.3 **no cumple al menos cuatro requisitos** del perfil GL2.1 (`alphaToOne`, maintenance5, swapchain mutable format y border color swizzle). El parser separa extensiones ausentes de promociones a Vulkan core. [Investigación y reproducción](../MESA_ZINK_FEASIBILITY_2026-10-14.md).
- [ ] No intentar empaquetar Zink en CallofRecomp para el WSA actual; faltan requisitos del driver y frontend OpenGL/EGL de Mesa. Comprobar el perfil en TECNO ARM64 cuando vuelva a estar disponible.
- [ ] Considerar ANGLE (GLES→Vulkan) como alternativa de integración Android menos invasiva que Mesa Zink, después de examinar requisitos; cualquier cambio requiere A/B/A de gameplay real.
- [x] Estado de producción intacto, ninguna prueba de FPS del juego, estrategia y contador **0/5** sin cambios.

## WSA temporal, evaluación Vulkan/DirectX12 y bloqueo de métricas Mali (2026-10-14)

- [x] El TECNO no está disponible: usar solo **WSA x86_64 (`127.0.0.1:58526`)** para las siguientes pruebas locales; no asumir que su rendimiento representa al ARM64.
- [x] [Auditoría de APIs gráficas, causa de permisos GPU y decisión Vulkan/DX12](../WSA_VULKAN_DX12_RENDERER_DECISION_2026-10-14.md). Código real Vulkan en WSA pasó `vkCreateInstance`, enumeró AMD Vulkan 1.3 y `VK_KHR_swapchain`.
- [x] Surface+swapchain+present Vulkan aislados: **75,014 FPS FIFO** con clear a color sólido, NO FPS del juego.
- [x] **Nuevo hito Vulkan:** shaders SPIR-V reales, pipeline gráfico y 4 vértices/6 índices, `vkCmdDrawIndexed` en WSA. **74,999 FPS** FIFO (1.276 frames, CPU del hilo 1,918 ms/frame), 75 Hz; captura confirma geometría coloreada. [Informe técnico](../WSA_VULKAN_INDEXED_MESH_2026-10-14.md).
- [x] **Nuevo hito de texturas Vulkan en WSA:** `VkImage` RGBA8 real, staging buffer, transiciones de layout, sampler/descriptores y fragment shader `sampler2D`. **75,117 FPS FIFO** / 1,989 ms CPU del hilo; son medidas de prototipo, no del juego. [Informe](../WSA_VULKAN_TEXTURE_2026-10-14.md).
- [x] **Hito Vulkan depth/stencil + transparencia:** 5 attachments de profundidad independientes, stencil REPLACE/EQUAL y blending alfa; **4 draw calls/frame** y resultado visual verificado en WSA. **75,005 FPS FIFO** / 2,206 ms CPU del hilo, todavía **no FPS del juego**. [Informe](../WSA_VULKAN_DEPTH_STENCIL_BLEND_2026-10-14.md).
- [x] **Captura tipada GL→Vulkan implementada en generador**, con estructuras para profundidad/stencil/blending/culling, matrices y unidades de textura; prototipo Vulkan reutiliza el traductor. Una muestra real de CallofRecomp en WSA confirma **164 snapshots, todos con incompatibilidades**; [informe de cobertura](../GL_VK_STATE_BRIDGE_2026-10-14.md).
- [x] **Hito TexEnv/alpha:** captura tipada de MODULATE/REPLACE en `glTexEnv[i/f/iv/fv]` y shader Vulkan con prueba alfa GL_GREATER/discard, ejecutado en WSA en 2 quads con textura RGBA8. **75,043 FPS FIFO de prototipo**, NO gameplay. [Informe técnico](../WSA_VULKAN_TEXENV_ALPHA_2026-10-14.md).
- [x] **Matrices y proyección GL:** observación de ocho llamadas `glTranslate/Rotate/Scale/Ortho/Frustum` desde wrappers generados; matrices column-major `PROJECTION×MODELVIEW`, sintaxis ARM64 y demo `--scene matrix` en WSA con 3 quads indexados y shader que corrige clip Y/Z. **75,024 FPS FIFO** de prototipo, **no del juego**. [Informe](../WSA_GL_MATRIX_BRIDGE_2026-10-14.md).
- [ ] Siguiente bloque: otros modos TexEnv y multitextura/combiners, texturas/samplers reales, arrays de vértices y traducción de draw calls, seguido de equivalencia visual y A/B/A del juego.
- [x] Juego OpenGL A1/A2 en WSA: **55,20 / 55,05 FPS** en Camp Toccoa.
- [x] Diagnóstico del cap WSA x86_64: **A2/B/A3 55,05 → 57,20 → 55,30 FPS**; CPU 17,315 → 17,47 → 17,27 ms. Solo evita pacing, no Vulkan.
- [ ] Renderizador Vulkan que dibuje la partida y A/B/A final: PENDIENTES. [Mediciones](../WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md).
- [ ] GPU física ARM64: contadores Mali aún pendientes de herramientas compatibles y disponibilidad del teléfono. No pedir permisos ordinarios de Android ni root.
- [x] Renderer OpenGL/GL4ES conservado sin cambios, estrategia actual y contador **0/5** sin cambios.

## Ejecución real de la estrategia vigente (2026-10-14)

- [x] **Fase 1 CPU:** dos perfiles ARM64 del spawn, muestras totales 7.953 y 6.541; Build ID de ELF comprobado contra el APK instalado; última referencia 24,70 FPS / 38,895 ms CPU/frame / p10 23,30; [informe con evidencia y método](../PERFORMANCE_STRATEGY_RUN_2026-10-14.md).
- [ ] **Fase 1 GPU:** traza gráfica Perfetto básica guardada de forma privada; `gpu.counters` ausente y sysfs Mali bloqueado por permisos. Tiempo real de GPU pendiente, no asumir GPU libre.
- [x] **Fase 2 selección:** `0x0041B8F0`, 270 muestras A1 y 196 A2, con cargas/movimientos dominantes; `restrict` ya existe en el generador, así que no duplicar la optimización.
- [ ] **Fase 2 parche estructural:** pendiente de prueba de CFG, estado y comparación del ARM64 compilado; **fase 3:** pendiente de evidencias.
- [x] Herramientas reproducibles para perfilar, simbolizar y reportar costes. **0/5 intentos válidos fallidos** (son diagnósticos, no hay candidato A/B).

## Estrategia vigente de rendimiento (decisión formal)

**Fuente autoritativa:** [Estrategia actual y registro de experimentos](../PERFORMANCE_STRATEGY_CURRENT.md).

1. Perfilar el frame CPU/GPU real del TECNO (Simpleperf, perfiles GPU, frecuencias y temperaturas).
2. Probar una optimización estructural del traductor/recompilador en **una única función caliente**, verificando diferencias en ARM64 nativo.
3. Priorizar fast paths ARM64 completos por coste dinámico y validarlos con equivalencia de estado y FPS sostenido A/B/A/B/A.

**Política de revisión:** después de **5 experimentos válidos consecutivos sin mejora reproducible**, revisar formalmente el enfoque antes de seguir invirtiendo tiempo. El contador comienza en **0/5** desde la adopción de esta política; los ensayos históricos no se computan retroactivamente. Éxitos confirmados reinician el contador; ensayos inconclusos no cuentan. El umbral exige revisión, **no cambio automático**. Meta 60 FPS sostenidos: **PENDIENTE**.

## Current status snapshot (2026-10-14)

- Exact 1.5 original PE32/DLL fingerprints, SP ABI probes and the portable host: implemented and exercised in local tests.
- Native ARM64 and WSA x86_64 debug APKs: compiled and signed; WSA menus, training and saves have functional smoke coverage. Full campaign on a real phone remains unverified.
- Recompiled graphics path: GL4ES/GLES2; original-menu parse repeats after `Hunk_Clear`. Never label it duplicate per-frame rendering or skip lifecycle work without memory analysis.
- **New diagnostics:** [function-entry/chunk correlation](../FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md) is verified with private original p-code (6,228 mapped entry points). Native per-function CPU attribution and crowded ARM64 scene measurements remain pending.
- `-O2`, `-Oz`, GL4ES batching and VBO mode 2/3 experiments were neutral/negative in controlled WSA tests; do not enable indiscriminately.
- **TECNO ARM64:** an opt-in native x87 transform at original CoDSP.exe `0x005061B0` improved one saved training view from 21.45 to **25.65 median FPS** (A/B/A, +19.58%). Default Android build **OFF**; see [measured phone report](../TECNO_CK6N_ARM64_PERF_2026-10-14.md).



## DCE en el generador pcode2c: optimización fuente sin ganancia ARM64

- [x] `--prune-dead-temporaries --dead-temp-parts 1,8`, optativo OFF por defecto. Reduce 32.704 operaciones únicas estáticas y ~1,25 MB de C entre p1/p8.
- [x] Validación C compilada de estado completo, ejecución ARM64 en TECNO y dos APK con **idéntico SHA256 de `.text`**. Clang ya eliminaba todo ese trabajo; **no hay mejora de FPS**.
- [ ] Cambiar a perfil real de instrucciones *sobrevivientes* (x87 y memoria/alias), con experimentos que modifiquen instrucciones máquina y un A/B/A de spawn antes de aprobar. [Informe](../CODSP_PCODE_TEMP_DCE_2026-10-14.md).

## FCOM x87 p1/p8: ganancia B1 no reproducida en B2 (OFF)

- [x] Simpleperf TECNO: 86,13 % de muestras CPU en `libmain`, 1,43 % GL4ES, 4,70 % driver GLES Mali (no cuenta ejecución GPU). Revisados GL4ES y renderer del proyecto.
- [x] 448 comparaciones completas, ruta nativa optativa detrás de `--x87-fcom-fastpath`, OFF por defecto; oráculo diferencial ARM64 de 151.638 estados.
- [x] A/B/A/B/A de 40 ventanas en spawn: **24,90 → 26,15 → 24,90 → 19,80 → 25,10 FPS**. B2 tuvo regresión importante, por lo que el ahorro de B1 no es estable ni está aprobado. CPU 38,59 → 36,875 → 38,625 → 48,210 → 38,305 ms/frame. No equivale a 60 FPS.
- [ ] Investigar variación B2 con trace de frecuencias, cargas y perfil comparativo; medir misiones variadas, comprobar estado original x86 de manera independiente y probar reducción de cálculos de flags muertos con liveness por bloque. Mantener FCOM OFF. [Informe](../ARM64_RENDERER_CPU_FCOM_2026-10-14.md).

## Nuevo experimento: x87 normal-f2d (FPS sin validar)

- [x] Se probó un fast path opcional para valores binary80 normales representables exactamente como binary64 (CoDSP p1/p8), **OFF por defecto**.
- [x] En TECNO ARM64 coincidieron **1.205.360 patrones** frente a `f2d` existente; microbenchmark aislado ~17 % menos tiempo de conversión.
- [x] APK ARM64 compilada, firmada e instalada; arranca al menú. Se conservó copia y se restauró en TECNO la referencia anterior.
- [ ] A/B/A en spawn de training y controles de HUD/partidas; no adoptar hasta medir FPS de juego y no extrapolar el microbenchmark. **60 FPS todavía pendientes.** [Detalles](../ARM64_X87_NORMAL_F2D_2026-10-14.md).

## Próximo cuello de botella por instrucción: comparaciones x87

- [x] Atribución aproximada del perfil ARM64 de 5.476 muestras al C anterior y Ghidra v2, corrigiendo primero el desplazamiento de líneas del C generado `p1`. La visibilidad `0x004D94C0` concentra **37 de sus 150 muestras** en `0x004D9511`; geometría `0x0041B8F0` concentra 23/247 en `0x0041B986`.
- [x] Confirmado que la sola instrucción `0x004D9511` tiene **30 p-code ops**, incluidas NaN, comparación y banderas. El fast path limitado a NaN no elimina la mayor parte del trabajo.
- [ ] Próxima fase: fast path optativo para una comparación x87 completa en estos puntos, **solo** tras demostrar estado exacto y retorno seguros; medir CPU/FPS A/B/A. Meta **60 FPS en spawn** pendiente.

## TECNO ARM64: clasificación NaN binary80 (equivalente, FPS sin mejora acreditada)

- [x] `--x87-nan-bits` optativo **OFF por defecto** en CoDSP `p1/p8`; 1.178 expresiones estáticas acelerables con parcheador que valida las etiquetas originales.
- [x] Comparación de **955.360 casos binary80** sobre hardware TECNO ARM64 contra `isnan(f2d(v,10))` del recompilador; igualdad completa. Regresión **98 Python (4 omitidas), 29/29 CTest**.
- [x] A/B/A/B/A físico del entrenamiento: referencia **24,75 / 24,75 / 25,45 FPS**, candidata **25,60 / 25,70 FPS**. La ventaja respecto a A3 de solo 0,15–0,25 FPS está dentro de la variabilidad; **no activar ni anunciar una ganancia de FPS**.
- [x] Mantener x87 (+19,58 % verificado antes) y correcciones de HUD. Dispositivo y build local restaurados al perfil de referencia.
- [ ] Próximo experimento: aislar PC originales calientes dentro de colisiones/geom. `0x0041B8F0` y `0x004196F0`, con diferencia integral de RAM/regs/PC y A/B/A. **60 FPS pendiente**.

[Ver experimento NaN y cinco corridas](../ARM64_X87_NAN_BITS_2026-10-14.md).

## TECNO ARM64: copy32 y visibilidad -O2 (sin nuevo aumento de FPS)

- [x] Especialización privada de la copia `0x0042B0A0`: **17.000 diferenciales completos en ARM64 y 249.371 bloques** equivalentes a la traducción p-code; A/B/A de FPS **25,45 / 25,10 / 25,30** (referencia/candidato/referencia). Sin ganancia. Flag **OFF por defecto**.
- [x] Compilar solo `codsp_recomp_p8.c` con `-O2 -ffp-contract=off`: A/B/A **25,30 / 25,50 / 25,45**. Diferencia de solo 0,05 FPS frente a la repetición; no es mejora aceptada. Flag **OFF por defecto**.
- [x] Se mantienen el avance x87 (+19,58 % frente a la versión inicial), la APK de referencia en el teléfono y la visión panorámica/HUD ya corregidos.
- [ ] Próxima intervención: optimización semánticamente equivalente *dentro* de geometría/colisiones (`0x0041B8F0`, `0x004196F0`) o visibilidad (`0x004Dxxxx`), con pruebas completas de estado + nuevo A/B/A. **60 FPS sostenidos pendientes.**

[Ver resultados detallados de ambos ensayos](../ARM64_PERF_EXPERIMENTS_2026-10-14.md).

## Health bar and circular objective stars (corrected on TECNO)

- [x] Scale all Health script children (cross, backdrop, fill) together,
  without changing health values or right-edge alignment.
- [x] Distinguish cgame's 0x4a color call from the 0x4b direct objective
  draw at `0x3001cf40`; enter the original CoDSP callback, not a host thunk.
- [x] Convert pre-scaled pixel geometry back to virtual HUD units before
  applying the compass shape adjustment, then return to device pixels.
- [x] Objective gold ring measured **29×29 actual screen pixels** on
  TECNO CK6n; full 94 Python / 27 CTest regression passed.
- [ ] 60 FPS at training spawn and other untested campaign icon variants
  are still open, independently of this completed HUD fix.

## Widescreen dynamic compass pointers (corrected in training)

- [x] Isolated the original cgame dynamic friend, tank and objective marker
  callbacks rather than changing the 3D projection or other HUD elements.
- [x] Applied aspect-correct marker sizes and radial bounds so complete
  icons remain inside the circular compass without changing direction.
- [x] TECNO training screenshot plus runtime logs verified green friend
  and objective-pulse correction; 94 Python tests and 27/27 CTest passed.
- [x] Main objective-star circle visually verified in training (actual
  screenshot bbox 29×29px; cgame draw 64×38.4 → 38.4×38.4px).
- [ ] Tank and additional campaign objective icon coverage remains pending.
- [ ] Target of **60 sustained FPS at training spawn** still pending;
  current visual-fix benchmark ~25.75 FPS is not a new proven speedup.

See the HUD widescreen report for geometry and verification evidence.

## Visual aspect fix before further performance experiments (completed)

- [x] Retain real 3D widescreen camera: 1280×576 EGL aspect 2.22222 and expanded ~108.87° horizontal FOV, **not** a stretched 4:3 projection.
- [x] Correct the compass plus selected square 2D HUD icons, as confirmed on the TECNO CK6n. Original resources are unchanged; Android generates a private override from imported data before engine startup.
- [x] Guard original PK3 ZIP duplication compatibility, save/player controls and no proprietary redistributable assets; maintain synthetic Java tests and Android build.
- [ ] Separately fulfill the **60 FPS spawn target**. The widescreen HUD repair is not a performance milestone; prior +19.58% FPS remains measured and the goal is open.
- [Documentation and verification](../HUD_WIDESCREEN_2026-10-14.md).

## Meta exigida: 60 FPS sostenidos donde aparece el jugador (NO alcanzada)

- [x] Mejora reproducida en TECNO CK6n, training/Equilibrado: **21,45 -> 25,65 FPS (+19,58 %)** y **44,745 -> 37,495 ms CPU/frame** mediante fast path nativo optativo de CoDSP 0x005061B0. Esta mejora sí cuenta como avance.
- [ ] Objetivo final: **60 FPS sostenidos en la zona de aparición inicial del entrenamiento**, sin sustituirla por el menú o una zona menos exigente.
- [ ] Medir al menos 60 ventanas estables seguidas, FPS bajos, CPU y temperatura; confirmar A/B/A, guardado y jugabilidad.
- [ ] Identificar en el teléfono los cuellos de botella restantes y validarlos uno a uno. El objetivo exige ~16,67 ms por frame frente a ~37,50 ms CPU/frame ahora.
- **Estado:** inacabado; la optimización experimental sigue OFF por defecto en la compilación estándar.

## Phase 0 — Immutable baseline

- Fingerprint original binaries with SHA-256.
- Record exact version and archive inventory.
- Keep original files outside Git.
- Generate machine-readable PE/PK3 reports so later findings can be reproduced.

**Status:** completed for the verified exact CoD 1.5 SP binary baseline.

## Phase 1 — Recover module boundaries and ABI

- Map `CoDSP.exe` engine responsibilities.
- Recover the `dllEntry` / `vmMain` ABI used by `gamex86.dll`, `cgamex86.dll` and `uix86.dll`.
- Identify syscall IDs and argument shapes from wrapper stubs.
- Build a symbol ledger with confidence levels: observed / matched / inferred.

**Status:** core SP ABI mapping verified; detailed names/semantics of some syscall IDs remain unresolved. `dllEntry` stores the engine callback and modules call it by numeric syscall ID.

## Phase 2 — Static analysis pipeline

- Add deterministic function discovery and call-target extraction.
- Integrate a headless decompiler workflow for functions selected by address.
- Export function metadata to JSON instead of relying on a GUI project file.
- Add cross-reference and string-reference reports.
- Add optional matching against public id Tech 3 reference code where behavior is genuinely homologous; never assume identity from naming alone.

## Phase 3 — Reconstructed platform-neutral core

- Recreate engine/module interfaces in clean C/C++.
- Preserve gameplay/data formats while replacing Win32-specific platform code.
- Create regression harnesses for parsers, command dispatch, math and serialization.

## Phase 4 — Android host layer

- Android NDK / ARM64 build.
- Filesystem bridge for externally supplied game assets.
- Renderer adaptation from desktop OpenGL behavior to a supported Android path.
- Audio backend replacement for Miles/Win32-specific calls.
- Input abstraction for touch, controller and keyboard/mouse where available.

## Phase 5 — First boot milestone

Definition of done:

1. Native ARM64 executable/library starts on Android.
2. Filesystem initializes and reads original PK3 data.
3. Renderer opens a frame and reaches the game UI.
4. Single-player module initializes through the reconstructed ABI.
5. A map can be entered without x86 emulation.

## Phase 6 — Correctness and optimization

- Compare deterministic behavior against the PC baseline.
- Fix endian/alignment/pointer-width assumptions.
- Optimize renderer/resource loading only after correctness.
- Add device-specific input/UI polish.

## Phase 7 — Function-level performance proof and measured optimization (active)

- [x] Restore Ghidra original function-entry metadata to an optional, ignored mapping sidecar without changing default compiled behavior.
- [x] Associate existing guest CPU chunk samples with the exact private maps, without fabricating per-function CPU percentages.
- [x] Archive references, rejected experiments, repeatable commands and correctness restrictions in [the 2026-10-14 research](../FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md).
- [x] Export noncontiguous original Ghidra B body ranges from the saved project into ignored v2 provenance maps; real modules yielded 519,757 uniquely assigned x86 instructions and 80,013 unassigned.
- [x] Add native ARM64 ELF-PC → inline stack → generated C line → x86 instruction → Ghidra body resolution, verified with the unstripped real shared library and artificial ELF-address fixtures.
- [x] Capturadas muestras reales con Simpleperf en el TECNO ARM64 en la entrada de training; correlación estadística a funciones mediante DWARF y Ghidra (ver [auditoría TECNO](../TECNO_CK6N_ARM64_PERF_2026-10-14.md)). No equivale a tiempo exclusivo por función.
- [ ] If source-line sampling is insufficient, capture guest function entry/return activity behind opt-in instrumentation and measure overhead before enabling any native fast path.
- [ ] Capture **native physical ARM64** CPU/GPU traces from the crowded training scene with controlled camera/save/thermal variables.
- [x] Identificada función x86 caliente original CoDSP.exe 0x005061B0 (656 muestras en un perfil físico) y descartados -O2, -Oz y reducción global de detalle como solución.
- [x] Implementar y medir **optativamente** la ruta matemática 0x005061B0: 75.000 diferenciales bit a bit frente al p-code, A/B/A físico +19,58 % FPS en una vista concreta, 26/26 CTest. Mantener OFF por defecto.
- [ ] Antes de habilitar por defecto, completar oráculo de ejecución **x86 original** independiente (la evidencia actual compara contra p-code), excepciones/precisión FPU, jugabilidad y calidad visual en otras misiones/escena concurrida y más dispositivos.

**Non-goals until evidence exists:** wholesale renderer replacement, disabling menu reloads after `Hunk_Clear`, changing original game logic or promising a universal FPS gain.
