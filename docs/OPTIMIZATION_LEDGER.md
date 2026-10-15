# Registro acumulativo de optimizaciones — estado verificable

**ARM64-MET-02 / CI:** el run `38814719518` fallo por seis imports de PIL ausente. Se declara `Pillow==11.3.0`, la version usada en las pruebas locales, en `tests/requirements.txt`; se conserva la comprobacion de escenas en CI sin omitirla.

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
| SEG-01: `--cfg14-geom-region` y `--hot-x87-transform` antiguo | Código protegido por validaciones del builder | **BLOQUEADOS por corrección** | Original x86 muestra fallos de R/PC en CFG y errores binary80→double; no desbloquear por ganar FPS. [Análisis CFG](performance/cfg/PHASE14D_EPILOGUE_FAULT_SAFETY_2026-10-15.md), [x87](performance/wsa/WSA120_LIMITER_AND_RENDERER_PROFILE_2026-10-15.md). |
| GFX-01: ANGLE/Vulkan, GL4ES VBO modos 2/3 | Ensayados como alternativas o diagnósticos | **No integrados como optimización** | [ANGLE](performance/graphics/ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md) y [GL4ES](guides/ANDROID_PERFORMANCE.md). Hubo controles sin ganancia o con regresiones; no confundir mejora potencial con mejora demostrada. |

## Contrato para añadir una fila

Mantener esta tabla breve: ID, ABI/dispositivo, commit y banderas, estado en código/APK, oráculo, A/B/A/B, cambios CPU/FPS/frame/presentación, prueba de escena y partida, evidencia pública y ruta privada **sin datos comerciales**. Evitar duplicar largos informes aquí.

Estados válidos: **integrado verificado**, **integrado experimental**, **opt-in inconcluso**, **regresivo/desactivado**, **bloqueado por corrección**, **pendiente**. Cada candidato seguro puede aportar una ganancia pequeña y acumulable. Para el delta cerca del ruido, mantenerlo disponible sin declarar mejora y repetir con suficiente potencia estadística. Revalidar el conjunto acumulado porque sus ganancias no se suman linealmente.

## Índice para IAs

1. Leer `../AGENTS.md`, [estado](PROJECT_STATUS.md), [cola vigente](ROADMAP.md) y este registro **antes** de buscar scripts o informes históricos.
2. Para métricas WSA finales, abrir WSA-02 y luego WSA-01; para TECNO, usar solo perfiles ARM64 y su Build ID. No confundir FPS del motor con presentación.
3. Acceder a `.local/profiles/` solo por experimento y hash exacto indicados en el informe. Excluir de búsquedas genéricas compilaciones, CMakeFiles, terceros descargados y backups A/B; nunca recorrerlo entero para responder cuál es la optimización activa.
4. `PROGRESS.md` es cronología; los encabezados «pendiente» de experimentos fechados pueden estar resueltos por commits posteriores. Confirmar siempre flags/código real antes de implementarlos otra vez.
