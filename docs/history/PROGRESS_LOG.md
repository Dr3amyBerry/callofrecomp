# Project Progress

> Living project log for the Call of Duty 1.5 PC → Android ARM64 recompilation effort.
>
> **Rule:** this file must be updated whenever a meaningful phase starts, completes, changes direction, discovers a blocker, or requires a new external tool.

**Last updated:** 2026-10-15
**Primary branch:** `main`
**Primary target:** Call of Duty 1.5 single-player
**Long-term target:** native Android ARM64 execution without x86 emulation

### 2026-10-15 — Reorganización de conocimiento y archivo de builds (sin cambios de ejecución)

- 78 documentos trasladados por tema (guías, WSA, TECNO, CPU, CFG, gráficos e historia), enlaces relativos actualizados y catálogo regenerable en `docs/history/DOCUMENT_CATALOG.md`.
- `PROGRESS.md` se mantiene como entrada breve; esta bitácora completa se preserva en `docs/history/PROGRESS_LOG.md`.
- Meta **60 FPS TECNO CK6n ARM64 sigue vigente**, pendiente de revalidación con el hardware y build actual. No extrapolar ganancias WSA x86_64; [protocolo TECNO](../TECNO_REVALIDATION.md).
- Se movieron 4 compilaciones CFG14 antiguas y 3 releases anteriores a `.local/builds/history/`; las junctions, la build actual, `recomp_out` y el release v0.2.3 no cambiaron.
- Índices privados de scripts y duplicados bajo `.local/catalog/`, sin eliminar experimentos ni datos. Verificación documental: 119 Markdown, 0 enlaces locales rotos; migrador idempotente. Regresión Python local **396 tests, 6 omitidos, 0 fallidos** y **38/38 CTest**; `git diff --check` aprobado. La reorganización privada no modifica APK, saves, flags ni mediciones FPS. Commit y push se registrarán por Git.

### 2026-10-15 — Política incremental y mapa de conocimiento (solo documentación)

- Confirmadas en builder las opciones WSA acumulativas, el enlace local de estado guest y los bloqueos CFG14/transform double; no se alteraron APK, código de rendimiento ni partidas.
- Nueva fuente rápida de decisiones: [registro acumulativo](../OPTIMIZATION_LEDGER.md), enlazado desde el índice y las reglas de agentes. Las mejoras pequeñas comprobadas se conservan, las ambiguas se mantienen opt-in y los fallos de precisión/estado permanecen bloqueados.
- El contador histórico de cinco intentos deja de decidir retenciones. La bitácora e informes antiguos mantienen su contexto temporal; ninguna prueba FPS nueva se infiere de esta reorganización.


### 2026-10-15 — Perfil aplicado: enlace local de estado y medición GL

- `--local-guest-state`: R/MEM/U/PC locales a libmain, otros 545 exports conservados y 28 fuentes generadas idénticas. El ensamblador elimina cargas GOT sin modificar instrucciones guest, precisión o escrituras.
- A/B/A/B sobre la acumulativa, x87 activo en ambas: mejora pequeña de FPS/CPU en ambas parejas. [Tabla y límites](../performance/wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md).
- Nueva agregación GL ponderada por frames y medición diagnóstica de Draw/índices/buffers; no se implementan cachés sin invalidación demostrada. Desambiguadas las muestras del postámbulo x87.
- APK normal candidata restaurada, contadores GL retirados y guardados intactos. 120 FPS sostenidos sigue abierto.
- Código `bb9d200`, [CI 38780053644 aprobada](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38780053644).

### 2026-10-15 — APK B actual: perfil reproducible del CPU y GL4ES; sin cambios de código

- [x] APK instalada recuperada desde WSA y cotejada por SHA-256 **a19ea65e…da1702**, Build ID ELF binario/archivo Simpleperf **23df3b5f…b2e4** y **28/28** fuentes generadas verificadas por hash. `main` base: `d6d6f8e`.
- [x] Gameplay Alta/1280×720/límite 120: **35 ventanas / 35,47 s** sin profiler simultáneo: **67,2 FPS**, **14,89 ms CPU/frame**, p10 **60,3**, presentación **63,48/s**, p99 **32,29 ms**, pacing **0**, modo WSA **75 Hz**, cobertura completa.
- [x] Simpleperf app UID **12.695 muestras /25 s**; perfil DWARF adicional **5.074/25 s**, ambos 0 pérdidas. `libmain.so` **9.465** (74,6 %), `libc` **1.292**, OpenGL encoder/transporte con coste significativo. 5.788 muestras de libmain atribuidas a cuerpo Ghidra B único; restantes sin inventar propietarios.
- [x] Zonas concretas: `recomp_rt.h:19–20,84,115` (rd/wr/f2d/d2f); hotspots `0x004196F0`, `0x0041B8F0`, `0x0041CD60`, `0x0042B100` (copia32), `0x004CC6E9`; `gl_thunks.c:1187–1191` y rutas `glUtilsPackPointerData` / `AddressSpaceStream`. La familia inline memcpy de libmain suma **3.337 muestras**, f2d **1.769**, d2f **857**, **sin convertirlas a ms exclusivos**.
- [x] Informe nuevo [Perfil de la APK optimizada instalado](../performance/wsa/WSA120_OPTIMIZED_APK_CPU_PROFILE_2026-10-15.md), evidencia original en `.local/profiles/wsa120_20261015/postopt_reprofile_20261015/` ignorado. **No se alteró código, APK, saves, calidad ni configuración**; solo documentación.
- [ ] Prioridad: estudiar ensamblador nativo de la materialización R/U/x87 y medir empaque de arrays GL con instrumentación controlada; no implementar una supuesta ganancia de FPS antes de probar oráculo y A/B. Meta 120 FPS abierta, margen de **~6,56 ms/frame** respecto de la captura nueva.

### 2026-10-15 — Integración acumulativa y ganancia física WSA

- Región x87 binary80 integrada en el APK y preset `--wsa-cumulative` con opciones compatibles existentes. Corregidas compatibilidades de parches, guarda copy32 de páginas y alias CW fijo observado en el juego.
- A/B/A/B Alta, misma escena/guardado y límite 120: conjunto activo en ambas B; mejora repetida de CPU y FPS. Guardados intactos. [Tabla, alcance y reproducción](../performance/wsa/WSA_CUMULATIVE_2026-10-15.md).
- Oráculo del adaptador final: 22.344 casos WSA sin diferencias; repetición con alias CW contrastada también contra CPU i686 original. Se mantienen bloqueos de rutas con errores conocidos.
- Preset experimental instalado y activo en WSA. No acredita 120 FPS sostenidos, TECNO ni estabilidad prolongada; próximo perfil debe usar el ELF nuevo.
- Código `8401f29`, [CI 38773880404 aprobada](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38773880404).

### 2026-10-15 — Metadatos, alias y captura precisa de faltas x87

- Adaptador público: metadatos guest explícitos tras una instrucción de memoria completada y lectura del estado aritmético desde FXSAVE64 de señal, con reconstrucción de tags físicos por TOP. Pruebas contra FNSAVE nativo, 24 patrones de pila y preservación de todos los demás campos.
- **22.344 casos de alias/metadatos** sin diferencias de RAM, CW/SW/tags, ocho slots y metadatos frente al original i686, repetidos en Windows x64 y WSA.
- **540 pares de faltas reales**, uno por cada 45 instrucciones con memoria × 12 controles. Contexto x86 y señal WSA coinciden en PC/RAM/metadatos/FPU. Confirmado que los 1.080 registros corresponden al objetivo elegido; WSA ejecutó el decodificador público.
- Matriz final Windows/WSA O0/O2/O3 **6/6**. No hay reanudación del acceso, RET por pila ni integración en runtime/APK todavía; no se afirma mejora FPS. [Alcance y siguiente integración](../performance/wsa/WSA120_NATIVE_X87_STATE_2026-10-15.md#continuación-metadatos-alias-y-fallos-reales).
- Regresión final **37/37 CTest**, 68,05 s. Estado actual consolidado para evitar repetir como pendientes las pruebas ya resueltas en laboratorio.
- Código `b0256db`, [CI 38741645925 aprobado](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38741645925).

### 2026-10-15 — Adaptador de estado x87 y oráculo CPU de 32 bits

- Implementado `x87_native_state.h`: entorno de 108 bytes, mapeo R medido, selectores explícitos, tag completo/TOP/ocho slots binary80 y preservación de bytes ajenos. Sigue fuera del juego.
- Original ejecutado nativamente en proceso i686 frente a región x64 Windows y WSA: **1.596 casos sin diferencias** en RAM/CW/SW/tags/ocho slots. Incluye pila llena, TOP, flags previos, NaN/Inf/subnormales. Excluye metadatos host, alias y fallos.
- Revisión corrigió formato host a FXSAVE64/FXRSTOR64, bit reservado CW y excepción host pendiente que el test reprodujo como fallo numérico. FNINIT tras guardar y antes de FRSTOR evita dispararla; el estado pendiente se conserva al salir.
- Math/state O0/O2/O3 aprobados Windows/WSA (12 ejecuciones); **37/37 CTest** finales. Ensayo aislado con contexto: 441,349 ns generados / 210,508 ns nativos, sin costes R/guardas/fallos; no equivale a ahorro por frame.
- [Informe y frontera pendiente](../performance/wsa/WSA120_NATIVE_X87_STATE_2026-10-15.md). Sin cambios en APK/partidas ni ganancia FPS declarada. Siguen metadatos, alias y recuperación precisa antes de integrar.
- Código `d68e164`, [CI 38737576358 aprobado](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38737576358).

### 2026-10-15 — Operaciones binary80 nativas, todavía sin integración guest

- Implementado `tools/recomp/runtime/x87_native_math.h`: ADD/SUB/MUL/DIV binary80 explícito, CW y estado de operación capturado antes de almacenar. Conserva x87/MXCSR host; rechaza excepciones sin máscara/controles inválidos y soporta alias. No modifica APK ni lowering.
- Nuevo smoke CMake: 12 controles, precisión/rango extendidos, subnormales, NaN, flags, alias y restauración. Rojo inicial por componente ausente; verde Windows/WSA con O0/O2/O3 y avisos estrictos. Revisión corrigió intercalado posible entre bloques asm; ahora save/cálculo/restore es un bloque único. Regresión final host **36/36**, matriz específica final aprobada.
- Ensayo privado WSA de la transformación: mediana generada 435,083 ns frente a nativa aislada 135,617 ns, diez rondas alternadas de 300.000. Un input fijo y sin exportar estado guest en la candidata: **no demuestra ahorro por frame ni mejora FPS**.
- [Diseño, evidencias y contrato pendiente](../superpowers/plans/2026-10-15-wsa-native-binary80.md). Sigue pendiente una integración arquitectónica completa y su A/B/A/B; bloqueos de fast paths incompatibles conservados.
- Escaneo PE/p-code localiza FLDCW/FNSTCW en `R+0x10a0` y FNSTSW/FNCLEX en `R+0x10a2`; validar esos campos y FRSTOR antes de introducir estado paralelo. El lowering matemático actual no usa ese CW.
- FRSTOR generado comprobado con patrón sintético: mapeo directo del entorno de 108 bytes a control/status/tag/metadatos y ocho slots binary80 documentado; no certifica actualización aritmética ni excepciones. Publicado componente `f389f2d`, [CI 38734909191 aprobado](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38734909191).

### 2026-10-15 — Viabilidad x87 nativa comprobada en WSA

- Prototipo privado aislado de la transformación caliente: 123 entradas × 12 controles de precisión/redondeo = **1.476 casos**, sin diferencias en las seis salidas frente al original ejecutado con Unicorn.
- Unicorn no reflejó los flags de precisión/redondeo que produjo el host: **1.412 diferencias de status word**. No sirve como único oráculo del estado FPU completo.
- Compilado con NDK y ejecutado en WSA: **0 diferencias de salida/status frente a Windows nativo**, **0 fallos de restauración del entorno x87/MXCSR y registros x87 comprobados** con pila centinela. Sin integración ni ganancia FPS declarada.
- [Alcance y pendientes](../performance/wsa/WSA120_LIMITER_AND_RENDERER_PROFILE_2026-10-15.md#continuación-prototipo-x87-nativo-aislado): materialización del estado guest binary80, alias/fallos/excepciones, entradas especiales y coste del aislamiento. APK y partidas sin cambios en este experimento.

### 2026-10-15 — Control reversible de FPS y seis corridas WSA con Alta

- Archivo privado `frame_limit`: original/60/120/unlimited, coordinando `com_maxfps` y host sin cambiar relojes. Sin archivo conserva launcher/diagnóstico anterior. Pruebas de entrada inválida, redondeo y stalls; ejecutable nativo aprobado en WSA.
- APK completa compilada/verificada e instalada conservando datos. Seis corridas válidas con Alta, misma partida y 45 ventanas cada una: 52,2–56,6 FPS y 17,65–19,01 ms CPU/frame. No se demuestra mejora causal CPU; controles también variaron. Presentación real ~51–55 Hz y modo virtual de 75 Hz.
- Capturas con cobertura completa y partidas intactas; una B2 de briefing fue rechazada. Restaurado el límite normal y retirado el archivo de override. No se habilitaron fast paths incompatibles.
- [Informe completo y próximo objetivo](../performance/wsa/WSA120_LIMITER_AND_RENDERER_PROFILE_2026-10-15.md): perfil ELF exacto de renderer/x87, bloqueo `5ebe4cd`, límites de evidencia. 120 FPS, GPU time y validación compleja/prolongada siguen abiertos.
- CI del bloqueo detectó dos errores en un selector de pruebas ligado a un comentario CMake renombrado. Reproducidos y corregidos usando límites por nombres de opciones; 2/2 específicos aprobados sin quitar aserciones. **Commit `234065c`, CI [38732364851 aprobada](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38732364851)**.
- Siguiente diseño: el NDK x86_64 real define long double de 113 bits de mantisa / 16 bytes (binary128). No asumir binary80 de escritorio: investigar representación y operación x87 explícitas con oráculo antes de modificar el lowering.

### 2026-10-15 — Bloqueo independiente de precisión en transformaciones x87

- Perfil WSA nuevo con ELF exacto: el renderer `0x005061B0` reúne 717/3.992 muestras (~17,96 %), candidato de impacto real.
- Unicorn ejecutó sus 58 instrucciones originales y RET con CW `0x037f`; el helper double divergió en salida float32 en **20/23 casos**, incluidos diez casos con entradas entre 0 y 1. GPR/PC coincidentes no compensan la diferencia numérica; no se declara equivalencia FPU completa.
- Builder y CMake ahora rechazan el fast path antiguo con `ORIGINAL_X87_PRECISION_UNSAFE`; no se habilitó durante las pruebas WSA. Tests CLI de ambas ABI pasaron tras fallo esperado; CMake/NDK aislado ON rechazado por ese motivo y OFF configurado correctamente.
- Regresión del árbol de trabajo: **386 Python (4 omitidas), 35/35 CTest**. Datos originales y DLL de auditoría quedan privados. El siguiente diseño debe mantener binary80 y semántica de estado/fallos.

### 2026-10-15 — Dependencias de oráculos declaradas para CI

- El run `38691095500` fallaba al importar dos suites CFG por ausencia de Unicorn.
- `tests/requirements.txt` fija Unicorn 2.1.4 y Capstone 5.0.6, versiones instaladas localmente; el workflow las instala antes de ejecutar CTest. No se ocultan tests ni se cambian oráculos.
- Verificado: commit `fbbf074`, [CI 38727099017 aprobado](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38727099017). No equivale a una mejora de FPS.

### 2026-10-15 — Captura automática de presentación WSA

- `capture_wsa_presentation.py`: timestamps reales de la SurfaceView, deduplicación de buffers, detección de huecos, p95/p99 de intervalos individuales y captura simultánea de ventanas CPU/FPS del motor. Guarda trazas únicamente bajo `.local/profiles/`.
- Tres tests sintéticos aprobados; validación real de 15,16 s: 587 intervalos y ningún hueco. Esta validación coincidió con compilación y **no es una línea base de rendimiento**. Suite Python integrada en CTest aprobada tras añadir los tests.
- Perfil con stacks independiente: 4.045 muestras, ninguna perdida; aparecen envío de atributos y copias del transporte gráfico. No sumar tiempos inclusivos ni usar el ELF local distinto para inventar atribuciones de código original.
- Control configurable de FPS en desarrollo; pruebas host y ejecutable de pacing en WSA aprobados, APK completa todavía compilándose. Sin aceleración demostrada.

### 2026-10-15 — Nueva misión WSA 120 FPS y reglas de eficiencia

- Instrucción actual: desarrollo local autónomo para 120 FPS reales en WSA, sin reducir calidad ni precisión; el objetivo TECNO anterior queda como antecedente independiente.
- `AGENTS.md`: scripts y salidas resumidas primero; capturas visuales solo ante incertidumbre o validación necesaria, sin omitir pruebas de fidelidad.
- APK/perfil/partidas respaldados; A1 actual: 52,7 FPS y 18,66 ms CPU/frame (35 ventanas). Simpleperf posterior: 12.329 muestras, ninguna perdida. Pantalla WSA actual de 75 Hz y doble cap guest/host de 60 comprobados.
- [Evidencia, límites y siguiente bloque](../performance/wsa/WSA120_BASELINE_2026-10-15.md). Sin mejora nueva declarada; faltan perfil fino, opción configurable, A/B y validación compleja/prolongada.

### 2026-10-15 — Consolidación documental y auditoría de GitHub

- Fuente de estado vigente: [PROJECT_STATUS.md](../PROJECT_STATUS.md); índice completo: [INDEX.md](../INDEX.md). Esta bitácora conserva hechos y decisiones en su contexto temporal: sus antiguas colas, capacidades e hitos no describen automáticamente el presente.
- Estrategia y roadmap consolidados, con copias previas archivadas; README reducido a rutas de entrada. Checkpoint del 14 marcado histórico. No se borraron informes ni se cambiaron motor, APK o flags.
- Código local/remoto revisado `bda83a6`; CI remoto fallido por `unicorn` ausente en dos imports, pese a regresiones locales previas aprobadas. Reparación de CI pendiente y visible en P0.
- Siguiente investigación: coste transversal de mantenimiento x87 en ARM64, con fidelidad y fallos comprobados antes de A/B físico; no repetir candidatos negativos sin nueva evidencia. FPS nuevos: no medidos.

### 2026-10-15 — Fase 15: perfiles físicos TECNO, ROI/Amdahl y coste x87 transversal

- [x] Dos capturas físicas Simpleperf distintas verificadas contra **ELF Build ID `80dc3884c64e395f87d7975f200d34edccf648fd`**, checksum y conteos nativos: **7.953/6.541 muestras del proceso**, **6.675/5.491 de libmain.so**. p-code original y mapa Ghidra B con SHA-256 fijados; no se usó WSA como sustituto de ARM64.
- [x] **Ocho funciones originales** (incluida `0x0042B0A0`, entera sin x87) suman **1.557/7.953 = 19,578 %** y **1.244/6.541 = 19,018 %** de las muestras. Para 60 FPS desde 38,895 ms CPU/frame haría falta ~**57,15 % de reducción**; suprimir estas ocho funciones por completo **no bastaría**. Cota Amdahl aproximada CPU-only ~31,8–32 FPS, **NO pronóstico ni ms exclusivos**.
- [x] Atribución exhaustiva PCs nativos→líneas C→instrucciones x86 originales, con comprobación del reporte histórico: de esos **1.557/1.244** samples, **1.255/1.005** (~81 %) corresponden a instrucciones que manipulan estado x87. **Etiquetas de instrucciones, no tiempo de cada micro-op**, y muchas mezclan x87, LOAD y flags.
- [x] **565 POPCOUNT p-code** dentro de ocho funciones; variante especializada por ancho (8/16/32/64/128) pasó **20.495 entradas**, pero Clang ARM64 `-O1`/`-O2` generó **mismo tamaño de funciones**; experimento rechazado, sin cambiar runtime ni recompilador.
- [x] Herramientas `prioritize_profiled_cpu.py` y `attribute_cpu_hot_microops.py`, pruebas sintéticas y guía [fase 15](../performance/tecno/PHASE15_TECNO_CPU_PROFILE_CROSSCUTTING_2026-10-15.md). Metadatos y archivos `perf.data` bajo `.local/profiles` ignorado.
- [x] **Regresión: 382 Python (4 omitidas, 0 fallos), 35/35 CTest**, compilación host correcta, revisión de sintaxis/diffs limpia. No se modificó la ejecución del juego.
- [ ] Próximo bloque: inspección de nativo ARM64 alrededor de x87/rd/wr en **múltiples funciones**, preservar binary80/flags/estado y exigir oráculo original Unicorn; solo instalar tras mejora demostrada. TECNO no conectado (ADB solo WSA); CFG14 sigue BLOQUEADO.


### 2026-10-15 — Fase 14F: superregiones multi-CFG sin RAM + contrato Android de faltas

- [x] Herramienta `cfg_superregion.py` descubre solo **bloques completos originales Ghidra B** unidos mediante aristas CFG reales hacia delante, con entrada única líder, salida a **dispatcher original**, excluyendo memoria guest (incluye varnodes `m`), x87, CALL, RETURN, CALLOTHER, microbranches ambiguos, overlaps y loops nativos no verificados.
- [x] Entre siete funciones calientes, **9 candidatos multi-bloque**, máximo **8 instrucciones x86 en tres bloques**; bloques sin memoria en fase 14E: 68 / 158 instrucciones.
- [x] `benchmark_cfg_superregion.py`: originales PE/p-code/mapa con SHA fijados, Capstone límites/aristas x86, Unicorn x86 original y versiones C A/B. **Tres regiones reales x 96 = 288 casos** coinciden en 8 GPR, 5 flags materializados, **R 8192 B** y PC, sin lecturas/escrituras de memoria guest. Se contabilizan ramas **realmente visitadas**: geometría `0x0041BAB2` dos caminos (un salto incompleto); geometría `0x0041BC6D` solo un camino; visibilidad `0x004D78B6` ambos resultados de sus dos saltos (tres salidas).
- [x] Objetos Android NDK `-O1`/`-O2`: cache5 versus sin caché en geometría 8ins **332→348 B, stores 22→25**; geometría 7ins **224→240 B, 17→20**; visibilidad 7ins **360→368 B, 22→25**. Ninguna reduce cargas; **no integrar** ni atribuir FPS.
- [x] Contrato concreto de falla/reentrada Android documentado (verificar dirección/ancho/permiso de cada página con overflow 4GiB; snapshot R y PC antes de MEM; no reejecutar STORE, hilo/carreras, ART/JNI, x87/SEH, fallo nativo versus guest, pruebas reales). `audit_cfg_runtime_recovery.py` confirma guardias de CMake y builder, reporte **no apto para producción**; los guardias continúan.
- [x] No se cambió `pcode2c.py`, `guest.c`, CMake, el helper privado pinneado, gráficos ni la APK. Solo diagnósticos, tests sintéticos y documentación. [Informe superregiones](../performance/cfg/PHASE14F_MEMORY_FREE_SUPERREGIONS_2026-10-15.md) · [Contrato Android](../performance/cfg/PHASE14F_ANDROID_FAULT_RECOVERY_CONTRACT_2026-10-15.md).
- [x] Regresión final: **369 tests Python ejecutados, 4 omitidos, 0 fallidos** y **35/35 CTest** después de compilar el host; `py_compile` de las herramientas nuevas y `git diff --check` sin errores.
- [ ] Medir perfiles originales para regiones/lazos más grandes y encontrar ahorro CPU comprobable. La recuperación Android real sigue **pendiente y bloqueada**; TECNO y FPS no medidos.


### 2026-10-15 — Fase 14E: checkpoints x86 de memoria y reentrada sin repetir escrituras (OFFLINE)

- [x] **24 accesos a RAM guest:** 16 LOAD, 6 STORE y 2 lecturas absolutas `m` en el bloque `0x0041C017` de 29 instrucciones; antes de cada memoria se vuelcan a R los registros modificados y se actualiza el PC original del x86.
- [x] `0x0041C073`: diferir CF/OF constantes cero hasta después del LOAD; rechazar escrituras arquitectónicas prematuras, micro-CFG, STORE anterior a otro acceso que pueda fallar y demás reordenaciones sin prueba.
- [x] Unicorn x86 original: **24/24** puntos de fallo con R 8192 B, RAM, 8 GPR, 5 flags y PC equivalentes, **40/40** ejecuciones normales, **120/120** reentradas desde cada PC fallido usando el **x86 original** y el **traductor A de `pcode2c.Gen` sin caché**; se conservan las **6 STORE** una sola vez.
- [x] ARM64 estático: fast path inseguro **404 B / 32 loads / 22 stores**; checkpoint ingenuo **820 / 33 / 143**; checkpoint incremental **652 / 32 / 62**. Sigue costando +248 B y +40 escrituras frente al código sin checkpoint, sin información de FPS.
- [x] Alternativa sin memoria: **68 bloques y 158 instrucciones**, máximo 5 instrucciones. Dos candidatos (geometría `0x0041BAB6` y visibilidad `0x004D6FD0`) pasaron 120/120 A/B por variante, pero **no disminuyeron cargas, escrituras ni tamaño ARM64**.
- [x] El helper original privado de compilación conserva **los mismos bytes y SHA256**. No se cambiaron `pcode2c.py`, runtime/Android, CMake, renderizador ni APK. El flag `CODRECOMP_CFG14_GEOM_REGION` permanece **BLOQUEADO**, sin handler de señales Android.
- [x] Suite final: **355 tests Python**, 4 omitidos y ninguna falla; **35/35 CTest**; regresión del helper C privado original SHA-256 idéntico.
- [ ] Deoptimización de señales real con todas las garantías (páginas, threading, estado completo) o superregiones CFG sin RAM; A/B físico TECNO pendiente. [Informe 14E](../performance/cfg/PHASE14E_PRECISE_CHECKPOINTS_AND_RESUME_2026-10-15.md).


### 2026-10-15 — Fase 14D: epílogo original y FALLO de seguridad por excepciones

- [x] Oráculo Unicorn sobre el epílogo `0x00523CD9` (PE CoDSP original, Capstone y `pcode2c.Gen`): **128/128** retornos con cookie correcta y **128/128** saltos con cookie incorrecta verificados en 8 GPR, cinco EFLAGS materializados, R completo, PC, pila y RAM. `RET` también modifica `R+0x284` (EIP sombra), confirmado.
- [x] Recorrido ampliado de error hasta el primer `CALL 0x0051FF90` pasando por `PUSH 8` y `PUSH 0x533B68`: **64/64** errores y **64/64** retornos normales, incluida la pila y ESP. **El cuerpo llamado NO está verificado**. Control negativo con destino corrupto detectado.
- [x] Auditoría de excepciones en bloque de 29 instrucciones `0x0041C017`: Unicorn desmapea páginas reales de 4 KiB; el helper privado se interrumpe justo en el acceso correspondiente. **15/18** puntos de fallo de tres semillas tenían estado arquitectónico R/PC divergente; primer acceso **3/3** correcto. `--require-safe` devolvió **rechazo 4** como debe. **BLOQUEO REAL de seguridad** pese a 40/40 comparaciones normales.
- [x] `build_android.py` rechaza `--cfg14-geom-region` aun en ARM64 optimizado. **CMake ON ahora también bloqueado con `FAULT_STATE_UNSAFE`** por los 15/18 fallos; pruebas reales de rechazo CMake ON (exit 1) y configuración OFF correcta.
- [x] **Link AArch64 integral aislado del viejo candidato ON:** Ninja **292/292**, `lib/libmain.so` **229.834.608 B**, ELF ET_DYN AArch64, símbolo `codsp_cfg14_geom_41c017` definido mediante `llvm-readelf`. **No APK, no ejecución, no permiso de habilitación**.
- [x] Regresión: **343 tests Python (4 omitidos, 0 fallidos)** y **35/35 CTest**, control negativo del epílogo con destino alterado detectado.
- [ ] El TECNO no aparece en `adb devices -l`: solo WSA x86_64. No hay pruebas físicas ARM64, CPU/frame ni FPS nuevos. Próxima prioridad: deoptimización segura antes de accesos guest a memoria o regiones enteras sin accesos de memoria. [Informe](../performance/cfg/PHASE14D_EPILOGUE_FAULT_SAFETY_2026-10-15.md).


### 2026-10-15 — Fase 14C/D: oráculo original x86 y guard CFG productivo opt-in (OFF por defecto)

- [x] Nuevo oráculo independiente Unicorn sobre **29 instrucciones x86 originales** del bloque caliente de geometría `0x0041C017`, con direcciones invitadas **exactas** y **24 MiB de RAM**: **40/40** escenarios A y B coincidieron en 8 GPR, cinco flags materializados, R completo, memoria mapeada y salida `0x00523CD9`. **Cinco escenarios**, dos con alias read-after-write realmente ejecutado. Se conserva el epílogo original.
- [x] Helper derivado de `pcode2c.Gen` **en archivo privado ignorado** `recomp_out/codsp_cfg14_geom_41c017.c`, con cinco campos R cacheados, flush en salida, sin memoria plegada; 40 casos originales adicionales verificados con la forma final del helper. Control negativo: quitar el flush de ESP fue **detectado**.
- [x] Dispatcher en `runtime/guest.c` con guard por PC líder y módulo CoDSP, opción de CMake **`CODRECOMP_CFG14_GEOM_REGION=OFF`**, builder `--cfg14-geom-region` y fallback intacto a `dispatch_index_find/all_chunks` para el resto. Bloquea versión no verificada por SHA p-code, mapa y C privado.
- [x] **CMake/Ninja real ARM64 ON/OFF** en carpetas aisladas: OFF no enlaza helper ni define macro; ON compila `guest.c.o` y helper privado, símbolos `U/T` compatibles; `llvm-nm` confirma ausencia de referencia experimental en OFF. **NO se ha vinculado un .so o APK de juego completa con flag ON**.
- [x] Pruebas sintéticas y negativas de evidencia, firma SHA, memoria exacta, opción OFF y fallback. Suite Python **331 tests ejecutados, 4 omitidos, 0 fallidos** y **35/35 CTest** aprobados, además de smoke real del CLI con combinaciones inseguras rechazadas.
- [ ] Todavía pendiente: oráculo x86 del **epílogo completo** y efectos de excepciones/page faults durante cache R; prueba completa de APK ON y medida A/B de **ms de CPU/frame** en TECNO. Ninguna mejora FPS declarada. [Informe](../performance/cfg/PHASE14C_REAL_X86_GUARDED_RUNTIME_2026-10-15.md).

### 2026-10-15 — Fase 14C: primeras regiones CFG A/B verificadas OFFLINE (NO integradas)

- [x] Detección estricta de **227 bloques básicos / 855 instrucciones x86 / 4.469 microoperaciones** elegibles para experimentos de región integer-only entre siete funciones calientes. Se excluye x87 completo y metadata, CALL/RETURN, indirectos, CALLOTHER, divisiones peligrosas y ausencia de p-code.
- [x] Nuevo generador experimental aislado `cfg_region_lab.py`, basado en `pcode2c.Gen`: caché de vistas R disjuntas durante **bloque CFG completo**, etiqueta de entrada por PC, flush en cada salida y modo `start_only` con fallback simulado al traductor A para todas las entradas interiores. Ningún cambio productivo de runtime o APK.
- [x] Geometría `0x0041C017` (29 instrucciones): A/B start_only reduce ARM64 `.text 976→804 B`, cargas `51→40` y escrituras `48→31`. Recorrido `0x0047BD40` (15 instrucciones): `648→616 B`, `39→31` cargas y `37→33` escrituras. **Estadísticas de código estático; NO FPS.**
- [x] **696/696** casos A/B host en geometría (24 fast / 672 delegados), **360/360** en recorrido (24 fast / 336 delegados), comparando R completo, memoria plegada de 64 KiB y PC; se verificaron además **96 entradas rápidas por bloque** en ensayos anteriores. **Solo igualdad del traductor A/B, no independencia x86 ni alias reales.**
- [x] Estrategia con `all_entries` se **descartó** para los bloques largos por cargas/código ARM64 crecientes, pese a pasar A/B. Control negativo: una DLL privada sin volcado ESP fue rechazada por el diferencial.
- [x] Validación global: **325 pruebas Python**, 4 omitidas y 0 fallidas; **35/35 CTest** aprobados.
- [ ] Falta oráculo original Unicorn del bloque de 29 instrucciones completo, alias RAM real, integración guardada por PC y posterior A/B físico con TECNO. **La fase 14C de producción NO está terminada.** [Plan](../performance/cfg/PHASE14C_CFG_REGION_EXPERIMENT_PLAN_2026-10-15.md) · [Resultados](../performance/cfg/PHASE14C_CFG_AB_OFFLINE_RESULTS_2026-10-15.md).

### 2026-10-15 — Fase 14B, checkpoint siguiente: bloqueador binary80 y epílogo compartido

- [x] Auditoría real Unicorn x86 vs `pcode2c.Gen` sobre **256 entradas por checkpoint** en 5 instrucciones originales `FLD, FSUB, FMUL, FSUB, FSTP`. Coincidencias `binary80` de ST0: **256/256; 255/256; 126/256; 89/256** antes del pop. Los **167/256** estados distintos después de la cuarta instrucción hacen **NO ELEGIBLE** la sustitución nativa ciega de este subgrafo.
- [x] El método de leer ST0 físico fue contrastado con **11 instrucciones sintéticas FSTP m80** (representación Unicorn igual a memoria x86 en los 11 casos). Control estricto `--require-bitwise-st0` probó rechazo de **96 estados** con diferencias y retornó el código de error esperado **4**; no se marca una divergencia como éxito.
- [x] Auditoría del epílogo **`0x00523CD9`**: tres JMP de geometría convergen en una **función Ghidra separada** que compara ECX contra memoria `0x00563940`, retorna cuando coincide y salta a `0x00523CA8` en fallo. Comprobado el CFG frente al PE real con Capstone. El chequeo debe conservarse, no reemplazarse por un simple retorno ARM64.
- [x] Nuevos diagnósticos de solo lectura y pruebas sintéticas con targets alterados, p-code opaco, FPU extrema y condiciones de fallo. No se ha modificado motor, `pcode2c.py`, runtime, APK ni dispositivo; sin aumento de FPS medido.
- [x] Validación general de esta entrega: **315 Python (4 omitidas, 0 fallidas)** y **35/35 CTest** después de compilación host. No se habilitó ningún nuevo fast path.
- [ ] Pendiente 14B: equivalencia integral de `FPCW/FPSW/FPTAG`, precision x87, variantes de rama y ruta del fallo/RET. La siguiente optimización estructural debe escoger subgrafos seguros o mantener fallback, no convertir `float80` a `double` sin prueba. [Informe](../performance/cfg/PHASE14B_X87_BINARY80_SHARED_EPILOGUE_2026-10-15.md).


### 2026-10-15 — Fase 14B: oráculo x86 bifurcado y contratos de estado por byte (PARCIAL, offline)

- [x] Dos caminos x86 auténticos de `0x0041B8F0`: 20 instrucciones (JE no tomado) y 27 (JE tomado). `512/512` pruebas con 8 GPR, CF/PF/ZF/SF/OF, PC, tres regiones RAM y bytes R no tocados; Unicorn original vs `pcode2c.Gen` de LLVM-MinGW. **AF y x87 sin comprobar**.
- [x] Control negativo con DLL privada y PC tomado alterado: rechazo verificado, mientras la rama intacta siguió pasando.
- [x] Contratos `read-before-def/must-write/may-write/live-in/live-out` por byte en 450 bloques de siete funciones; `0x0041B8F0` con 187 LOAD, 67 STORE y 80 bytes x87 observados. Salidas externas conservan R y p-code opaco bloquea optimización.
- [x] CLI privado reproducible, checks SHA y pruebas sintéticas para alias de bytes, bucles, entradas y salida al dispatcher.
- [x] Suite de regresión: **301 pruebas Python** (4 omitidas), **35/35 CTest** aprobados; el dispositivo no se utilizó.
- [ ] Ampliar oráculo a binary80, estado de FPU y epílogos de la función antes de aplicar optimización nativa. Sin APK, TECNO ni FPS nuevos. [Informe 14B](../performance/cfg/PHASE14B_STATE_BOUNDARIES_ORACLE_2026-10-15.md).

### 2026-10-14 — Fase 14A: CFG de funciones completas verificado contra x86 original, offline

- [x] Nuevo analizador **por función original Ghidra B**, no chunks arbitrarios: micro-CFG, saltos relativos de p-code, llamadas, retornos, indirectos, entradas externas, bloques básicos, peligros, fallthrough y propiedad de rangos discontinuos.
- [x] Sobre CoDSP 1.5 **3.326 instrucciones/450 bloques básicos** de siete cuerpos calientes; cuatro instrucciones con p-code vacío bloqueadas, sin inventar operaciones ni convertir faltantes en NOP.
- [x] Capstone independiente sobre el PE original: **3.326/3.326 límites x86**, **342/342 clases/destinos de control verificables** coincidentes con el p-code; **0 discrepancias**. Esto **no** verifica EFLAGS/x87/RAM/PC finales, tiempo CPU ni FPS.
- [x] Nuevas herramientas puras `region_cfg.py`, `diagnostics/analyze_cfg_regions.py` y `diagnostics/verify_cfg_against_x86.py`; los tres insumos se verifican mediante SHA antes de emitir informes privados bajo `.local/profiles`.
- [x] Pruebas sintéticas con inyección de targets/tamaños erróneos, CFG compartido y huecos, entradas múltiples y rechazo de rutas inseguras.
- [x] Validación general: **287 Python (4 omitidas, 0 fallidas) y 35/35 CTest**. Sin modificar `pcode2c`, motor de ejecución, APK, ni archivos originales.
- [ ] **14B pendiente:** frontera byte a byte de R/EFLAGS/x87/RAM, ampliar oráculo independiente Unicorn desde el prólogo al cuerpo/ramas; luego 14C SSA y sustitución A/B reversible. **Ninguna APK ni FPS modificados**. [Plan maestro](../performance/cfg/PHASE14_CFG_ARCHITECTURE_MASTER_PLAN_2026-10-14.md) · [Informe 14A](../performance/cfg/PHASE14_CFG_INITIAL_RECOVERY_2026-10-14.md).

### 2026-10-14 — Fase 14: referencias CFG/BSP/colisiones preparadas, sin modificar el motor

- [x] Descargadas y verificadas como clones Git sparse bajo `.local/references` (ignorada): **ioq3**, **KILLTUBE/iocod** y **QEMU/TCG**. Recuperados solo subárboles relevantes, incluyendo `cm_trace.c`, `tr_bsp_cod1.c` y `tcg/optimize.c`; hashes exactos y licencias revisados.
- [x] **OpenCoD1**, **OpenMoHAA** y **Quake3e** ya existían y fueron reutilizados sin cambiar su revisión. Los seis orígenes y SHAs están en el manifiesto local; no se añade código ajeno al binario ni se publican recursos originales.
- [ ] CFG regional, análisis de entradas/salidas y reemplazo nativo **no iniciados**; se necesita mapa de funciones real, oráculo x86 independiente y A/B de ARM64 antes de introducir optimización en el motor. **60 FPS pendientes**. [Inventario y plan](../performance/cfg/PHASE14_CFG_REFERENCE_SOURCES_2026-10-14.md).

### 2026-10-14 — Fase 13: grandes bloques CoDSP geometry/traversal, ARM64 OFFLINE

- [x] Dos perfiles Simpleperf del TECNO archivados, sin usar el teléfono. A/B de **chunks completos de 1.500 instrucciones**: geometría chunk18: -1.186 cargas y -2.135 escrituras ARM64 estáticas; estructuras chunk88: -899 cargas y -1.528 escrituras usando `-O2` con FP estricto en vez de `-O1`.
- [x] **p4 completa** AArch64: `.text` 1.998.764→1.979.316 B (−19.448); cargas 82.258→77.931 (−4.327); escrituras 68.537→54.388 (−14.149). Recuentos estáticos, **NO ciclos ni FPS medidos**.
- [x] Compilación alternativa en visibilidad chunk152 **descartada** por más código (+17.636 B) y cargas (+2.310). `-Os`, temporales escalares, DCE y caché de registros de chunk no justificaron conservar cambios; prototipos retirados.
- [x] Opción opt-in `--core-hot-o2` / `CODRECOMP_CORE_HOT_O2=ON`, ARM64 y SHA de p-code verificado, únicamente CoDSP p0/p1/p4, con `-ffp-contract=off`, **OFF por defecto**; CMake aislado y orden de flags comprobados. **P8 excluida**. 35/35 CTest aprobados, suite Python **272 tests (4 omitidos, 0 fallidos)** y tests del constructor ampliados.
- [ ] Sin APK experimental instalada ni prueba A/B/A física; **60 FPS pendientes**, rendimiento jugable sin mejora verificada. [Informe](../performance/tecno/CPU_PHASE13_HOT_BLOCK_COMPILER_AB_OFFLINE_2026-10-14.md).

### 2026-10-14 — Fase 12: fusión estructural de pila x87, ARM64 offline

- [x] Identificados 18.194 grupos de siete copias exactas de registros x87 en 333.208 instrucciones CoDSP; nueva transformación optativa, con control de saltos internos y copia exclusiva de diez bytes por ranura.
- [x] Integrados `pcode2c --x87-stack-shift-outline`, ayudantes nativos y parche reversible de las 12 particiones en `build_android --x87-stack-shift-outline`; OFF por defecto. Restauración exacta de cada archivo comprobada.
- [x] Compilación NDK de p4 completo: .text AArch64 **1.998.764 -> 1.774.024 bytes**, ahorro **224.740 bytes (11,244 %)**; ejemplos de geometría y visibilidad también se redujeron cerca del 11 %.
- [x] Equivalencia R/RAM/U/PC en casos sintéticos a O0/O1/O2; **269 pruebas Python (4 omitidas)** y **35/35 CTest**. No se utilizó el teléfono ni se instaló una APK.
- [ ] FPS no medidos. Candidata estructural preparada para evaluación A/B/A futura. [Informe](../performance/tecno/CPU_PHASE12_X87_STACK_SHIFT_OUTLINE_OFFLINE_2026-10-14.md).

### 2026-10-14 — Fase 11: clasificación del solapamiento `memcpy` / `rd` / `wr`, OFFLINE

- [x] Reutilizados exclusivamente **dos perfiles Simpleperf ya archivados** de CoDSP p4, con 1.017/889 muestras nativas; recuperadas exactamente **974/840 muestras** a PC original, sin una nueva ejecución en TECNO ni en WSA.
- [x] Conteos inclusivos `memcpy` **409/353**, `rd` **233/204**, `wr` **154/123**; **todos los samples atribuidos a `rd`/`wr` tienen un marco `memcpy` más interno**. Eliminar el doble cómputo antes de priorizar costes; las clasificaciones de pila no equivalen a ciclos exclusivos ni a FPS.
- [x] Nuevo auditor puro con tres pruebas sintéticas aprobadas y suite completa **260 Python (4 omitidas, 0 fallidas)**; el extractor y las capturas de CPU permanecen privados. [Informe de fase 11](../performance/tecno/CPU_PHASE11_P4_INLINE_OVERLAP_OFFLINE_2026-10-14.md).
- [ ] Próxima fase: inspeccionar ensamblado ARM64 y producir un candidato verificable de ahorro de cargas/copias de estado `rd`/`wr` manteniendo semántica original; **ningún cambio de producción habilitado**, 60 FPS pendientes.

### 2026-10-14 — Fase 10: TECNO A/B/A físico de p4 x87 perfilado, NO aprobado

- [x] Ensayo con el TECNO CK6n (Camp Toccoa, Equilibrado, cámara estática): 55 s de juego por pasada y últimas 40 ventanas estables. Referencia **A1 26,00 FPS / 37,100 ms CPU**; candidata **B2 26,05 FPS / 36,980 ms CPU**; retorno **A2 25,90 FPS / 37,145 ms CPU**. B frente al promedio A: **+0,10 FPS (~0,39 %) y -0,1425 ms CPU (~0,38 %)**, sin mejora causal demostrada. P10 por ventanas, NO p10 de frames individuales.
- [x] A/B difieren únicamente en `lib/arm64-v8a/libmain.so`; recursos, resolución **2400 × 1080**, juego, partida y calidad equivalentes. Capturas de gameplay verificadas, sin evidencia de elementos visuales retirados. B1 careció de medición válida por fallo de sincronización de navegación automatizada, corregido para B2.
- [x] **Restauración automática exitosa:** APK originalmente instalada y `libmain.so` verificados por SHA-256; `training.svg` 30.360 bytes inalterado (hash coincidente en cada etapa y comprobación posterior). La aplicación quedó cerrada. **Mantener `CODRECOMP_X87_NORMAL_F2D_P4_PROFILED=OFF`**. Los tests de fases previas no son pruebas de FPS.
- [x] [Informe físico A/B/A](../performance/tecno/CPU_PHASE10_TECNO_P4_PROFILED_ABA_2026-10-14.md). Próximo bloque: identificar operaciones `rd`/`wr`/`memcpy` verdaderamente dominantes usando dos perfiles históricos y diferenciación inclusiva/exclusiva, antes de modificar código. Meta 60 FPS sostenidos **pendiente**; no repetir estas capturas.

### 2026-10-14 — Fase 9: auditoría del empaquetado x87, experimento descartado OFFLINE (0/5)

- [x] Validada una fórmula aritmética alternativa de binary80: **1.205.360 comparaciones C de bits** más 20.000 pruebas binary32/64 y **44.000 comparaciones R/RAM/PC** sobre instrucciones x87 reales (Clang O1/O2).
- [x] En función ARM64 aislada el código bajó de 324 a 320 bytes, pero en los tres chunks reales p4 no cambió el tamaño ni el histograma de instrucciones; la sección .text de libmain.so permaneció en **42.359.988 bytes** (diferencia 0). **No hay evidencia de mejora del juego.**
- [x] Prototipo de conversor y nuevo flag de Android **retirados**. Se conserva solamente un auditor reutilizable de símbolos/instrucciones ARM64 offline, cuatro tests Python y una prueba C del cálculo sin cambiar código de producción ni calidad gráfica.
- [x] **257 pruebas Python (4 omitidas), 35/35 CTest**; C original, ELF y biblioteca APK restaurados exactamente a referencia A por SHA-256; eliminado el flag CMake temporal. [Informe fase 9](../performance/tecno/CPU_PHASE9_X87_INTEGER_PACK_OFFLINE_2026-10-14.md). TECNO sin uso; 60 FPS pendientes.
- [x] Dos perfiles históricos: muestras inline inclusivas de memcpy **409/353**, rd **233/204**, wr **154/123**, f2d **366/329** y d2f **110/102**; estas categorías se solapan. Siguiente objetivo offline: costes de lectura/escritura de estado arquitectónico.

### 2026-10-14 — Fase 8: 124 PCs x87 observados en dos perfiles; SOLO OFFLINE (0/5)

- [x] Se correlacionaron **dos** perfiles históricos Simpleperf/ELF de Build ID idéntico, recuperando marcos inline DWARF (en vez de solo el primer marco `memcpy`/`f2d`), la línea C externa y el PC x86 original. Muestras `p4` examinadas: **1.017/889**; con PC guest recuperado: **974/840**. Dentro de las cuatro funciones originales calientes se localizaron **240/218 muestras** atribuibles a conversiones `f2d(rd(...),10)` (458 combinadas).
- [x] Selección reproducible: de 190 PCs observados, los **124 PCs con ≥2 muestras combinadas** representan **392/458 muestras (85,6 %)** de conversiones del subconjunto histórico, sin que las instrucciones ausentes se consideren frías. Manifiesto público **solo de identificadores numéricos**, ningún dato del juego.
- [x] `tools/recomp/patch_codsp_p4_f2d_selective.py --profiled`: guarda original/restauración por SHA-256; aplica fast path inline únicamente a **277 conversiones C** de los 124 PCs; conserva la selección alternativa de 520 sitios de fase 7. Nuevo `--x87-normal-f2d-p4-profiled` ARM64 OFF por defecto y mutuamente excluyente con p4 completo/selectivo; constructor restaura ambas variantes antes de una build normal.
- [x] Oráculo diferencial **22 instrucciones FLOAT reales de cuatro funciones** bajo Clang `-O1/-O2`: **44.000 estados R/RAM/PC completos** idénticos, incluyendo valores especiales x87. No prueba las 277 conversiones exhaustivamente ni sustituye a una CPU x86 independiente.
- [x] Compilada APK ARM64 perfilada sin instalar. `libmain.so` `.text`: A **42.339.912**, fase 6 **42.551.344**, fase 7 **42.374.108**, fase 8 **42.359.988 bytes**. Fase 8 aumenta `.text` **+20.076** vs A, pero evita **14.120 bytes** vs fase 7 y **191.356 bytes (~90,5 %)** del crecimiento de fase 6; tres chunks nativos modificados. **No hay prueba ni afirmación de ganancia FPS.**
- [x] Suite final **253 pruebas Python (4 omitidas) y 34/34 CTest**, y verificación por SHA-256 de fuente C p4, `libmain.so` ELF y biblioteca empaquetada **idénticas a A**, flags experimentales p4/dispatch OFF. [Informe](../performance/tecno/CPU_PHASE8_P4_PROFILE_GUIDED_X87_OFFLINE_2026-10-14.md). TECNO sin uso, 60 FPS pendientes.

### 2026-10-14 — Fase 7: conversión x87 SOLO en 520 sitios calientes de p4, OFFLINE (0/5)

- [x] Nuevos parche/reversor privados por hash `tools/recomp/patch_codsp_p4_f2d_selective.py`, `--apply/--restore/--analyze`: **520 conversiones `f2d(rd(...),10)` en 276 etiquetas PC x86** de cuatro funciones calientes recuperadas (517 muestras en un perfil histórico, **no 517 conversiones dinámicas**). El resto de p4 sigue en el convertidor anterior.
- [x] Nuevo flag ARM64 `--x87-normal-f2d-p4-selective` y CMake `CODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE=OFF`, requiere el x87 ya probado, rechaza combinarlo con p4 completo y verifica hashes de p-code y C parcheado. Las compilaciones normales restauran el parche privado byte a byte y no fuerzan hashes de juegos ajenos.
- [x] Oráculo diferencial **24 instrucciones x87 reales, seis de cada una de las cuatro funciones originales**; **48.000 comparaciones de R completo/RAM/PC** Clang `-O1/-O2` idénticas, incluidos valores especiales. No es ejecución nativa de x86 original ni cobertura de 520 casos.
- [x] ARM64 compilado/firmado offline: `libmain.so` `.text` A **42.339.912**, B selectivo **42.374.108**: **+34.196 bytes** en vez de los +211.432 de p4 completo, **177.236 bytes (83,8 %) de crecimiento evitado**. Solo **3 chunks nativos** cambiaron, frente a 16 de p4 completo. **Sin FPS nuevos ni TECNO.**
- [x] **250 tests Python (4 omitidas), 34/34 CTest**. Restauración final de p4 C y libmain nativa/APK **idénticas a A por SHA-256**, selectivo OFF y fast paths p1/p8 preservados. [Informe fase 7](../performance/tecno/CPU_PHASE7_P4_SELECTIVE_X87_OFFLINE_2026-10-14.md).
- [ ] Pendiente medir rendimiento real y visuales A/B/A/B en el teléfono solamente cuando se autorice. 60 FPS todavía pendiente.

### 2026-10-14 — Fase 6: extensión exacta x87 a CoDSP p4, OFFLINE (0/5)

- [x] Perfiles físicos **preexistentes**, sin ADB: entre las 40 funciones CoDSP calientes de un perfil histórico, **p1 847 / p8 827 / p4 789** muestras CPU. P1/p8 ya tenían el conversor x87 comprobado; en p4 hay **4.114 expresiones estáticas `f2d(...,10)`**, no llamadas por frame.
- [x] Extensión **experimental** `--x87-normal-f2d-p4` para ARM64, dependiente de `--x87-normal-f2d`, con `CODRECOMP_X87_NORMAL_F2D_P4=OFF` por defecto. Guardas SHA-256 de p-code y C p4 originales; no cambia el renderer ni la calidad.
- [x] Oráculo diferencial de **18 instrucciones FLOAT reales de p4 / 36.000 comparaciones completas de R/RAM/PC** (Clang `-O1/-O2`) sin diferencias para la variante inline. NO es oráculo independiente Intel x86 ni comprobación de toda p4.
- [x] APKs ARM64 A/B offline con firma V2/V3. Activar la vía rápida inline de p4 hace crecer `libmain.so` `.text` **+211.432 bytes** entre compilaciones equivalentes, concentrados en 16 funciones nativas. **FPS/CPU por frame no medidos: no declarar mejora.**
- [x] Prototipo de helper compartido `noinline` **rechazado por discrepancia de R en FLOAT_MULT con entrada x87 especial**; 36.000 verificaciones finitas sí coincidieron, pero no reemplazan la equivalencia completa. Revertido totalmente del código público; no se instaló.
- [x] **244 pruebas Python (4 omitidas) y 34/34 CTest**. APK/ELF ARM64 normal reconstruidos y verificados **idénticos a la referencia A**; NDK `CODRECOMP_X87_NORMAL_F2D_P4=OFF` y dispatcher experimental OFF. [Informe](../performance/tecno/CPU_PHASE6_X87_P4_OFFLINE_2026-10-14.md). TECNO no utilizado; 60 FPS pendientes.

### 2026-10-14 — Fase 5: despacho por último chunk, investigación OFFLINE (0/5)

- [x] Procesados sin ADB los dos perfiles físicos históricos Simpleperf con un nuevo auditor de Build ID/ELF, símbolo `guest_run` y líneas nativas inlined. De 7.953/6.541 muestras totales, `guest_run` obtuvo 506/432 (6,36 %/6,60 %), incluyendo 90/77 muestras en `dispatch_index_find`. Son muestras de CPU, **no tasa de llamadas ni FPS**.
- [x] Caché optativa `CODRECOMP_DISPATCH_LAST_CACHE` / `--dispatch-last-cache`, **OFF por defecto**, válida únicamente si el PC coincide con el chunk guardado y la generación no ha cambiado después de cargar/descargar módulos. Smoke de límites, huecos, recargas y llamadas anidadas aprobado.
- [x] Microbenchmark **PC Windows**, 403 chunks sintéticos: acelera un bloque repetido (~6,62 → ~4,28 ns/consulta) y ráfagas de ocho (~7,91 → ~5,32), pero **regresa** alternando dos (~6,13 → ~9,82) y con aleatorios (~8,63 → ~14,59). No se activa para producción.
- [x] APKs ARM64 A/B firmadas y compiladas **sin instalar ni usar el TECNO**. `libmain.so` `.text` B−A **+148 bytes**; `guest_run` **+172 bytes**. Retornado `CODRECOMP_DISPATCH_LAST_CACHE:BOOL=OFF` en build local.
- [x] **243 pruebas Python (4 omitidas), 34/34 CTest** correctas; informe [Fase 5](../performance/tecno/CPU_PHASE5_OFFLINE_DISPATCH_CACHE_2026-10-14.md). Se mantienen la APK estable, el juego y el objetivo de 60 FPS sin afirmaciones nuevas de mejora.
- [ ] Antes de habilitar: medir la tasa real de reutilización de chunks y comparar A/B/A en TECNO cuando vuelva a estar disponible, sin cambiar la escena ni la calidad.

### 2026-10-14 — Fase 4: eliminación de escrituras arquitectónicas, TECNO (0/5)

- [x] Análisis CFG por byte de registro con `tools/recomp/register_liveness.py`; opción `pcode2c.py --prune-hot-register-writes` **OFF por defecto** y protegida por SHA-256 de CoDSP 1.5. Solo p0/cuerpo `0x004196F0`, sin modificar p1/p8 o contenido de la escena.
- [x] **427 escrituras COPY muertas** eliminadas del generado, `−17.253` bytes C y `−3.868` bytes `.text` ARM64. Oráculo de **12.000 comparaciones ARM64** en 6 pares reales y 239 tests Python (4 omitidas), 34/34 CTest; sin diferencias de estado para los casos probados.
- [x] A/B/A físico en Camp Toccoa: FPS mediana **25,75 / 25,70 / 21,90** y CPU/frame **37,380 / 37,475 / 43,470 ms** (A1/B1/A2, 40 ventanas cada una, 45 °C batería). B1 no mejoró A1; la caída de A2 revela una variación ambiental importante, sin causa confirmada. **No hay mejora de FPS demostrada.**
- [x] Generado p0 y `libmain.so` originales restaurados y hashes verificados; save intacto. Se conserva el pass experimental desactivado. [Informe](../performance/tecno/CPU_PHASE4_ARCH_REGISTER_DCE_TECNO_2026-10-14.md).
- [ ] Próxima prioridad: muestreo de CPU e instrucciones ARM64 realmente ejecutadas bajo la misma escena, para evitar optimizaciones de código frío. 60 FPS sostenidos pendientes.

### 2026-10-14 — Fase 3: caché acotada de registros x86 en geometría, medida en TECNO (0/5)

- [x] Prototipo `pcode2c.py --cache-hot-registers` **OFF por defecto**, restringido al bloque lineal de `0x004196F0` en CoDSP `p0`. No altera soldados, geometría visible, HUD ni calidad; preserva aliasing de registros, flags, x87 y saltos fuera de su ámbito.
- [x] Fuente privada `p1` con parches FCOM/NaN preservada; `p0` reproducible y respaldado. Oráculo diferencial en **TECNO ARM64: 24 instrucciones reales / 49.152 casos** iguales contra traductor actual; 235 Python (4 omitidas) y 34/34 CTest.
- [x] Gameplay real Camp Toccoa, 40 ventanas A/B/A: **A1 25,70 / B1 cache 25,15 / A2 restaurada 25,20 FPS**; CPU/frame **37,495 / 38,200 / 38,130 ms**. Como A2 cae hasta B1, **NO hay ganancia demostrada ni regresión causal confirmada**. No habilitar la caché.
- [x] APK B x87 anterior exacta reinstalada y verificada SHA-256; autosave intacto. C generado experimental revertido **byte a byte** y objeto C recompilado realmente para evitar caché obsoleta de Ninja. [Informe](../performance/tecno/CPU_PHASE3_P0_REGISTER_CACHE_TECNO_2026-10-14.md).
- [ ] Próximo trabajo: liveness/SSA entre instrucciones y medición del ARM64 real; no anunciar 60 FPS (pendiente).

### 2026-10-14 — TECNO ARM64: x87 normal-f2d mejora FPS reales, A/B/A/B (0/5)

- [x] A/B/A/B en Camp Toccoa, TECNO CK6n fisico, Equilibrado y 40 ventanas estables/corrida: **A1 24,90 / B1 25,70 / A2 25,00 / B2 25,85 FPS**; medias A **24,95** vs B **25,775**, mejora **+0,825 FPS (+3,31 %)**.
- [x] CPU/frame A promedio **38,570 ms** vs B **37,270 ms** (ahorro **1,300 ms/frame**), p10 por ventana 24,35 vs 25,20. B funciona con `--hot-x87-transform --x87-normal-f2d` sin modificar HUD/calidad; guardado comprobado identico SHA-256.
- [x] Ensayo adicional `-O2` solo en geometria CoDSP p1: C1 **25,90 FPS mediana / 19,90 p10 / 37,180 ms CPU**, sin mejora CPU ni FPS medianos frente a B2. **Descartado; codigo de flag reverted y APK B reinstalada y verificada byte a byte**. 231 tests Python (4 omitidas), 34/34 CTest.
- [ ] Meta TECNO **60 FPS sostenidos todavia pendiente**: quedarian ~20,6 ms/frame por ahorrar a partir de B. No extrapolar la mejora a otras misiones ni generalizar x87 sin oraculo independiente. [Informe completo](../performance/tecno/TECNO_X87_NORMAL_F2D_GAMEPLAY_ABAB_2026-10-14.md).

### 2026-10-14 — WSA: conversion x87 f2d, A/B/A sin mejora (0/5)

- [x] Recuperada y auditada la build x86_64 `--x87-normal-f2d`, compilada y firmada; `CODRECOMP_X87_NORMAL_F2D=ON` solo en CoDSP p1/p8. APK A y dos saves verificados intactos antes del ensayo.
- [x] Camp Toccoa real y GL4ES, misma vista y perfil Equilibrado: **A1 55,10 FPS / 17,31 ms CPU**, **B1 x87 54,55 / 17,765**, **A2 restaurada 55,35 / 17,29**; 20 ventanas de ~1 s en cada captura y cap 60 FPS. Los percentiles bajos de FPS son de ventanas, no de frames individuales.
- [x] B no acelera WSA: aproximadamente **-1,22 % FPS** y **+2,69 % CPU/frame** respecto a la media A. Se reinstalo A con `libmain.so` identica a la referencia SHA-256; candidate B y evidencia permanecen privadas. El flag sigue **OFF** por defecto, 60 FPS TECNO **pendiente**, contador ARM64 **0/5**. [Informe](../performance/wsa/WSA_X87_NORMAL_F2D_ABA_2026-10-14.md).
- [ ] Hacer A/B/A fisico en TECNO ARM64 (sin extrapolar WSA); completar el perfil dinamico de los costes CPU antes de otro fast path.

### 2026-10-14 — Fase 2: condiciones x87 FCOMP contrastadas con x86 real (0/5)

- [x] `verify_fcom_condition_oracle.py`: Unicorn ejecuta `FLD` y `FCOMP` originales sobre `float32`; una DLL host independiente invoca el helper FCOM optativo del proyecto, **sin activar el fast path en Android**.
- [x] **1.037/1.037 pares** (13 casos especiales + 1.024 pseudoaleatorios finitos) coinciden en **C0/C1/C2/C3**, máscara x87 `0x4700`. Un C0 intencionalmente alterado fue detectado en los **13 casos fijos**. Se agregan seis pruebas sintéticas.
- [ ] **No** se comparan TOP, exception flags, estado binary80 completo ni pila x87. Es una comprobación parcial, **no certifica FCOM como sustituto general** ni demuestra FPS ARM64. El flag de producción permanece **OFF**, contador **0/5**. [Informe](../performance/tecno/CPU_PHASE2_FCOM_CONDITION_ORACLE_2026-10-14.md).

### 2026-10-14 — Fase 2: oráculo x87 de salida `float32` (0/5)

- [x] Implementado **`verify_x87_window_oracle.py`** con x86 Unicorn y el `pcode2c.Gen` real, abarcando cinco instrucciones de la función `0x0041B8F0`: `[0x41B960,0x41B973)`, `fld/fsub/fmul/fsub/fstp`.
- [x] **1.024/1.024 estados finitos** con resultado `float32` **idéntico bit a bit**, misma memoria de pila y operandos, registros generales y PC. Control negativo alterando un byte del resultado **rechazado**.
- [x] Cinco pruebas offline sintéticas y bloqueo por hashes PE/p-code e identidad Capstone de las instrucciones; archivos privados nunca publicados, juego estable intacto.
- [ ] Aún **NO** equivalencia del estado x87 completo `binary80`, control/status word, FCOM, NaN o excepciones; no equivale a la función completa ni a mejora ARM64. **0/5**. [Informe](../performance/tecno/CPU_PHASE2_X87_WINDOW_ORACLE_2026-10-14.md).

### 2026-10-14 — Fase 2: oráculo x86 real ejecutado y validado (0/5)

- [x] `verify_x86_prefix_oracle.py` ejecuta en **Unicorn x86** 20 instrucciones auténticas del prólogo de `0x0041B8F0` y las compara con el C compilado desde **`pcode2c.Gen` real**; binario y p-code privados verificados con SHA-256 fijo antes de empezar.
- [x] **1.024/1.024 ejecuciones correctas** sobre memoria/estado sintetizado, **512 rutas JE tomadas + 512 no tomadas**; equivalencia exacta de 8 registros, CF/PF/ZF/SF/OF, tres regiones de memoria y PC. Inyección intencionada de un PC incorrecto **detectada**.
- [x] Siete pruebas offline adicionales de seguridad/procedencia, rechazo de salidas no ignoradas, destinos de salto falsos y traducciones no soportadas. El C/DLL original derivado se queda bajo `.local/profiles`; ninguna APK o shader del juego cambia.
- [ ] Ampliar después de la primera rama y cubrir **x87 binary80**, AF, estados excepcionales y CFG del resto de la función; esta prueba no certifica los 553 x86 ni mide FPS. Contador TECNO **0/5**. [Informe del oráculo](../performance/tecno/CPU_PHASE2_X86_PREFIX_ORACLE_2026-10-14.md).

### 2026-10-14 — Fase 2 CPU: 0x0041B8F0 delimitada y laboratorio ARM64 auditado (0/5)

- [x] **Auditoría reproducible** de `0x0041B8F0`: 553 instrucciones x86 / 3.957 p-code, dos intervalos Ghidra y chunk 19 compartido por 12 funciones; **1.789 COPY**, 187 LOAD, 67 STORE, 418 operaciones flotantes. La lista de 100 sitios nativos cubre solo 127 de 270 muestras, así que la selección de ventanas no es un perfil completo.
- [x] `tools/recomp/diagnostics/audit_hot_function.py` cruza p-code, propiedad del cuerpo y sitios ARM64, sin publicar material comercial; rechaza mapa inconsistente, intervalos solapados, propiedad ambigua y muestras duplicadas. Pruebas sintéticas incorporadas.
- [x] **Experimento sintético x87:** comparar 7 copias de registros de 10 bytes mediante `rd/wr` frente a `memcpy` (respetando huecos de 6 bytes): **20.000 casos idénticos**, pero **29 instrucciones AArch64** en ambas variantes con NDK Clang `-O1` y `-O2`. Se **descarta** el parche simplista: no hay ahorro nativo demostrado.
- [ ] Próxima tarea: validar CFG completo, aliasing, EFLAGS y x87 de un único subbloque; crear oráculo independiente antes de transformar código. No se modificó el motor/renderer ni la APK. TECNO no conectado; **0/5**. [Auditoría y decisión](../performance/tecno/CPU_PHASE2_41B8F0_AUDIT_2026-10-14.md).

### 2026-10-14 — Ensayo A1/B/A2 real de Camp Toccoa: ANGLE sin ganancia en WSA (0/5)

- [x] WSA x86_64 en **Camp Toccoa, spawn 3D**, guardado idéntico, cámara estática, **Equilibrado** y cap de 60 FPS; tres capturas de ~30 s cada una, 20 ventanas ~1 s analizadas por captura, sin menú/carga.
- [x] **A1 GL4ES:** 54,75 FPS medianos / 50,2 FPS p10 / 17,54 ms CPU; **B ANGLE→Vulkan:** 55,15 / 47,6 / 17,80; **A2 GL4ES:** 55,20 / 54,6 / 17,43. B apenas +0,175 FPS (**+0,318 %**) frente a la media de ambos controles A; p10 B por debajo de ambos. **No hay mejora de rendimiento demostrada**.
- [x] Verificado ANGLE+Vulkan antes/después de la captura B mediante **Logcat del mismo PID 10539**, contexto WSA Vulkan 1.3 AMD. Mundo 3D y HUD visibles; captura comparada con GL4ES **SSIM 0,995943** en región de 1.280×540, no certifica toda la campaña.
- [x] Dos guardados privados respaldados y verificados sin alteración tras A/B/A; WSA nuevamente **sin ANGLE**, configuración driver en `null`, APK A1 de referencia intacta. Herramientas nuevas: guard de saves, `--backend angle` con identidad Vulkan y resumen A/B/A con test de falsos positivos.
- [ ] Mantener **GL4ES producción** y estrategia CPU actual; próxima fase, `0x0041B8F0` ARM64 con equivalencia y benchmarks físicos al conectar TECNO. **0/5**. [Informe completo](../performance/graphics/ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md).

### 2026-10-14 — Punto de control consolidado y continuidad técnica (0/5)

- [x] Estado integral a fecha actual, referencias, arquitectura, ensayos ANGLE/Vulkan, hashes y límites recogidos en [**PROJECT_STATUS_CHECKPOINT_2026-10-14.md**](checkpoints/PROJECT_STATUS_CHECKPOINT_2026-10-14.md).
- [x] Verificados `main` limpio en `1906ace`, [CI de `1906ace` aprobado](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38598366421), WSA API 33 x86_64 como único dispositivo; no hay TECNO ARM64 conectado.
- [x] Estado de referencia: GL4ES estable, ANGLE desinstalado, settings de driver `null`; **60 FPS TECNO** sin confirmar, baseline física 24,70 FPS/38,895 ms CPU-frame y contador **0/5**.
- [ ] Continuar con validación de **escena 3D Camp Toccoa** e imagen A/B bajo GL4ES vs ANGLE en WSA; medir FPS solo si hay escena idéntica y proceso reproducible. La optimización CPU ARM64 sigue pendiente de teléfono.

### 2026-10-14 — ANGLE x86_64 compilado y ejecutado sobre Vulkan en CallofRecomp WSA (0/5)

- [x] Build Linux upstream real **exitosa**, [GitHub Actions #38591658796](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38591658796) (**34m50s**): `AngleLibraries.apk` x86_64 **8.162.364 bytes** y SHA-256 **`40a48ae3cb3ee6051768c6b7f9d23fea3e3eeea7e1876e4d833c950ab275baa3`**, commit/árbol oficial pinneado concordante, APK de `org.chromium.angle` con firma válida **CN=Unknown** (NO Google).
- [x] **Ensayo real WSA:** `org.callofrecomp/.GameActivity` reanudada, Logcat del **mismo PID y hora** confirma `ANGLE debug package enabled: org.chromium.angle` y `Renderer (Vulkan 1.3.0 (AMD Radeon Graphics))`. En el tercer ensayo el verificador registró `angle_vulkan_execution_verified=true`. Se corrigieron dos falsos negativos de la herramienta: `JUGAR` en UIAutomator y variante `ANGLE debug package enabled` en Android.
- [x] Capturas reales del **menú** con ANGLE/Vulkan y GL4ES nativo: elementos visibles sin diferencias evidentes en inspección visual, no comparación píxel a píxel. Los cuatro errores GLSL iniciales concuerdan con **sondas de capacidades** de GL4ES (`testTextureCubeLod` y 3× `testGLSL`); no ocultar avisos ni concluir que el mundo 3D sea correcto.
- [x] Rollback WSA sin errores, paquete ANGLE ausente, preferencias `null`, `libmain.so` estable A1 con SHA-256 intacto. No se registraron FPS, no se validó gameplay 3D completo, ni se probó TECNO: **0/5**. [Informe del hito y pendientes](../performance/graphics/ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md).

### 2026-10-14 — WSA: entrada optativa a GameActivity para prueba ANGLE (0/5)

- [x] `angle_wsa_launcher.py`: localizador puro del botón Android `Jugar` (paquete, clase, estado clicable/habilitado y límites) y comprobación estricta de `GameActivity` reanudada. Sin coordenadas fijas ni clics sobre paquetes ajenos.
- [x] `angle_wsa_trial.py --enter-game` incorpora el paso **explícitamente optativo** de accesibilidad `uiautomator`, eliminación del XML temporal y verificación de Activity; conserva el rollback y la prohibición de medir FPS sin escena real. Pruebas sintéticas de errores y aceptación incorporadas.
- [x] **Avance posterior:** [build manual #38591658796](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38591658796) terminada con éxito y ANGLE/Vulkan verificado en WSA; ver [resultado posterior](../performance/graphics/ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md). El contador TECNO sigue **0/5**.

### 2026-10-14 — Captura Logcat ANGLE ligada a proceso y tiempo real (0/5)

- [x] El ensayo WSA ahora toma la hora **del dispositivo** antes del lanzamiento y analiza `adb logcat -v epoch`; rechaza mensajes anteriores, de otro PID o sin formato reconocible. Solo acepta evidencia ANGLE/Vulkan cuando tanto la selección de paquete como el renderer Vulkan proceden del **mismo proceso de CallofRecomp en esa ejecución**.
- [x] Verificado el formato Logcat realmente soportado por WSA API 33 y ampliadas pruebas sintéticas contra falsos positivos por registros históricos y ajenos. El launcher Java no crea por sí solo un contexto GLES: se debe pulsar **Jugar** dentro del período de prueba antes de atribuir un renderizador al juego.
- [ ] Sigue pendiente una compilación completa de ANGLE; **ningún ensayo real del driver**, nueva comparación FPS o cambio de APK. Contador **0/5**.

### 2026-10-14 — WSA ANGLE: prueba transaccional aislada preparada (0/5)

- [x] Añadido `tools/recomp/diagnostics/angle_wsa_trial.py` con **preflight de solo lectura**, verificación offline de APK antes de instalar, selección exclusivamente para `org.callofrecomp`, salida de Logcat y restauración de settings/paquete en bloque `finally`.
- [x] Preflight real WSA: API 33 x86_64, juego debuggable **no ejecutándose**, no existe ANGLE instalado, ajustes del driver `null`, ningún bloqueo de entorno. No se ejecutó la opción `--execute` ni se cambiaron preferencias.
- [ ] La ejecución GitHub Actions `38591658796` sigue sin APK validada; cualquier eventual carga de ANGLE y FPS del juego deben probarse por separado. [Guía](../performance/graphics/ANGLE_BUILD_PIPELINE_2026-10-14.md). Contador oficial **0/5**.

### 2026-10-14 — Build Linux ANGLE preparado para ejecución manual, APK aún ausente (0/5)

- [x] Añadidos script Linux fijado al commit oficial ANGLE `43140711d13063716fd32a15de829885d0bce469`, `gclient sync` con dependencias Android, build `x64` con Vulkan, SHA-256 y manifiesto de procedencia.
- [x] Nuevo workflow GitHub Actions **solo manual** (`workflow_dispatch`), con permisos `contents:read`, sin activación al publicar commits; los runners gratuitos pueden carecer de recursos. Se añadió comprobador offline `verify_angle_apk.py` que exige identidad de paquete, firma Android, archivos ELF x86_64 y digest cuando se facilita.
- [ ] **Primera compilación Linux en GitHub Actions iniciada**: [run #38591658796](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38591658796), resultado todavía pendiente. No existe APK validada todavía, no se instalaron APK/driver en WSA, no hubo ensayo ANGLE→Vulkan ni comparación FPS. [Procedimiento reproducible](../performance/graphics/ANGLE_BUILD_PIPELINE_2026-10-14.md). Prioridad oficial TECNO CPU/GPU intacta, **0/5**.

### 2026-10-14 — ANGLE oficial descargado; GLES2→Vulkan investigado sin modificar WSA (0/5)

- [x] Clonado **ANGLE oficial** desde Chromium Git: commit fijo **43140711d13063716fd32a15de829885d0bce469**, árbol Git **06315a7275a6cc870b55e2e32c6eab165604357d**. Los dos remotos (Chromium y espejo Google/ANGLE GitHub) coinciden; `git fsck --full --no-reflogs` PASS, checkout limpio. Ruta `.local/profiles/angle-research/angle-src` privada/ignorada.
- [x] Comprobado el código real ANGLE/EGL/Vulkan y su guía Android: **GL4ES → GLES2 ANGLE → Vulkan** encaja sin reescribir wrappers clásicos; la selección de driver por APK requiere app debuggable/Java-launch o root.
- [x] Auditoría **WSA real, solo lectura**: Android **API33 x86_64**, CallofRecomp instalada **DEBUGGABLE**, actividad **GameActivity extends SDLActivity**. `org.chromium.angle` y `org.chromium.angle.agi` **NO** están instalados; todos los ajustes de ANGLE permanecen **null**.
- [x] Restricción de build: doc oficial ANGLE Android **requiere Linux**, pero **WSL no tiene distro**; `gn/gclient/autoninja` ausentes y dependencias ANGLE todavía sin `gclient sync`. **Solo se descargó el código fuente, NO se compiló ni ejecutó AngleLibraries.apk.**
- [x] Auditor de entorno `tools/recomp/diagnostics/angle_readiness.py`, pruebas sin modificaciones del sistema, informe JSON privado y tests sintéticos que nunca confunden selección de driver con ANGLE/Vulkan realmente ejecutado. `libmain.so` de referencia A1 de CallofRecomp en WSA permanece idéntica.
- [ ] Próximo bloqueo: entorno Linux/depot_tools + build ANGLE **x86_64** de procedencia verificada, carga por paquete solo para CallofRecomp, Logcat identificando **Vulkan**, equivalencia visual y comparación de FPS A/B/A real. [Informe](../performance/graphics/ANGLE_GLES_VULKAN_FEASIBILITY_2026-10-14.md). Contador **0/5** sin cambios.

### 2026-10-14 — Mesa Zink 26.2.4 descargado y descartado para WSA por requisitos Vulkan (0/5)

- [x] Fuente oficial de Mesa/Zink **26.2.4 descargada** (68.613.948 bytes), SHA-256 cotejado con el release de Mesa: `bce5f7fbebb934373b86c999a064d52fb5065878dc57f287f95346648ec832e9`. Conservada en `.local/profiles/mesa-zink/` (ignorado, NO se sube a GitHub).
- [x] Extraído `VP_ZINK_requirements.json` de la versión fijada; su perfil `VP_ZINK_gl21_baseline` exige Vulkan >=1.2, features y extensiones específicas, no únicamente compatibilidad con Vulkan 1.0.
- [x] Censo Vulkan **ejecutado en WSA x86_64** usando NDK, sin permisos especiales ni alterar drivers: AMD Radeon Graphics Vulkan 1.3, `alphaToOne=0`, sin `VK_KHR_maintenance5`, `VK_KHR_swapchain_mutable_format` ni `VK_EXT_border_color_swizzle`. **4 requisitos obligatorios comprobados ausentes**, con promociones Vulkan core 1.2/1.3 contabilizadas correctamente.
- [x] Script de comparación `analyze_zink_requirements.py` y 5 pruebas unitarias sintéticas; probe C independiente compilado para WSA y validado sintácticamente para ARM64. No se intentó ejecutar Zink ni atribuir mejoras de FPS.
- [x] Revisión de integración: CallofRecomp usa SDL2/EGL GLES2 + GL4ES, mientras Zink es Gallium desktop OpenGL → Vulkan, con requisitos Mesa/NIR/frontend/contexto; no existe cambio directo de backend solo por copiar una librería.
- [ ] **Decisión WSA: no integrar Mesa Zink ahora**; el TECNO físico debe comprobarse antes de descartarlo en Mali. Posible alternativa WSA a evaluar: ANGLE detrás de GL4ES, sin promesas de FPS. [Informe detallado](../performance/graphics/MESA_ZINK_FEASIBILITY_2026-10-14.md).
- [x] APK original GL4ES, guardados, datos del juego, referencia FPS y estrategia vigente intactos. Contador de intentos A/B **0/5**.

### 2026-10-14 — Transformaciones y proyección de matrices OpenGL hacia Vulkan (0/5)

- [x] `gl_vk_state` reconoce `glTranslatef/d`, `glRotated/f`, `glScale[d/f]`, `glOrtho` y `glFrustum`, aplicando `M←M×T` en matrices MODELVIEW/PROJECTION/TEXTURE, con validación de ejes, dimensiones de frustum y valores no finitos.
- [x] `gen_gl.py` produce hooks de los ocho wrappers x86 con `F32` o `F64(esp, 0/2/4/6/8/10)` correctamente; **486 wrappers regenerados**, observación opcional sin sustituir GL4ES.
- [x] `gl_vk_state_mvp` exporta `PROJECTION×MODELVIEW` y nuevo shader `wsa_matrix.vert` adapta Y y rango Z a Vulkan. La nueva escena WSA `--scene matrix` dibuja **tres objetos indexados** (traslación, rotación, escalado, ortho y perspectiva), confirmados visualmente.
- [x] Primera ejecución detectó correctamente un error `dlopen: cannot locate symbol hypot` en la app independiente; se corrigió el enlace con **`-lm`**. La app inició y renderizó con éxito; el log incompleto se descartó.
- [x] Ejecución WSA FIFO aislada completa: **1.276 frames / 17,008 s, 75,024 FPS**, CPU del hilo **2,38144 ms/frame**, 3 dibujos/frame a 1280×720. **No son FPS del juego ni demuestran mejora frente a GL4ES.**
- [x] Pruebas: **140 Python (4 omitidas), 33/33 CTest**, comprobación de sintaxis ARM64, build WSA con shader SPIR-V validado; regresiones de build depth y alpha. Builds diagnósticos del juego `--gl-vk-state-capture` ON y normal OFF aprobados. **Estado final OFF**.
- [x] APK original de CallofRecomp en WSA permanece byte a byte igual a A1 por SHA-256; datos guardados y perfiles anteriores intactos. No se repitieron benchmarks del juego.
- [ ] Sigue pendiente la traducción de vertex arrays/draw calls del juego, texture uploads/samplers, combiners multitextura y equivalencia visual completa. [Informe de matrices](../performance/graphics/WSA_GL_MATRIX_BRIDGE_2026-10-14.md). Estrategia oficial y contador **0/5**.

### 2026-10-14 — TexEnv MODULATE/REPLACE y descarte alfa Vulkan (0/5)

- [x] Modelo tipado GL registra `glTexEnv[i/f/iv/fv]` en su **unidad activa**, con modos GL_MODULATE (por defecto) y GL_REPLACE; DECAL, BLEND, ADD y COMBINE continúan en **fail-closed** sin shader equivalente.
- [x] `gen_gl.py` incorpora los cuatro hooks de estado `glTexEnv*` sin editar manualmente 486 wrappers ni sustituir OpenGL/GL4ES en la APK normal.
- [x] Nuevo prototipo Vulkan independiente WSA `--scene alpha` dibuja **2 quads indexados** usando una textura RGBA8 con píxeles alfa 0/255 y un fragment shader de `discard` para `GL_GREATER` con umbral 0.5.
- [x] Validación visual WSA: gradientes a la izquierda con MODULATE, colores amarillos originales a la derecha con REPLACE, huecos transparentes en ambos. **1.276 frames / 17,004 s = 75,043 FPS**, CPU del hilo **1,99041 ms/frame**, FIFO 75 Hz: **no representa FPS del juego**.
- [x] Tests de estados y generador, 11 tests de parser de escena Vulkan, sintaxis NDK ARM64, compilación de APKs prototipo texture/depth anteriores. **138 tests Python (4 omitidas), 32/32 CTest** aprobadas.
- [x] Registro anterior de gameplay y datos A1/A2/B1/A3 conservados sin repetir; APK A1 original instalada y SHA-256 verificado.
- [ ] Quedan otros modos TexEnv, multitextura/combiners, uploads/samplers del juego, matrices y traducción completa de draw calls. [Informe de avance](../performance/graphics/WSA_VULKAN_TEXENV_ALPHA_2026-10-14.md). Contador **0/5** sin cambios.

- [x] Cierre: compilaciones x86_64 del juego con captura **ON** y normal **OFF** verificadas, final `CODRECOMP_GL_VK_STATE_CAPTURE=OFF` en cache; APK original WSA intacta por hash SHA-256.
### 2026-10-14 — Puente tipado OpenGL → Vulkan: captura de estados del juego real (0/5)

- [x] Modelo `gl_vk_state` para depth, blending, stencil, culling, alpha test, matrices column-major y unidades de textura; rechazo explícito de enums/estados sin equivalencia.
- [x] `gen_gl.py` genera observación de estado **después** de las llamadas host OpenGL/GL4ES; `--gl-vk-state-capture` OFF por defecto y el código del observador no se compila en la APK normal.
- [x] Conversor `wsa_vk_gl_state_map.c` a estructuras Vulkan depth/stencil, blend y raster; prototipo WSA revalidado visualmente con la escena texturizada/transparente existente. No hay renderer Vulkan del juego.
- [x] **Una sesión real de CallofRecomp en WSA** entre menú y entrenamiento: **164 snapshots, 0/164 declarados traducibles**, flags de incompatibilidad **0x19** (capacidad desconocida, textura, GL heredado). Los incrementos acumulados de llamadas **NO** son FPS ni CPU/frame.
- [x] Registro privado `.local/profiles/vk_bridge`, analizador y pruebas reproducibles; APK A1 original reinstalada y hash de `libmain.so` verificado.
- [x] Histograma por familias (tex state/upload, matrix, vertex, lights, buffers, otros) implementado para **capturas futuras**, ausente en el log existente; no se repitieron benchmarks históricos.
- [ ] Pendiente: equivalencia de `glTexEnv`, transformaciones GL, alpha discard, texturas múltiples, estado de buffer/arrays y renderer Vulkan completo. [Informe](../performance/graphics/GL_VK_STATE_BRIDGE_2026-10-14.md). Estrategia oficial **0/5**.

### 2026-10-14 — Vulkan experimental: profundidad, stencil y alpha blend probados en WSA (0/5)

- [x] `--scene depth` en APK de prueba independiente: 5 attachments `VkImage` depth+stencil (uno por framebuffer), formato **D32_SFLOAT_S8_UINT**, memory DEVICE_LOCAL, clear depth 1/stencil 0.
- [x] Renderpass de color+depth, pipeline opaco con **depth LESS_OR_EQUAL y stencil ALWAYS/REPLACE**, segundo pipeline **stencil EQUAL 2, sin depth write, alpha blend SRC_ALPHA / ONE_MINUS_SRC_ALPHA**.
- [x] Cuatro `vkCmdDrawIndexed` por frame (fondo, primer plano, objeto rechazado en profundidad, overlay transparente recortado). Confirmación visual WSA en PNG privado.
- [x] Compilación/validación de nuevo `wsa_overlay.frag` a SPIR-V y módulo `wsa_vk_depth.c` con detección de formato, creación y cleanup por swapchain.
- [x] **WSA FIFO 1280×720:** **1.276 frames / 17,012 s = 75,005 FPS**, CPU del hilo de prueba **2,20648 ms/frame**; NO representa CallofRecomp. Corrida inicial 75,096 FPS y marcadores ajustados en segunda corrida; no se repitieron benchmarks históricos.
- [ ] Próximo trabajo: traductor tipado de estados GL fixed-function (depth/blend/stencil/alpha, matrices, texturas) antes de integrar backend al juego. Estrategia y contador **0/5** intactos. [Informe](../performance/graphics/WSA_VULKAN_DEPTH_STENCIL_BLEND_2026-10-14.md).

### 2026-10-14 — Vulkan experimental: VkImage texturizada, sampler y descriptor probados (0/5)

- [x] `--scene texture` en APK Vulkan independiente de WSA: **64×64 RGBA8** generado por la CPU, `VkBuffer` de staging, memoria HOST_VISIBLE+HOST_COHERENT, `vkCmdCopyBufferToImage` sobre imagen DEVICE_LOCAL, layout transitions hasta SHADER_READ_ONLY_OPTIMAL.
- [x] Pipeline optativo con `VkImageView`, `VkSampler` nearest, `VkDescriptorSetLayout`, pool/set combinado y `sampler2D` en fragment shader. La captura física WSA muestra cuadros **sampleados de la textura** sobre la malla indexada.
- [x] **1.277 frames / 17,000 s = 75,117 FPS FIFO**, **1,989 ms CPU del hilo/frame**, resolución 1280×720. Son FPS del prototipo aislado, **no** de CallofRecomp ni mejora demostrada de FPS.
- [x] Marcadores `VK_TEXTURE_READY` y pruebas del parser para distinguir `clear`, `mesh` y `texture`; datos privados en `.local/profiles/wsa_vulkan_ab/texture-fifo`. APK original del juego verificada por SHA-256 sin cambios.
- [x] Pruebas del bloque: **129 Python (4 omitidas), 31/31 CTest** y syntax check ARM64 sin errores. Referencia GL4ES instalada verificada por SHA-256 byte a byte, sin repetir benchmarks del juego.
- [ ] Depth/stencil, blending, texturas múltiples y estados fixed-function, integración a renderer del juego y A/B/A real pendientes. [Informe técnico](../performance/graphics/WSA_VULKAN_TEXTURE_2026-10-14.md). Estrategia vigente, **0/5 intentos**.

### 2026-10-14 — Vulkan experimental: primera geometría indexada con shaders SPIR-V (0/5)

- [x] `--scene mesh` añadido a la APK Vulkan de diagnóstico independiente. Compilación GLSL → SPIR-V con `glslc` y validación `spirv-val` del NDK; carga de assets Android y creación de `VkGraphicsPipeline`.
- [x] Render real con `VkBuffer` de vértices/índices, memoria `HOST_VISIBLE|HOST_COHERENT`, push constants, atributos posición/color/UV y `vkCmdDrawIndexed` (4 vértices, 6 índices, patrón checker procedural). Captura de WSA muestra la geometría coloreada.
- [x] WSA Vulkan 1280×720 FIFO: **1.276 frames / 17,013 s = 74,999 FPS**, **1,918 ms de CPU/frame del hilo de prueba**, mediana de ventanas 74,993 FPS, p10 74,910. Limitado por 75 Hz: **no es FPS del juego**.
- [x] Clear anterior **75,014 FPS / 1,902 ms CPU/frame**; no puede inferirse diferencia de carga GPU por FIFO. Evidencia privada en `.local/profiles/wsa_vulkan_ab/mesh-fifo`; [informe técnico](../performance/graphics/WSA_VULKAN_INDEXED_MESH_2026-10-14.md).
- [x] Cierre de validación: **127 pruebas Python (4 omitidas), 31/31 CTest**, sintaxis ARM64 de módulo de malla aprobada. APK original del juego intacta y app Vulkan aislada detenida.
- [ ] Siguiente bloque: texturas GPU subidas con `VkImage`, descriptor/sampler, depth y estados heredados; solo después integrar adaptador de OpenGL del juego. Contador oficial **0/5**, APK de CallofRecomp sin cambios.



- [x] Recuperados los datos previos sin repetir mediciones: B1 GL4ES sin cap **57,20 FPS**, A3 GL4ES restaurado **55,30 FPS**; no hubo reducción de CPU/frame.
- [x] Tras detectar una diferencia entre el nuevo build estable y el backup A1, reinstalada en WSA **la APK original exacta**, no una variante recompilada. SHA-256 de `lib/x86_64/libmain.so` instalada = referencia A1: `403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde`. Datos de aplicación conservados.
- [x] `CODRECOMP_WSA_UNCAP_BENCH:BOOL=OFF` en el build local, por defecto OFF. Resultados, herramientas y limitaciones recogidos en [informe WSA](../performance/graphics/WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md).
- [ ] A/B/A real del **juego** usando Vulkan, no solo color sólido: PENDIENTE. Teléfono no disponible y contador formal sin cambios en **0/5**.

### 2026-10-14 — Benchmark por etapas WSA, sin ganancia Vulkan del juego aún (0/5)

- [x] Camp Toccoa Equilibrado GL4ES antes/después: **A1 55,20 FPS / 17,14 ms CPU; A2 55,05 FPS / 17,315 ms CPU**, 60 ventanas cada uno.
- [x] Vulkan NativeActivity Android separado: `VkAndroidSurfaceKHR`, `VkSwapchainKHR`, clear y present, 1280×720. **1.276 frames / 17,01 s = 75,014 FPS**, solo color sólido. Repetición solicitando inmediato volvió a FIFO: 75,055 FPS.
- [x] WSA pantalla 75 Hz, Vulkan sin modo inmediato; juego tiene límite de 60 FPS en `frame_pacing.h`.
- [x] Capturadores y pruebas reproducibles; logs, APK y guardados comerciales fuera de Git.
- [x] Diagnóstico opcional `--wsa-uncap-bench` exclusivamente x86_64 y OFF por defecto: **A2/B/A3 55,05 → 57,20 → 55,30 FPS**; CPU/frame 17,315 → 17,47 → 17,27 ms. Solo se evita ~2 FPS de pacing, NO es Vulkan. La APK original fue reinstalada.
- [ ] Backend Vulkan del juego completo y comparación final A/B/A siguen PENDIENTES. **No declarar mejora ni 120 FPS del juego**.
- [x] [Informe de benchmarks](../performance/graphics/WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md), contador oficial 0/5.

### 2026-10-14 — WSA sustituye temporalmente al TECNO; Vulkan Android confirmado, DirectX12 no integrado (0/5)

- [x] Solo WSA en ADB, `127.0.0.1:58526` (x86_64, Android 13). Teléfono no disponible. El juego existente abrió su menú mediante OpenGL/GL4ES; no se alteraron saves ni APK.
- [x] Renderer auditado: Win32 GL original → `gl_thunks.c` → GL4ES → GLES2 → emulación EGL Microsoft. No existe Vulkan/D3D12 integrado en el runtime.
- [x] Prueba Vulkan del NDK dentro de WSA: API **1.3**, `vkCreateInstance=VK_SUCCESS`, un AMD Radeon, extensiones `VK_KHR_swapchain` y colas. **No hay superficie, swapchain real ni present de frames verificado.**
- [x] Host Windows: DirectX 12 detectado por `dxdiag` y Vulkan 1.3 por `vulkaninfo`, pero los niveles D3D12 del driver no se confirmaron; evitar un segundo renderer Windows sin justificación.
- [x] Aclarado `Permission denied` del TECNO previo: ADB `shell` no puede leer frecuencia Mali en `/sys/class/devfreq/...`; contadores de GPU Perfetto de ese hardware no estaban expuestos. No es permiso de cámara/archivos, ni implica que la GPU esté bloqueada.
- [ ] Próximo paso: spike **Vulkan surface/swapchain/present aislado** en WSA, luego comparar CPU+GPU antes de considerar cambios al renderer. **60 FPS ARM64 sigue pendiente; estrategia vigente y 0/5 sin cambios.**
- [x] Documentación: [Decisión Vulkan/DirectX12 y permisos](../performance/graphics/WSA_VULKAN_DX12_RENDERER_DECISION_2026-10-14.md). Ningún parche de renderer habilitado.

### 2026-10-14 — Ejecución de estrategia: perfil CPU real, objetivo estructural seleccionado (0/5)

- [x] Fase 1: dos sesiones Simpleperf durante gameplay en el TECNO con Build ID instalado coincidente con ELF sin strip. A1 7.953 muestras/21,94 s sin pérdidas; A2 6.541 muestras. Mayor CPU muestreado en `libmain.so`: 83,93 % de A1.
- [x] Referencia spawn: 40 ventanas, **24,70 FPS mediana**, **23,30 FPS p10**, **38,895 ms CPU/frame**, **2,07 ms swap**; déficit de CPU ~22,23 ms frente al presupuesto 60 FPS.
- [x] Monitoreo de frecuencias/temperatura; sin estado térmico alarmado. GPU: lectura directa de Mali bloqueada y sin `gpu.counters` Perfetto, traza `gfx` básica privada. No se afirma tiempo real de GPU.
- [x] Fase 2: función elegida **`0x0041B8F0`**. 270 muestras con ARM64 muestreado (98 bits/movimientos; 81 cargas/store; 46 entero). Pista `restrict` para espacios disjuntos ya existente: **no duplicar**. El experimento estructural de registros queda **pendiente de prueba de alias/CFG**, sin modificación de gameplay.
- [x] Herramientas de captura con verificación Build ID, análisis original de Ghidra y estimaciones CPU bien etiquetadas; **117 Python (4 omitidas), 31/31 CTest**.
- [ ] Fase 2: una implementación demostrablemente equivalente y A/B/A en TECNO; fase 3 fast paths nuevos aún no iniciada. Meta **60 FPS pendiente; contador 0/5** porque no hubo ensayo A/B de una optimización nueva. [Informe](../performance/tecno/PERFORMANCE_STRATEGY_RUN_2026-10-14.md).

### 2026-10-14 — Estrategia oficial de rendimiento adoptada (0/5)

- [x] Documento autoritativo: [Estrategia vigente de rendimiento](../PERFORMANCE_STRATEGY_CURRENT.md) con tres fases: perfilado CPU/GPU en TECNO → optimización estructural de una función → fast paths nativos completos basados en muestras reales.
- [x] Establecido contador **0/5 intentos válidos consecutivos fallidos** a partir de esta decisión. Antecedentes previos (FCOM, DCE, NaN, GL4ES, flags) documentados pero **no contados retroactivamente**.
- [x] Exigidas pruebas controladas, integridad de HUD/partidas y mejora reproducible para confirmar éxito. Intentos inconclusos no cuentan y los éxitos confirmados reinician el contador.
- [ ] Al llegar a **5/5 fallos**, revisión formal obligatoria y decisión documentada de mantener, modificar o sustituir estrategia; **no cambio automático**.
- [ ] **60 FPS sostenidos en Camp Toccoa TECNO: PENDIENTE**. No se ejecutaron nuevas pruebas de rendimiento como parte de esta decisión documental.

### 2026-10-14 — DCE de temporales en pcode2c (ARM64 final sin cambios)

- [x] Implementado `temp_liveness.py`: liveness por byte/CFG/bucles para temporales únicos cuyos consumidores eran flags x86 ya muertos, solo para operaciones enteras sin posible fallo. Activación `pcode2c.py --prune-dead-temporaries --dead-temp-parts 1,8`, OFF por defecto.
- [x] Sobre 333.208 instrucciones Ghidra CoDSP, se eliminaron 15.555 operaciones de p1 y 17.149 de p8 del C fuente, manteniendo índices, etiquetas y líneas originales.
- [x] Validado con **109 pruebas Python (4 omitidas)**, **31/31 CTest**, 2.048 estados diferenciales completos en TECNO ARM64 y compilación ARM64 real de ambas particiones.
- [x] **Resultado negativo de rendimiento:** A/B de APK ARM64 `libmain.so` contiene `.text` **idéntica byte a byte** (41.779.524 bytes, SHA-256 `8846b89d...`) pese a la reducción del fuente. Clang `-O1` ya realizaba la eliminación. **Sin ganancia FPS demostrada.**
- [ ] Objetivo **60 FPS sostenidos ABIERTO**. Siguiente bloque: analizar instrucciones ARM64 *que sobreviven al compilador* (x87/alias de memoria/dispatcher), medir con Simpleperf y exigir A/B/A in-game. [Informe](../performance/cpu/CODSP_PCODE_TEMP_DCE_2026-10-14.md).

### 2026-10-14 — Auditoría GL4ES/Mali y FCOM p1/p8: experimento inconcluyente/regresión B2

- [x] Reprocesado perf.data TECNO con Simpleperf: 6.358 muestras, `libmain` 86,13 %, driver Mali GLES 4,70 %, GL4ES 1,43 %. No extrapolar a tiempo GPU.
- [x] 448 comparaciones x87 completas fusionadas tras validación estricta de tres patrones/hashes en CoDSP p1/p8, flag `--x87-fcom-fastpath` **OFF por defecto**.
- [x] Equivalencia de estado completo en ARM64 TECNO: **151.638 casos correctos**. Suite local final **103 Python (4 omitidas)** y **31/31 CTest**.
- [x] A/B/A misma partida, 40 ventanas tardías por corrida: x87 referencia **24,90 FPS / 38,590 ms CPU**, FCOM+x87 **26,15 FPS / 36,875 ms**, referencia reinstalada **24,90 FPS / 38,625 ms**. **B2 cae a 19,80 FPS / 48,210 ms; A3 sin FCOM recupera 25,10 FPS / 38,305 ms.** NO SE ACEPTA ganancia estable. Se conserva flag OFF por defecto, pendiente de explicación de regresión.
- [ ] Conseguir **60 FPS sostenidos** en spawn (referencia estable ~25) sin bajar calidad. Siguiente: análisis de eliminación segura de EFLAGS muertos en traductor y nuevos hotspots Simpleperf, con oráculo de estado. [Informe](../performance/tecno/ARM64_RENDERER_CPU_FCOM_2026-10-14.md).

### 2026-10-14 — Nuevo experimento x87 normal-f2d (OFF por defecto)

- [x] Auditoría de la sesión anterior: Git `bd84510` limpio y sincronizado; 98 tests Python, 29/29 CTest, registros A3/B2 comparados de nuevo (**25,45 vs 25,70 FPS**; mejora NaN no acreditada).
- [x] Añadida conversión directa binary80→binary64 normal exacta en CoDSP `p1/p8`, optativa `--x87-normal-f2d` OFF por defecto, sin modificar C generado ni partidas. **1.205.360 casos** bit a bit en TECNO ARM64 sin discrepancias; 98 Python (4 omitidas), 30/30 CTest.
- [x] Microbench ARM64 original ~45,5 ms frente a candidato ~37,7 ms por 6,29 millones de conversiones (**~17 % menor coste aislado; no extrapolable a FPS de juego**).
- [x] APK ARM64 candidata compilada y firmada V2/V3, instalada en TECNO: arranca hasta menú (~53 FPS, **no** gameplay); respaldo separado preservado y APK x87 anterior reinstalada al terminar.
- [ ] **A/B/A en spawn**, validar HUD/partidas y cuantificar FPS en training (no comprobado en este ensayo). Meta **60 FPS sostenidos: ABIERTA**. [Informe](../performance/tecno/ARM64_X87_NORMAL_F2D_2026-10-14.md).

### 2026-10-14 — Perfil fino de comparaciones x87

- [x] Resueltas 5.476 muestras ponderadas originales del perfil ARM64 x87 mediante `llvm-addr2line`, C generado con offsets corregidos y mapas Ghidra v2: puntos importantes `0x004D9511` (37/150 muestras de su función), `0x004D82DB` (28/155), `0x0041B986` (23/247).
- [x] La instrucción caliente `0x004D9511` traduce a 30 operaciones p-code con dos NaN, comparaciones LESS/EQUAL y manipulación de banderas; esto sugiere estudiar **la comparación completa**, no solo NaN.
- [ ] Probar una especialización semánticamente equivalente de esta secuencia x87, preservando estado total y todas las ramas antes de nuevas mediciones de FPS. **60 FPS aún pendientes**.

### 2026-10-14 — Optimización NaN binary80: equivalencia ARM64 validada, FPS no concluyentes

- [x] Identificados **1.178 sitios estáticos** de `isnan(f2d(binary80))` en CoDSP `p1` (632; geometría) y `p8` (546; visibilidad). Desarrollado parcheador privado estricto e idempotente y ayudante `codsp_x87_isnan_bits`; `--x87-nan-bits` **OFF por defecto** y recuperación exacta de la expresión anterior cuando está OFF.
- [x] **955.360 comprobaciones binarias en el TECNO ARM64** frente al runtime p-code existente sin discrepancias, incluidas formas x87 no canónicas; **98 pruebas Python (4 omitidas) y 29/29 CTest**. APK arm64 compilada, firmada y partida visible con HUD panorámico intacto.
- [x] A/B/A/B/A de **40 ventanas de juego por variante** en la zona inicial: referencia x87 **24,75 / 24,75 / 25,45 FPS**, candidata **25,60 / 25,70 FPS**. Al acercarse A3 al candidato, la ventaja aparente baja a **0,15–0,25 FPS**, menor que la variación de controles. **NO se acredita nueva mejora de FPS**.
- [x] Restaurada la APK x87 anterior en el teléfono y la configuración Android local de referencia. Los registros, binarios originales, C recompilado y APK de prueba permanecen privados e ignorados.
- [ ] **60 FPS sostenidos en el spawn: PENDIENTE.** Siguiente fase: perfil por instrucciones de `0x0041B8F0` y `0x004196F0`, optimización de subcálculos comprobada por equivalencia/visual y medición real.
- Informe: [equivalencia y 5 corridas de NaN binary80](../performance/tecno/ARM64_X87_NAN_BITS_2026-10-14.md).

### 2026-10-14 — Rendimiento: dos experimentos ARM64 descartados tras A/B/A

- [x] Restaurada la investigación del perfil físico: CoDSP `0x0042B0A0` (copia; 152 muestras) y visibilidad `0x004D8280`, `0x004D94C0`, `0x004D8420`, `0x004D6BC0` (587 muestras combinadas, no tiempos exactos).
- [x] Ruta de copia32 **optativa OFF por defecto** (`--fast-copy32`); prueba de equivalencia en el TECNO de **17.000 llamadas completas, 249.371 bloques** frente al p-code, estado total de registros/banderas/RAM/PC idéntico. A/B/A estable: **25,45 → 25,10 → 25,30 FPS** (A1/B/A2); **no mejoró** el juego.
- [x] Compilación selectiva `-O2 -ffp-contract=off` para CoDSP `p8`, con `--visibility-o2` **OFF por defecto**. A/B/A estable: **25,30 → 25,50 → 25,45 FPS** (A1/B/A2). La diferencia de +0,05 FPS frente a A2 **no es significativa**.
- [x] Ambos ensayos usaron el mismo guardado de training en TECNO CK6n/Equilibrado, 40 ventanas estables por corrida, sin perfilador intrusivo; APK experimental firmada y datos privados preservados. **96 pruebas Python (4 omitidas), 28/28 CTest**.
- [x] Restaurada la APK x87 de referencia en el teléfono; la configuración normal queda con copy32 OFF y visibilidad -O2 OFF, **conservando x87 optativo que demostró +19,58 % y todas las reparaciones panorámicas/HUD**.
- [ ] Sigue siendo obligatorio conseguir **60 FPS sostenidos en el spawn**. Próximo paso de trabajo: estudiar subcálculos dentro de geometría `0x0041B8F0`/ `0x004196F0` y visibilidad `0x004Dxxxx`, probar equivalencia de estado y FPS A/B/A, sin retocar calidad.
- Investigación, comandos y resultados: [experimentos ARM64 posteriores a x87](../performance/tecno/ARM64_PERF_EXPERIMENTS_2026-10-14.md).

### 2026-10-14 — Barra de salud y estrellas circulares sin deformación

- [x] La salud en `ui/hud.menu` seguía con las medidas virtuales 4:3: cruz 12×12, fondo 130×12 y relleno 128×10. `HudWidescreen.patchHealth` aplica el factor horizontal común **0,60** (TECNO 1280×576), conserva el 100 % del avance de salud, altura y esquina derecha (borde original x=631). Menús modificados/no reconocidos se dejan intactos.
- [x] Hallado el error exacto en el hook de estrellas: `0x3001ceda` era el retorno de la llamada **0x4a de color**, no el dibujado. El P-code original confirma la llamada **0x4b de dibujo** en `0x3001cf3a`, retorno `0x3001cf40`.
- [x] El callback de cgame entra al motor CoDSP **recompilado**, normalmente no al puente de thunks de host. Ahora se protege el parche por el puntero de `dllEntry`, el retorno exacto `0x3001cf40`, el syscall `0x4b`, módulo cargado y un PK3 privado con HUD compatible. Convierte solo los parámetros ya escalados a píxeles de estrella a coordenadas virtuales, corrige su ancho/radio y vuelve a píxeles. Los verdes previamente arreglados no se tocan.
- [x] **Prueba física TECNO CK6n**: registro de la estrella 64×38,4 → **38,4×38,4** píxeles, escalas de cgame 2,0/1,2 y factor 0,60; medición del anillo amarillo en captura real: **29×29 píxeles**. Barra de salud visualmente más corta y cruz alineada; panorámico real intacto (1280×576, FOV horizontal ~108,87°).
- [x] Compilación y firma de APK ARM64, instalación sobre el mismo teléfono conservando partidas; **94 pruebas Python (4 omitidas), 27/27 CTest**. APK previa respaldada en área privada ignorada; no se distribuyen originales comerciales.
- [ ] Sigue pendiente verificar otros iconos de misión que no aparezcan en este entrenamiento (especialmente tanque), y conseguir **60 FPS sostenidos en el spawn**. La reparación gráfica no se contabiliza como ganancia de FPS; no se hizo A/B/A controlado de rendimiento.

### 2026-10-14 — Indicadores verdes dentro de la brújula panorámica

- [x] Hallado el problema real: el cgamex86.dll original calcula los puntos verdes, tanques y objetivos con un radio propio de **43,75 unidades**; la corrección anterior solo había estrechado el dibujo del círculo.
- [x] Verificados con P-code y decompilación privada los puntos de llamada para aliados, tanques, objetivos principales y pulso de objetivos, sin publicar código o datos comerciales.
- [x] Añadida una corrección de geometría exclusiva para esos llamadores: ancho horizontal proporcional a la resolución real y límite radial teniendo en cuenta el tamaño del icono. Mantiene ángulo, zoom, distancia de los puntos interiores, cámara 3D y FOV real.
- [x] Protegida para activarse únicamente en Android panorámico cuando está presente el HUD corregido privado; en 4:3, ante módulos ausentes o parámetros no válidos, conserva los dibujos originales.
- [x] Prueba real en TECNO CK6n 1280x576: el motor confirmó que corrigió los indicadores de aliados y el pulso del objetivo; las capturas del entrenamiento muestran los puntos verdes dentro del círculo, sin afectar la visión 3D. Las rutas de tanques y estrella principal están implementadas y probadas matemáticamente, pero falta verlas en su misión.
- [x] Regresión: **94 Python (4 omitidas), 27/27 CTest**, APK ARM64 firmada con la mejora anterior de x87 todavía experimental. En 30 ventanas de juego, mediana **25,75 FPS / 37,525 ms CPU/frame**, compatible con el resultado previo ~25,65 FPS sin demostrar un incremento adicional.
- [ ] **60 FPS sostenidos en la aparición de training sigue PENDIENTE**; no confundir esta reparación visual con una mejora de rendimiento.

### 2026-10-14 — Panorámico real conservado y HUD 2D corregido

- [x] Verificado mediante el registro del TECNO que el motor continúa usando proporción **2,22:1** y FOV horizontal **108,87°**: no se estira artificialmente una imagen 4:3.
- [x] Reparada la deformación horizontal de la brújula original y de iconos cuadrados (postura, cursor y tanque), sin alterar la proyección 3D, el menú principal, barras no cuadradas, el guardado ni las optimizaciones previas.
- [x] `HudWidescreen.java` genera automáticamente en el arranque un pequeño PK3 privado a partir de los originales importados. El lector soporta entradas duplicadas que Android `ZipFile` rechaza; valida tamaños, CRC y límites; nunca modifica los PK3 comerciales ni distribuye sus datos.
- [x] Prueba visual con paquete privado en la partida del TECNO: la brújula recuperó su forma circular. Tras eliminar el paquete manual, la nueva APK volvió a generarlo automáticamente: **HUD aspect fix enabled at 1280x576**. Pruebas Java sintéticas incluyen ZIP duplicados, formatos 16:9 y 2,22:1 y comportamiento 4:3.
- [x] Regresión final: **94 pruebas Python (4 omitidas), 26/26 CTest**, APK ARM64 firmada con la vía x87 previa aún optativa y sin recursos comerciales incluidos; el TECNO cargó de nuevo el entrenamiento y el PK3 privado autogenerado apareció en la ruta de búsqueda original.
- [ ] La meta separada de rendimiento (**60 FPS sostenidos en spawn**) sigue pendiente; esta corrección de interfaz no implica una mejora de FPS.

### 2026-10-14 — Perfil residual tras fast path x87 en TECNO

- [x] Medido con Simpleperf el spawn de training **después** de habilitar la APK optimizada: 6.358 muestras en 17,95 s, cero perdidas, 5.476 muestras en libmain.so; 3.784 resueltas a cuerpos de funciones Ghidra únicos.
- [x] Nuevos costes localizados: CoDSP.exe 0x0041B8F0 (247 muestras; geometría/colisiones), 0x0047BD40 (181), 0x004196F0 (158), 0x004D8280 (155), 0x0042B0A0 (152; copia de memoria), 0x004D94C0 (150), 0x004D8420 (143), 0x004D6BC0 (139). No son tiempos exclusivos ni una ganancia nueva de FPS.
- [ ] Siguiente trabajo: estudiar **familia geométrica y de visibilidad** y validar rutas alternativas bit a bit antes de entrar al juego; FPS A/B real y meta de 60 FPS aún pendientes. Perfiles y código comercial permanecen privados.

### 2026-10-14 — Objetivo de rendimiento: 60 FPS sostenidos en zona inicial (PENDIENTE)

- **Criterio de cierre del usuario:** NO dar el proyecto de rendimiento por terminado hasta alcanzar **60 FPS sostenidos donde aparece el jugador al iniciar training** en el TECNO CK6n ARM64, calidad Equilibrado y misma partida/vista. Esto se refiere a la zona de aparición, no al menú ni a una zona diferente.
- **Mejora previa confirmada y conservada, pero NO objetivo completado:** A/B/A real: APK anterior A2 **21,45 FPS / 44,745 ms CPU**, fast path nativo B **25,65 FPS / 37,495 ms CPU**, **+4,20 FPS (+19,58 %) y -7,25 ms CPU/frame**, 40 ventanas de ~1 s por corrida; A1 original 21,55 FPS.
- **Brecha restante:** faltan 34,35 FPS respecto al objetivo; presupuesto de frame de 60 FPS ~16,67 ms frente a ~37,50 ms de CPU/frame ahora. La ruta x87 sola no basta.
- [ ] Validar ≥60 ventanas consecutivas de ~1 segundo de **juego estable** en el punto de aparición con FPS cerca del techo de 60, tiempos de CPU, FPS bajos y variables térmicas; excluir carga, menús, pantallas de pausa y transiciones; repetir A/B/A.
- [ ] Continuar perfilando Simpleperf sobre la APK **ya optimizada** y atacar nuevos cuellos de botella con pruebas de equivalencia y A/B/A. Mantener el fast path OFF por defecto hasta validar su seguridad general.

### 2026-10-14 — Fast path x87 nativo optativo y FPS A/B/A reales

- [x] Se continuó el trabajo anterior **sin descartar ni sobrescribir** sus cambios no confirmados. Se conservan el informe TECNO, analizador de FPS y perfiles privados.
- [x] Se implementó una ruta nativa **opt-in (OFF por defecto)** para CoDSP.exe 1.5 `0x005061B0`, con respaldo a p-code ante solapamientos, entradas no finitas o punteros no compatibles. No cambia el generador ni los archivos propietarios.
- [x] En el TECNO físico: **75.000** comparaciones del estado completo de registros y RAM frente a la función p-code (69.152 fast, 5.848 fallback) fueron idénticas; microbenchmark separado ~315 ms frente a ~26 ms por 250.000 llamadas, sin extrapolarlo a FPS.
- [x] Repetición A/B/A en el mismo guardado Camp Toccoa/Equilibrado, 40 ventanas estables cada vez: referencia A1 **21,55 FPS**, experimental B **25,65 FPS**, referencia A2 **21,45 FPS**. B frente A2: **+4,20 FPS (+19,58 %)** y **-7,25 ms CPU/frame**. Comprobada visualmente la entrada de training; no se ha validado la zona concurrida ni toda la campaña.
- [x] 93 tests Python (4 omitidos), **26/26 CTest**, compilación ARM64 firmada para ambas opciones. `build_android.py --hot-x87-transform` activa solo esta prueba. El artefacto opcional queda privado en `.local/profiles/`; `recomp_out/callofrecomp-arm64-debug.apk` fue **reconstruida con flag OFF**.
- [x] Tras A2 se volvió a instalar la APK experimental en el teléfono preservando los datos; el lanzador confirmó «Instalación lista» en Equilibrado. Recursos propietarios, mapas Ghidra y perfiles brutos siguen fuera de Git.
- [ ] Pendiente: comparación independiente contra ejecución Intel x86 original, comprobación de excepciones/precisión x87 y jugabilidad/visuales en escenas concurridas y toda la campaña. Mantener el fast path **desactivado por defecto** hasta esas pruebas.

### 2026-10-14 — Primera prueba real en TECNO CK6n ARM64

- [x] Conectado el teléfono TECNO CK6n Android 14, validada la instalación propia de Call of Duty 1.5 (cuatro SHA-256 correctos) y 17 PK3; importación mediante codpack oficial, sin publicar recursos. Menú, partida guardada y mapa training comprobados.
- [x] Referencia física en entrada de training, calidad Equilibrado: 40 ventanas tardías; **21,55 FPS mediana**, **44,585 ms CPU/frame** y **2,31 ms swap/frame**. Predomina coste de CPU.
- [x] Simpleperf en teléfono: 5.504 muestras, cero pérdidas, 4.661 de libmain.so. Se localizaron 3.439 muestras en cuerpos únicos de Ghidra. La función original CoDSP.exe **0x005061B0** (transformación vector/matriz x87) acumuló **656 muestras**. 4.586/4.661 muestras de libmain.so ejecutadas en núcleos rápidos 6/7, por lo que fijar afinidad no está justificado.
- [x] Experimentos físicos: optimización selectiva -O2 (21,65 vs 21,45 FPS en ventanas tardías, diferencia ~0,93 % no demostrable), -Oz (9,8–13,4 FPS en 7 ventanas; empeoró claramente) y preset Ligero (40 ventanas medianas 21,40 FPS, degradando visuales sin ganancia sostenida).
- [x] Se restauró en el teléfono el APK normal y el perfil Equilibrado, conservando guardado y originales; se reconstruyó el APK normal -O1 en el PC, flags experimentales OFF. El paquete codpack temporal en Descargas se borró después de importarse para liberar espacio.
- [x] Añadido analizador reproducible sin datos comerciales, tools/recomp/analyze_frame_stats.py, con pruebas sintéticas; **93 pruebas Python correctas (4 omitidas) y 25/25 CTest correctas**. Evidencia y decisiones en [informe TECNO ARM64](../performance/tecno/TECNO_CK6N_ARM64_PERF_2026-10-14.md).
- [x] Esta fase identificó el objetivo 0x005061B0; la siguiente fase optativa (arriba) alcanzó una mejora de FPS en una escena de training. La zona concurrida sigue pendiente.

### 2026-10-14 — Ghidra function bodies and ARM64 inline-aware sample resolution

- [x] Extended Ghidra's private `ExportPcode.java` data with inclusive `B` function-body ranges, preserving disconnected regions; `--function-bodies-only` extracts just metadata from the saved project without re-exporting P-code or compiling the game.
- [x] Added compatible v2 sidecar mapping and `--body-records` input; it rejects stale/nonmatching original F entries, empty body data and dangerous destination overwrites. The existing legacy v1 files and default generated gameplay C remain unchanged.
- [x] Used saved private Ghidra 12.1.4 projects and original exact CoD 1.5 raw P-code to build all four private v2 maps: 7,116 original Ghidra function-body intervals; 519,757 uniquely owned translated instructions, 80,013 not uniquely owned, out of 599,770. This is static Ghidra membership only, NOT actual per-function CPU.
- [x] Added `resolve_guest_samples.py`: accepts pre-symbolized source-line TSV or normalized native ELF PC TSV, queries unstripped Android `libmain.so` via `llvm-addr2line -a -f -i`, recovers *inlined* generated-C call sites, then resolves guest instruction label and possible Ghidra function body. Header-only/helper PC samples, unknown lines and ambiguous bodies remain explicitly unowned.
- [x] Verified a real unstripped ARM64 `libmain.so` resolves to private generated CoDSP C files. An **artificial** 11-sample ELF-address smoke linked 10 to guest instructions and unique body entries, 1 remained unresolved; this validates the symbolization chain, NOT game FPS or a representative CPU profile.
- [x] Verified Ghidra 12.1.4 `-process ... -noanalysis` body exports for all four original modules; 90 Python tests pass (4 skips), and 25/25 CTest pass. No normal APK was rebuilt, since runtime/guest rendering C is unchanged.
- [x] El TECNO ARM64 ahora está disponible y se recopilaron muestras Simpleperf reales **en la entrada de training**, con mapas de funciones x86; sigue pendiente un perfil de la escena concurrida y la validación automatizada de build-ID/SHA de fuentes.

### 2026-10-14 — Original x86 function-entry diagnostics (research archived)

- [x] Preserved previously discarded Ghidra `F` metadata in an opt-in JSON sidecar for `pcode2c.py`, plus a standalone streaming `I/F` header mapper and a non-attributing existing-CPU-log analyzer. No native rendering, simulation, loader or default generated C behavior changed.
- [x] Verified original private CoD 1.5 p-code maps: 599,770 instructions / 403 generated dispatch chunks / 6,228 exact matched Ghidra function entries; **378 chunks contain multiple entries**. No raw proprietary data or generated maps in Git.
- [x] An existing opt-in menu profile had 22 chunk records covering 13 unique chunks; all resolved to one map. Hot CoDSP chunk 207 includes 28 original function entries. Chunk CPU times cannot be attributed to any one function.
- [x] Added deterministic synthetic tests for mapping, chunk/part assignments, CLI safety, generated-C identity with the optional sidecar, and honest sample annotation. Full verification: **79 Python tests passed (4 skipped)**; **25/25 host CTest passed**. No Android APK was rebuilt in this metadata-only phase.
- [x] Saved the external project comparison, evidence limitations, reproducible commands and ranked future experiments in [docs/performance/cpu/FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md](../performance/cpu/FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md).
- [ ] Obtain actual guest function-level CPU attribution (not just chunk-level), validate native ARM64 crowded scenes, and only then test differential-equivalent native fast paths. No new FPS claim.

### 2026-10-14 — PE32 load validation and controlled menu optimization trial

- [x] Hardened the recompiled module loader: validate MZ/PE32 headers, image size, all section source/destination bounds and guest IAT targets **before committing the guest image**. Reject corrupt binaries safely rather than reading/writing unbounded addresses.
- [x] Added synthetic malformed-PE regression cases and a module-lifecycle test proving failed loads do not register modules or commit guest image memory; 25/25 host CTest targets pass.
- [x] Measured two current WSA menu-load baselines (2,065 and 2,017 ms total for two renderer initialization passes) and two isolated UI-module -O2 candidates (2,006 and 2,026 ms). Difference too small to show an improvement; trial-only build setting removed and normal installed APK restored with matching SHA-256.
- [x] Diagnostic guest CPU sampling shows hot guest chunks across renderer/menu initialization, but its overhead increased total UI parse time to 2,435 ms. Do not compare instrumented time as an A/B or claim a gameplay FPS gain.
- [ ] Repeated menu parsing remains a legitimate lifecycle after Hunk_Clear; prove safe data ownership and GPU-handle reinitialization before a parsing cache or bypass.
- [x] Compiled and signed the normal x86_64 WSA and ARM64 Android debug APKs (v2/v3 signing; CPU/GL profiling OFF). Reinstalled updated x86_64 WSA APK, exercised the original menus, training mission, save, and continued frames successfully (15 stable one-second windows, 51.5 FPS median). This is functional compatibility evidence, not an FPS improvement; no physical ARM64 device was available.

### 2026-10-14 — Verified repeat menu parsing and added safe log analyzer

- [x] Reconfirmed two R_Init cycles around the training transition (second follows RE_Shutdown(0) and Hunk_Clear) in two WSA logs. The same 25 original UI menu paths are parsed in both cycles; this is initialization work, not proof of duplicated per-frame draws.
- [x] Added tools/recomp/analyze_menu_reloads.py with synthetic unit tests and aggregate-only output. WSA capture A: 951/1,040 ms of menu parsing; capture B: 1,496/1,516 ms. These runs are not an A/B of a code optimization.
- [ ] Prove UI allocation ownership and GL resource validity before caching parsed menus across Hunk_Clear; no unsafe bypass implemented, no FPS claim.

### 2026-10-14 — Translation/rendering optimization audit and Vulkan feasibility

- [x] Compared the real pinned GL4ES revision to upstream master: both at `ec16bedd` (2026-10-04); no unreviewed dependency switch.
- [x] Tested documented GL4ES batching on the same WSA saved training view: 54.50 normal vs **51.75 FPS** with `LIBGL_BATCH=1`, 17.75 vs 19.125 ms CPU. Experimental APK was discarded and normal mode restored.
- [x] Inspected 500k AArch64 instructions in the generated CoDSP p10 object; 1,813 private raw p-code operations in chunk 186 are conservative elimination candidates, NOT proven runtime work or compiler-surviving instructions.
- [x] Compiled p10/p11 separately with AArch64 `-Oz`: text 1,999,712 -> 654,000 B (p10), 855,176 -> 575,236 B (p11). WSA A/B **54.50 -> 49.95 FPS**, CPU 17.75 -> 19.865 ms: no production compiler-flag change; trial-only flags reverted.
- [x] Benchmarked float32-to-x87 binary80 specialization with equality fixtures and ARM64 assembly inspection; no speed benefit over existing translation, removed experiment.
- [x] Documented ANGLE and Zink/Vulkan compatibility constraints and native ARM64 Simpleperf/AGI profiling priorities in `docs/performance/graphics/RENDER_TRANSLATION_AUDIT_2026-10-14.md`.
- [ ] Profile the actual crowded scene on the real Mali-G52 ARM64 device; attribute time to original x86 renderer functions, GL4ES, driver, and GPU counters before further invasive changes.

### 2026-10-14 — WSA A/B closure and targeted renderer compiler tests

- [x] Math hot-path same-scene WSA A/B: 54.55 vs 54.50 FPS, 17.70 vs 17.75 ms thread CPU; no FPS improvement but keep locally verified operation and correctness optimization.
- [x] Renderer p10/p11 O2 selective APK tested: 54.50 vs 54.25 FPS, 17.75 vs 17.79 ms CPU. Keep feature opt-in OFF by default.
- [x] GL CPU bridge diagnostic: approx 2.64 ms/frame inside host drawing functions in a stable 272-frame window, vs 18ms total engine CPU. The remainder is NOT established to be renderer-only.
- [x] Full ARM64 normal libmain.so built and linked, AArch64 ELF and normal settings verified. GL CPU timing, GL call counting, sampled CPU and selective O2 all OFF; no GL diagnostic format strings in normal library. Proprietary assets remain private.

### 2026-10-14 — Renderer GL bridge CPU timing and selective compiler experiment

- [x] Resumed the interrupted WSA x86_64 arithmetic APK packaging (no redo of the 35 already compiled C objects).
- [x] Added an opt-in, compiled-out-by-default `CODRECOMP_GL_TIMING` profile and private `gl_time` marker. It accounts for CPU inside selected OpenGL GL4ES/GLES entry points, not time spent in the guest renderer or GPU. Generator and generated bridge are synchronized and covered by test.
- [x] In the same Camp Toccoa entrance, a 272-frame window measured ~2.64 ms/frame CPU in guest-indexed draw calls, ~0.10 ms GL state, ~0.09 ms attribute pointer setup, ~0.044 ms texture binding, ~0.013 ms locks. These are not GPU timings and do not prove the whole remaining frame is renderer time.
- [x] Added OFF-by-default `CODRECOMP_RENDER_O2` / `--render-o2` to target only the hot CoDSP p10/p11 compiled units, without affecting normal graphics settings. Same-scene A/B completed, no FPS gain.
- [x] All 24 host CTest cases passed, including new timing aggregation; Python generator and builder CLI unit tests pass; diagnostic WSA build compiled/linked and ran the training mission.
- [x] Controlled WSA A/B complete: math FPS 54.55 to 54.50; selective p10/p11 O2 FPS 54.50 to 54.25. Neither improves FPS significantly; ARM64 library compiled correctly.

### 2026-10-14 — Native signed-arithmetic hot path (WSA A/B completed)

- [x] Profiled actual CoDSP p-code operations in renderer chunks 186/187 and 0x0051EE2F..0x0052079A. These regions contain repeated INT_SCARRY/INT_SBORROW and signed comparisons; static operation counts are not dynamic call counts.
- [x] Replaced signed overflow detection with checked native 8/16/32/64-bit arithmetic and defined unsigned bit tests for uncommon 9..16-byte widths. Found and corrected a real signed-128-bit overflow bug: the old width-16 test fails, the new one passes.
- [x] Added `overflow_flags_smoke`: all 65,536 pairs of 8-bit operands, boundary tests and 30,000 seeded 128-bit pairs per width 1..16, checking carry, borrow and sign extension against independent references.
- [x] Host verification: 23/23 CTest, 12/12 targeted generator tests; Android NDK AArch64 smoke source compiles (object only, not executed on a phone).
- [x] Win64 Clang -O1 4-million-iteration microbenchmark per width (seven samples): 32-bit median 26.826 ms before / 12.421 ms after; 64-bit 27.672 ms before / 12.213 ms after, identical checksums.
- [x] ARM64 Clang -O1 static assembly comparison: signed subtraction overflow n=4: 15 → 3 instructions; signed add/sub overflow n=8: 11 → 3 instructions each. 32-bit signed add remained 3 instructions, not falsely claimed as a speedup.
- [x] Full-game WSA same-save A/B completed: 54.55 FPS previous to 54.50 after arithmetic optimization. No FPS gain established, retain native arithmetic improvement and 128-bit correctness fix.
- [x] Same-scene WSA 60-window A/B completed; native ARM64 shared library compiled; selective O2 A/B tested and OFF by default. Next: real ARM64 device and crowded soldier scenes.

### 2026-10-14 — Rescate de optimización del dispatcher con beneficio local verificado

- [x] Se comprobó que `main` y `origin/main` estaban sincronizados en `8ce2829` y se conservaron los informes privados y APK del A/B original; no se repitió una compilación completa de CoDSP.
- [x] Se recuperó el acceso al chunk anterior en páginas de 4 KiB compartidas: evita la búsqueda binaria habitual cuando el objetivo es el vecino anterior. La comparación sintética guardada en Windows dio aproximadamente 152 ms frente a 41 ms, con igual checksum y más pruebas de límites y huecos.
- [x] **No afirmar aumento de FPS**: la medición de una escena en WSA había sido 52,7 frente a 52,15 FPS; el cambio se conserva por la mejora concreta en el dispatcher, no como aceleración global validada.
- [x] Se mantiene **sin habilitar** el alineamiento opcional por funciones: 52,1 FPS y 19,135 ms de CPU frente a 52,7 FPS y 18,865 ms de referencia. Los archivos privados experimentales permanecen disponibles para trabajos posteriores.
- [ ] Pendiente: perfilado y optimización del trabajo por instrucción en los chunks calientes, más ensayos controlados en escenas exigentes y ARM64 real.

### A/B de modos VBO internos de GL4ES en WSA — 2026-10-13

- [x] Prueba A/B aislada sin alterar main: se forzó LIBGL_USEVBO=2 y LIBGL_USEVBO=3 por separado en android/native_host.c de un worktree temporal y se compilaron APK x86_64 firmadas. Ambos modos llegaron a la misma entrada de training con la misma partida y perfil Equilibrado.
- [x] Valores de 60 ventanas de ~1 segundo de frame stats del motor: modo normal 1 FPS mediano 54.5 / CPU hilo mediana 17.855 ms / tiempo de cuadro medio de ventana mediana 18.34 ms; modo 3: 51.55 FPS / 19.35 ms CPU / 19.39 ms cuadro; modo 2: 49.25 FPS / 20.29 ms CPU / 20.305 ms cuadro. Los modos experimentales empeoran ~5.4% y ~9.6% FPS en esta escena de WSA; no se habilitan.
- [x] Restaurada APK normal con profiling GL deshabilitado y modo VBO por defecto; comprobado SHA-256 de APK instalada contra copia normal y ausencia de cadenas del modo experimental en libmain.so. La partida de entrenamiento se conserva. Se revirtió android/native_host.c del worktree temporal.
- [ ] Pendiente: analizar rutas internas reales de draw y copias de GL4ES, probar escena exigente con varios soldados, y medir en teléfono ARM64 real. No extrapolar resultados de WSA a GPU móvil.

### Opt-in WSA OpenGL bridge counters — 2026-10-13

- [x] Built a separate x86_64 APK from commit 9147588 with CODRECOMP_GL_PROFILING=ON; a private gl_stats marker enabled actual guest OpenGL call counters during the preserved Camp Toccoa training scene.
- [x] One stable approximately 5-second window recorded 274 native frames, 9,590 glDrawElements, 18,632 glDrawRangeElements, 31,784 glBindTexture, 11,234 active-texture calls, 8,494 glLockArrays pairs and 42,018,996 requested indices. Per-frame averages: **103 indexed draw requests; 116 texture bind calls; 41 active texture calls; 31 lock/unlock pairs; 153,354 indices**.
- [x] No explicit guest VBO bind/buffer uploads appeared during that steady scene. GL4ES can still use internal buffers, so these metrics do **not** establish what the GPU did or the relative CPU cost of these GL operations.
- [ ] Performance hypothesis to test in isolated builds: GL4ES usevbo=2/3 compiled-array pathways; do not enable them in normal APKs unless repeated WSA A/B, visual correctness, and real ARM64 device validation support the change.

### WSA reproducible performance check and first-open overlay copies — 2026-10-13

- [x] Built signed x86_64 APK from detached clean worktree at commit `9147588`, installed with `adb install -r`, and confirmed loading/resuming the preserved Camp Toccoa training save in WSA. All private original game content remained external.
- [x] Compared original WSA v0.2.3 APK and `9147588` with the same save, camera direction, Balanced graphics settings, 60 one-second engine-log windows at the start of the training mission. Median of window-averaged FPS **54.5 vs 54.5**, CPU thread window medians **17.920 vs 17.855 ms**, median window-averaged frame times **18.36 vs 18.34 ms**, p95 of window averages **20.187 vs 20.119 ms**. **No established FPS improvement**: the prior snapshot at 44.3 FPS came from a different scene and was not a valid A/B.
- [x] `CL_InitCGame` took 7.07 s before and 6.71 s after in one run each; this is not enough repetitions to establish a load-time improvement.
- [x] Improved copy-on-first-write into the app's writable overlay: use a 16-KiB buffered stream rather than byte-by-byte `fgetc/fputc`; check errors/close and remove incomplete overlays. It does **not** change read-only PK3 handling or simulation logic.
- [x] Synthetic Windows host microbenchmark with 16 MiB and 5 trials per method: byte-copy median 291.540 ms vs buffered median 11.919 ms (**24.46x for this microbenchmark only**). Runtime copy fixtures cover binary content, empty streams and NULL pointers; all 22 host CTest tests pass. Android ARM64 libmain builds.
- [ ] Further work: capture opt-in GL bridge counts, attribute GL4ES internal draws/copies, and test actual ARM64 phone scenes. WSA's integrated OpenGL ES translator is not representative of a Mali/Adreno mobile GPU.

### GL bridge performance implementation — 2026-10-13

- [x] Implemented correct guest-side GL_ARRAY_BUFFER and GL_ELEMENT_ARRAY_BUFFER binding state in the generated GL thunks. Attribute and index pointers become byte offsets only while the corresponding target is bound; unbind, deletion and gl_load reset state. The advertised guest extension list is deliberately unchanged.
- [x] Generator tools/recomp/gen_gl.py now reproduces the pointer semantics and optional instrumentation; synthetic generator test and the real GL thunk bridge smoke test cover the behavior.
- [x] Added compile-time OFF-by-default CODRECOMP_GL_PROFILING and a private gl_stats marker to count guest draw requests, elements/vertices, texture operations, buffer-upload bytes and lock/unlock, aggregated every ~5 seconds without per-draw logs. Host metrics regression and Android Clang diagnostic compilation pass. This does not measure real GLES submissions or GPU execution time.
- [x] Changed wglGetProcAddress thunk-table resolution from linear scan to binary search, relying on generator-enforced sorted names. Synthetic lookup and actual guest shim resolution tests pass.
- [x] Added --cpu-profile and --gl-profile opt-in flags to the private Android builder, explicitly OFF by default. Defaults preserve normal noninstrumented code.
- [x] Host CMake+CTest all 21 tests passed. ARM64 NDK libmain.so linked with GL profiling ON (profile format present), then profiling OFF (profile format absent); the local default is restored to OFF. No APK install or actual ARM64 device run was performed.
- [ ] Pending: current ARM64 frame/GPU baseline, GL4ES direct/intercept byte-copy attribution, risky guest VBO exposure (not enabled), reducing duplicate menu parsing with correct allocator lifetimes, profiling exact hot renderer functions and any native NEON replacement. No unsupported FPS claims.

### Performance study of downloaded references — 2026-10-13

- Reviewed public runtime dispatch/GL bridge, Android compiler flags and targeted renderer, VM, filesystem and animation code in the four local upstream references.
- The full study remains local and ignored because it uses private diagnostic evidence. No private measurements or derived original-code analysis are published in this note.
- Follow-up proposals: measure the current baseline, compare selective compiler optimization, investigate native kernels, count graphics conversion work and separate loading stages. These are candidates rather than verified improvements.
- Study only: no game behavior changes, device execution or visual checks. New performance improvements remain proposed and unmeasured.

### Local workspace organization — 2026-10-13

- Follow-up: tracked VS Code settings hide legacy root aliases and exclude local/private build trees from search and file watchers. The editor now presents local material through `.local/` rather than duplicate root entries.

- Downloaded clean Git references for Quake3e, openmohaa, gl4es and opencod1, including declared submodules; revisions recorded in `docs/WORKSPACE.md` and the ignored local manifest.
- Installed the official Windows Android Performance Analyzer 0.9.0 portable distribution under `.local/toolchains/`; ZIP CRC verified and SHA-256 recorded. No visual inspection or phone capture performed.
- Grouped local build trees, pinned dependencies and private inputs under `.local/`, preserving old absolute paths through Windows junctions. Locked `build-retrotouch` and `recomp_out` remain physically in their original locations with reverse junctions into the organized folders.
- Added repeatable organization and APA launcher scripts; `.local/` is ignored. Game code and build dependency revisions are unchanged.
- Verified clean reference checkouts/submodules, accessible original build/APK paths, successful host build and all 19 CTest tests. Re-running the organization script completed without changes.

### Public release v0.2.3 — published 2026-10-13

- Published [v0.2.3](https://github.com/Dr3amyBerry/callofrecomp/releases/tag/v0.2.3) from commit `ebc663373a0825c49f39c70854cbec830c9e8094` with the latest CPU optimizations and updated release notes/README.
- Public ARM64 APK: version 0.2.3/code 5, 50,217,788 bytes. GitHub asset digest matches local SHA-256 `5a8a8026c9909821d7dcdcbc0a8bc66947b3fe64252cabd283e9ddbdb7970369`; Android v2/v3 signatures verified before upload.
- Release contains only `callofrecomp-arm64.apk` and `SHA256SUMS.txt`. Public APK contains no original game resources; the bundled private APK remains local.
- This release updates ARM64 only; WSA x86_64 remains available in v0.2.2. Gameplay FPS and the training wire scene still require user verification.

---

## 1. Operating objective

The objective is to complete as much of the reverse-engineering and native recompilation work as possible autonomously, with the least possible user intervention.

Default operating model:

1. Inspect the original game files from the connected Google Drive.
2. Build reproducible static-analysis tooling in this repository.
3. Record evidence and uncertainty instead of guessing.
4. Reconstruct interfaces and behavior in clean C/C++.
5. Build a portable platform-neutral core.
6. Add the Android ARM64 host/platform layer.
7. Validate against the original PC behavior.
8. Ask the user for help only when a required capability is genuinely outside the available tools or permissions.

I should not stop merely because a task is large. Work should be split into phases and committed incrementally to `main`.

---

## 2. Current status

### Crowded training scene CPU work — 2026-10-13

- User reports Samsung near 5 FPS at the wire/machinegun/crawling-soldier area.
  They confirm this is the previously installed APK, not the later local APK
  containing disjoint register/RAM parameters. The scene is not reproduced here:
  phones remain unused and all visual/gameplay checks stay with the user.
- Added conservative byte-level liveness of CF/PF/ZF/SF/OF across p-code control
  flow. Only pure writes proven overwritten before any read on every future path
  are replaced by semicolons; operation indices and branch labels remain stable.
  External/indirect exits, host/user ops and unknown instructions observe all flags.
  Faulting memory operands and arithmetic with effects are not removed. Diagnostic
  `--keep-dead-flags` retains the original generation path.
- Existing sampled hot chunks at 0x505485 and 0x5069dd lose 886/8,605 and
  471/7,339 statements respectively; 0x41aa7e loses 689/10,365. This counts
  generator statements, not time saved. Compiled full-state differential tests
  at O1/O2 cover every synthetic instruction entry, branch outcomes, overlapping
  reads, bounded relative loops and RAM effects; 14 dataflow regression tests pass.
- Reproducible owned `bench_flags.py`: paired host O1 runs 622/574/575 ms baseline
  versus 458/458/452 ms optimized, same full register image and checksum. It does
  not measure Samsung FPS.
- Evaluated a bit-exact common binary80 fast path. It matched 262,144 patterns,
  but inline ARM64 code made hot chunk 186 grow from 186,724 to 201,664 bytes.
  The small, variable isolated conversion gain does not justify that instruction
  cache cost. Withdrew the experiment, benchmark/reference duplication and halted
  its build; binary80 conversion is unchanged in the final implementation.
  Final flags-only ARM64 hot chunks shrink 186,724 to 174,656 and 137,804 to
  130,392 bytes, reducing the code footprint without the floating experiment.
- Graphics audit found ordinary GLES2 arrays already passed directly to the
  backend. The earlier identity-normalization patch applies to intercepted/list
  paths and is not established as active for the user's scene. No speculative
  VBO/batching settings or gameplay/quality reductions were introduced.
- Fixed diagnostic sampling aliasing: variable pseudorandom intervals replace
  the fixed 257-call cadence. Regression records 4,044 samples covering every
  phase of a repeating 257-call sequence. Compiled out of normal APKs; this is
  a diagnostic correctness fix, not an FPS optimization.
- All 19 CTest targets pass; independent review found no production blockers.
  Review's empty-block/unsorted-input robustness issue was fixed and regression
  tested. ARM64 version 0.2.3 (code 5) builds with profiling OFF; public and
  private local APKs include the preceding optimization as well. Public APK is
  50,217,788 bytes without original resources; private is 1,312,803,540 bytes.
  Signatures, alignment and private payload CRC pass; both native libraries match.
  Final sampler-enabled Android guest source compiles separately; normal native
  library contains no sampling strings. Code commit a829e80 passes GitHub CI.
  Phone FPS and GPU frame time remain unverified; original resources remain local.
  Published release v0.2.2 is unchanged. No phones or visual checks were used.

### CPU recompilation and graphics translation optimization — 2026-10-13

- Working without phones or visual checks. Generated supported chunks now expose
  the existing disjoint register/RAM invariant through scoped restrict parameters.
  Byte aliases within each space remain legal. Unsupported operations retain the
  identical global diagnostic path; `--shared-spaces` selects the old baseline.
- Compiled differential tests compare full registers, RAM and next PC for global
  temporaries, local baseline and local separated spaces, at O1 and O2. Includes
  overlapping registers, overlapping RAM, indirect addresses, branches and x87.
  Reproducible owned benchmark: `tools/recomp/bench_spaces.py`; host O1 baseline
  228–229 ms versus 59–76 ms optimized, identical checksum across three runs.
  NDK ARM64 O1 assembly for the same workload shrinks from 337 to 77 instructions,
  with loads reduced from 133 to 8; this is static code inspection, not a timer.
  This is an isolated memory/register workload, not phone FPS or mission loading.
- Pinned GL4ES patch skips subtracting zero from every ushort/uint draw index.
  Min/max and empty-array behavior stay exact. 40,000 differential cases pass;
  protected-memory probes prove this path no longer writes the index buffer.
  This reduces CPU graphics translation work; GPU frame-time improvement remains
  unmeasured. The build applies the patch idempotently and rejects foreign edits.
- Normal Android builds explicitly disable sampled CPU profiling, including when
  a prior diagnostic CMake cache enabled it. All 18 host tests pass; fresh review
  found no blockers and the initial optimization commit passes GitHub CI.
- ARM64 rebuild and local private packaging completed; signatures, alignment and
  private payload CRC pass. The public resource-free APK is 54,743,868 bytes;
  private APK is 1,317,325,524 bytes. Cache and native strings confirm profiling
  OFF. Public/private native libraries match exactly. The GL4ES applicator also
  handles Windows CRLF without changing line endings (regression test passes).
  Original resources remain local; published release v0.2.2 is unchanged.

### Further CPU and memory commitment optimization — 2026-10-13

- Real Tecno follow-up after installation: CL_InitCGame 46.87 seconds; gameplay
  intervals ranged from 4–17 FPS in parts of the route to 26–39 FPS elsewhere.
  The user still reports deplorable performance. The isolated improvements do
  not resolve the device's loading/gameplay bottleneck; do not claim otherwise.
- Added opt-in frame timing for engine-thread CPU, swap wait and host pacing,
  and split sampled host CPU by DLL/function rather than one combined bucket.
  Profiling compile flags affect guest.c only, avoiding a full generated-code
  rebuild when enabling diagnostics. The detailed diagnostic is installed on
  the Tecno as a small local update reusing already imported original files.
  Detailed gameplay: roughly 9–15 FPS with profiling, frame wall time 90–110 ms,
  engine-thread CPU 85–107 ms, swap 2–4 ms, pacing approximately zero. Includes
  profiling overhead and CPU graphics translation; short swap does not prove
  GPU work is free. Normal profiling remains OFF. Periodic sampling can alias
  repeated call sequences; sampled times are candidates, not exact percentages.

- Confirmed ARM64 signed divisions were calling the 128-bit `__divti3` helper
  for operands no wider than 64 bits. Native signed division/remainder now
  replaces that path, with explicit MIN/-1 overflow handling before truncation;
  genuinely wider inputs retain the original implementation. Unsigned division
  was already compiled into a native instruction and was left unchanged.
- Compiled equivalence tests cover all 64 input-width pairs from 1 through
  8 bytes, 128,000 deterministic input combinations including signed extrema.
  Isolated WSA division benchmark: 7.27 ns/op baseline versus 2.31 ns/op native,
  identical checksum. This does not measure game FPS or the Tecno.
- Guest memory commitment now batches consecutive new 4-KiB pages into one
  OS call, stopping at already committed pages and preserving their contents.
  A fresh 64-MiB range requires one call instead of 16,384. WSA isolated
  commitment CPU time averaged 2,596.15 versus 4.56 microseconds over eight
  allocations; page faults/data initialization are excluded from this probe.
- 18 host tests pass; independent review found no blocking correctness issue.
  The actual memory lifecycle test also passes as an NDK executable on WSA.
  Final ARM64 APK compiles, verifies its signature and contains no original
  EXE/DLL/PK3 assets. The private bundled APK is rebuilt locally only; release
  v0.2.2 remains the previously published build. No visual checks or phone tests
  were made, and these microbenchmarks do not establish improved whole-game FPS.

### Android loading feedback and runtime overhead — 2026-10-13

- Follow-up: instruction temporaries now use compact local storage when byte-level
  control-flow analysis proves every read is initialized on every reachable path.
  Overlapping byte aliases are preserved; one unproven instruction rejects local
  generation and requires explicit global storage for all linked modules.
  Independent review caught the danger of a silent per-module fallback when
  uniques cross module boundaries; that fallback was removed. All four exports passed
  this analysis. Before replacing generated outputs, diagnostic regeneration
  with global temporaries matched each existing source exactly.
- WSA isolated memset benchmark: 197 ns/call with global temporaries versus
  102 ns/call with local temporaries; output and the entire register image matched.
  This is a microbenchmark, not measured whole-game FPS or a Tecno result.
  Compiled synthetic equivalence checks cover 1,000 random register states,
  overlapping byte aliases, conditional paths, memory stores and x87 conversions.
- Full WSA training initialization, alternating baseline/optimized twice with no
  compiler running: 13.50 / 8.85 and 13.77 / 8.97 seconds (CL_InitCGame), about
  35% less initialization time. Same WSA/profile, warm caches; this measures
  initialization rather than gameplay FPS. The earlier 16.46-second baseline ran
  during compilation and is excluded from the comparison. Both final ABI APKs
  are signed and verified; ARM64 shrank from about 74.6 to 57.7 MB. Generated-code
  builds retain line tables instead of enormous per-temporary debug records.
  Removed the temporary benchmark autoexec and restored the normal APK in WSA.
  The Tecno is unavailable for further tests; the user requested continuing with
  automated comparisons. WSA cannot simulate its Mali GPU or certify its FPS.
- Added a native-driven, indeterminate loading indicator for engine startup,
  PK3 initialization, graphics, menu and mission loading. It consumes actual
  original console milestones and waits for a presented frame before hiding;
  no fabricated percentage or timer-based readiness. Android polls four times
  per second and suspends polling in the background.
- A regression check also covers menu-only graphics restarts: they do not emit
  Common Initialization a second time, so a finished menu parse followed by
  presentation releases the overlay. Mission parsing remains blocked until
  CL_InitCGame completes even if graphics are restarted during mission loading.
- Read-only PK3 handles use demand-paged mappings on Android/POSIX, with bounded
  copies, logical seek/EOF behavior and FILE fallback. Archives are neither
  extracted again nor copied wholesale into RAM. Windows/writable handles retain
  the FILE implementation. Synthetic seek/EOF tests pass on Windows, WSA and Tecno.
- Indexed recompilation dispatch by 4-KiB guest pages, replacing repeated binary
  searches with a direct lookup except for shared-page boundaries. Index costs
  2 MiB and is rebuilt after module load/unload; lifecycle and boundary tests pass.
- 17 freshly built host tests pass. Both Android ABI builds compile and verify
  signatures. Full-device 60 FPS is not established: prior Tecno logs showed
  5,566 ms + 1,204 ms for menu parsing, and the user reported training stutter in
  Equilibrado. The user confirmed the indicator appears and disappears correctly,
  but reported no improvement in loading or gameplay. New Tecno logs confirm
  CL_InitCGame still takes 47.17 seconds, with 8–15 FPS during the gameplay test.
  File mapping and the dispatch index do not resolve the main bottleneck.
- Added opt-in, sampled per-chunk thread CPU timing (`profile/cpu_stats`) to
  distinguish generated engine work from host calls before further optimization.
  The diagnostic APK was installed locally and the user completed a fresh run,
  recording 5–12 FPS during movement. Sampling includes clock overhead and nested
  calls, so it identifies candidates rather than exact CPU percentages. Profiling
  is compiled out of normal APKs (`CODRECOMP_CPU_PROFILING` defaults OFF). Debuggerd
  and simpleperf are restricted on this phone; device security was not changed.
- Package version 0.2.2 (code 4). Private bundled resources remain local. No
  screenshots or visual checks were performed; user reviews the loading overlay.

### Tecno full-screen surface sizing — 2026-10-13

- Read-only ADB diagnostics on the connected TECNO CK6n (1080×2400) confirmed
  the private APK's SurfaceView occupied only 1280×602 pixels, with no compositor
  upscaling. SDL's default RelativeLayout parameters were WRAP_CONTENT, which
  measured the fixed-size rendering buffer as the display view itself.
- PerformanceSurface now supplies MATCH_PARENT parameters before SDL adds it,
  retains the lower-resolution EGL buffer, recalculates its aspect after layout
  changes, and defers SDL startup for stale pre-layout buffer callbacks.
- GameActivity requests immersive full-screen mode. Package version is 0.2.1
  (code 3). Private bundled APK stays local; public release excludes all game data.
- No screenshots or visual checks were performed; the user verifies appearance.
- Installed the private 0.2.1 update over the previous APK on the Tecno, retaining
  app data. The user confirmed that the image now fills the screen. Public APKs
  contain the same surface correction, without the private bundled resources.

### Public package importer and published 0.2.0 prerelease — 2026-10-12

- Added a browser-local, dependency-free installation packager under `web/dist/`.
  It checks the four baseline PE hashes, excludes saves/configuration, and streams
  uncompressed CODPACK1 files with per-file CRC32. Large packages use Chrome/Edge
  file-system writes; in-memory download fallback is limited to 512 MiB.
- Android now accepts `.codpack` through the document picker, extracts into staging,
  rejects unsafe names/duplicates/truncation/CRC errors/oversized inputs, then checks
  the existing SHA-256 baseline before replacing resources. Failed extraction cleans
  staging and preserves the previous installation; profile data stays separate.
- Added synthetic Java/JavaScript tests, including browser-writer → Java-reader
  interoperability, and CI coverage. Android package version is now 0.2.0 (code 2).
- Reworked the README around installation, performance profiles, honest verification
  limits and development requirements; retained the detailed analysis guide separately.
- Public release assets must be the regular ARM64/x86_64 APKs only. The ignored
  preimported private APK and all original game files must remain local.
- Published the [public packager](https://callofrecomp-packager.mauvezebra128.chatgpt.site)
  and [0.2.0 prerelease](https://github.com/Dr3amyBerry/callofrecomp/releases/tag/v0.2.0).
  Release commit: `366629c4c3a78e8f070200b49df829545d024af5`;
  [CI](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38342929777) passed.
  Both public APKs have verified v2/v3 signatures and 16-KiB ZIP alignment;
  their uploaded SHA-256 digests match the local files. Assets are ARM64 (74,625,852
  bytes), x86_64 WSA (83,526,451 bytes), and SHA256SUMS.txt only. APK content audit
  confirmed no original EXE/DLL/PK3 or private-originals asset directory.
- Visual checks and real-device gameplay remain delegated to the user as requested;
  this import feature does not establish that campaign objectives are completable.

### Android modest-device profiles and tutorial objectives — 2026-10-12

- User clarified objectives appeared together rather than completing themselves.
  Inspection of owned `maps/training.gsc` confirms all eleven are registered by
  concurrent startup threads; individual completion waits on their original
  triggers/events. No tutorial script or mission behavior was modified.
- Added persistent launcher graphics profiles: balanced (up to 1280×720), light
  (up to 960×540), and native. Low-RAM Android devices default to light, others
  balanced. Resolution budgets preserve the display ratio without upscaling.
  SurfaceHolder fixed-size buffers lower actual GPU raster work while Android
  scales the image across the full view; RetroTouch/menu overlays remain full size.
  SDL fallback touch coordinates are transformed from view to buffer space.
- Lower profiles reduce texture/LOD expense, dynamic lights and shadows; light
  additionally simplifies sky/detail textures. Original graphics cvars are applied
  before renderer initialization, including old profiles. High mode restores these
  settings. Android frame pacing sleeps during the final fractional interval
  instead of repeatedly yielding; audio mixing computes its rate ratio once per
  voice/buffer rather than every output frame.
- Manual performance, surface scaling and input verification remain with the user
  in flash mode. The cap remains 60 FPS, with no guarantee of reaching it on all
  phones. This change has not been benchmarked on a physical modest ARM64 device.

### Native widescreen configuration — 2026-10-12

- User reported stretched 4:3 presentation and supplied the original custom-mode
  workaround. The Android host previously set only custom width/height, omitting
  `r_customaspect` and camera FOV. Added the actual display ratio and a horizontal
  FOV derived from the original 80-degree 4:3 view, preserving vertical coverage
  while revealing more of the world horizontally (about 96.42 degrees at 16:9).
- PC startup now uses the current display dimensions and ratio too; explicit
  command-line arguments can override its defaults. Android applies its landscape
  display settings on launch, including existing profiles. Uses the original
  renderer's custom mode, with no asset rescaling or projection interception.
- Visual validation belongs to the user in flash mode. Check world geometry,
  aiming, menus/HUD and touch alignment; legacy 2D artwork has not been redesigned.

### 60 FPS and campaign fixes packaged — 2026-10-12

- Added monotonic presentation pacing with a 60 FPS ceiling, no catch-up burst
  after slow frames, and an Android `com_maxfps 60` startup setting. Fractional
  touch-look deltas now accumulate instead of losing slow camera movements.
- Found a real campaign blocker: ten-byte x87 slots contained padded doubles,
  while the original embedded CRT expected binary80. Corrected slot encoding;
  arithmetic remains double precision/range, not a full x87 implementation.
  A private original-function probe reproduced infinite yaw before the fix and
  six correct vector angles afterward. Rebuilt native PC objects now load and
  exit Brecourt and Hurtgen, both of which previously timed out.
- Added reproducible private static campaign/resource auditing and native map
  startup probing. Static graph: 33 reachable maps, 26 gameplay/training, six
  briefings and credits. All 33 initialized and exited normally in the numeric-fix
  startup sweep. This sweep preceded the subsequent lifecycle/audio changes.
  Objective completion, AI/trigger reachability and every exit remain
  separate interactive obligations; neither static checks nor forced-success
  fixtures certify that all missions are completable.
- A private forced-success fixture exposed stale navigation data after changing
  levels: `FreeLibrary` was a no-op. Its isolated unload/reload experiment reached
  training → us_intro → pathfinder, then exhausted memory. Implemented DLL
  reference counts, detach/unload, dispatch removal and zeroed image reloads.
  Private CRT heaps now have distinct owners and real `HeapDestroy` reclamation;
  freed TLS slots are cleared and reused across DLL reloads;
  PCM WAV metadata borrows original payload bytes instead of leaking copies.
- Final PC, Android ARM64 and native WSA x86-64 builds completed. All 15 CTests
  and Java installation/touch checks pass. No final gameplay/visual verification
  was performed: the user explicitly requested flash mode and took responsibility
  for manual checks. Entire campaign completability remains unverified.
  See `docs/guides/MANUAL_PLAYTEST.md` and `docs/guides/CAMPAIGN_VERIFICATION.md`.

### Original menus and Android host checkpoint — 2026-10-12

- Current user priority is RetroTouch controls that can be hidden for menus,
  and playable **training before campaign missions**, tested through
  ADB on local WSA (`127.0.0.1:58526`, Android 13, ARM64 native-bridge support).
- Restored original cleanup callbacks `0x0047EEE0`, `0x0051A430`, `0x00532010`
  and `0x00532020`, each verified against original instructions/registration
  sites. The private export now contains 333,208 instructions. Actual desktop
  startup parses the original menus, completes common initialization and exits
  normally with `+quit` (exit 0); previously it failed during cleanup.
- Added thread-safe queued input for normalized menu touches, scancodes, buttons
  and relative look. A 400-event burst reproduced dropped releases; pumping
  now pauses before the Win32 message queue fills, preserving later events.
  All 12 CTests pass, including the new touch and overflow regressions.
- Android SDL2/GL4ES integration and all four modules now compile to a private
  ARM64 debug APK (about 51 MiB), with verified v2/v3 signature and 16-KiB
  ELF/ZIP alignment. The reproducible SDK builder also supports native x86-64 WSA.
- Real WSA launcher and SAF import succeed; SHA-256 validation accepts the owned
  baseline and rejects other binaries. Spanish localization is selected from
  imported packs. Profiles/logs use separate internal storage, preserving saves.
- ARM64 under WSA's Houdini 14 bridge completes common initialization and parses
  original menus, but a first frame/gameplay is still unverified. An isolated
  SDL inline-atomic experiment did not resolve it and was removed. An optimized
  native x86-64 comparison now displays original menus and playable Camp Toccoa.
  The user also confirmed the visible original menu in WSA; physical ARM64
  gameplay remains unverified.
- Integrated the actual pinned RetroTouch 1.0.0-beta.4 AAR, its FPS layout,
  editable/persistent buttons, movement, look, fire/aim, reload/use, stance,
  prone/lean/objectives, grenade, melee and next weapon. CONTROLES/OCULTAR selects GAMEPLAY/OFF;
  MENU sends Escape and hides controls. Hide, pause and focus loss release input.
- Fixed splash-to-game activation and absolute menu mapping to the verified
  640x480 UI cursor. Batched touches replace pending movement; the regression
  failed before that fix and passes after it. UI movement still runs through
  the original engine's VM context, not a direct module callback.
- WSA x86-64 tests: direct Options/back/new-game touches, Regular -> `Server:
  training`, Camp Toccoa briefing/start, visible 3D characters/world, joystick
  movement, relative look and original pause menu with controls hidden.
  Loading the training autosave through Continue also succeeds; TUMBARSE changes
  the stance to prone in the visible training world without a keyboard.
  Both ARM64/x86-64 APKs build with v2/v3 signatures and 16-KiB ELF/ZIP alignment.
- Android host/build commit `bd071cb` pushed; GitHub CI `38278346310` passed.
- A restricted desktop CTest run exposed missing LLVM-MinGW `libc++.dll` and
  `libunwind.dll`, producing Windows loader dialogs. The build now deploys C++
  runtime DLLs once for all C++ tests. Reproduction changed from status
  `0xC0000135` to exit 0 in the same restricted environment; 12/12 checks pass.
- Actual ARM64 WSA logs now confirm `Current language: spanish`. The Android
  host must pass numeric `cl_language=4`, per the recovered original table;
  passing the string `spanish` silently selected English. Java tests now assert
  the numeric engine indices instead of only the resource-pack names.

### PC mission checkpoint — 2026-10-12

- Current user priority: first mission playable on PC, then Android.
- Added real MP3 stream decoding through original engine filesystem callbacks,
  with owned compressed bytes, fixed decoded blocks, seek, pause and loop states.
  Decoder source is pinned CC0 minimp3; original assets remain outside Git.
  Vendored decoder files retain LF endings so recorded hashes survive Windows
  checkouts with automatic line-ending conversion.
- All 12 CTest checks pass, including synthetic MP3 streams with short reads.
- Actual `+spmap training` finishes `CL_InitCGame` and visibly shows the original
  Spanish briefing with “Haz clic para iniciar la misión”. Screenshot and run log
  are private artifacts under `recomp_out`; the process stays active beyond 45s.
- First-person scene, movement and sustained gameplay are not verified yet.
  This checkpoint does not complete the playable-mission goal.
- A queued fast-click regression reproduced lost button transitions (exit 7).
  Mouse state now follows each SDL event; the regression and all 12 CTests pass.
- Added a separate optional timed SDL integration probe. Its actual briefing
  click reached missing entry `0x004DD6E0`. Original instructions verify its
  assignment at `0x004F101A` to slot `0x011D92E4`; the entry is now included in
  the reproducible export ledger. Gameplay verification is continuing.
- The rebuilt probe passes `0x004DD6E0` and next reaches a missing GL setup
  switch branch, `0x004DBD61`. All four destinations from the original bounded
  jump table at `0x004DC180` are verified and added to the export ledger.
- An actual branch to `0x004DC14B` exposed overlapping Ghidra code units.
  Explicit code-entry export now requires an instruction starting exactly at the
  verified address and retries the independently decoded instruction span when
  necessary, then revalidates all explicit entries before writing the output.
  Original `JE` at `0x004DC13E` verifies that destination; successful export now
  contains 333,204 engine instructions. No sweeping of arbitrary bytes is enabled.
- The actual probe now enters the visible first-person training scene, with
  soldiers, terrain and HUD, and remains active after timed W down/up input.
  Original Foley speech exposed PCM WAV streams (mono, 22,050 Hz); these now use
  real SDL decoding and owned PCM. WAV stream test reproduced failure (exit 44)
  and now passes with all 12 tests. The rebuilt `pathfinder` campaign probe
  finishes `CL_InitCGame` (18.37s) but crashes at `0x0052E84C`, accessing
  `0xEF7AF00C`, before the timed click. That memory access is the next blocker;
  campaign movement and sustained gameplay remain unverified.
- The exact-entry exporter was exercised against a deliberately conflicting byte
  inside a known five-byte MOV in a read-only Ghidra session. It recovered the
  entry and exported the same 333,204 instructions without saving project changes.
- Located the campaign crash: TIB and CPUID scratch overlapped the declared 4-MiB
  stack. A large original game frame overwrote the SEH pointer. Both service pages
  now live below the stack; a regression checks disjoint ranges and fills the
  entire stack while preserving TIB/CPUID (RED exit 26, GREEN 12/12 CTest).
- The rebuilt `pathfinder` probe starts the mission, creates the original save
  and queues movement. The user confirms this is mission 1 and controls work,
  and clarifies that reload is smooth while aiming with the initial weapon
  stutters. ADS interpolation is now the active investigation.
  Closing the game also exposes missing shutdown entry `0x0047EEE0`.
- Added optional frame statistics and timed fire/reload/aim input. The first
  campaign sample rendered around 64 FPS after entry, but an existing-autosave
  operation produced the original “insufficient disk space” error despite ample
  host free space. Save finalization needs investigation before that pacing sample
  can cover the full weapon sequence.
- Located the repeated-autosave failure: MoveFileA returned failure without
  setting GetLastError, so the original CRT reported rename success and skipped
  the engine's delete-and-retry path. File moves now reject an existing target on
  every host and report Win32 errors; DeleteFileA also reports failure errors.
  Synthetic replacement regression failed with exit 9 before the fix and all
  12 CTests pass after it. The original campaign probe now replaces the existing
  autosave successfully and continues rendering. A private GL framebuffer capture
  confirms the first-person campaign scene; original assets remain ignored.
- Reproduced the isolated ADS stutter: 6 distinct aim fractions in 34 rendered
  transition frames, held between roughly 50-ms server updates. Per-call fake
  clocks made CPU calibration report 0.0625 MHz and select a no-prediction profile.
  Real mode now uses monotonic time and native x86 RDTSC; deterministic trace
  mode remains unchanged. The original engine measures 3.59 GHz, selects its
  2000-MHz profile and keeps cg_nopredict at its registered default 0. The repeat
  probe records 26 distinct fractions in 26 transition frames. Clock regression
  failed before the change (exit 17); all 12 CTests now pass. Existing profiles
  require restoring cg_nopredict 0; visual user confirmation is pending.

### Completed foundation

- [x] Connected to and inspected the supplied Call of Duty Deluxe installation in Google Drive.
- [x] Confirmed the base game reports Call of Duty **1.5** on PC.
- [x] Isolated the initial single-player binaries:
  - `CoDSP.exe`
  - `gamex86.dll`
  - `cgamex86.dll`
  - `uix86.dll`
- [x] Confirmed all initial target binaries are PE32 / x86.
- [x] Fingerprinted the initial binaries with SHA-256.
- [x] Inventoried the base `main/` PK3 set at Drive metadata level.
- [x] Established the repository policy that original proprietary game assets remain outside Git.
- [x] Added a dependency-free PE32 analysis tool.
- [x] Added a non-extracting PK3 inventory tool.
- [x] Added a first module-ABI probe.
- [x] Confirmed all three single-player modules export `dllEntry` and `vmMain`.
- [x] Recovered the module-global syscall callback slots installed by `dllEntry`.
- [x] Recovered indexed `vmMain` dispatch tables.
- [x] Began recovering numeric module → engine syscall IDs.
- [x] Located the native module loader / VM creation path in `CoDSP.exe`.
- [x] Located the engine `VM_Call` wrapper and all three VM-handle globals.
- [x] Located the game/cgame/ui module→engine syscall callbacks.
- [x] Recovered all three engine-side syscall jump tables and their numeric ranges.
- [x] Added an engine VM probe that emits reproducible JSON for both directions of the ABI.
- [x] Extended the PE inspector to record import IAT addresses.
- [x] Confirmed the dynamic OpenGL/WGL loader path: `LoadLibraryA("opengl32.dll")` + `GetProcAddress` and renderer function-pointer population.
- [x] Corrected and completed the current SP UI export map: IDs 0–8 and 10–13 are matched; ID 9 remains deliberately unnamed.
- [x] Mapped the evidence-backed SP game syscall prefix 0–19, including SP-only `G_ENDGAME` and `G_CVAR_SETVAR` insertions.
- [x] Added a verified build profile containing hashes and recovered VM addresses for this exact CoD 1.5 SP baseline.
- [x] Added a one-command baseline analyzer that verifies the binary hashes before generating PE/module/engine VM reports.
- [x] Added a portable 32-bit legacy VM word ABI header and the first reconstructed SP game syscall enum.
- [x] Added CMake host-build scaffolding and a first ABI smoke test.
- [x] Added CI that compiles/smoke-tests analysis tools and builds/runs the host ABI test.
- [x] Documented the external-reference verification/licensing policy; public reconstruction code without a declared license is not copied into this repository.
- [x] Established an evidence ledger using `observed`, `matched`, and `inferred` confidence levels.
- [x] Audited the current `main` tree before editing; preserved the newer engine/renderer/reference findings and existing build files.
- [x] Rechecked SHA-256 fingerprints for all four private single-player binaries; they match the pinned baseline.
- [x] Reproduced module `vmMain` limits and callback-slot RVAs using the original binaries.
- [x] Verified existing CI runs pass before expanding tools.
- [x] Added six offline Python regression tests covering synthetic PE structure, malformed input, ASCII extraction, dispatch limits, immediate syscall sites, and an optional exact-binary check.
- [x] Registered those Python regressions with CTest; existing GitHub Actions executes them without requiring a workflow rewrite.
- [x] Added an evidence-only engine syscall-handler edge inventory tool using bounded `objdump` disassembly.
- [x] Recorded the first direct branch targets for all 24 SP game syscall handler entries 20–43 in `analysis/game_syscall_edges_20_43.md`.
- [x] Added a decoded-branch regression test for the new edge tool.
- [x] Recovered direct argument-slot references and return shapes for SP game syscall IDs 20–43 against the original `CoDSP.exe`.
- [x] Added `tools/syscall_signature_probe.py` with deterministic JSON export and conservative confidence terminology.
- [x] Verified the result categories for all 24 cases: **12 forced-zero EAX**, **6 tail-jumps**, and **6 EAX-not-cleared**.
- [x] Added five synthetic unit tests covering argument indexing, explicit zero returns, tail returns, untouched EAX and out-of-range instruction windows.
- [x] Added seven independently matched non-contiguous SP syscall names (21–23, 36–37, 40–41) to `include/codrecomp/game_sp_syscalls.h`.
- [x] Added numeric ABI assertions to the C host smoke test and verified GitHub CI success for the test/header changes.
- [x] Documented signatures, addresses, evidence and unverified cases in `analysis/sp_game_syscall_signatures_20_43.md`.
- [x] Identified all seven canonical game-module syscall wrappers (21/22/23/36/37/40/41) at their exact 1.5 SP virtual addresses.
- [x] Independently confirmed the DLL callback pointer slot at `0x200A4834` and reconstructed ordered wrapper argument origins.
- [x] Provenanced ID 40's *fourth* callback argument to a preserved `EAX` value and its first to the caller's stack word; avoided a three-argument ABI mistake.
- [x] Added `tools/module_wrapper_probe.py` with optional SHA-256 guard, bounded scanning, deterministic JSON output and fail-closed parsing.
- [x] Added wrapper-provenance regression tests (four synthetic + one optional exact-original DLL check).
- [x] Added portable native-pointer-width filesystem/command service contract `include/codrecomp/host_services.h` (interface only; runtime bridge not yet implemented).
- [x] Added `tests/host_services_smoke.c` and registered it in CTest/CMake to verify calling through the new host boundary without pointer truncation.
- [x] GitHub Actions succeeded for wrapper tests and host-services compilation/CTest registration.
- [x] Documented source addresses and exact argument order in `analysis/module_syscall_wrapper_provenance.md`.
- [x] Extended the one-command verified baseline analyzer with the optional `--with-wrapper-provenance` flag; the existing default pipeline remains unchanged.
- [x] Updated the README to document provenance recovery and pointer-width-safe host service contracts.
- [x] Implemented a **working read-only C++17 VFS** for loose files and ZIP32/PK3 members with zlib.
- [x] Added central-directory indexing, stored/DEFLATE extraction, CRC-32 and file-size validation.
- [x] Added traversal/absolute path/symlink escape checks, 64 MiB per-file read caps, and ZIP32-only fail-closed behavior.
- [x] Added `tests/vfs_smoke.cpp` with generated stored/deflated PK3 fixtures, invalid CRC/ZIP, mount order and traversal checks.
- [x] Verified original `main/pakb.pk3` can be mounted and its two known binary/menu members read and CRC-validated (24 indexed files).
- [x] Verified original Spanish localization PK3 `localized_spanish_pak4.pk3` mounts and both menu files can be read and CRC-validated (2 indexed files).
- [x] Integrated `codrecomp_vfs` with zlib and CTest in CMake; corrected a compilation error found by CI and confirmed a subsequent GitHub Actions run succeeded.
- [x] Fixed CI paths so changes under `src/**` trigger source compilation/testing.
- [x] Independently mapped the four numeric `FS_FOpenFile` branches in original `CoDSP.exe`, leaving their semantic mode names unverified.
- [x] Documented this phase in `analysis/filesystem_vfs_phase.md`.
- [x] Implemented native read-only `ReadOnlyHostAdapter`: connects VFS to `cod_host_services_t` callbacks (`fs_open`/`fs_read`/`fs_close`).
- [x] Added opaque host handles, independent read cursors, partial read/EOF handling, error checks and mutex-protected handle state.
- [x] Exposed a caller-provided accepted read mode; **did not** guess or hardcode the original game's numeric mode semantics.
- [x] Kept write/rename/list/console host callbacks disabled until their semantics are verified.
- [x] Added `tests/host_adapter_smoke.cpp` and CTest target; local test and GitHub CI completed successfully.
- [x] Updated `analysis/filesystem_vfs_phase.md` with the host interface versus original VM ABI distinction.
- [x] Verified original FS open modes against the exact CoD 1.5 SP binary: `0=rb/read`, `1=wb/write`, `2=ab/append`, `3=ab/append with post-write sync flag`.
- [x] Located the original filesystem searchpath head at `0x013F9E3C`, its linked-list traversal from the read helper, and a conditional insertion routine; full package/localization priority remains **unresolved**.
- [x] Added `analysis/fs_modes_and_searchpath_evidence.md` with original VAs and reproducible disassembly commands.
- [x] Implemented `GuestMemory` as bounded explicit 32-bit address regions with mapping permissions, NUL-bounded string reads, overflow checks and little-endian u32 access.
- [x] Added `LegacyFsReadBridge` for observed SP syscall IDs `21` (mode 0 open), `22` (read) and `37` (close). The bridge never casts a guest address to a native pointer.
- [x] Added guest-memory, handle, bounds, error, EOF and forbidden-write regression tests in `tests/guest_vm_bridge_smoke.cpp`, integrated into CMake/CTest.
- [x] Confirmed **6/6 CTest targets passed** in GitHub Actions for commit `8a1f743`, including the new VM bridge. No original game binary was bundled.
- [x] Documented contract, confidence limits and test instructions in `docs/guides/LEGACY_FS_BRIDGE.md`.

### Confirmed module ABI data

| Module | `vmMain` commands | callback-slot RVA | jump-table RVA |
|---|---:|---:|---:|
| `gamex86.dll` | 25 (`0..24`) | `0x000A4834` | `0x0001CF4C` |
| `cgamex86.dll` | 26 (`0..25`) | `0x000657E8` | `0x00018F3C` |
| `uix86.dll` | 14 (`0..13`) | `0x00034030` | `0x00007A50` |

### Confirmed engine VM boundary

| Module | engine VM-handle slot | module→engine callback | syscall range |
|---|---:|---:|---:|
| `game` | `0x013F9DB8` | `0x0044A2F0` | `0..211` |
| `cgame` | `0x014BD620` | `0x00401A50` | `0..252` |
| `ui` | `0x014BD648` | `0x00410B00` | `0..84` |

Observed engine VM functions:

- native VM loader / creation path: `0x0044F0E0`
- VM call wrapper: `0x0044F270`

### First module syscall recovery pass

| Module | indirect callback calls | distinct immediate IDs recovered | unresolved sites |
|---|---:|---:|---:|
| `gamex86.dll` | 1,187 | 161 | 214 |
| `cgamex86.dll` | 1,144 | 240 | 179 |
| `uix86.dll` | 377 | 74 | 63 |

These IDs are numeric evidence only. Semantic names are not assigned until supported by additional evidence.

### First engine→module command recovery pass

| Module | classified `VM_Call` sites | distinct immediate command IDs |
|---|---:|---:|
| `game` | 43 | 19 |
| `cgame` | 33 | 23 |
| `ui` | 37 | 13 |

The narrow scanner intentionally leaves non-immediate/register-driven cases unresolved rather than guessing.

### UI export commands matched so far

The supplied SP UI binary now has evidence-backed working names for IDs 0–8 and 10–13:

`UI_GETAPIVERSION`, `UI_INIT`, `UI_SHUTDOWN`, `UI_KEY_EVENT`, `UI_MOUSE_EVENT`, `UI_REFRESH`, `UI_IS_FULLSCREEN`, `UI_SET_ACTIVE_MENU`, `UI_GET_ACTIVE_MENU`, `UI_CONSOLE_COMMAND`, `UI_DRAW_CONNECT_SCREEN`, `UI_LOAD_SCRIPT_MENU`, and `UI_GET_FONT_INFO`.

ID 9 is an observed zero-argument menu-state boolean query but remains intentionally unnamed instead of inheriting an incorrect RTCW/MP label.

### SP game syscall semantic recovery

The game-module dispatcher range is `0..211`. IDs `0..19` now have independently verified working semantics:

`G_PRINT`, `G_ERROR`, `G_ERROR_NOPREFIX`, `G_ENDGAME`, `G_MILLISECONDS`, the VM-cvar register/update/set/setvar/query group, `G_ARGC`, `G_ARGV`, and the first hunk allocation/temp-allocation group.

The SP table is not a drop-in copy of the known multiplayer enum: `G_ENDGAME` is inserted at ID 3 and a VM-cvar set-by-handle operation is also present.

---

## Verification checkpoint (2026-10-07)

- Inspected the repository `main` tree and current commit before changes. Existing analysis and source were not overwritten.
- Recomputed SHA-256 hashes of the four exact private PC 1.5 SP binaries and independently confirmed the stored fingerprints.
- Re-ran the PE32 metadata collector and initial VM ABI probe against all four originals; observed the original module-command and immediate-call counts.
- Ran the new synthetic/optional-real binary tests locally before publishing; **6 passed** with `CODRECOMP_ORIGINALS` set. Without original files, **5 passed + 1 expected skip**.
- GitHub CI for the Python/CTest regression integration and subsequent edge-tool update completed successfully. This verifies repository checks, not Android playability.
- A change to `.github/workflows/tools-ci.yml` was not accepted by the integration; the necessary test registration was instead made through the existing `CMakeLists.txt`/CTest path. No workflow override was needed.
- The edge analysis is evidence-only: entries 20–43 have decoded direct branch destinations, **not** fully identified syscall semantics.
- **Next task (superseded by the signature pass below):** signature/return categories and selected evidence-backed semantic names are now recovered. Full callee argument/ownership tracing remains open.

## Signature-analysis checkpoint (2026-10-07)

**Inputs verified:** the pinned original `CoDSP.exe` SHA-256 matches `analysis/baselines/cod1_sp_pc_1_5.json`. All 24 dispatcher cases (20–43) were parsed from binary disassembly, and their direct `[EBP + offset]` references were decoded to argument indices.

- EBP points to the syscall word array; slot `[EBP+0]` is the syscall ID, not a user argument.
- 12 handlers force EAX=0; 6 delegate via a tail jump; 6 do not reset EAX. These are **low-level shapes**, not finalized C types or behavior claims.
- Matched working names: `G_FS_FOPEN_FILE` (21), `G_FS_READ` (22), `G_FS_WRITE` (23), `G_FS_RENAME` (36), `G_FS_FCLOSE_FILE` (37), `G_FS_GETFILELIST` (40), `G_SEND_CONSOLE_COMMAND` (41).
- ID 20 and the other unnamed IDs remain intentionally **unknown**; an adjacent `Hunk_Clear` diagnostic is **not enough** to name ID 20 because it belongs to a different entry address.
- Five new synthetic tests passed locally. The corresponding tool and enum/smoke-test CI runs have completed successfully on GitHub.
- No new external tool is needed yet. A full decompiler (e.g. Ghidra) will be requested only when materially necessary to recover unverified callee semantics/ownership.
- **Next autonomous work:** trace the module-side syscall wrappers for the seven matched IDs, strengthen argument/return signatures, and implement portable filesystem/Cbuf interface contracts without relying on C casts from 64-bit pointers to 32-bit legacy VM words.

Reference: [`analysis/sp_game_syscall_signatures_20_43.md`](../../analysis/sp_game_syscall_signatures_20_43.md).

## Module-wrapper and native host-interface checkpoint (2026-10-07)

**Verified original DLL:** `gamex86.dll` SHA-256 `27930aa3f663d0af39a90e6956c980be1e599e0f0c98191a9fb7eaba61481577`; `dllEntry` stores callback at `0x200A4834`.

Canonical native wrappers recovered directly from the original DLL:

| ID | Wrapper VA | Data words supplied to engine callback |
|---:|---:|---|
| 21 | `0x20042840` | `EDX, ECX, EAX` |
| 22 | `0x20042850` | `EDX, ECX, EAX` |
| 23 | `0x20042860` | `EDX, ECX, EAX` |
| 36 | `0x20042940` | `ECX, EAX` |
| 37 | `0x20042950` | `EAX` |
| 40 | `0x20042980` | `stack_arg_0, EDX, ECX, EAX` |
| 41 | `0x200429A0` | `ECX, EAX` |

The word order is **observed**, but does **not** establish each wrapper's higher-level C calling convention. This is a bounded and deliberately conservative analysis. Code that accesses unmodeled instructions fails rather than inventing sources.

**Validation:** an implementation prototype ran the five wrapper-provenance checks against the original local binary (passed); the same narrow logic and synthetic fixtures were committed. GitHub Actions successfully ran the new tests and the new host-services CMake target. The host interface is currently a compiled/tested **contract**, not a working filesystem implementation or native Android binary.

**No active external blockers.** The existing GitHub Actions CI also passed the opt-in baseline analyzer change. Remaining work: trace caller/callee parameter types, filesystem modes, directory policy and handles, then implement a safe 32-bit VM-to-native host bridge with runtime validation. Do not confuse the new native host-service prototypes with original x86 exports.

See [`analysis/module_syscall_wrapper_provenance.md`](../../analysis/module_syscall_wrapper_provenance.md).

## Read-only VFS/PK3 checkpoint (2026-10-07)

- A C++17/zlib VFS now compiles and **reads real game data**, not just PK3 metadata.
- The independently supplied `main/pakb.pk3` indexed 24 unique non-directory files; `ui_mp/createserver.menu` (27,514 bytes) and `ui_mp_x86.dll` (274,432 bytes) were decompressed with matching CRC-32.
- The original Spanish localization archive `localized_spanish_pak4.pk3` indexed 2 non-directory entries; `ui_mp/spanish/createserver.menu` (15,193 bytes) and `ui_mp/spanish/joinserver.menu` (35,057 bytes) passed the same read/CRC checks.
- Synthetic tests cover stored + deflated entries, empty files, case-insensitive PK3 lookup, path traversal, invalid archives, invalid CRC, symlink escape and explicit mount priority.
- The original engine's `FS_FOpenFile` routine at `0x00425FD0` dispatches numeric modes **0–3**, but these modes do not yet have independently proven semantics or names. The VFS does **not** implement original filesystem modes.
- The provisional precedence used here is **most recently mounted source wins**; original COD1 priority, paths and localization behavior remain to be mapped.
- Source and tests are committed only to `main`; original EXE/DLL/PK3 assets remain external. GitHub CI passed after correcting a C++ compilation mistake. The failed intermediate runs are historical and not counted as successful tests.
- **Scope remains M1 + early M2:** there is no engine/VM adapter, savegame write support, streaming/seek, Android NDK executable, menu or playable campaign yet.
- **Next autonomous task:** trace original PK3 precedence and file-open mode behavior, then implement a validated read-only VM/host bridge and streaming handle operations.

See [`analysis/filesystem_vfs_phase.md`](../../analysis/filesystem_vfs_phase.md).

## Host service adapter checkpoint (2026-10-07)

- The independently tested native VFS is now wired to a separate, functioning read-only host callback layer with opaque handles.
- `ReadOnlyHostAdapter` loads VFS contents on open (bounded to 64 MiB), tracks cursor and allows partial reads and EOF, and frees the associated buffer when closed.
- Thread safety is limited to adapter-owned handle/cursor state. The VFS mount list must not be modified concurrently.
- This is **not** a reconstruction of the original game module's callback ABI or an ARM64 build: there is no conversion of untrusted legacy 32-bit pointers into host pointers, and original file-open modes remain unverified.
- Test coverage now includes synthetic ZIP fixtures and host callback semantics; local checks against two original PK3 archives were also successful.
- The updated CMake job passed on GitHub Actions: `https://github.com/Dr3amyBerry/callofrecomp/actions/runs/37559079417`.
- **Next task:** verify original file mode semantics and package precedence, then implement a validated VM→host bridge; follow with streaming seek and writable save/config support only once their behaviors are understood.
- **Active blockers:** none for continued static analysis and native host scaffolding. Android NDK and real-device validation will be needed later.

## Verified file modes and read-only guest VM bridge checkpoint (2026-10-07 UTC)

- The original `CoDSP.exe` dispatches `FS_FOpenFile` mode **0** to an `rb` path, **1** to `wb`, and **2/3** to `ab`; mode 3 additionally sets a flag tested by the write/flush path. See [mode evidence](../../analysis/fs_modes_and_searchpath_evidence.md).
- The **linked-list searchpath implementation** is observed (head `0x013F9E3C`; read helper `0x004226A0`; conditional insertion `0x004248B0`), but exact PK3 priority is still not reconstructed. Do not silently switch the current provisional last-mounted-wins VFS rule.
- `GuestMemory` maps host-provided bytes into explicit bounded guest 32-bit VA ranges, checks write permissions, rejects overlaps/overflow and provides NUL-terminated strings and little-endian word access. Host pointers are never truncated.
- `LegacyFsReadBridge` now calls the native host service table only for **21 FS_FOPEN_FILE (read mode 0)**, **22 FS_READ** and **37 FS_FCLOSE_FILE**; all write/rename/list/console syscalls remain unsupported. Open handles are tracked, stale/invalid handles rejected, and incomplete reads never partially copy into guest RAM.
- Synthetic regression tests validate the bridge without original proprietary EXE/DLL/PK3 files. GitHub CI compiled the C++ library and ran **6/6 CTest targets successfully**: `https://github.com/Dr3amyBerry/callofrecomp/actions/runs/37560393331`.
- This is a **portable host-side ABI harness**, not native execution of CoD game/cgame/ui modules. No Android build, renderer or playable menu is yet present.
- **Next autonomous phase:** complete original mount order and file-read error/handle semantics; add safe streaming/seek and a writable sandbox separately, then integrate the bridge into a reconstructed module host.
- **External blockers:** none for immediate static/host work; Android NDK and a runnable emulator/device will eventually be needed for ARM64 validation.

## Searchpath insertion checkpoint (2026-10-07 UTC)

- Confirmed the byte fingerprint of the **55-byte** searchpath insertion function at `CoDSP.exe` VA `0x004248B0`; its SHA-256 is `51a41202f498c49d4e8c7d001c8ac647d531882c324f220c57fc7bb6ebe07683`. Verification is tied to the original known-good executable hash.
- Modeled its conditional linked-list behavior in portable C++: zero-class nodes prepend; nonzero-class nodes insert after the head and its consecutive zero-class successors. The model includes unusual nonzero-only ordering that simple priority sorting would get wrong.
- Added `tools/searchpath_order_probe.py` and portable C++ regression fixtures; no proprietary executable bytes are committed.
- The `+0x0C` flag semantics and **full engine startup/mount precedence are still unconfirmed**. The model deliberately stays separate from the working VFS until discovery calls and class assignments are traced.
- No additional user action is required. Next: trace node construction and connect the recovered behavior to actual PK3/locale discovery; continue streaming I/O development.

## Bounded-memory sequential VFS streaming checkpoint (2026-10-07 UTC)

- Added `Vfs::open_stream` with persistent `ReadStream` cursors for loose files, ZIP-stored members and raw-DEFLATE PK3 members. Input is refilled in fixed **32 KiB** blocks instead of allocating the complete uncompressed member.
- The existing `Vfs::read_file` API remains unchanged for compatibility. The new stream validates ZIP headers/names, bounds and CRC/declared lengths upon reaching EOF; failed integrity checks remain latched for the lifetime of the cursor.
- Updated `ReadOnlyHostAdapter` to retain one streaming cursor per opaque handle instead of an entire decompressed file. The guest VM bridge continues to stage requested bytes atomically before copying them into guest memory.
- Synthetic tests cover partial reads, EOF, empty files, loose files, CRC failures and >150 KiB DEFLATE data spanning multiple input/output refills. The optional original-PK3 test now compares streamed bytes **byte-for-byte** against the previously verified eager reader for a multiplayer menu and a Spanish localized menu. Local AddressSanitizer/UndefinedBehaviorSanitizer checks of the synthetic VFS suite passed.
- **Limitations:** seeking is not yet implemented; ZIP CRC cannot be known until the stream is fully consumed. Loose-file opens remain vulnerable to a path-replacement race between path canonicalization and opening on filesystems modified concurrently; Android sandbox hardening is still needed. The VFS searchpath order remains provisional.
- No original binaries or archives are included in commits.

## Stream seek + host callback checkpoint (2026-10-07 UTC)

- Added `ReadStream::seek(delta, origin)` using begin/current/end origins with overflow-safe signed offset calculations and strict file bounds. Nonzero negative deltas and `INT64_MIN` are handled without signed overflow.
- For DEFLATE streams, a backward seek resets the inflater and replays through bounded 32 KiB buffers from the beginning; forward seeks discard through `read` so CRC coverage remains correct. The same bounded replay strategy validates ZIP-stored members. This is **correctness-first**, not fast random access.
- Added host-only optional `fs_seek` to `cod_host_services_t`, implemented for `ReadOnlyHostAdapter` with verified native handles. Host origin values 0/1/2 **are new adapter conventions**, not CoD syscall IDs. The 32-bit legacy bridge deliberately does not expose an unverified seek syscall.
- Synthetic tests cover backward/forward/end-relative seeks, bad ranges, large DEFLATE refills, CRC sticky errors and host EOF recovery. The VFS is still read-only; full mount precedence and locale classification are **not yet reconstructed**.
- **Next:** inspect original startup/locale searchpath node constructors; reduce remaining filesystem compatibility gaps and optimize seek when evidence permits.

## Startup indexed searchpath discovery checkpoint (2026-10-07 UTC)

- Fingerprinted the exact original `CoDSP.exe` function at `0x004250E0`. Its first call invokes helper `0x00424E10` with two zero immediate inputs. A subsequent loop invokes the same helper with selector `1` and index values `13` down to `0` (14 calls).
- Added `tools/searchpath_startup_probe.py`, synthetic unit tests and [analysis/searchpath_startup_scan.md](../../analysis/searchpath_startup_scan.md), preserving the uncertainty around register arguments and the meaning of package/language flags.
- This is **not the full PK3/locale search-order mapping**; node creation and classification are still under investigation, and the provisional VFS search priority is unchanged.
- **Verification:** GitHub Actions workflow `37564560085` completed successfully with all **7/7 CTest targets passing**, including the new seek fixtures and startup scan unit tests. Latest test evidence: https://github.com/Dr3amyBerry/callofrecomp/actions/runs/37564560085.
- **Open risk:** stream seeking is O(target offset) for compressed ZIP entries because it replays DEFLATE to preserve CRC; this is safe but may be costly for large map resources. No seek syscall is yet mapped into the original 32-bit VM bridge.

## Localization table and source-node identification checkpoint (2026-10-07 UTC)

- Decoded all **14** language-table entries at `CoDSP.exe` VA `0x00564B08` (English/French/German/Italian/**Spanish index 4**/British/Russian/Polish/Korean/Taiwanese/Japanese/Chinese/Thai/Leet).
- Independently established the original 20-byte searchpath-node fields: `+0` next, `+4` PK3 object pointer, `+8` directory pointer, `+0x0C` **localized flag**, `+0x10` language index. Verified through five SHA-pinned original instruction ranges and localization diagnostics.
- Matched the list-insertion model's previously unknown `class_flag` to the localized boolean without renaming/breaking the existing API. Added a focused mixed-entry regression test.
- Verified the supplied `main/` inventory includes **six localized Spanish PK3s** (`localized_spanish_pak0..5`) and **eleven plain pak* archives**. Two inspected sample PK3s have Spanish/plain menu variants, but this does not prove actual active-language selection.
- Added `tools/searchpath_localization_probe.py` to export table, prefixes, node offsets, evidence fingerprints and filename **candidates**, plus **six unit tests** (one optional real-input test). All six passed locally using the exact original executable; tests without originals skip the exact-input check.
- **Remaining unknowns:** language activation and filters, PK3 discovery order, `sp_`/`mp_`/`zz_` filename handling and directory-vs-PK3 collision behavior. The VFS mount ordering remains unchanged pending full verification.
- **No new external dependencies** for this analysis.

See [`analysis/localization_searchpath.md`](../../analysis/localization_searchpath.md).

## Active-language searchpath filter checkpoint (2026-10-07 UTC)

- Recovered **two distinct runtime lookup branches** that consult the verified `node+0x0C` localized flag, a global rejection check from `(*0x014DBA84)+0x20`, and the current-language index from `(*0x014BD624)+0x20` versus `node+0x10`. Both instruction windows are SHA-256 fingerprinted in the localization probe.
- Added an evidence-based `SearchpathOrder::eligible(active_language_index, reject_localized)` filter, maintaining the original insertion order and preserving the existing `class_flag` API. Added C++ tests with Spanish, English and nonlocalized nodes, plus a test for rejecting all localized nodes.
- Verified Python probe tests against the original executable and tested C++ filtering locally with strict compiler warnings. The node ordering/filter model remains **independent from the VFS** until complete startup order and global initialization semantics are known.
- **Verification:** CMake compiled successfully and GitHub Actions completed **8/8 CTest targets** on commit `b064dbd`: https://github.com/Dr3amyBerry/callofrecomp/actions/runs/37565673848. The independent Python suite also passed 6/6 locally against the supplied original executable, and the C++ filter passed a strict local `-Wall -Wextra -Werror` build.
- **Next:** identify creators and update paths for both global settings, all path-discovery/PK3-level precedence and the exact search behaviors for unmatched language resources. No Android runtime yet.

## 3. Current work queue

### Phase A — strengthen the static-analysis pipeline

- [ ] Recover every `vmMain` target and produce deterministic function maps.
- [ ] Recover syscall wrappers with argument-count / argument-shape evidence.
- [x] Add first direct-call recovery around the engine `VM_Call` boundary.
- [ ] Expand direct/indirect call-target recovery beyond the current narrow patterns.
- [x] Add first reproducible absolute string-reference scanner.
- [ ] Extend string/xref recovery with instruction-aware decoding and broader reference forms.
- [ ] Add broader cross-reference output suitable for machine processing.
- [x] Produce reproducible JSON reports for the PE, module ABI, and engine VM boundary.
- [x] Map engine code responsible for loading the game/cgame/ui modules.
- [x] Confirm the dynamic OpenGL loader path rather than only inferring it from strings.
- [ ] Inventory the renderer GL/WGL function-pointer table and classify Android replacement requirements.
- [ ] Recover engine-side semantic names for remaining syscall IDs with independent evidence.
- [x] Map SP game syscall IDs 0–19.
- [x] Extract first bounded direct `call` / `jmp` edges for SP game syscalls 20–43 (addresses only; semantic names remain unverified).
- [x] Recover direct argument-slot references and EAX-return shapes for syscall handlers 20–43.
- [x] Identify seven evidence-backed filesystem/console SP syscall names in the 20–43 range.
- [ ] Recover full argument semantics, indirect inputs, ownership and side effects for remaining unknown IDs in 20–43.
- [x] Recover observed module-wrapper argument word order for the seven matched IDs (21–23, 36, 37, 40, 41).
- [ ] Trace every caller of these wrappers to determine higher-level register/stack calling conventions and actual input types.
- [ ] Independently recover filesystem modes, pointer ownership, path normalization and output-buffer semantics before adopting final C prototypes.
- [ ] Harden the binary parsers' bounds checks against malformed PE files and add failure-mode tests.

### Phase B — reconstruct interfaces

- [x] Define the first portable C declarations for the observed 32-bit VM word/call representation.
- [x] Codify the verified SP game syscall prefix 0–19 without naming unverified IDs.
- [ ] Expand portable ABI declarations as additional syscall/export ranges are verified.
- [x] Define the first portable host-side filesystem/console command function-pointer contract (interface only, without guessed legacy ABI).
- [x] Implement validated 32-bit guest address resolution and a **read-only** VM→native host filesystem bridge for IDs 21/22/37.
- [ ] Verify `FS_GETFILELIST` list-buffer encoding and directory precedence against the original engine.
- [ ] Recover native caller-level data types and filesystem error semantics before implementing platform I/O.
- [x] Connect the functioning VFS to **native host** open/read/close callbacks, preserving host-width pointers.
- [x] Validate legacy x86 pointer/handle translation for **read-only** game FS syscalls 21/22/37 with synthetic host/file inputs.
- [ ] Extend beyond the read-only subset (seek, list, mode 1–3 writable save/config sandbox) only after verifying original behavior.
- [ ] Integrate this bridge with reconstructed game-module/engine dispatch logic; original x86 code is **not** executed by the bridge.
- [ ] Reconstruct the minimum filesystem/cvar/command/memory interfaces needed for module startup.
- [ ] Build a host-side test harness that can call reconstructed module interfaces without launching the full game.

### Phase C — data and boot path

- [ ] Deep-inventory required PK3 contents.
- [ ] Identify formats required before the first menu/map boot.
- [x] Build and test an independent, read-only PK3/loose-file loader; **does not yet reproduce original mount priority**.
- [x] Model the original engine's **one verified searchpath insertion routine** and fingerprint the exact original code region.
- [x] Recover searchpath node type/classification and the 14-language lookup table (including Spanish index 4).
- [x] Recover the observed per-node language acceptance checks in two filesystem lookup branches; independent model and tests added.
- [ ] Recover initialization/updates of language and rejection globals, the complete startup discovery sequence and only then integrate it with the VFS.
- [x] Implement bounded-memory sequential reads of loose files, ZIP-stored and raw-DEFLATE PK3 members, with end-of-stream integrity checks.
- [x] Implement bounded seek (replay-based, CRC-preserving) through VFS streams and host handles.
- [ ] Precise original error mapping; keep original mount selection unresolved.
- [ ] Reconstruct configuration and localization loading.
- [ ] Trace single-player startup from process entry to first rendered frame.

### Phase R — static recompilation of modules (hybrid plan, approved 2026-10-12)

Current direction: recompile `CoDSP.exe` and the three SP module DLLs automatically
(Ghidra p-code → C), retaining the original engine's resource parsers, renderer
and module/syscall paths. The earlier ioquake3 proposal is superseded by this
working original-engine pipeline.

- [x] Ghidra p-code exporter and `pcode2c.py` generator; zero unsupported ops across ui/cgame/game.
- [x] Recompiled `uix86.dll` matches the real DLL's 10,856-syscall init trace (DllMain + 5 vmMain calls).
- [x] Recompiled `cgamex86.dll` / `gamex86.dll` match the real DLLs up to the same harness-induced crash.
- [x] Build the generated C for Android ARM64 (NDK r30) and rerun the trace check on a real device: identical.
- [ ] Richer fake engine so game/cgame run past init; then wire real engine syscalls.
- [x] Recompile the original engine and start it through CRT/WinMain.
- [x] Replace window/context creation, GL entry-point loading and basic input with SDL2 shims.
- [x] Load the original PK3 search path and finish original renderer initialization on desktop.
- [ ] Replace the Miles audio boundary and reach the menu through the real engine.
- [ ] Exercise campaign map loading and sustained gameplay.

See [`analysis/static_recompilation_prototype.md`](../../analysis/static_recompilation_prototype.md).

### Desktop renderer checkpoint — 2026-10-12

- Resumed Claude's uncommitted SDL/OpenGL work and repaired its interrupted string literal.
- The pinned `CoDSP.exe` hash remains `c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47`.
- Fixed `GetFileType`: real open files now report `FILE_TYPE_DISK`, allowing the guest CRT to read PK3s.
- Runtime reports **30,283 files in PK3 files**, executes `default.cfg` and initializes the original renderer on an AMD desktop compatibility context.
- Bounded GL extension reporting preserves supported S3TC; omitting it falsely rejected the GPU, while forwarding the unbounded driver string exposed the legacy engine's buffer limit.
- Native pointer outputs from GL are translated back to 32-bit guest pointers; external host pointers fail explicitly.
- Added a reproducible desktop builder and synthetic CTest regressions for the file/GL boundaries. Local CMake build and **10/10 CTest tests passed**.
- Current engine execution reaches `----- finished R_Init -----`, then stops at missing `mss32.dll!_AIL_set_file_callbacks@16`. **Menu, map loading, audio and Android renderer execution are not verified.**
- ADB currently lists no connected devices. Desktop work can continue; device validation requires a device when the Android host is ready.

### Audio and callback recovery checkpoint — 2026-10-12

- User clarified the immediate objective: **first mission playable on PC**, before Android gameplay validation.
- Added a portable Miles-import boundary backed by SDL audio: owned PCM buffers, WAV decoding, conversion, volume/pan/rate, looping and playback state. The audio callback never executes guest code.
- Real-engine run `recomp_out/engine_audio4.log` opens **44,100 Hz stereo float**, initializes 32 positional channels and parses every UI menu through `ui/pregame.menu`.
- Extended p-code export to discover indirect callbacks stored in initialized non-executable data. UI export now contains **40,507 instructions**; the engine contains **331,853** after explicit recovery of a verified code entry mislabeled as data.
- Missing UI callback `0x40016DB0` was verified against original instructions and recovered. The subsequent engine blocker `0x00518050` is an original `RET` stored as a callback by `0x00518073`; exported with `--code-entry 0x00518050`.
- Rebuilt and ran the engine again: it passes that recovered callback and stops at another missing entry, `0x0050B990` (`recomp_out/engine_audio5.log`). Recover remaining indirect entries before claiming menu completion.
- Confirmed `0x0050B990` is another original `RET`, installed at `0x0050B9EE`, and explicitly recovered it; export contains **331,854 instructions**. Reproducible arguments and assignment sites are recorded in [`analysis/recomp_verified_code_entries.json`](../../analysis/recomp_verified_code_entries.json).
- An unoptimized diagnostic build timed out after 40 seconds at `FS_Startup`; this does not verify the second callback at runtime. Restore optimized objects and rerun before advancing the checkpoint. The original menu uses `spmap training` and `spmap pathfinder` for the intended PC gameplay checks.
- UI traces still have **10,867 lines** in both runs. The generic comparator reports three differences in surplus logged argument words (IDs 51/26/8), so its strict exit status is not a clean comparison; do not report that command as passing.
- Review found and tests reproduced audio ABI/state bugs (x87 float return, 8-bit offsets, stale-buffer replay) plus invalid metadata acceptance. Fixed them before commit; **11/11 CTest tests pass** including WAV decoding and malformed metadata rejection.
- Music MP3 streams, double-buffer loading, positional attenuation/effects and full menu/map gameplay remain unfinished. Device startup is not proof of audible sound or a visible menu.
- Public source changes remain separate from ignored generated C, binaries, traces and original assets. See [`docs/guides/AUDIO_BRIDGE.md`](../guides/AUDIO_BRIDGE.md).

### Cinematic audio and first PC map attempt — 2026-10-12

- Optimized engine with both recovered RET callbacks reaches **Common Initialization Complete** (`recomp_out/engine_audio7.log`). The next missing import was `AIL_minimum_sample_buffer_size` for cinematic audio.
- Added a native x86 Miles probe using silent PCM and the supplied original DLL. Measured automatic buffer startup, one-time reservation of free slots, alternating consumption and per-buffer byte positions; no proprietary code or audio is committed.
- Implemented two owned PCM buffers, minimum buffer sizing, free/reserved/queued states, refill after underrun and EOF. Added regressions for ownership, alternation, position reset, end/EOF and invalid-buffer reservation recovery. **11/11 CTest tests pass.**
- The engine stays active through a 40-second observation after common initialization (`recomp_out/engine_buffers1.log`). This does **not** prove visible rendering, video completion or gameplay.
- Direct `+set com_introplayed 1 +spmap training` exercises a resource/UI restart and then reaches missing original code `0x0045AA90` (`recomp_out/engine_training1.log`). Its assignment at `0x0045A6ED` is confirmed by binary disassembly; explicitly exported it, bringing engine coverage to **332,034 instructions**. Optimized compilation is in progress; map completion remains unverified.
- Optimized rerun passes that entry and now stops at **guest heap exhausted (4096 bytes)** (`recomp_out/engine_training2.log`). The runtime has a 256 MiB bump arena, no-op HeapFree/VirtualFree, and VirtualAlloc shares that arena. Correct allocation/release semantics are the next concrete task; no playable-map claim is made.
- The first campaign route remains the original `spmap pathfinder`; training is the preliminary map-loading check. MP3 streaming, spatial audio and sustained input/rendering validation remain required.

### Memory lifecycle checkpoint — 2026-10-12

- Reproduced the old no-op HeapFree behavior with a synthetic thunk test (exit 2 before the fix).
- Replaced monotonic-only heap allocation with tracked live blocks and coalescing free spans, including HeapFree, HeapSize and failure-preserving HeapReAlloc.
- Separated VirtualAlloc reservations from the 256 MiB CRT heap. Added page commit/decommit, exact-base release and region reuse; reservation metadata remains host-owned.
- Review exposed an inclusive-end lookup bug between adjacent reservations; regression failed at exit 17, then passed after excluding the end address. **12/12 CTest tests pass**, including heap reuse/coalescing, reserve/commit lifecycle and overflow checks.
- Original `+set com_introplayed 1 +spmap training` now passes heap exhaustion and stops at **RaiseException(c000008f)**, called by the original CRT at return address `0x00524BE3` (`recomp_out/engine_training4.log`). Next: investigate guest floating-point state and the CRT exception path. Do not suppress the exception without evidence.
- Scope and remaining memory limitations are recorded in [`docs/guides/RECOMP_MEMORY.md`](../guides/RECOMP_MEMORY.md). Playable training/campaign, visible rendering, MP3 and sustained input remain unverified.

### x87 startup checkpoint — 2026-10-12

- Located the original CRT exception call at `0x00524BDD` (return `0x00524BE3`). Its control-word updates depend on the initial x87 exception masks.
- Verified Ghidra x86 `ia.sinc`: FPUControlWord/StatusWord/TagWord are at register offsets `0x10A0/0x10A2/0x10A4`; FINIT defines control `0x037F`, status zero and tag `0xFFFF`. Runtime previously left all three zero.
- A regression reproduced the invalid initial state (exit 25). Initialized these registers before engine entry; **12/12 CTest tests pass**.
- The original training run now passes the CRT exception, starts **Server: training**, restarts resources/UI and reaches missing **gamex86.dll callback `0x20035480`** (`recomp_out/engine_training5.log`). Verified original instructions at that address; expanding game-module callback coverage next. This is server initialization, not verified map completion or gameplay.

### Original training resource loading checkpoint — 2026-10-12

- Expanded game-module data-held callback coverage: **188 candidates disassembled**, **144,114 instructions**, zero unsupported p-code operations. Explicit callback `0x20035480` is referenced by original data slot `0x200A4DE8`; hash and reproduction arguments are in [`analysis/recomp_verified_game_entries.json`](../../analysis/recomp_verified_game_entries.json).
- Expanded client-module coverage before its deeper map path: **154 candidates disassembled**, **81,941 instructions**, zero unsupported operations. Both regenerated private modules compile with Clang `-O1` and link with the actual engine.
- Original `spmap training` now runs past the game callback and loads **surfaces, cull groups, visibility, models/entities and lights**, merges lightmaps and initializes the effects system (`recomp_out/engine_training6.log`). This is materially deeper than boot/UI parsing.
- The next concrete blocker is **mss32.dll!AIL_open_stream**, called from original sound playback at return address `0x00442D9F`. Implement original filesystem-callback access and compressed audio streaming next; no dummy success or audio suppression.
- Local repository checks remain **12/12 CTest passing**; CI for memory and x87 commits succeeded. Rendered map, movement/input, sustained gameplay and the campaign `pathfinder` map remain unverified. The first mission goal is still active.

### Phase D — native implementation

- [x] Start portable C/C++ host scaffolding with CMake and an ABI interface target.
- [x] Add the first deterministic host ABI smoke test.
- [ ] Add regression tests for recovered parsers, dispatch tables, and reconstructed subsystem behavior.
- [ ] Replace Win32 filesystem/time/thread/input dependencies with portable interfaces.
- [ ] Replace Miles/Windows-specific audio integration with a portable backend.
- [ ] Adapt rendering to an Android-supported graphics path.

### Phase E — Android ARM64

- [ ] Add Android NDK/CMake target.
- [ ] Build ARM64 native library/executable.
- [ ] Add Android asset/filesystem bridge for user-owned original game files.
- [ ] Add touch and controller input layer.
- [ ] Reach menu.
- [ ] Load first single-player map.
- [ ] Validate gameplay and save/load behavior.

---

## 4. What I can do directly

The following work is currently within my reach and should be performed without asking the user to do it manually:

- Read and list the connected Google Drive installation.
- Download individual original binaries or archives from Drive when needed for analysis.
- Read and write the private GitHub repository.
- Commit directly to `main`.
- Create and maintain analysis tools, source code, tests, build files, and documentation.
- Parse PE32 binaries and PK3/ZIP structures.
- Compute hashes and reproducible metadata.
- Use local Python for binary-analysis automation.
- Use local `objdump` and `llvm-objdump`.
- Compile/test portable C and C++ locally with Clang.
- Use CMake and Ninja for host-side builds.
- Perform static string/import/export/xref/function-pattern analysis.
- Build custom disassembly/analysis utilities when practical.
- Compare behavior against public reference implementations where legally and technically appropriate.
- Design the portable architecture and Android boundary.
- Keep the progress log, symbol ledger, findings, and roadmap synchronized with actual work.
- Make safe incremental commits without requesting approval for every commit.

---

## 5. Capabilities not currently available in the working environment

These are tool/environment limitations, not reasons to abandon the project.

### Not currently installed

At the time of this update the working environment has:

- available: Python, GNU `objdump`, `llvm-objdump`, Clang/Clang++, CMake, Ninja
- available on the local Windows workstation (2026-10-11): Ghidra 12.1.4 headless (`tools/ghidra_decompile.sh`), JDK 21, Android SDK + `adb`
- Android NDK r30 installed (2026-10-12); an arm64-v8a device is reachable over adb
- not currently available: radare2/rizin, GNU binutils on Windows (tools fall back to `llvm-objdump`)

When one of the missing tools becomes the most efficient or necessary path, I should record the exact requirement here and ask the user to provide/enable it rather than making the user perform the analysis manually.

### Outside direct reach

I cannot directly:

- operate the user's physical Android phone unless a device/emulator interface is made available;
- click through software running only on the user's local Windows desktop;
- inspect a local-only file that has not been uploaded/shared through an accessible source;
- use a proprietary decompiler/debugger that is not installed or connected;
- obtain unpublished proprietary Call of Duty source code;
- guarantee that decompiler output is identical to the original source code;
- perform real-device performance/input/audio validation without an accessible Android runtime/device;
- sign or publish a final application with user-owned store/signing credentials unless those capabilities are explicitly provided;
- continue executing work in the background after the current tool execution ends.

These limitations should be handled by building automated artifacts/scripts so that any unavoidable user action is minimal and narrowly specified.

---

## 6. User assistance policy

The project should require the least possible help from the user.

### Do not ask the user for

- manual binary inspection that I can automate;
- copying function addresses by hand;
- manually listing Drive files I can access;
- creating repository files or commits I can create myself;
- running ordinary static-analysis commands merely to paste their output back;
- repeatedly approving safe incremental work on `main`.

### Ask the user only when necessary for

- granting access to a file, repository, device, or service I cannot access;
- providing/installing a missing specialist tool that materially blocks the next phase;
- attaching an Android device/emulator/runtime for validation;
- supplying signing/store credentials for release work;
- making a product/legal decision that should not be chosen silently;
- authorizing an irreversible or externally consequential action.

Whenever user help is required, the request must state:

1. **exactly what is missing**;
2. **why it is needed now**;
3. **the minimum action the user must take**;
4. **what work will resume immediately afterward**.

---

## 7. Tool requests / blockers

### Active blockers

None for the current static-analysis phase.

The available Python + PE tooling + objdump/LLVM tooling is enough to continue recovering the ABI, call graph, strings, loaders, and binary structure.

### Expected future tool needs

These are anticipated, not yet active blockers:

| Tool/capability | Why it may be needed | When to request it |
|---|---|---|
| Ghidra headless | scalable decompilation, p-code, xrefs, function recovery | **installed**; full SP decompilation is exported to ignored `decomp/` |
| Android NDK | native ARM64 compilation | when the reconstructed portable core reaches Android build stage |
| Android SDK + adb or accessible emulator/device | install/run/log/debug | when first Android binary is ready |
| Optional debugger/emulator | runtime behavioral validation of original x86 code | only if static evidence is insufficient for a specific behavior |

Do not request these merely because they could be useful. Request them only when they become the next concrete dependency.

---

## 8. Quality rules

- Never commit original proprietary game binaries/assets.
- Never present inferred semantics as recovered facts.
- Every recovered interface should be reproducible from scripts where practical.
- Prefer small focused commits with a clear technical purpose.
- Keep working on `main` unless the user explicitly requests another branch.
- Avoid dead code and one-off throwaway patches.
- New tooling should have a deterministic CLI and machine-readable output when useful.
- The Android port should ultimately use user-owned original assets externally rather than bundling proprietary game data.
- Correctness comes before optimization.
- A subsystem is not considered reconstructed merely because it compiles; behavior must be validated.

---

## 9. Definition of major milestones

### M1 — Static architecture mapped

**Status: in progress.**

Complete when the executable/module boundaries, startup path, `vmMain` commands, syscall interfaces, major engine subsystems, and necessary asset formats have usable evidence-backed maps.

The native VM boundary is now mapped, the Win32 OpenGL dynamic-loader seam is confirmed, the SP UI export table is mostly named, the SP game syscall prefix 0–19 is mapped, and portable host scaffolding has started. Remaining M1 work is dominated by the rest of the syscall/export semantics, startup/subsystem maps, renderer dispatch classification, and required data formats.

### M2 — Portable host harness

Complete when reconstructed interfaces can initialize and execute meaningful module behavior in a host-side C/C++ test program without the original Windows executable.

### M3 — Native desktop proof

Complete when enough reconstructed engine behavior runs natively from our own build to exercise startup/data/module paths using externally supplied original assets.

### M4 — Android first boot

Complete when an ARM64 Android build initializes, reads original PK3 data, opens graphics/audio/input subsystems, and reaches visible game UI.

### M5 — Playable single player

Complete when the Android build can enter a campaign map and sustain core gameplay without x86 emulation.

### M6 — Compatibility/polish

Save/load correctness, controls, audio, rendering fixes, device compatibility, performance, and packaging are addressed after the playable milestone.

---

## 10. Progress-log maintenance rule

Every substantive commit should cause this file to be reviewed.

Update at least one of:

- completed work;
- current work queue;
- confirmed findings;
- blockers/tool requirements;
- milestone status;
- scope changes.

The log should reflect what actually exists in the repository, not what is merely planned.
