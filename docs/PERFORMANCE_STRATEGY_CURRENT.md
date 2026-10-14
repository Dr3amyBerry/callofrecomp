# Estrategia vigente de rendimiento — CallofRecomp

**Estado:** VIGENTE · **Desde:** 2026-10-14 · **Versión:** 1 · **Decisión:** no cambiar de estrategia sin evidencia nueva suficiente.

## Meta y referencia

**Meta no negociable:** al menos **60 FPS sostenidos** en el punto de aparición del entrenamiento de Camp Toccoa, en el **TECNO CK6n ARM64**, perfil **Equilibrado**, sin reducir calidad, alterar el HUD panorámico, colisiones, controles ni partidas. No confundir FPS del menú, WSA o microbenchmarks con FPS del juego.

**Referencia operativa:** compilación x87 estable anterior, aproximadamente **24,9–25,1 FPS medianos** y **38,3–38,6 ms CPU/frame** en la vista estática de training de los controles recientes. Conservar una APK A reproducible y el estado de Git/build exacto de cada comparación. Esos valores son históricos, no una nueva medición.

## Estrategia actual: tres fases en orden

### Fase 1 — Perfilado profundo del frame real (prioridad inmediata)

1. Capturar una escena *reproducible* en el TECNO: mismo guardado, cámara, perfil, HUD, duración y condición térmica; incluir también una escena concurrida para comprobar si el cuello cambia.
2. Muestrear con **Simpleperf** (CPU) y resolver PCs ELF a funciones originales mediante los mapas Ghidra v2, atribuyendo por separado geometría, visibilidad, lógica, x87, accesos de memoria, despacho, GL4ES y driver. Diferenciar tiempo inclusivo/exclusivo y no atribuir toda una partición a una sola función.
3. Complementar con un **perfil GPU real** (AGI/Mali si el hardware y permisos lo permiten), frame pacing, carga y frecuencias CPU/GPU, temperatura y memoria. Si hay contadores no accesibles, dejar el hueco documentado: nunca inventar métricas.
4. Entregable de fase: tabla de cuellos de botella en *milisegundos por frame medidos o estimados con metodología explícita*, ranking dinámico con evidencia y selección de un único objetivo para la siguiente fase. No desarrollar un parche costoso sin este fundamento.

### Fase 2 — Optimización estructural del recompilador (prototipo acotado)

1. Tomar **una sola función caliente** del perfil. Investigar la agrupación de operaciones x86, valores de registros virtuales mantenidos en variables ARM64, eliminación segura de movimientos `rd/wr` y estados que sobreviven a Clang, y simplificación de despacho/aliasing.
2. Medir **antes y después del código máquina ARM64**: tamaño y `llvm-objdump`/perfil de instrucciones ejecutadas. Un C más corto **no es un éxito** si la sección `.text` y la ejecución permanecen idénticas (resultado ya observado con DCE).
3. Comparar con oráculo independiente x86 cuando sea posible; además, contrastar registros, EFLAGS, x87, RAM, PC, aliasing, NaN, ramas y resultados del motor. Flag experimental **OFF** hasta superar todos los controles.
4. Solo generalizar a otras funciones cuando haya una mejora sostenida en el teléfono y ningún fallo de imagen, controles o partidas.

### Fase 3 — Fast paths ARM64 de funciones completas

1. Elegir por **coste dinámico acumulado**, no por cantidad de instrucciones estáticas ni por aparecer en una lista de «top functions».
2. Tomar como modelo la experiencia de `0x005061B0`, cuya especialización optativa mostró alrededor de **+19,58 %** en una escena; no trasladar esa ganancia a nuevas funciones sin pruebas.
3. Implementar rutas nativas **con fallback** ante entradas o estados no cubiertos, validar con equivalencia completa y medir A/B/A/B/A en el TECNO.
4. Documentar el ahorro por función, su cobertura y el coste agregado restante. Nunca declarar que una mejora aislada garantiza 60 FPS.

Las fases definen **prioridad**, no una prohibición de recoger perfiles adicionales durante las fases 2/3. Si el nuevo perfil invalida la hipótesis, se vuelve a la fase 1 para seleccionar un objetivo sin abandonar automáticamente esta estrategia.

## Regla de decisión: 5 intentos válidos consecutivos sin mejora

**Contador actual: 0 de 5.** Los experimentos históricos anteriores al establecimiento de esta política son *antecedentes*, **no** cuentan de manera retroactiva.

Un **intento válido** es un experimento de optimización bajo esta estrategia, con hipótesis específica, versión A/B identificable, métrica objetivo declarada, código ARM64 o comportamiento relevante verificable, pruebas funcionales y captura controlada del mismo escenario en el TECNO (idealmente **A/B/A/B/A**, mínimo A/B/A suficientemente comparable y documentado). Los datos deben registrar FPS medianos, percentil bajo de ventanas, CPU/frame, temperatura, frecuencias si es posible y cualquier regresión. El tamaño del código, un benchmark sintético o una captura del menú por sí solos **no** constituyen un intento válido de rendimiento.

**Éxito:** mejora reproducible de FPS y/o reducción de CPU/frame **superior al ruido observado entre las referencias**, repetida en las corridas candidatas, sin regresión significativa de FPS bajos, estabilidad, visuales ni jugabilidad. Los resultados deben ser compatibles con avanzar hacia 60 FPS; una ganancia transitoria como FCOM B1 seguida de una caída B2 **no** es éxito. Si el experimento es un diagnóstico de fase 1 y no propone una mejora de rendimiento, no consume intento.

**Sin éxito (suma +1):** experimento válido que no supera el control, queda por debajo del ruido, o presenta una regresión. **Inconcluso (no suma):** faltan mediciones o las condiciones no son comparables; corregir el protocolo y repetir sin alterar el contador. **Éxito confirmado (reinicia a 0)**, sin declarar cumplida la meta de 60 FPS.

**Al acumular 5 fracasos válidos consecutivos:** **detener nuevos parches de esa línea de optimización** y abrir una *revisión formal de estrategia* basada en CPU/GPU, coste de las fases, resultados negativos y alternativas. La revisión debe decidir explícitamente y documentar si se **mantiene, modifica o reemplaza** la estrategia. **No cambiar automáticamente** de dirección solo porque el contador llegó a 5. Antes de ese umbral, se prioriza completar las fases previstas; excepciones razonables: riesgo de corrupción de datos, regresión grave, barrera técnica demostrada o un perfil nuevo que invalide claramente la premisa. Cualquier excepción requiere justificación escrita.

## Registro de intentos de la estrategia vigente

| ID | Fase y objetivo | Experimento | Estado | Resultado TECNO | Contador tras prueba |
| --- | --- | --- | --- | --- | --- |
| — | — | *Aún no hay intentos válidos bajo esta versión* | Pendiente | — | **0/5** |

**Actualización obligatoria tras cada intento:** anotar fecha, ID, commit y flags A/B, enlace a evidencia privada (sin subir partidas/APK/binarios comerciales), escena, ventanas, FPS p10/mediana, CPU/frame, térmica, comportamiento de HUD/partidas, decisión y valor nuevo del contador. Si faltan datos, registrar «inconcluso». Cada revisión de estrategia crea una nueva versión de este documento, sin borrar el historial.

## Evidencia histórica (no suma al contador)

- Fast path x87 de `0x005061B0`: ganancia real en una vista controlada, optativo.
- `--x87-fcom-fastpath`: ganancia B1 no reproducida y regresión B2 (19,8 FPS); rechazado.
- `--prune-dead-temporaries`: 32.704 operaciones estáticas eliminadas del C, pero sección nativa `.text` idéntica; sin mejora de FPS.
- `-O2` / `-Oz`, GL4ES batching/VBO, copy32 y NaN: beneficio insuficiente o regresiones en los escenarios ensayados. No volver a probarlos a ciegas.

Referencias: [perfil real TECNO](TECNO_CK6N_ARM64_PERF_2026-10-14.md), [renderer y FCOM](ARM64_RENDERER_CPU_FCOM_2026-10-14.md), [DCE p-code](CODSP_PCODE_TEMP_DCE_2026-10-14.md), [análisis funcional](FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md).

**Esta página es la fuente autoritativa sobre la estrategia vigente y su contador.** El roadmap y el log de progreso enlazan aquí. No convertir hipótesis en logros de FPS antes de confirmarlos en hardware real.
