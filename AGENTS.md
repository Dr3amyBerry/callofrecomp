# Reglas de trabajo

## Eficiencia de contexto y verificación

- Priorizar scripts reproducibles, búsquedas dirigidas y resultados estructurados. Mostrar resúmenes, errores y métricas relevantes; guardar logs completos y artefactos privados bajo `.local/`.
- Agrupar consultas independientes y evitar releer documentación o repetir verificaciones ya aprobadas salvo cambios, fallos o incertidumbre nueva.
- Usar logs, marcadores de carga, PID, jerarquía accesible y métricas para automatizar navegación y mediciones. No capturar pantallas en cada paso ni sondear procesos sin necesidad.
- Reservar comprobaciones visuales para establecer una escena desconocida, resolver navegación ambigua, investigar una anomalía o validar equivalencia visual tras cambios gráficos. Reutilizar referencias y comparar imágenes mediante scripts antes de inspeccionarlas manualmente.
- Ahorrar tokens no justifica omitir pruebas funcionales, equivalencia x86, protección de partidas ni las mediciones físicas necesarias. No afirmar equivalencia visual o rendimiento basándose únicamente en logs o tests parciales.
- Comunicar avances breves: hallazgo, evidencia y siguiente acción. Evitar volcar archivos completos, inventarios extensos o salidas repetidas en el chat.

## Fuente de verdad y optimización incremental (vigente desde 2026-10-15)

- **Orden de lectura por defecto:** `AGENTS.md` → `docs/PROJECT_STATUS.md` → `docs/ROADMAP.md` → `docs/OPTIMIZATION_LEDGER.md` → `docs/PERFORMANCE_STRATEGY_CURRENT.md`. Leer informes fechados únicamente por hipótesis o evidencia concreta; `docs/history/PROGRESS_LOG.md` y `docs/archive/` son historia, no órdenes vigentes. Para reproducir usar el informe fechado y su carpeta privada exacta.
- **Búsquedas económicas:** empezar con rutas dirigidas (`docs/`, `tools/recomp/`, `android/`, `tests/`); no recorrer recursivamente builds, CMakeFiles, referencias externas, APK, fuentes generadas, repositorios descargados ni perfiles privados salvo que la tarea lo requiera. Buscar `.local/profiles/<estudio>` explícitamente con identidad de ELF/APK/escena. Nunca leer binarios originales o partidas para catalogar documentación.
- **La mejora comprobada se acumula, aunque sea pequeña.** No exigir un porcentaje mínimo arbitrario ni descartar código correcto por no alcanzar de forma individual la meta FPS. Documentar y conservar opción/patch, baseline y evidencia. Verificar el conjunto acumulado mediante A/B/A/B: los porcentajes aislados no se suman automáticamente.
- **Inconcluso no es mejora demostrada.** Si el delta cabe en el ruido, mantener resultado y candidato opt-in para repetir, sin imponerlo como default ni afirmar aceleración. Una regresión repetida obliga a desactivarlo de la candidata activa, conservando código/experimento para reevaluarlo con hipótesis nueva.
- **Correctitud primero:** cualquier divergencia x86 real, precisión binary80, PC/RAM/flags/alias/faltas, corrupción de saves o regresión visual/funcional es bloqueo, no una «mejora pequeña» acumulable. Mantener CFG14 y el transform antiguo double bloqueados.
- **No mezclar plataformas:** WSA x86_64 y TECNO ARM64 tienen ELFs, drivers, límites de FPS y métricas separados. La misión activa es 120 FPS WSA sin reducir calidad; 60 FPS TECNO es un objetivo vigente, temporalmente pendiente de nueva medición por falta del teléfono. Ver `docs/TECNO_REVALIDATION.md`. El panel WSA de 75 Hz no acredita 120 presentaciones visibles/s.
- Al finalizar cada cambio: actualizar `docs/OPTIMIZATION_LEDGER.md` y, si cambia el estado, `docs/PROJECT_STATUS.md`/`docs/ROADMAP.md`. Dejar commit, flags, SHA APK/ELF si aplica, oráculo, medidas, limitaciones y estado `integrado / opt-in / inconcluso / regresivo / bloqueado`. Nunca declarar FPS nuevo sin captura física comparable.
