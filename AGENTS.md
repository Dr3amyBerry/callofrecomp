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

## Contrato obligatorio de artefactos y scripts — ChatGPT / RigorCore Dev MCP

Leer [la guía de artefactos privados](docs/guides/LOCAL_ARTIFACTS.md) **antes** de usar el MCP para guardar capturas, perfiles, logs, APK o scripts. La regla antigua «guardar en .local» queda precisada así:

1. **Prohibido crear nuevos archivos sueltos en `.local/profiles/` o `.local/` raíz.** Crear una sesión única con `python tools/local_workspace.py new-run --target wsa --slug HIPOTESIS --agent chatgpt-mcp`. Usar sus directorios `captures/`, `logs/`, `metrics/`, `scripts/`, `builds/`, `reports/` y `raw/`.
2. **Antes de crear un script:** ejecutar `python tools/local_workspace.py find PALABRA --kind script` para localizar la herramienta versionada o el experimento previo. Preferir `tools/` y añadir parámetros + pruebas a duplicar scripts `v2`/`final` sin motivo.
3. **Capturas persistentes:** `python tools/local_capture.py android --run RUTA_SESION --serial SERIAL_ACTUAL --name escena-a` o variante `windows`. Una imagen recibida visualmente por el MCP no demuestra que exista un PNG en disco: guardar y comprobar ruta/bytes si se necesita evidencia. No imprimir capturas base64 en logs.
4. **Otra IA puede estar trabajando aquí.** No mover ni renombrar estudios activos, editar sesiones ajenas, borrar pruebas, tocar partidas ni modificar APK instalada para una limpieza. Crear destinos únicos, comprobar Git antes de cada escritura y hacer staging solo de archivos propios (nunca `git add -A`/`reset --hard`/`clean` en trabajo concurrente).
5. **No fusionar pruebas solo por nombres similares.** Una diferencia de ABI, Build ID, CW/x87, semillas, ramas o A/B puede ser esencial. Archivar requiere comparar referencias y hashes, dejar manifiesto reversible y no romper rutas originales. TECNO 60 FPS sigue como objetivo vigente.

Para búsquedas, consultar `.local/catalog/profiles_index.json` mediante el comando `find`; para duplicaciones estudiar `.local/catalog/script_similarity_2026-10-15.json` sin abrir todo el árbol.

## Verificación obligatoria del orden privado

El **flujo canónico** para esta zona es `tools/local_workspace.py` + `tools/verify_local_artifacts.py`; los traslados históricos se gestionan solamente con `tools/organize_legacy_scripts.py` y los manifiestos en `.local/catalog/`. **Las otras IAs deben ajustarse a estas rutas, no crear una estructura paralela.**

- Para auditar antes y después de una tanda: `python tools/local_workspace.py refresh`, `python tools/verify_local_artifacts.py --save`, `python tools/refresh_doc_catalog.py --check-only`, y pruebas unitarias.
- **Segunda tanda verificada:** otros 100 scripts (64 CFG14, 36 CPU) con manifiesto independiente `.local/catalog/archived_legacy_scripts_2026-10-15_batch02.json`. Total: **200 archivados y 353 sueltos**. Hacer el preflight con `python tools/audit_private_script_refs.py --batch-id 2 --write` y operar por `--batch-id` sin sobrescribir manifiestos; el verificador audita ambos.
- La primera tanda **100 scripts** se archivó bajo `.local/profiles/history/scripts/` con SHA256, filtrado de referencias y restauración. Manifest: `.local/catalog/archived_legacy_scripts_2026-10-15.json`. Cualquier otro movimiento requiere **un manifiesto nuevo y otra verificación**, no sobrescribir el anterior.
- **La reorganización de scripts históricos está centralizada:** otros agentes pueden crear nuevas sesiones y usar las herramientas comunes, pero no deben mover o deduplicar los scripts legados por su cuenta. La única excepción son cambios coordinados explícitamente y comprobados.
- **No ejecutar scripts históricos en una auditoría:** inspeccionar sintaxis con AST y referencias sin efectos secundarios; un script de parche defectuoso no invalida el motor pero debe quedar señalado como no ejecutable.
- Un auditor privado debe señalar desviaciones y fallos de SHA sin borrar nada. El verificador se ejecuta también antes de hacer commit.

## Clasificación funcional obligatoria de scripts

Los primeros 200 scripts de `.local/profiles/history/scripts/` ya tienen [catálogo funcional por archivo](docs/history/ARCHIVED_SCRIPT_ROLES_FIRST200.md) derivado de AST y rutas: **103 ediciones puntuales**, **94 pruebas/experimentos de contexto** y **3 capacidades extraídas a `tools/recomp/diagnostics/profile_evidence.py`**.

**Antes de crear un nuevo script:**
1. Buscar en el catálogo y en `tools/local_workspace.py find` si la función ya existe.
2. Si es **un cambio textual/de una sola vez**, hacer edición puntual y verificar diff/tests. El script de parche debe ser local al `runs/<target>/<fecha>/<estudio>/<sesion>/scripts/` o no crearse si no hace falta. No promocionar un script por haberlo ejecutado una vez.
3. Si es **un experimento**, mantener juntos script, versión, parámetros, entradas, hashes, oráculos y resultados en su sesión; no mezclar WSA con TECNO.
4. Si es **una verificación repetible**, incorporar opciones y tests a una utilidad canónica en `tools/`, en vez de clonar variantes con nombres distintos. Para hashes de perfiles, inventario y metadatos usar `tools/recomp/diagnostics/profile_evidence.py`.
5. No borrar, deduplicar ni ejecutar automáticamente los 200 scripts históricos. `python tools/review_archived_scripts.py --check` debe confirmar que su clasificación y hashes siguen válidos.

El criterio es **función e identidad de entradas**, no solo nombre o antigüedad. La clasificación estática sirve para orientar mantenimiento; no garantiza que un viejo parche sea seguro.

## Seguridad de la portabilidad ARM64 / WSA, 2026-10-15


WSA y TECNO **no comparten** codigo nativo x87. La ganancia
`--local-guest-state` de WSA no garantiza nada en ARM64; en TECNO
`--arm64-local-guest-state` es una variante separada OFF por defecto,
auditada para ocultar exclusivamente R/MEM/U/PC, y documentada en
`docs/performance/tecno/ARM64_WSA_LOCAL_STATE_BINARY80_2026-10-15.md`.
No habilitarla ni combinarla con renderer/copy/dispatch sin A/B independiente,
calidad y partidas iguales, temperaturas razonables y verificacion ABI.

La referencia `tools/recomp/diagnostics/binary80_arithmetic_reference.py`
es SOLO laboratorio numerico de operandos finitos y CW=0x037f; nunca conectarla
al motor porque no implementa SW/C1/TOP/tags, excepciones, fallos ni CW completos.
`--hot-x87-transform` sigue BLOQUEADO por divergencia con el x86 original.


## Protocolo obligatorio de estabilidad y ganancias pequenas (TECNO / WSA)

Conservar TODA mejora positiva pequena como experimento rastreable; no descartar por un umbral arbitrario. Tampoco proclamar una mejora sin pasadas A/B repetibles con las mismas APK, calidad, escena, camara y guardados.
- Usar `tools/recomp/diagnostics/stable_frame_gate.py` para comprobar deriva temporal, calentamiento y repetibilidad en A/B/A/B. Una sola mediana no valida FPS estables.
- Usar `tools/recomp/diagnostics/android_perf_environment.py` para observar temperatura HAL y relojes CPU en el TECNO sin modificar governors, afinidad ni potencia. El monitor tambien puede alterar el rendimiento y su overhead debe controlarse en mejoras inferiores al 1%.
- Esperar gameplay estable por logs antes de capturar 40 ventanas. No hacer decenas de fotos. Fallar cerrado si la escena deriva.
- Registrar pruebas en `docs/performance/tecno/TECNO_STABILITY_GATE_2026-10-15.md`. El atajo x87 double impreciso permanece BLOQUEADO.
