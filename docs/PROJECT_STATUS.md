# Estado actual de CallofRecomp

> **Nueva misión (2026-10-15): 120 FPS reales en WSA mediante desarrollo local.**
> [Línea base actual y trabajo abierto](WSA120_BASELINE_2026-10-15.md).
> El corte TECNO y el estado de CI descritos abajo siguen como antecedentes;
> no son mediciones nuevas ni la prioridad de rendimiento de esta misión.

**Corte:** 2026-10-15. **Código revisado:** `bda83a6532b7cbf6489740f42830eb9f55fdff98` (fase 15). Esta página es la fuente de estado actual; los informes fechados conservan evidencia histórica.

[Documentación completa](INDEX.md) · [Próximo trabajo](ROADMAP.md) · [Estrategia 60 FPS](PERFORMANCE_STRATEGY_CURRENT.md) · [Bitácora](../PROGRESS.md)

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
| GitHub CI | Último run del código revisado **falló**; 32/33 CTest | `static_analysis_python`: dos errores de importación por `unicorn` ausente en Linux |

## Decisión para avanzar hacia 60 FPS

Estudiar **copias, materialización de pila y transferencias de estado x87 que se repitan en varias funciones**, usando ensamblador ARM64 y perfiles archivados. Después escoger una sola candidata con ahorro nativo plausible, demostrar estados y fallos, y medir en el TECNO. Las ocho funciones seleccionadas cubren ~19 % de muestras; no bastaría eliminarlas enteras para cubrir el presupuesto CPU hipotético de 60 FPS. [Fundamento y puertas de validación](PERFORMANCE_STRATEGY_CURRENT.md).

La referencia separada de 38,895 ms CPU/frame exigiría bajar a 16,667 ms (−57,15 %), bajo hipótesis CPU-bound. No es el rendimiento actual medido ni una promesa de aceleración. Hay además controles posteriores cercanos a 37,1 ms y ~26 FPS; no mezclar sesiones.

## GitHub y continuidad

El 2026-10-15 se verificó mediante el conector GitHub y después Git HTTPS fuera del sandbox: `main` remoto coincide con el SHA indicado. No había PR ni issues abiertos en esa consulta. `gh auth status` funciona fuera del sandbox; dentro, el acceso al keyring de Windows falla y puede aparentar token inválido. No se modificó SSH ni el remoto.

Último run inspeccionado: [tools-ci 38691095500](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38691095500), job `116276942932`. El log muestra `ModuleNotFoundError: No module named 'unicorn'` en `test_cfg_exception_checkpoint` y `test_cfg_region_fault_state`. Los dos runs anteriores también fallaron; se verificó la causa del último. El paso Python quedó en 367 tests, 2 errores y 5 omitidos; CTest en 32/33. **Próxima prioridad operativa: reparar dependencias de CI antes de integrar otra optimización.** Esta revisión no modifica el workflow ni declara ese fallo resuelto.

Al retomar: comprobar `main` remoto, diff local, último run y evidencia; actualizar esta página y la cola cuando cambien. «Mantenerse al día» describe ese protocolo durante el trabajo; no hay monitor permanente configurado.

## Disponibilidad y artefactos

La última fase de ingeniería registró TECNO ausente y solo WSA accesible; esta revisión no volvió a consultar ADB. El análisis offline puede continuar con `.local/profiles/` y el ELF correspondiente. Una medición física nueva necesita el teléfono disponible. APK, partidas, perfiles crudos, binarios comerciales y C generado permanecen privados e ignorados; las rutas se explican en [WORKSPACE.md](WORKSPACE.md).

## Organización de la documentación

Se inventariaron 98 Markdown versionados previos a esta revisión. No se detectaron párrafos idénticos largos (>220 caracteres normalizados) entre archivos; sí reiteración de resúmenes y prioridades contradictorias por fecha. Se consolidaron estado, estrategia y cola; se preservaron las versiones previas de estrategia/roadmap y todos los informes. El índice distingue guías, evidencia y archivo. El informe privado del 13 de octubre es antecedente, no guía vigente.
