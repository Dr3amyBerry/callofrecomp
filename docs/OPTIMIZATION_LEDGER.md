# Registro acumulativo de optimizaciones — estado verificable

**ARM64-BIND-LOCAL-01 (2026-10-23, opt-in/OFF, sin FPS):** `--arm64-bind-local` anade `-fno-plt` al compilar y `-Wl,-Bsymbolic-functions` al enlazar libmain; elimina stubs PLT y la interposicion de llamadas internas entre chunks/dispatch, sin tocar C generado, x87, memoria ni exportaciones. Evidencia offline (sonda AArch64 clang+lld, sesion privada arm64-offline/dispatch-abi): sin flags 1 PLT y 2 relocs; con ambos 0 PLT y 1 reloc, salto interno directo. Solo ARM64, test de rechazo en x86_64. Pendiente: diff de 490 exportaciones/.text con NDK, APK A/B y A/B/A/B fisico TECNO; ninguna ganancia afirmada. Estado: opt-in/inconcluso.
**ARM64-X87-CONV-FAST (2026-10-24, opt-in/OFF, offline):** `--arm64-x87-conv-fast` (`CODRECOMP_ARM64_X87_CONV_FAST`) añade a `d2f(double,10)` y `f2d(binary80,10)` de `recomp_rt.h` una vía rápida exacta para valores normales finitos (d2f), binary80 canónico normal y ±0 (f2d); todo lo demás cae en la ruta genérica sin cambios. Cubre todas las conversiones binary80 de todos los módulos (no solo 39/10/3 PCs). Oráculo host bit a bit (`tests/test_arm64_x87_conv_fast.py`: todos los signo/exponente, 65.536 `se` x significandos estructurados, 2M+ aleatorios): PASS; AArch64 Unicorn (`verify_arm64_x87_conv.py`): resultados y FPSR idénticos; instrucciones dinámicas por llamada (incl. wrapper) d2f normal 27→15, cero 27→16 aprox., f2d canónico 26→16, cero 22→11; **peor** en f2d binary80 que requiere redondeo (+7) y codificaciones raras inf/NaN/unnormal (+8,5): esperadas poco frecuentes pero no medidas. Sin FPS, sin APK compilada, sin ADB; estado **opt-in, pendiente de A/B/A/B físico** (no combinar con hot-x87-transform, que sigue BLOQUEADO). Evidencia privada: `.local/profiles/runs/arm64-offline/2026-10-24/x87-conv/20261024T032808Z-18564-00/reports/conv_unicorn3/result.json`.
**ARM64-X87-ARITH-AUDIT (2026-10-23, inconcluso / sin candidato, offline):** auditoría estática de `tools/recomp/recomp_rt.h`, `pcode2c.py` (FLOAT_ADD/SUB/MULT/DIV/SQRT/comparaciones) y `runtime/*x87*`. El motor NO tiene helpers soft-float binary80 para fadd/fsub/fmul/fdiv/fsqrt/fcom: el p-code se lowerea a `f2d(...)` -> operador C `double` (`+ - * /`, `sqrt`, `<`, `==`) -> `d2f(...)`; el propio `recomp_rt.h` documenta "arithmetic still uses double precision/range". Cada operación aritmética es ya 1 instrucción AArch64 (`fadd/fsub/fmul/fdiv/fsqrt/fcmp`), por lo que no existe bucle interno que acelerar ni ahorro de instrucciones posible en la aritmética; solo `f2d`/`d2f` cuestan (cubiertos por `--arm64-x87-conv-fast` en otra rama). Un fast path "exacto" sustituiría 1 instrucción por ruta binary80 completa (más lenta) y cambiaría la semántica actual (doble redondeo, sin SW/C1 ni CW), es decir, es una corrección de fidelidad, no una optimización; `--hot-x87-transform`/atajos double siguen BLOQUEADOS y `binary80_arithmetic_reference.py` no se conecta al motor. Sin flag, sin cambios de código, sin claim FPS.

**ARM64-FLD32-NATIVE-CLASS-TELEMETRY (2026-10-16, diagnóstico integrado):** verificador Unicorn AArch64 ampliado para contar instrucciones por normal, cero firmado, subnormal, inf y NaN; clasificación de patrones con tests públicos sin archivos comerciales. Original→FLD32 normal 55→52 instrucciones nativas; los especiales son más costosos. Variante experimental cero/Inf: 1 instrucción menos en ceros, 6 menos en Inf, pero 5 más en subnormales/NaN; en los 512 inputs sintéticos, +36 instrucciones respecto al helper actual. Variante **rechazada** y revertida; runtime/CMake/builder idénticos a HEAD previo. [Datos](performance/tecno/ARM64_X87_FLD32_CLASS_COST_2026-10-16.md).


**ARM64-NARROW-LEFT-HOT-16 (2026-10-16, OFF):** de 9.869 `INT_LEFT` estáticos de CoDSP 1.5 se distinguieron 2.487 con cuenta variable; en regiones calientes, 16 variables (4 p0, 12 p8), 273 constantes no transformadas al no ahorrar en wrapper. Parche fuentes SHA y reversible, helper 64-bit low-mask exacto, oráculo independiente host O0/O1/O2 y AArch64 Unicorn sin divergencias. ABI 490 símbolos exportados y recursos intactos; B `.text` −44 B, chunk18 −4 B/−1 instrucción, chunks151/152 0 B. No FPS medidos. [Resultados](performance/tecno/ARM64_NARROW_LEFT_SHIFT_SELECTIVE_2026-10-16.md).


**ARM64-X87-FLD32-VISIBILITY-10 (2026-10-16, opt-in/OFF):** 10 PCs en p8 de visibilidad y geometría, runtime binary80 exacto para normales, no altera otras entradas (excepciones especiales conservan ruta original); 9 tests + 7 tests helper PASS; 2.400 comparaciones completas host R/U/MEM/PC. APK A/B firmadas, 490 exportaciones y recursos idénticos; delta nativo `.text` **+428 bytes** (16+89 instrucciones estáticas en chunks 151/152). Sin FPS causal ni x86 independiente; conservar OFF. [Análisis](performance/tecno/ARM64_X87_FLD32_VISIBILITY_2026-10-16.md).


**ARM64-OFFLINE-TRIAGE (2026-10-16):** auditoría independiente repetida de dos capturas Simpleperf verificadas Build ID `80dc3884...`, 16 PC x86 en top-20 de ambos perfiles. 1.255/1.557 y 1.005/1.244 muestras atribuibles a instrucciones asociadas con x87 dentro de ocho cuerpos, sin ser coste exclusivo. Optimización directa de `sx` descartada: **delta 0 bytes** en 11 wrappers O1 y O2. `x87-nan-bits` y `x87-fcom-fastpath` ya experimentados (FCOM B2 regresivo), no duplicar ni activar. [Datos](performance/tecno/ARM64_HOTPATH_RESEARCH_2026-10-16.md).


**ARM64-NARROW-SAR-01 (2026-10-16, opt-in/OFF):** SAR de ancho 1..8 B usando int64 y extensión final a 128 bits; fallback sin cambios en n>8. A/B NDK −184 B `.text`, cinco chunks CoDSP −44 instrucciones estáticas, 490 exportaciones iguales y recursos inmutables. Oráculo byte independiente + 8.192 ejecuciones en Unicorn sin discrepancias. Sin evidencia de FPS ni fidelidad de juego completo. [Datos](performance/tecno/ARM64_NARROW_SAR_2026-10-16.md).


**ARM64-CORE-HOT-O2-SUBSET (2026-10-16):** selector de particiones de `--core-hot-o2` con requisitos SHA/ABI/FP estrictos y default inalterado. Físico previo de las tres particiones +1,51 % FPS promedio descriptivo, por debajo de la variación A1/A2; **inconcluso**. Offline `p1`: 42.338.448 bytes `.text` (`−1.652` vs A), 490 exportaciones intactas, no FPS medidos. [Evidencia](performance/tecno/ARM64_CORE_HOT_O2_PARTITIONS_OFFLINE_2026-10-16.md).


**ARM64-MET-04 resultado físico y CI (2026-10-16):** `517910e` reparó CI [run 38846701351 PASS](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38846701351), manteniendo oráculos locales privados. A1 FLD32 17,10 FPS y 56,16 ms CPU frente a referencia 21,675: rechazo antes de B, imagen/entorno registrados en sesión privada, APK original y save restaurados exactos. **Sin nueva ganancia FPS certificada**; investigar estado de ejecución 17/22. [Detalles](performance/tecno/TECNO_ARM64_CI_AND_BASELINE_DIAGNOSTIC_2026-10-16.md).


**ARM64-MET-04 — diagnóstico de A1 y CI privada/pública (2026-10-16):** Conservar verificación de p-code real en estaciones autorizadas, marcar `skip` solo cuando falten los originales en CI y mantener tests sintéticos. En calentamiento fallido del runner ARM64 registrar evidencia privada antes de restaurar, sin aceptar FPS ni instalar B. [Informe](performance/tecno/TECNO_ARM64_CI_AND_BASELINE_DIAGNOSTIC_2026-10-16.md).


**ARM64-X87-FLD32-NORMAL-01, 39 sitios en 0x5061B0 (2026-10-16):**
Estado opt-in OFF. 4.096 casos/8.192 ejecuciones AArch64 más 16 faltas de RAM equivalentes; normal 55→52 instrucciones aisladas, especiales 54→59. Texto ELF B +1.144 bytes, 490 exportaciones A/B; fuentes y build A restauradas. A1 física no comparable, B no instalada, ninguna mejora FPS demostrada. [Informe](performance/tecno/TECNO_ARM64_HOT_FLD32_2026-10-16.md).


**ARM64-MEM-EXPERIMENT-01, física y AArch64 (2026-10-16):**
La caché de dispatch tuvo A1/B1/A2 estables, B2 inestable (17→22 FPS, deriva casi 30 %); no se demuestra mejora. Enlace local A1 rechazado antes de B. Dos prototipos de comparación de rango aumentaron instrucciones y lecturas en Unicorn: revertidos exactamente. Ningún cambio de motor ni flag por defecto. [Datos](performance/tecno/TECNO_ARM64_MEM_DISPATCH_AUDIT_2026-10-16.md).


**ARM64-SIGN80-02, A/B/A/B TECNO (2026-10-16):**
Variante experimental de 3 PCs: 4/4 escenas y capturas estables, B más lenta en ambas parejas, −0,68 % FPS y +0,71 % CPU descriptivos; no activar por defecto. Original 0.2.4/save restaurados por hash. [Prueba física](performance/tecno/TECNO_FCHS_SIGN_ABAB_2026-10-16.md).


**ARM64-SIGN80-01, tres FCHS exactos (2026-10-16):**
Implementado **opt-in/OFF** con pcode sha estricto, tres PCs, transformación reversible, build APK ARM64; reduccion de 1.032 bytes de `.text`, sin cambios de 490 contratos exportados. Valor sign-bit probado con Unicorn (4.000 ejecuciones) y oraculo x86 de 65.536 casos, *no* full FPU state ni fps probado. [Evidencia](performance/tecno/ARM64_X87_FCHS_SIGN_BITS_2026-10-16.md).


**ARM64-MET-03 / A/B/A/B reutilizable:** [candidatas y automatizacion preparada](performance/tecno/ARM64_OFFLINE_READY_2026-10-15.md). CLI offline + ejecucion separada; reutiliza logs, escena historica y guardas, una imagen por pasada. Tres planes con APK/SHA fijados, sin ADB ni capturas nuevas. Recuperacion por sesion de instalacion verificada con dobles; firmware fisico pendiente.

**ARM64-08 / shifts estrechos:** [helper, oracle y APK A/B](performance/tecno/ARM64_NARROW_RIGHT_SHIFT_2026-10-15.md). Opt-in OFF; `.text` neta -16 bytes, cambios mixtos por chunk y ninguna ganancia FPS demostrada. 8.192 casos AArch64 por variante; 494 pruebas Python y 40 CTest. Siguiente: preparar comparaciones fisicas de candidatas y continuar segun el coste real, sin activar rutas inseguras.

**ARM64-07 / dispatch:** [cache de entrada completa](performance/tecno/ARM64_DISPATCH_ENTRY_CACHE_2026-10-15.md), opt-in OFF. APK ARM64 A/B y oracle AArch64 preparados; menos instrucciones con localidad, mas con fallos frecuentes. Sin nuevos FPS. Siguiente: estado/memoria en chunks calientes y A/B/A/B fisico pendiente.

**ARM64-MET-02 / CI:** el run `38814719518` fallo por seis imports de PIL ausente. Se declara `Pillow==11.3.0`, la version usada en las pruebas locales, en `tests/requirements.txt`; se conserva la comprobacion de escenas en CI sin omitirla. Corregido en `f279fb1`; [run 38818087031 aprobado](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38818087031), 38/38 CTest Linux.

**ARM64-06 / trabajo offline vigente:** [safe ICF y copias x87](performance/tecno/ARM64_SAFE_ICF_2026-10-15.md). Candidata experimental OFF: -13.620 bytes de codigo sobre los mismos objetos; 12.000 llamadas AArch64 equivalentes. APK privada compilada, sin nuevos FPS ni ADB. Helpers externos descartados por aumentar instrucciones. Siguiente: coste dinamico de estado/dispatch, luego A/B/A/B fisico cuando se autorice.

**ARM64-MET-02:** comparador offline `scene_fingerprint.py`, seis pruebas aprobadas. Una imagen por pasada y comparacion automatica de encuadre; no mide estado 3D ni FPS. Complementa la guarda temporal, no la sustituye.

**ARM64-MET-01, control de FPS (2026-10-15):**
Dos corridas de la MISMA 0.2.4: R3 21.70 FPS / 44.250 ms CPU y R4 21.65 FPS / 44.440 ms CPU; diferencia relativa -0.23 %. Veredicto: repetibilidad de referencia aceptable. No es una ganancia de optimización; son dos medidas del mismo código. Implementadas herramientas read-only de estabilidad y telemetria CPU/termica; no hay cambios al motor ni a la calidad. Datos privados preservados; docs/performance/tecno/TECNO_STABILITY_GATE_2026-10-15.md.


**ARM64-05 / WSA-POR-01 (2026-10-15):**
[Port del enlace local WSA + A/B/A/B TECNO](performance/tecno/ARM64_WSA_LOCAL_STATE_BINARY80_2026-10-15.md), exactamente 4 simbolos ocultos y 486 exports preservados; FPS brutos 19.57->22.12 (+13.03%), **no ganancia confirmada** por A1 anómala; INCONCLUSO. R/RAM/FPU invariantes por codigo fuente; no equivale a prueba total de estado ni a native x87 ARM64. Ruta OFF por defecto.

**ARM64-04 / REL-024 (2026-10-15): regresivo frente a referencia experimental insegura.** [TECNO 0.2.4 A/B/A/B](performance/tecno/TECNO_RELEASE024_ABAB_2026-10-15.md): A1/A2 26,05/25,90; B1/B2 22,15/21,90 FPS. Media de medianas -15,21 %, CPU +17,59 %. APK completas; no atribucion causal por bandera. B segura permanece instalada; A contiene transform double bloqueado.

**WEB-01 (2026-10-15):** empaquetador en [GitHub Pages](https://dr3amyberry.github.io/callofrecomp/); workflow con prueba CODPACK y despliegue exclusivo de `web/dist`. Sin cambios de APK ni nuevas medidas FPS.

**Corte:** 2026-10-15. **Misión activa:** 120 FPS de motor en WSA x86_64, sin rebajar calidad o precisión. Meta aún abierta; presentación visible a 120 Hz no es posible demostrarla con el panel WSA observado a 75 Hz. Objetivo TECNO ARM64 de 60 FPS se sigue por separado.

Este es un **mapa de decisiones, no otra bitácora**. El detalle numérico y los SHA completos se conservan en cada evidencia enlazada. Nunca sumar ganancias de variantes, escenas o plataformas distintas.

| ID / línea | ¿En código? | Estado correcto | Evidencia y alcance |
| --- | --- | --- | --- |
| REL-024: `--wsa-release`, APK separadas y página de recursos simple | Sí; defaults únicamente WSA, overrides reversibles | **Integrado experimental; 0.2.4 publicado** | Código `f493638`, [notas y límites](history/releases/RELEASE_NOTES_v0.2.4.md). WSA conserva WSA-01/02 con native x87 y límite120 por defecto; ARM64 normal-f2d/60 sin transform double bloqueado. 40/40 CTest, CI, CODPACK y smoke WSA aprobados; APK/hashes publicados. No son FPS nuevos ni revalidación TECNO. |
| WSA-01: preset `--wsa-cumulative` con región x87 binary80, copy32 guardado, NaN/f2d/FCOM, renderer/visibilidad O2 estricto y caché dispatch | Sí, opt-in en x86_64; APK B medida | **Integrado experimental y medido** | [A/B/A/B](performance/wsa/WSA_CUMULATIVE_2026-10-15.md): media de medianas 54,75→66,75 FPS y 18,250→14,985 ms CPU/frame. Ganancia **del conjunto**, no atribuible a cada bandera. |
| WSA-02: `--local-guest-state` para R/MEM/U/PC | Sí, opt-in x86_64; sumado sobre WSA-01 | **Integrado experimental y medido** | [A/B/A/B](performance/wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md): A acumulativa 65,75→B 68,15 FPS (+3,65 %) y CPU 15,2125→14,675 ms/frame; APK B instalada y diagnósticos retirados según informe. |
| WSA-03: contadores GL y reempaquetado de geometría | Solo instrumentación; caché nueva NO integrada | **Medido; optimización pendiente** | [Draw ≈103 solicitudes/frame, ~3,57 ms CPU instrumentado](performance/wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md). Faltan vida de buffers, spans/bytes e invalidación; GPU no medida. |
| WSA-04: optimización del postámbulo de x87 | Región nativa integrada, postámbulo sin simplificación especulativa | **Investigación pendiente** | FXRSTOR64 y restauración forman parte de los símbolos muestreados; no atribuirles ms exclusivos ni omitir preservación de estado. |
| ARM64-01: `--x87-normal-f2d` p1/p8 | Código y bandera disponibles, OFF por defecto | **Beneficio físico opt-in histórico, no equivalente x87 completo** | [A/B/A/B TECNO](performance/tecno/TECNO_X87_NORMAL_F2D_GAMEPLAY_ABAB_2026-10-14.md): +3,31 % FPS respecto a su propia referencia. No atribuirlo a WSA ni activar sin compatibilidad. |
| ARM64-02: `--fast-copy32` y `--visibility-o2` aislados | Opt-in, OFF generales | **Inconcluso/regresivo según variante física; conservar prueba** | [Ensayos TECNO](performance/tecno/ARM64_PERF_EXPERIMENTS_2026-10-14.md): no ganancia robusta aislada; opciones reutilizadas en preset acumulativo WSA con guards. |
| ARM64-03: `--x87-normal-f2d-p4-profiled`, superregiones pequeñas y POPCOUNT especializado | Pruebas offline/opt-in según línea | **Sin ganancia validada; no priorizar sin hipótesis nueva** | [Fase 10](performance/tecno/CPU_PHASE10_TECNO_P4_PROFILED_ABA_2026-10-14.md), [Fase 14F](performance/cfg/PHASE14F_MEMORY_FREE_SUPERREGIONS_2026-10-15.md) y [Fase 15](performance/tecno/PHASE15_TECNO_CPU_PROFILE_CROSSCUTTING_2026-10-15.md). No borrar evidencia ni convertir ruido en éxito. |
| ARM64-05: WSA local guest state, ARM64 | Si, opt-in ARM64 y OFF por defecto | **INCONCLUSO POR VARIACION DE ESCENA/TIEMPO** | [A/B/A/B TECNO](performance/tecno/ARM64_WSA_LOCAL_STATE_BINARY80_2026-10-15.md): 19.57->22.12 FPS, CPU 49.70->43.42 ms; ABI: cuatro objetos locales, 486 exports sin cambios; sin x87 nativo ARM. |
| ARM64-06 / AUDIO-01: `--audio-mix-span` (`CODRECOMP_AUDIO_MIX_SPAN`, solo `audio.c` del hilo de audio host) | Si, opt-in, OFF por defecto, ambas ABI | **Opt-in sin medir (no hay FPS ni CPU declarados)** | El mezclador llama `current_pcm()` por cada frame de salida; la variante recorre un span con el mismo aritmetico float/double y solo reconsulta al salir del span (`cursor >= count`), caso en que `current_pcm()` no tiene efectos laterales. Oraculo diferencial [tests/recomp_audio_mix_span_smoke.c](../tests/recomp_audio_mix_span_smoke.c): 300 rondas x 8 llamadas, voces planas/con buffers/bucles, salida y estado (cursor, playing, loops, buffers, eof) identicos bit a bit; mutacion deliberada detectada. Ruta de stream mp3 cubierta solo por argumento de codigo + `recomp_audio_smoke` existente. No toca RAM/PC/flags/x87 del guest. Pendiente: A/B/A/B TECNO (CPU/frame, hilo de audio) con APK `--audio-mix-span`; ganancia esperada pequena, no medida. Analisis: el acceso a memoria generado ya usa `restrict` (`*_chunk_N_spaces(R, MEM)`), por lo que no hay recargas de `MEM` que atacar. |
| SEG-01: `--cfg14-geom-region` y `--hot-x87-transform` antiguo | Código protegido por validaciones del builder | **BLOQUEADOS por corrección** | Original x86 muestra fallos de R/PC en CFG y errores binary80→double; no desbloquear por ganar FPS. [Análisis CFG](performance/cfg/PHASE14D_EPILOGUE_FAULT_SAFETY_2026-10-15.md), [x87](performance/wsa/WSA120_LIMITER_AND_RENDERER_PROFILE_2026-10-15.md). |
| GFX-01: ANGLE/Vulkan, GL4ES VBO modos 2/3 | Ensayados como alternativas o diagnósticos | **No integrados como optimización** | [ANGLE](performance/graphics/ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md) y [GL4ES](guides/ANDROID_PERFORMANCE.md). Hubo controles sin ganancia o con regresiones; no confundir mejora potencial con mejora demostrada. |
| ARM64-LAYOUT-01: `--arm64-code-layout` [+ `--arm64-symbol-order FILE`] | ARM64 TECNO CK6n (MT6768: 2xA75+6xA55); solo `-ffunction-sections -mtune=cortex-a55` y orden lld de simbolos calientes; sin cambio ISA, sin fast-math, `-ffp-contract=off` intacto | **opt-in sin medir** (offline) | Tests de plumbing y `tools/recomp/diagnostics/build_symbol_order.py`; sin ELF ni FPS. Pendiente: A/B/A/B fisico, `readelf -S`/`nm` del ELF, hash de partidas. No afirma mejora. |

## Contrato para añadir una fila

Mantener esta tabla breve: ID, ABI/dispositivo, commit y banderas, estado en código/APK, oráculo, A/B/A/B, cambios CPU/FPS/frame/presentación, prueba de escena y partida, evidencia pública y ruta privada **sin datos comerciales**. Evitar duplicar largos informes aquí.

Estados válidos: **integrado verificado**, **integrado experimental**, **opt-in inconcluso**, **regresivo/desactivado**, **bloqueado por corrección**, **pendiente**. Cada candidato seguro puede aportar una ganancia pequeña y acumulable. Para el delta cerca del ruido, mantenerlo disponible sin declarar mejora y repetir con suficiente potencia estadística. Revalidar el conjunto acumulado porque sus ganancias no se suman linealmente.

## Índice para IAs

1. Leer `../AGENTS.md`, [estado](PROJECT_STATUS.md), [cola vigente](ROADMAP.md) y este registro **antes** de buscar scripts o informes históricos.
2. Para métricas WSA finales, abrir WSA-02 y luego WSA-01; para TECNO, usar solo perfiles ARM64 y su Build ID. No confundir FPS del motor con presentación.
3. Acceder a `.local/profiles/` solo por experimento y hash exacto indicados en el informe. Excluir de búsquedas genéricas compilaciones, CMakeFiles, terceros descargados y backups A/B; nunca recorrerlo entero para responder cuál es la optimización activa.
4. `PROGRESS.md` es cronología; los encabezados «pendiente» de experimentos fechados pueden estar resueltos por commits posteriores. Confirmar siempre flags/código real antes de implementarlos otra vez.
