# Estado actual de CallofRecomp

**ARM64-MET-02:** comparador offline `scene_fingerprint.py`, seis pruebas aprobadas. Una imagen por pasada y comparacion automatica de encuadre; no mide estado 3D ni FPS. Complementa la guarda temporal, no la sustituye.

**Mediciones TECNO: control temporal (2026-10-15):**
Dos corridas de la MISMA 0.2.4: R3 21.70 FPS / 44.250 ms CPU y R4 21.65 FPS / 44.440 ms CPU; diferencia relativa -0.23 %. Veredicto: repetibilidad de referencia aceptable. No es una ganancia de optimización; son dos medidas del mismo código. Auditor permanente de FPS y telemetria HAL/CPU, docs/performance/tecno/TECNO_STABILITY_GATE_2026-10-15.md. Nueva guarda de referencia: A1 con 16,85 FPS frente a 21,675 FPS fue rechazado y la prueba cancelada; la APK 0.2.4 y el save se restauraron por SHA. Conservar las pequeñas mejoras ARM64 como opt-in hasta pruebas limpias.


**Adaptacion ARM64 de la mejora WSA de enlace local (2026-10-15):**
[informe y limite binary80](performance/tecno/ARM64_WSA_LOCAL_STATE_BINARY80_2026-10-15.md). ELF 490->486 exportaciones; solo R/MEM/U/PC locales, fuentes y recursos intactos. A/B/A/B, medias brutas 19.57->22.12 FPS (+13.03 %) y CPU 49.70->43.42 ms (-12.64 %); **no son ganancias atribuibles** porque A1 cayó 22.5->16.1 FPS en 40 ventanas; INCONCLUSO. 0.2.4 sigue como APK segura; x87 exacto ARM64 no implementado: oraculo numerico offline probado, sin estado/fallos. No activar por defecto.

**TECNO recuperado y medido (2026-10-15):** [TECNO 0.2.4 A/B/A/B](performance/tecno/TECNO_RELEASE024_ABAB_2026-10-15.md): 25,975 -> 22,025 FPS (-15,21 %), CPU 37,145 -> 43,680 ms/frame frente a la APK experimental previa con transform double inseguro. 0.2.4 instalada, partidas intactas; 60 FPS pendientes. Este corte sustituye las menciones de dispositivo ausente de los antecedentes siguientes.

**Web:** [GitHub Pages](https://dr3amyberry.github.io/callofrecomp/), con despliegue desde `web/dist`.

**Entrega 0.2.4:** [notas y descargas](history/releases/RELEASE_NOTES_v0.2.4.md), con APK ARM64 y WSA separadas y empaquetador público simplificado. El preset de release WSA activa las mejoras medidas y límite120 sin archivos privados; ARM64 conserva 60 y excluye el atajo double inseguro. La nueva build TECNO sigue sin medición física.

> **Nueva misión (2026-10-15): 120 FPS reales en WSA mediante desarrollo local.**
> [Control de FPS, perfil exacto del renderer y resultados actuales](performance/wsa/WSA120_LIMITER_AND_RENDERER_PROFILE_2026-10-15.md).
> El corte TECNO y el estado de CI descritos abajo siguen como antecedentes;
> no son mediciones nuevas ni la prioridad de rendimiento de esta misión.

**Política vigente:** [registro acumulativo y clasificación de cada optimización](OPTIMIZATION_LEDGER.md). Las ganancias verificadas, aunque pequeñas, se conservan; el antiguo límite de cinco intentos no aplica. Prioridad operativa 120 FPS WSA; **el objetivo TECNO ARM64 de 60 FPS sigue vigente, en espera de nueva medición**. Ver [plan de revalidación](TECNO_REVALIDATION.md).

**Aplicación del perfil:** [enlace local del estado guest, A/B/A/B y medición GL](performance/wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md). Conjunto anterior conservado; candidata normal instalada con **68,0–68,3 FPS / 14,64–14,71 ms CPU/frame** en ambas B. Mejora pequeña repetida, no 120 FPS sostenidos. Guardados intactos, instrumentación retirada.

**Perfil base conservado:** [CPU y renderizador antes del enlace local](performance/wsa/WSA120_OPTIMIZED_APK_CPU_PROFILE_2026-10-15.md), 12.695 muestras y 5.074 con stacks. Corresponde a la APK acumulativa anterior; no resolver sus PC contra el ELF nuevo. Se midieron además draws/índices/buffers y CPU GL sobre una APK diagnóstica separada; GPU y reutilización de geometría siguen sin certificar.

**Continuación WSA:** límites original/60/120/sin límite implementados y probados
en la misma escena con Alta; no hay ahorro CPU demostrado por retirarlos.
La pantalla virtual sigue en 75 Hz. El perfil exacto prioriza conversión/copia
x87 y la transformación `0x005061B0`. Su helper antiguo queda **BLOQUEADO**
por diferencias float32 frente al x86 original (commit `5ebe4cd`). Su alternativa
nativa binary80 ya está integrada. GPU time y sesiones complejas/prolongadas
siguen pendientes; 120 FPS no alcanzados. El informe enlazado es la fuente
de métricas y límites de estas pruebas.

**CI del release 0.2.4:** `f493638`, [run 38792819349 aprobado](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38792819349). [Release publicado](https://github.com/Dr3amyBerry/callofrecomp/releases/tag/v0.2.4), APK ARM64/WSA y hashes verificados; empaquetador público actualizado conservando su URL. Smoke WSA de actualización/defaults/entrenamiento aprobado sin cambios de partidas.
**Integración acumulativa medida:** [APK, opciones, pruebas y A/B/A/B](performance/wsa/WSA_CUMULATIVE_2026-10-15.md).
Región x87 binary80 conectada al runtime, retorno probado y conjunto compatible
activo en WSA. Misma escena/Alta: medias de medianas **54,75 → 66,75 FPS**,
**18,25 → 14,985 ms CPU/frame**. Capturas físicas completas; guardados intactos.
Los ensayos originales de [estado/alias/faltas](performance/wsa/WSA120_NATIVE_X87_STATE_2026-10-15.md)
son antecedentes; el oráculo de 22.344 casos se repitió con el adaptador final
y con el alias CW real del juego sin diferencias. La reanudación SEH, excepciones
sin máscara, estabilidad larga y 120 FPS sostenidos siguen sin certificarse.

**Corte:** 2026-10-15. **Código base de la revisión de CPU WSA:** `d6d6f8e174a24f259978fd30885ece63fc14902b` (solo documentación; APK acumulativa B integrada en `8401f29`). Esta página es la fuente de estado actual; los informes fechados conservan evidencia histórica.

[Documentación completa](INDEX.md) · [Próximo trabajo](ROADMAP.md) · [Estrategia 60 FPS](PERFORMANCE_STRATEGY_CURRENT.md) · [Bitácora](history/PROGRESS_LOG.md)

## Reorganización de fuentes de conocimiento — 2026-10-15

- La carpeta `docs/` mantiene únicamente entradas operativas y divide **78 documentos trasladados** entre guías, WSA, TECNO, CPU, CFG, gráficos e historial. [Índice corto](INDEX.md) y [catálogo completo](history/DOCUMENT_CATALOG.md).
- **TECNO CK6n sigue siendo meta vigente de 60 FPS**; la falta del dispositivo solo aplaza su revalidación. [Protocolo sin extrapolación de WSA](TECNO_REVALIDATION.md).
- Archivadas siete carpetas de builds pasadas, sin tocar las junctions ni la compilación actual; catálogo privado de 732 scripts, incluyendo duplicados exactos, sin borrarlos.
- Validación de esta reorganización: **396 pruebas Python, 6 omitidas, 0 fallos**, **38/38 CTest**, **119 Markdown sin enlaces internos rotos**, migradores repetibles sin nuevas mudanzas. Son pruebas de regresión, **no nuevas mediciones FPS**.

## Organización de perfiles privados — 15/10/2026

La raíz de `.local/profiles/` tenía **948 archivos sueltos**, incluidos 553 scripts Python, 33 imágenes PNG y 40 APK. Se archivaron **33 PNG históricos WSA sin referencias textuales** en `.local/profiles/history/wsa_20261013/captures/`, con manifiesto de origen y SHA256 reversible. **No se movieron directorios de perfiles activos, scripts históricos ni APK** que pudieran usar otras IAs.

Se agregaron [reglas de sesión y reutilización](guides/LOCAL_ARTIFACTS.md), un índice local consultable sin búsquedas recursivas y capturadores reutilizables sin serial ADB fijo. El análisis de similitud inspeccionó **734 scripts Python** sin errores AST, detectó un par idéntico y varios pares similares que preservan variantes A/B, ELF, entradas y condiciones. Validación: **6/6 pruebas unitarias**, **120 Markdown sin enlaces locales rotos**, compilación sintáctica y `git diff --check` correctos. No se ha ejecutado una captura real de dispositivo ni un benchmark nuevo; **no son mediciones FPS**. TECNO ARM64 sigue en espera de nueva validación física, no obsoleto.

## Revisión funcional de 200 scripts históricos — 2026-10-15

**Clasificación verificada contra dos manifiestos SHA256:** **103 scripts de edición puntual**, **94 experimentos/comprobaciones de escenario fijo** y **3 patrones convertidos en una utilidad genérica**. Se analizaron AST, llamadas y literales de rutas de cada uno de los 200 scripts archivados, sin ejecutar ninguno. Los 200 originales siguen en `.local/profiles/history/scripts/`. [Catálogo por archivo](history/ARCHIVED_SCRIPT_ROLES_FIRST200.md).

La nueva utilidad `tools/recomp/diagnostics/profile_evidence.py` sustituye las *capacidades* (no los archivos históricos) de inventario de capturas, comparación de SHA256 y resúmenes de metadatos con validación de Build ID. **Prueba sobre evidencia archivada real:** el hash de `strategy_spawn_cpu_v1.perf.data` y `strategy_spawn_cpu_v1.telemetry.json` se guardó y verificó correctamente (**2/2**) en una sesión `.local/profiles/runs/shared/...`. No se midieron FPS nuevos ni se alteraron APK, motor, saves o datos del TECNO. Las próximas tandas deben priorizar por comportamiento y entradas, no solo por nombre. Validación final: **438 pruebas Python** (6 omitidas, 0 fallos), **38/38 CTest**, 121 Markdown sin enlaces rotos, y verificación adicional del índice y los 200 archivos históricos.

## Segunda tanda de archivo de scripts — 2026-10-15

Se archivaron **100 scripts adicionales** (64 CFG14, 36 fases CPU). Hay **200 scripts históricos archivados** con dos manifiestos SHA256 independientes y **353 scripts Python sueltos** en `.local/profiles/`. No se borraron datos, ni se modificaron APK, saves o perfiles WSA/TECNO activos.

El nuevo preflight versionado `tools/audit_private_script_refs.py` revisó **453 scripts y 1.560 fuentes de código y documentación**, incluidos scripts archivados y carpetas anidadas. Encontró 145 candidatos; excluyó referencias nominales, importaciones de módulos hermanos, `__file__`, archivos recientes y scripts con sintaxis inválida. Los catálogos JSON no se tratan como consumidores de código. Se archivaron los primeros 100 elegibles con el argumento `--batch-id 2`, un manifiesto nuevo y comprobación SHA256.

`tools/verify_local_artifacts.py --save` verificó **200/200 scripts**, **33/33 PNG** y **7/7 builds** históricos, sin archivos privados registrados en Git. Conserva la advertencia de un script CFG14 antiguo con sintaxis incorrecta. Es una auditoría organizativa, no una mejora de FPS; las metas WSA 120 y TECNO 60 siguen independientes.

## Primera tanda de auditoría de scripts — 2026-10-15

Se verificaron **626 scripts Python privados** entre la raíz, perfiles anidados y archivos históricos: **625 con sintaxis válida y uno de parche CFG14 con error identificado** (conservado, no ejecutado). Se archivó una **tanda de 100 scripts** antes sueltos: 57 CFG14, 34 CPU, 7 ajustes puntuales y 2 capturadores TECNO obsoletos *como herramientas*, no sus perfiles de rendimiento. La raíz pasó de 553 a **453 scripts Python**. [Protocolo y restauración](guides/LOCAL_ARTIFACTS.md).

La herramienta `tools/verify_local_artifacts.py --save` revisó sin errores: **100/100 hashes de scripts**, **33/33 capturas**, **7/7 directorios de builds** históricos, directorios de nueva sesión, índice de rutas y **0 archivos privados rastreados en Git**. Clasifica explícitamente el script con error como advertencia y conserva manifiestos reversibles en `.local/catalog/`. Las **412 pruebas Python** de la suite local pasaron (6 omitidas) y el **CTest completo 38/38** también pasó. La primera ejecución CTest detectó un error de importaciones en tests nuevos; se corrigió y la repetición completa terminó con 0 fallos. Estas cifras **no son mediciones FPS** y no modifican la meta TECNO de 60 FPS.

## Qué existe y qué falta

| Área | Estado comprobado | Límite o pendiente |
| --- | --- | --- |
| Juego Android ARM64 | Arranque, menús, entrenamiento y gameplay físico documentados | Campaña completa, todos los guardados y todas las escenas sin verificar |
| Rendimiento TECNO CK6n | Capturas físicas, perfilado Simpleperf y ensayos A/B históricos | **60 FPS sostenidos no alcanzados**; no se midieron FPS nuevos en esta revisión documental |
| CPU fase 15 | Dos perfiles distintos del mismo ELF verificados: 7.953/6.541 muestras, Build ID comprobado | Etiquetas de instrucciones, no coste exclusivo de microoperaciones; no hay perfil simultáneo con frame stats |
| x87 | normal-f2d opt-in mostró mejora física modesta en su A/B/A/B | Fidelidad binary80 completa no demostrada; divergencias internas conocidas del traductor |
| CFG14 | Oráculos offline, auditoría de fallos y contrato Android documentados | **OFF y BLOQUEADO**; no apto para producción |
| Renderer | GL4ES/GLES de referencia; ANGLE 3D WSA ensayado sin mejora | Vulkan propio incompleto; WSA no certifica rendimiento ARM64/Mali |
| GPU física | No hay tiempo GPU Mali fiable en la evidencia revisada | No atribuir todo el frame a CPU por un swap corto |
| Regresión local previa | Fase 15 registra 382 Python (4 omitidas) y 35/35 CTest | Son resultados históricos del autor de esa fase, no ejecuciones nuevas de esta revisión |
| GitHub CI | Reparado en `fbbf074`: [run 38727099017 aprobado](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38727099017) | Se instalaron dependencias pinneadas; el fallo anterior de 32/33 queda como antecedente |

## TECNO hacia 60 FPS — objetivo vigente, en espera de disponibilidad

Estudiar **copias, materialización de pila y transferencias de estado x87 que se repitan en varias funciones**, usando ensamblador ARM64 y perfiles archivados. Después escoger una sola candidata con ahorro nativo plausible, demostrar estados y fallos, y medir en el TECNO. Las ocho funciones seleccionadas cubren ~19 % de muestras; no bastaría eliminarlas enteras para cubrir el presupuesto CPU hipotético de 60 FPS. [Fundamento y puertas de validación](PERFORMANCE_STRATEGY_CURRENT.md).

La referencia separada de 38,895 ms CPU/frame exigiría bajar a 16,667 ms (−57,15 %), bajo hipótesis CPU-bound. No es el rendimiento actual medido ni una promesa de aceleración. Hay además controles posteriores cercanos a 37,1 ms y ~26 FPS; no mezclar sesiones.

## GitHub y continuidad

El 2026-10-15 se verificó mediante el conector GitHub y después Git HTTPS fuera del sandbox: `main` remoto coincide con el SHA indicado. No había PR ni issues abiertos en esa consulta. `gh auth status` funciona fuera del sandbox; dentro, el acceso al keyring de Windows falla y puede aparentar token inválido. No se modificó SSH ni el remoto.

Fallo histórico: [tools-ci 38691095500](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38691095500), job `116276942932`: `ModuleNotFoundError: No module named 'unicorn'` al importar dos suites CFG. **Reparado y verificado** por el [run 38727099017](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38727099017) del commit `fbbf074`: el workflow instala Unicorn 2.1.4 y Capstone 5.0.6 desde `tests/requirements.txt`, sin ocultar tests. Los nuevos cambios de rendimiento requieren su propia CI.

Al retomar: comprobar `main` remoto, diff local, último run y evidencia; actualizar esta página y la cola cuando cambien. «Mantenerse al día» describe ese protocolo durante el trabajo; no hay monitor permanente configurado.

## Disponibilidad y artefactos

La última fase de ingeniería registró TECNO ausente y solo WSA accesible; esta revisión no volvió a consultar ADB. El análisis offline puede continuar con `.local/profiles/` y el ELF correspondiente. Una medición física nueva necesita el teléfono disponible. APK, partidas, perfiles crudos, binarios comerciales y C generado permanecen privados e ignorados; las rutas se explican en [WORKSPACE.md](WORKSPACE.md).

## Organización de la documentación

Se inventariaron 98 Markdown versionados previos a esta revisión. No se detectaron párrafos idénticos largos (>220 caracteres normalizados) entre archivos; sí reiteración de resúmenes y prioridades contradictorias por fecha. Se consolidaron estado, estrategia y cola; se preservaron las versiones previas de estrategia/roadmap y todos los informes. El índice distingue guías, evidencia y archivo. El informe privado del 13 de octubre es antecedente, no guía vigente.
