# Estrategia vigente de rendimiento

> **Objetivos vigentes:** 120 FPS reales en WSA x86_64, donde se trabaja ahora; y 60 FPS sostenidos en TECNO CK6n ARM64, **pendiente de revalidación cuando esté disponible el teléfono**. [La medición más reciente de WSA](performance/wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md) es la referencia de trabajo; [plan de revalidación TECNO](TECNO_REVALIDATION.md). Los cálculos y perfiles TECNO más antiguos no demuestran el rendimiento de la integración WSA.

> [Resultado posterior WSA](performance/wsa/WSA120_LIMITER_AND_RENDERER_PROFILE_2026-10-15.md):
> configurar 120/sin límite no demostró ahorro CPU; el perfil exacto prioriza
> x87 del renderer. **El helper normal-f64 de `0x005061B0` ahora está BLOQUEADO**
> tras fallar frente al x86 original, aunque los ensayos antiguos contra p-code
> y sus resultados de rendimiento se conserven abajo como antecedentes.

**Política vigente desde 2026-10-15:** mejora incremental y acumulativa con fidelidad obligatoria. **No existe el contador de cinco intentos** para dirigir nuevas decisiones; esa regla está preservada solamente como historial. Los resultados de laboratorio y A/B antiguos siguen disponibles con su alcance original.

[Estado actual](PROJECT_STATUS.md) · [Cola de trabajo](ROADMAP.md) · [Índice documental](INDEX.md)

## Evidencia WSA B previa al último cambio (2026-10-15, perfil ya completado)

[Perfil exacto de la APK optimizada instalada](performance/wsa/WSA120_OPTIMIZED_APK_CPU_PROFILE_2026-10-15.md): mediana de **67,2 FPS / 14,89 ms CPU/frame** durante 35 s de gameplay sin profiler simultáneo; **12.695 muestras** CPU con Build ID nativo y 28/28 fuentes verificadas, más **5.074** muestras con stacks DWARF. El nuevo perfil vincula `rd/wr`, `f2d/d2f` y el empaque `glUtilsPackPointerData` / `GL2Encoder::sendVertexAttributes` / `AddressSpaceStream` con puntos calientes específicos, **sin convertir esos samples en tiempos CPU exclusivos**. Prioridad WSA: inspeccionar ensamblador del código generado y cuantificar empaque de arrays antes de proponer otra transformación. Para 120 FPS faltan unos **6,56 ms/frame** y el modo visible continúa en **75 Hz**; no se midió GPU. Las prioridades TECNO que siguen son históricas.

## Decisión actual

**Continuación WSA aplicada:** [candidata de enlace local y mediciones](performance/wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md). Se conservó el conjunto acumulativo y se obtuvo una mejora adicional pequeña en ambas parejas. La siguiente candidata debe abordar conversiones o reempaquetado probado, usando el ELF correcto y sin convertir los contadores GL en tiempo GPU. El texto ARM64 siguiente conserva la estrategia histórica.

Priorizar una investigación transversal del coste de **materializar, copiar y convertir el estado x87 en ARM64**, apoyada en las dos capturas físicas verificadas de TECNO. La unidad inicial debe ser un patrón repetido en varias funciones, con una frontera original comprobable. No seguir ampliando cachés de pequeñas regiones enteras que ya dieron resultados nulos o regresivos.

La fase 15 encontró que ocho funciones reúnen **19,0–19,6 % de muestras del proceso**. La referencia separada de **38,895 ms CPU/frame** requiere una reducción CPU hipotética del **57,15 %** para entrar en 16,667 ms. Eliminar esas ocho funciones enteras tampoco bastaría bajo ese modelo. La presencia de x87 en ~81 % de las muestras seleccionadas **no equivale a 81 % del tiempo total ni al coste exclusivo de la aritmética x87**. Las etiquetas de memoria, copia y flags se solapan. [Evidencia y límites](performance/tecno/PHASE15_TECNO_CPU_PROFILE_CROSSCUTTING_2026-10-15.md).

## Orden de ejecución y puertas de salida

1. **Base verificable:** resolver primero el fallo conocido de CI por dependencia `unicorn` ausente y comprobar el run completo. Mantener identificadas APK, ELF, flags y Build ID de la referencia A.
2. **Diagnóstico offline útil desde ahora:** examinar PCs nativos y ensamblador del ELF que corresponde exactamente a los perfiles archivados; separar copias de pila, `rd/wr`, conversiones y spills. Entregar un patrón repetido, su cobertura observada y su coste nativo real; las muestras por instrucción no prueban causalidad por microoperación. No sumar rangos inline solapados.
3. **Candidata acotada:** solo si existe ahorro nativo plausible, preparar una transformación con fallback y opción OFF. Comparar contra el traductor vigente y contra el x86 original: R, GPR, flags, PC, RAM, alias, entradas interiores, binary80, TOP, CW/SW/tag y fallos observables. El runtime actual ya tiene divergencias binary80 conocidas: igualdad con el traductor no demuestra fidelidad x86. Ningún oráculo parcial autoriza sustitución completa.
4. **Validación en plataforma objetivo:** en WSA comparar A/B/A/B a igualdad de APK/escena/Alta/limitador; para ARM64, cuando TECNO esté disponible, capturar CPU/frame y perfil en la misma sesión, con escena, cámara, guardado, gráficos y condición térmica repetibles. Comparar A/B/A/B (mínimo A/B/A válido), FPS medianos y percentiles de ventanas, CPU/frame, estabilidad, imagen y partidas. Usar también una escena concurrida. Integrar ganancias repetidas incluso pequeñas; marcar como inconcluso el delta indistinguible del ruido y conservar la opción opt-in. Restaurar A como referencia activa si B es regresiva o insegura.
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

Fuentes: [normal-f2d](performance/tecno/TECNO_X87_NORMAL_F2D_GAMEPLAY_ABAB_2026-10-14.md), [p4](performance/tecno/CPU_PHASE10_TECNO_P4_PROFILED_ABA_2026-10-14.md), [binary80](performance/cfg/PHASE14B_X87_BINARY80_SHARED_EPILOGUE_2026-10-15.md), [superregiones](performance/cfg/PHASE14F_MEMORY_FREE_SUPERREGIONS_2026-10-15.md), [contrato Android](performance/cfg/PHASE14F_ANDROID_FAULT_RECOVERY_CONTRACT_2026-10-15.md), [ANGLE 3D](performance/graphics/ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md).

## Referencias de tiempo: no intercambiarlas

38,895 ms / 24,70 FPS es una referencia histórica separada usada por fase 15; ~37,1 ms / ~26 FPS pertenece a los controles de fase 10. Los ~95 ms del informe privado del 13 de octubre son anteriores, instrumentados y no describen el estado actual. Ninguna de esas series se capturó simultáneamente con los perfiles Simpleperf A1/A2. El tiempo GPU Mali sigue sin medirse; un swap breve no prueba GPU libre.

## Política vigente: retener y sumar mejoras demostradas

**Sustituye la antigua regla de «5 intentos» y el criterio de desechar todo cambio que no eleve claramente los FPS por sí solo.** Aquella política y su contador 0/5 se mantienen únicamente en la copia histórica de `archive/`; **no gobiernan nuevas decisiones**. No existe un umbral porcentual mínimo universal para que una mejora sea valiosa.

1. **Beneficio comprobado:** conservar en el conjunto candidato un cambio funcionalmente equivalente, incluso con mejora pequeña, cuando A/B/A/B sobre la misma escena/dispositivo/ELF muestra beneficio repetido de FPS, tiempo CPU/frame, estabilidad, latencia, memoria o carga según la métrica declarada. Distinguir optimización de FPS de mejoras de otros objetivos.
2. **Beneficio dentro del ruido:** clasificar `INCONCLUSO / OPT-IN`. Conservar el código, hipótesis, tests y trazas para la próxima integración; no presentarlo como aumento FPS demostrado ni activar por defecto una combinación sin verificar.
3. **Regresión reproducible:** retirar la opción del conjunto activo, sin borrar el conocimiento ni necesariamente el código; repetir únicamente con una hipótesis nueva y referencias controladas.
4. **Incorrectitud o riesgo:** `BLOQUEADO` aunque un microbenchmark o FPS parezcan mejores. Requiere demostrar equivalencia x86 original (R/GPR/flags/PC/RAM/x87 binary80/CW/SW/TOP/tags/alias/faltas) y ausencia de daño a partidas, gráficos o jugabilidad.
5. **Integración acumulativa:** comparar `A = conjunto correcto anterior` frente a `B = A + nueva candidata`. Nunca asumir que los porcentajes de dos pruebas independientes se suman. Guardar matriz de flags, APK/ELF SHA, tests, escena, preset, datos de ventanas y razones de descarte o retención.
6. **Priorización basada en perfil:** no detener todo el avance tras N experimentos fallidos. Cambiar de dirección cuando el cuello de botella o la evidencia lo recomienden; conservar candidatos correctos de bajo coste aunque todavía no muevan el FPS visible.
7. **Por plataforma:** 120 FPS de motor en WSA se separa de los límites de presentación del panel a 75 Hz y de la meta 60 FPS física TECNO. Un microbenchmark, una corrida aislada o un informe de otra ABI no certifican FPS.

La matriz de `integrado, experimental, inconcluso, regresivo y bloqueado` está en [Registro acumulativo](OPTIMIZATION_LEDGER.md). Los informes fechados preservan decisiones de su momento pero no sustituyen esta política.

## Mantenimiento

Esta página usa la política acumulativa anterior. El antiguo contador 0/5 pertenece al historial y no debe reiniciarse ni consultarse para nuevas decisiones.

Esta página conserva la política y la decisión vigente. Los resultados detallados viven en sus informes fechados; el estado de implementación y CI vive en [PROJECT_STATUS.md](PROJECT_STATUS.md). El registro anterior se conserva en [archivo previo a consolidación](archive/PERFORMANCE_STRATEGY_CURRENT_BEFORE_CONSOLIDATION_2026-10-15.md). Las mediciones históricas con resultados negativos o inciertos continúan disponibles para la siguiente hipótesis; el contador antiguo no se aplica ni se recalcula.
