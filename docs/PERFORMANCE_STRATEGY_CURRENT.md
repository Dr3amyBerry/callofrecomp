# Estrategia vigente de rendimiento

> **Cambio de objetivo por instrucción del usuario (2026-10-15): 120 FPS reales en WSA.** La [nueva línea base WSA](WSA120_BASELINE_2026-10-15.md) dirige el trabajo actual. Esta estrategia y su contador corresponden al objetivo TECNO anterior; se conservan los bloqueos de seguridad, sin transferir a WSA sus atribuciones de coste.

> [Resultado posterior WSA](WSA120_LIMITER_AND_RENDERER_PROFILE_2026-10-15.md):
> configurar 120/sin límite no demostró ahorro CPU; el perfil exacto prioriza
> x87 del renderer. **El helper normal-f64 de `0x005061B0` ahora está BLOQUEADO**
> tras fallar frente al x86 original, aunque los ensayos antiguos contra p-code
> y sus resultados de rendimiento se conserven abajo como antecedentes.

**Revisión documental:** 2026-10-15. Mantiene la estrategia adoptada el 2026-10-14 y su política de intentos; esta consolidación no es una nueva medición ni reinicia el contador.

[Estado actual](PROJECT_STATUS.md) · [Cola de trabajo](ROADMAP.md) · [Índice documental](INDEX.md)

## Evidencia nueva WSA B (2026-10-15, investigación sin implementación)

[Perfil exacto de la APK optimizada instalada](WSA120_OPTIMIZED_APK_CPU_PROFILE_2026-10-15.md): mediana de **67,2 FPS / 14,89 ms CPU/frame** durante 35 s de gameplay sin profiler simultáneo; **12.695 muestras** CPU con Build ID nativo y 28/28 fuentes verificadas, más **5.074** muestras con stacks DWARF. El nuevo perfil vincula `rd/wr`, `f2d/d2f` y el empaque `glUtilsPackPointerData` / `GL2Encoder::sendVertexAttributes` / `AddressSpaceStream` con puntos calientes específicos, **sin convertir esos samples en tiempos CPU exclusivos**. Prioridad WSA: inspeccionar ensamblador del código generado y cuantificar empaque de arrays antes de proponer otra transformación. Para 120 FPS faltan unos **6,56 ms/frame** y el modo visible continúa en **75 Hz**; no se midió GPU. Las prioridades TECNO que siguen son históricas.

## Decisión actual

Priorizar una investigación transversal del coste de **materializar, copiar y convertir el estado x87 en ARM64**, apoyada en las dos capturas físicas verificadas de TECNO. La unidad inicial debe ser un patrón repetido en varias funciones, con una frontera original comprobable. No seguir ampliando cachés de pequeñas regiones enteras que ya dieron resultados nulos o regresivos.

La fase 15 encontró que ocho funciones reúnen **19,0–19,6 % de muestras del proceso**. La referencia separada de **38,895 ms CPU/frame** requiere una reducción CPU hipotética del **57,15 %** para entrar en 16,667 ms. Eliminar esas ocho funciones enteras tampoco bastaría bajo ese modelo. La presencia de x87 en ~81 % de las muestras seleccionadas **no equivale a 81 % del tiempo total ni al coste exclusivo de la aritmética x87**. Las etiquetas de memoria, copia y flags se solapan. [Evidencia y límites](PHASE15_TECNO_CPU_PROFILE_CROSSCUTTING_2026-10-15.md).

## Orden de ejecución y puertas de salida

1. **Base verificable:** resolver primero el fallo conocido de CI por dependencia `unicorn` ausente y comprobar el run completo. Mantener identificadas APK, ELF, flags y Build ID de la referencia A.
2. **Diagnóstico offline útil desde ahora:** examinar PCs nativos y ensamblador del ELF que corresponde exactamente a los perfiles archivados; separar copias de pila, `rd/wr`, conversiones y spills. Entregar un patrón repetido, su cobertura observada y su coste nativo real; las muestras por instrucción no prueban causalidad por microoperación. No sumar rangos inline solapados.
3. **Candidata acotada:** solo si existe ahorro nativo plausible, preparar una transformación con fallback y opción OFF. Comparar contra el traductor vigente y contra el x86 original: R, GPR, flags, PC, RAM, alias, entradas interiores, binary80, TOP, CW/SW/tag y fallos observables. El runtime actual ya tiene divergencias binary80 conocidas: igualdad con el traductor no demuestra fidelidad x86. Ningún oráculo parcial autoriza sustitución completa.
4. **Validación física:** cuando TECNO esté disponible, capturar CPU/frame y perfil en la misma sesión, con escena, cámara, guardado, gráficos y condición térmica repetibles. Comparar A/B/A/B (mínimo A/B/A válido), FPS medianos y percentiles de ventanas, CPU/frame, estabilidad, imagen y partidas. Usar también una escena concurrida. Aprobar únicamente una ganancia repetida superior al ruido de A; restaurar A si no la hay.
5. **Generalización:** ampliar solo un patrón que haya pasado las puertas anteriores y actualizar el perfil del coste restante. La alternativa entera `0x0042B0A0` requiere primero un oráculo de función, alias y estimación del beneficio máximo; su presencia en el ranking no basta para justificar un reemplazo.

## Resultados que condicionan la selección

| Línea | Evidencia existente | Decisión |
| --- | --- | --- |
| normal-f2d p1/p8 | A/B/A/B TECNO: +3,31 % FPS y −1,300 ms CPU/frame frente a su propio A | Antecedente positivo; opt-in, no promesa de fidelidad x87 completa ni 60 FPS |
| p4 perfilado | A/B/A TECNO: ~0,39 % FPS, ~0,38 % CPU, sin repetición B suficiente | No aceptado; no convertir variación en mejora |
| POPCOUNT por ancho | 20.495 comparaciones; mismo tamaño ARM64 | Descartado; no repetir sin nueva evidencia |
| CFG14 con memoria | Estado R/PC divergente ante fallos; checkpoints offline añaden coste | **BLOQUEADO** en CMake y builder; no habilitar |
| Superregiones enteras sin RAM | Máximo 8 instrucciones; no reducen cargas y aumentan stores/tamaño | No integrar estos candidatos |
| ANGLE/Vulkan en WSA | Compatibilidad 3D ensayada, A/B/A sin ganancia demostrada | Mantener GL4ES como A; WSA no predice Mali |
| Vulkan propio / Zink | Prototipo incompleto / capacidades WSA insuficientes | Investigación secundaria, no siguiente apuesta para 60 FPS |

Fuentes: [normal-f2d](TECNO_X87_NORMAL_F2D_GAMEPLAY_ABAB_2026-10-14.md), [p4](CPU_PHASE10_TECNO_P4_PROFILED_ABA_2026-10-14.md), [binary80](PHASE14B_X87_BINARY80_SHARED_EPILOGUE_2026-10-15.md), [superregiones](PHASE14F_MEMORY_FREE_SUPERREGIONS_2026-10-15.md), [contrato Android](PHASE14F_ANDROID_FAULT_RECOVERY_CONTRACT_2026-10-15.md), [ANGLE 3D](ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md).

## Referencias de tiempo: no intercambiarlas

38,895 ms / 24,70 FPS es una referencia histórica separada usada por fase 15; ~37,1 ms / ~26 FPS pertenece a los controles de fase 10. Los ~95 ms del informe privado del 13 de octubre son anteriores, instrumentados y no describen el estado actual. Ninguna de esas series se capturó simultáneamente con los perfiles Simpleperf A1/A2. El tiempo GPU Mali sigue sin medirse; un swap breve no prueba GPU libre.

## Regla de decisión: 5 intentos válidos consecutivos sin mejora

**Contador heredado de los informes: 0 de 5; clasificación pendiente de conciliación.** Esta revisión no lo recalcula. Los experimentos históricos anteriores al establecimiento de esta política son *antecedentes*, **no** cuentan de manera retroactiva. Los ensayos físicos posteriores deben clasificarse explícitamente según las reglas siguientes antes del próximo intento.

Un **intento válido** es un experimento de optimización bajo esta estrategia, con hipótesis específica, versión A/B identificable, métrica objetivo declarada, código ARM64 o comportamiento relevante verificable, pruebas funcionales y captura controlada del mismo escenario en el TECNO (idealmente **A/B/A/B/A**, mínimo A/B/A suficientemente comparable y documentado). Los datos deben registrar FPS medianos, percentil bajo de ventanas, CPU/frame, temperatura, frecuencias si es posible y cualquier regresión. El tamaño del código, un benchmark sintético o una captura del menú por sí solos **no** constituyen un intento válido de rendimiento.

**Éxito:** mejora reproducible de FPS y/o reducción de CPU/frame **superior al ruido observado entre las referencias**, repetida en las corridas candidatas, sin regresión significativa de FPS bajos, estabilidad, visuales ni jugabilidad. Los resultados deben ser compatibles con avanzar hacia 60 FPS; una ganancia transitoria como FCOM B1 seguida de una caída B2 **no** es éxito. Si el experimento es un diagnóstico de fase 1 y no propone una mejora de rendimiento, no consume intento.

**Sin éxito (suma +1):** experimento válido que no supera el control, queda por debajo del ruido, o presenta una regresión. **Inconcluso (no suma):** faltan mediciones o las condiciones no son comparables; corregir el protocolo y repetir sin alterar el contador. **Éxito confirmado (reinicia a 0)**, sin declarar cumplida la meta de 60 FPS.

**Al acumular 5 fracasos válidos consecutivos:** **detener nuevos parches de esa línea de optimización** y abrir una *revisión formal de estrategia* basada en CPU/GPU, coste de las fases, resultados negativos y alternativas. La revisión debe decidir explícitamente y documentar si se **mantiene, modifica o reemplaza** la estrategia. **No cambiar automáticamente** de dirección solo porque el contador llegó a 5. Antes de ese umbral, se prioriza completar las fases previstas; excepciones razonables: riesgo de corrupción de datos, regresión grave, barrera técnica demostrada o un perfil nuevo que invalide claramente la premisa. Cualquier excepción requiere justificación escrita.

## Registro de intentos de la estrategia vigente

| ID | Fase y objetivo | Experimento | Estado | Resultado TECNO | Contador tras prueba |
| --- | --- | --- | --- | --- | --- |
| Histórico | CPU p0 y p4 | Ensayos físicos de fases 3, 4 y 10, sin mejora aceptada | Revisar validez/comparabilidad por ensayo; no declarar ausencia de pruebas | Véanse informes enlazados en el índice | **0/5 heredado, no auditado** |

**Actualización obligatoria tras cada intento:** anotar fecha, ID, commit y flags A/B, enlace a evidencia privada (sin subir partidas/APK/binarios comerciales), escena, ventanas, FPS p10/mediana, CPU/frame, térmica, comportamiento de HUD/partidas, decisión y valor nuevo del contador. Si faltan datos, registrar «inconcluso». Cada revisión de estrategia crea una nueva versión de este documento, sin borrar el historial.

## Mantenimiento

Esta página conserva la política y la decisión vigente. Los resultados detallados viven en sus informes fechados; el estado de implementación y CI vive en [PROJECT_STATUS.md](PROJECT_STATUS.md). El registro anterior se conserva en [archivo previo a consolidación](archive/PERFORMANCE_STRATEGY_CURRENT_BEFORE_CONSOLIDATION_2026-10-15.md). El contador heredado **0/5** no fue recalculado: hay ensayos físicos no aceptados cuyo encaje formal debe revisarse antes de registrar el próximo intento; no usar el contador para ocultar resultados negativos.
