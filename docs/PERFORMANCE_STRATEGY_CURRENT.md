# Estrategia vigente de rendimiento — CallofRecomp

**Estado:** VIGENTE · **Desde:** 2026-10-14 · **Versión:** 1 · **Decisión:** no cambiar de estrategia sin evidencia nueva suficiente.

## Fase 14C: arquitectura de caché de R por bloque original con fallback (prototipo offline)

**227 bloques** de los siete cuerpos calientes son candidatos a pruebas integer-only, sin FPU/opacos (855 instrucciones). En dos prototipos completos CFG compilados a ARM64, un único líder de entrada rápida con cache de registros disjuntos redujo código/cargas/escrituras estáticas: geometría **976→804 bytes .text, 51→40 cargas, 48→31 escrituras** y recorrido **648→616 bytes, 39→31 cargas, 37→33 escrituras**. La variante genérica que permite entrar en **todos** los PC dentro de la función rápida **provocó regresiones**, descartada. Un simulador de dispatcher delegó las entradas interiores al traductor original; diferencias host **696/696** y **360/360** estados iguales con RAM plegada de 64 KiB, no un oráculo x86 independiente. Sin prueba de alias real, integración productiva, nuevo ahorro en ms/frame ni mejora de FPS. **No se ha activado ninguna optimización de la APK.** [Plan](PHASE14C_CFG_REGION_EXPERIMENT_PLAN_2026-10-15.md) · [Resultados A/B](PHASE14C_CFG_AB_OFFLINE_RESULTS_2026-10-15.md).

## Fase 14B — Precisión x87 y contrato del epílogo compartido

Una auditoría Unicorn del `binary80` real en cinco operaciones x87 de `0x0041B8F0` reveló pérdida de precisión en el traductor basado en `double`: después del segundo `FSUB`, **167/256** estados ST0 no coinciden aunque el resultado `float32` final observado seguía coincidiendo en estos casos. Se verificó la lectura del registro físico x87 con **11 ejemplos FSTP m80** y se añadió una puerta estricta que **rechazó** el candidato en el ensayo negativo de 96 casos. **No se corrigió ni aceleró el runtime**: la conclusión es un bloqueo de equivalencia para reemplazos de funciones que toquen x87. Además, los tres saltos de salida van a la función `0x00523CD9`, una comparación contra el cookie global con retorno en éxito y rama de fallo; debe preservarse fuera de la región nativa. Ninguna mejora de FPS o ms/frame queda probada. [Informe y evidencias](PHASE14B_X87_BINARY80_SHARED_EPILOGUE_2026-10-15.md).


## Fase 14B: control de estado por byte y ejecución x86 en dos caminos

Se extendió el oráculo original de `0x0041B8F0` a 20 instrucciones si JE no se toma y 27 si se toma. Unicorn ejecutó los bytes x86 originales y se contrastó una DLL privada de `pcode2c.Gen`: **512/512 casos coincidentes** de ocho GPR, CF/PF/ZF/SF/OF, PC y RAM acotada, con una mutación de PC correctamente rechazada. `AF y x87 NO se han verificado`; ambas rutas se detienen antes de FPU. Análisis MAY/MUST por byte de R completado para 450 bloques, que detecta LOAD/STORE y 80 bytes x87 en la función prioritaria; **no habilita caché de registros ni transforma el motor**. Sin beneficio probado de FPS. [Informe técnico](PHASE14B_STATE_BOUNDARIES_ORACLE_2026-10-15.md).

## Fase 14A: control de flujo por función original, no ajustes de una operación

El análisis offline de los siete cuerpos calientes de CoDSP.exe 1.5 recuperó **3.326 instrucciones y 450 bloques básicos**, distinguiendo rango B discontiguo, accesos a estado, entrada externa, saltos locales p-code y retornos indirectos. Los límites y clases/targets x86 reales se comprobaron **independientemente con Capstone**: **3.326 límites y 342 transferencias coincidentes; cero discrepancias**, aunque **cuatro instrucciones carecen de p-code exportado**. Estos resultados **no** demuestran equivalencia del motor ni mejoras FPS. El objetivo de 14B es proteger y verificar los límites de `0x0041B8F0`, que tiene 553 instrucciones, 88 bloques, cero huecos o salidas indirectas conocidas, pero varias entradas/salidas externas; no optimizar hasta que la frontera y estado completo sean comprobados. No se tocó la APK, Android, los gráficos ni el TECNO. [Plan](PHASE14_CFG_ARCHITECTURE_MASTER_PLAN_2026-10-14.md) · [Reporte](PHASE14_CFG_INITIAL_RECOVERY_2026-10-14.md).

## Fase 13: compilación A/B de bloques calientes completos (nueva opción OFF)

Se compararon tres chunks completos (1.500 instrucciones p-code cada uno) en ARM64 por compilación NDK, usando dos perfiles CPU físicos antiguos y ninguna prueba nueva en TECNO. `-O2` con `-ffp-contract=off` reduce cargas/escrituras ARM64 **estáticas** en geometría chunk18 y recorrido chunk88. Sobre **p4 completa**: `.text` **1.998.764→1.979.316 B**, cargas **82.258→77.931**, escrituras **68.537→54.388**. **No** es una reducción medida de tiempo por frame ni FPS; el compilador puede afectar cada ruta de manera distinta.

**Visibilidad chunk152 se excluyó tras regresiones estáticas** en tamaño y cargas; tampoco se incorporaron los prototipos de escalarizar temporales, caché GPR de chunks ni DCE extra, al comprobar que LLVM ya los optimizaba o que empeoraban el nativo. Se añadió `CODRECOMP_CORE_HOT_O2` (flag Android `--core-hot-o2`) **solo p0/p1/p4, ARM64, hash verificado, OFF por defecto**, sin retirar renderizado ni alterar configuración gráfica. CMake/Ninja de Android verificó `-O2` efectivo para esos tres archivos; p8/p10 siguen `-O1`. Tests aprobados: **272 Python (4 omitidos), 35/35 CTest**. La referencia física continúa alrededor de **26 FPS**, **60 FPS todavía no demostrados**. [Análisis completo](CPU_PHASE13_HOT_BLOCK_COMPILER_AB_OFFLINE_2026-10-14.md).

## Fase 12 offline: fusión de siete movimientos x87 por llamada nativa compartida

Los perfiles Simpleperf archivados sitúan costes importantes en geometría, visibilidad y movimientos arquitectónicos; sus muestras no son tiempos exclusivos por función ni medidas nuevas de FPS. En el p-code CoDSP 1.5 se localizaron **18.194 secuencias** completas de siete copias x87 de 10 bytes con paso de 16. La transformación revisa los saltos al interior y consolida el grupo en un helper nativo `noinline`, conservando el padding observable. La herramienta optativa está implementada en el generador y constructor ARM64, con verificaciones de SHA-256 y restauración byte a byte en los 12 archivos generados; **OFF por defecto**.

El objeto AArch64 de la partición **p4 completa** pasó de **1.998.764 a 1.774.024 bytes** en sección `.text` (**−224.740, −11,244 %**), con imágenes de geometría y visibilidad compiladas aisladamente alrededor de −11 %. Tests: **269 Python (4 omitidas), 35/35 CTest** y equivalencia sintética completa de R/RAM/U/PC a O0/O1/O2. No es un perfil de ciclos ni una mejora probada de FPS; se preserva la APK estable y no se utilizó el TECNO. [Informe fase 12](CPU_PHASE12_X87_STACK_SHIFT_OUTLINE_OFFLINE_2026-10-14.md).

## Fase 11 offline: evitar doble cómputo de `rd`/`wr`/ `memcpy` en Simpleperf

Con el A/B/A de fase 10 cerrado, se reusaron dos perfiles históricos de chunks CoDSP p4 (**1.017/889 muestras; 974/840 atribuidas a PC guest**). La clase **más interna** de marcos DWARF fue `memcpy` en **409/353 muestras (~42 % de las atribuidas)**; `f2d` en **352/309**; `d2f` en **102/96**. Las muestras inclusivas de `rd` (**233/204**) y `wr` (**154/123**) están **enteramente solapadas con `memcpy`**; no son costes independientes para sumar. *Marco interno* NO equivale a tiempo exclusivo ni FPS: solo guía una auditoría futura del ensamblado, cargas/almacenamientos y equivalencia del estado completo. No se tocó la APK ni el TECNO. [Informe y pruebas](CPU_PHASE11_P4_INLINE_OVERLAP_OFFLINE_2026-10-14.md).

## Fase 10 TECNO: A/B/A físico de la candidata x87 p4 perfilada (DESCARTADA)

Se cerró el experimento que las fases 8 y 9 dejaban pendiente de medición física. Mismo TECNO CK6n, Camp Toccoa, Equilibrado, **2400 × 1080** y cámara estática. **A1 26,00 FPS / 37,100 ms CPU**, **B2 26,05 FPS / 36,980 ms CPU**, **A2 25,90 FPS / 37,145 ms CPU** (medianas de las últimas 40 ventanas de 55 segundos por ejecución). B vs. media A: **+0,10 FPS (+0,39 %) / −0,1425 ms CPU (−0,38 %)**: variación insuficiente para atribuir una mejora real a p4 x87. Las ventanas no son fotogramas independientes; B1 no cargó por temporización de la navegación y no tiene FPS válidos. Solo cambia `libmain.so` entre las dos APK experimentales; las capturas del gameplay permanecen prácticamente iguales, no idénticas píxel a píxel.

**Decisión: NO activar `CODRECOMP_X87_NORMAL_F2D_P4_PROFILED`.** La instalación previa exacta y el autoguardado fueron verificados y restaurados por SHA-256, con el juego detenido. Mantener también OFF las otras optimizaciones p4 no aprobadas y no reducir geometría, resolución, efectos, NPC ni fidelidad x87. **60 FPS sostenidos pendientes.** Siguiente investigación offline: distinguir costes inclusivos/exclusivos de `memcpy`, `rd` y `wr` en los perfiles archivados antes de elegir nuevos sitios; un cambio C o un binario más pequeño no demuestran FPS. [Informe](CPU_PHASE10_TECNO_P4_PROFILED_ABA_2026-10-14.md).

## Fase 9 offline: empaquetado x87 alternativo descartado; auditor ARM64 añadido (0/5)

Una variante aritmética de empaquetado binary80 fue bit-equivalente en **1.205.360 patrones** y **44.000 estados completos R/RAM/PC**, pero su supuesto ahorro de 4 bytes en una función aislada no apareció en los tres chunks reales. La sección ARM64 .text de libmain.so fue **42.359.988 bytes** tanto con el empaquetado previo como con el nuevo (delta 0), y tampoco variaron los recuentos ni histogramas de instrucciones. **Se descartó el cambio en el motor y el flag Android; no hay nueva ganancia FPS demostrada**. Se añadió una herramienta de análisis de símbolos ARM64 con prueba C y pruebas unitarias para futuras auditorías offline. Cierre: **257 pruebas Python (4 omitidas) y 35/35 CTest**; binario ARM64 y biblioteca empaquetada verificados idénticos por SHA-256 a referencia A, flags experimentales OFF, caché limpiada. [Informe](CPU_PHASE9_X87_INTEGER_PACK_OFFLINE_2026-10-14.md).

## Fase 8 offline: 277 conversiones x87 en 124 PCs con muestreo duplicado (OFF)

La atribución DWARF inline en **dos capturas físicas archivadas** recuperó 240 y 218 muestras de `f2d(rd(...),10)` en las cuatro funciones originales calientes de CoDSP p4. **124 PCs** con ≥2 muestras combinadas incluyen **392/458 muestras (85,6 %)** del subconjunto observado, sin confundir el muestreo con llamadas por frame. El nuevo `--x87-normal-f2d-p4-profiled` cambia **277 sitios estáticos** de esos PCs (frente a 520 de la fase 7), con hashes, reversión, opción CMake OFF y exclusión mutua entre tres perfiles experimentales p4. **22 instrucciones x87 reales / 44.000 comparaciones** R/RAM/PC Clang `-O1/-O2` idénticas. En ARM64 `libmain.so` `.text`, A **42.339.912**, B8 **42.359.988** (+20.076 bytes): **14.120 bytes de crecimiento menos** que B7, **191.356 menos** que p4 completo. Suite **253 Python (4 omitidas) y 34/34 CTest**; tras recompilar A sin flags de p4 se verificó por SHA-256 restauración exacta del C, ELF y biblioteca empaquetada. Solo compilación y firma de APK offline; **sin TECNO, sin FPS nuevos ni validación de gameplay**. La meta de 60 FPS sigue pendiente. [Informe](CPU_PHASE8_P4_PROFILE_GUIDED_X87_OFFLINE_2026-10-14.md).

## Fase 7 offline: fast path x87 restringido a cuatro cuerpos calientes de p4 (OFF)

Se redujo el experimento anterior a **520 conversiones `f2d(rd(...),10)`** en 276 PCs de 4 funciones originales calientes de CoDSP p4, elegidas mediante muestras físicas archivadas y cuerpo recuperado, con guardas SHA-256 y reversión byte a byte del C privado. Nuevo flag `--x87-normal-f2d-p4-selective`, **OFF por defecto**, excluye el flag de p4 completo y preserva la ruta original para el resto de instrucciones. **24 instrucciones genuinas / 48.000 comparaciones de estado R/RAM/PC** fueron idénticas con Clang `-O1/-O2`. `libmain.so` `.text` creció **+34.196 bytes** frente a A, en vez de **+211.432 bytes** con el p4 completo: ahorro relativo de **177.236 bytes (83,8 %)** del crecimiento previo; solamente 3 chunks nativos cambiaron, frente a 16. La suite terminó con **250 Python (4 omitidas) y 34/34 CTest**. APK solo compilada, nunca instalada; revertida la local a A con hashes idénticos y flag selectivo OFF. **No se ha demostrado ningún incremento de FPS.** [Informe](CPU_PHASE7_P4_SELECTIVE_X87_OFFLINE_2026-10-14.md).

## Fase 6 offline: ampliar x87 normal-f2d a CoDSP p4, opt-in NO aprobado (0/5)

En perfiles históricos de CPU, p4 reúne **789 muestras** de las funciones originales CoDSP calientes presentes en top-40; p1/p8 tenían 847/827 y ya reciben el helper validado en TECNO. Se añadió el flag ARM64 `--x87-normal-f2d-p4` (**OFF por defecto**), reutilizando la conversión inline bit-equivalente con guardas de hash de CoDSP 1.5. **18 instrucciones FLOAT de p4 / 36.000 oráculos completos de R, PC y RAM** coincidieron con el traductor previo en PC Clang `-O1/-O2`, pero el ejecutable nativo `.text` creció **211.432 bytes** frente a A. Un intento de helper `noinline` quedó **rechazado por una diferencia de estado con valores especiales x87** y fue revertido. Sin uso del TECNO ni FPS nuevos; no aprobar el flag hasta A/B/A físico. [Informe](CPU_PHASE6_X87_P4_OFFLINE_2026-10-14.md).

## Fase 5 offline: caché del último chunk, NO habilitada por regresiones posibles (0/5)

Reprocesados perfiles archivados sin usar ADB: `guest_run` representó 506/7.953 y 432/6.541 muestras CPU (6,36 % y 6,60 %); `dispatch_index_find` recibió 90/77 muestras, con ELF Build ID exacto comprobado. La búsqueda existente ya resuelve páginas con uno/dos chunks, que abarcan todas las páginas ocupadas de los cuatro módulos estáticos auditados (403 chunks, 560 páginas).

Se añadió un fast path opcional `CODRECOMP_DISPATCH_LAST_CACHE` (**OFF**), con validación de rango, generación por reconstrucción de índice y pruebas de carga/descarga, sin modificar reglas del juego. Un benchmark **del PC**, no de gameplay, muestra ahorro en repeticiones, pero penalización importante con alternancias y saltos aleatorios. En binario ARM64 B frente a A, `.text` **+148 bytes**, `guest_run` **+172 bytes**; ambas compilaciones firmadas, ninguna instalada. Completados **243 tests Python (4 omitidos) y 34/34 CTest**. La compilación normal volvió a OFF; **no existe ganancia de FPS demostrada**. [Informe](CPU_PHASE5_OFFLINE_DISPATCH_CACHE_2026-10-14.md).

## Fase 4: escritura arquitectónica muerta, reducción nativa pero SIN mejora de FPS

Análisis nuevo de liveness CFG inter-instrucción, conservador respecto a ramas, alias, EFLAGS/x87, RAM y salidas. Opt-in `--prune-hot-register-writes` solo CoDSP p0, OFF: elimina **427 COPY** muertas del generado; `libmain.so` `.text` baja **3.868 bytes** frente a la build A idéntica salvo p0. El TECNO ARM64 reprodujo **12.000** casos de equivalencia de seis pares reales, y pasaron 239 pruebas Python (4 omitidas), 34 CTest.

A/B/A Camp Toccoa (45 °C batería): A1/B1/A2 **25,75 / 25,70 / 21,90 FPS**; CPU/frame **37,380 / 37,475 / 43,470 ms**. B1 no mejora a A1; A2 cayó mucho con la referencia, por causas ambientales/no identificadas, y no debe utilizarse para proclamar victoria de B. Se revirtió p0 y se verificó el rebuild nativo original, APK x87 estable preservada. **60 FPS pendientes**, sin cambios a la escena. [Informe](CPU_PHASE4_ARCH_REGISTER_DCE_TECNO_2026-10-14.md).

## Fase 3 exploratoria: caché de registros CoDSP p0, sin incremento de FPS

Caché optativa por instrucción p-code `--cache-hot-registers`, sobre geometría `0x004196F0`, probada en TECNO ARM64 con toda la calidad intacta. A/B/A real (40 ventanas por corrida) **25,70 / 25,15 / 25,20 FPS** y **37,495 / 38,200 / 38,130 ms CPU/frame** (A/B/A). B no mejora; A2 se parece mucho a B1 por variabilidad/temperatura. 24 instrucciones auténticas y 49.152 diferenciales ejecutados en ARM64 frente al traductor existente, **no** Intel x86 original. Opt-in queda OFF, APK previa reinstalada con hash verificado, código generado original restaurado y recompilado. 235 tests Python (4 omisiones), 34 CTest. **60 FPS pendiente.** [Reporte](CPU_PHASE3_P0_REGISTER_CACHE_TECNO_2026-10-14.md).

## Resultado nuevo en TECNO fisico ARM64: x87 normal-f2d mejoro el gameplay (exito, 0/5)

**Datos controlados A/B/A/B**, Camp Toccoa, 40 ventanas de ~1 s por corrida: **A1 24,90 / B1 25,70 / A2 25,00 / B2 25,85 FPS mediana**. B tiene `--hot-x87-transform --x87-normal-f2d` y mantiene GL4ES y Equilibrado. Promedio B vs A: **+0,825 FPS (+3,31%)** y **1,300 ms CPU/frame menos** (38,570 → 37,270). Mejora fisica reproducida y mayor que variacion A, temperatura B incluso mayor; no alcanza 60 FPS. Ensayo `-O2` en geometria p1 no mejoro y tuvo p10 inferior (19,90), **descartado**. La APK B instalada se valido byte a byte contra respaldo; save intacto. **Contador de fallos validos: 0/5**, no modificar estrategia principal. [Informe TECNO A/B/A/B](TECNO_X87_NORMAL_F2D_GAMEPLAY_ABAB_2026-10-14.md).

## WSA: conversion normal x87 f2d medida en el juego — descartada en x86_64

A/B/A del **gameplay 3D de Camp Toccoa** con GL4ES, WSA x86_64, mismo guardado y camara: **A1 55,10 / B1 54,55 / A2 55,35 FPS medianos**, CPU/frame **17,310 / 17,765 / 17,290 ms** (20 ventanas por corrida). B es ~1,22 % mas lenta en FPS y suma ~0,465 ms CPU frente a la media A. **No hay ganancia demostrada**; `CODRECOMP_X87_NORMAL_F2D` queda OFF por defecto. APK original instalada nuevamente y binario `libmain.so` comprobado byte a byte. Es WSA, **no un intento valido en TECNO ARM64**; contador oficial **0/5**, fases vigentes intactas. [Informe](WSA_X87_NORMAL_F2D_ABA_2026-10-14.md).

## FCOM: cuatro bits de condición x87 validados, pero fast path todavía OFF

En el punto original `0x0041B986` se contrastaron **1.037 pares float32** del `FCOMP` x86 (Unicorn) con el helper experimental `codsp_fcom_pop_float32`: C0/C1/C2/C3 coincidieron en todos; corrupción deliberada del bit C0 detectada. **No** se inspeccionaron todos los bits de FSW ni pila `binary80`, TOP, excepción, control word final o equivalente completo. **No habilitar FCOM en producción** ni contar como optimización A/B. TECNO desconectado, **0/5**. [Informe](CPU_PHASE2_FCOM_CONDITION_ORACLE_2026-10-14.md).

## Fase 2: contraste limitado de un bloque x87 con Unicorn

Para las cinco instrucciones `[0x0041B960,0x0041B973)` del cuerpo caliente, Unicorn x86 y la versión compilada de `pcode2c.Gen` coincidieron en **1.024/1.024 valores finales float32, memoria observable, GPR y PC** para casos finitos controlados. Un byte de memoria alterado fue detectado. **No se comparó el estado interno binary80, excepciones ni palabras de control/status**; por tanto esta evidencia **no habilita optimizaciones de x87**. Contador TECNO **0/5**. [Informe](CPU_PHASE2_X87_WINDOW_ORACLE_2026-10-14.md).

## Fase 2: prueba independiente del prólogo x86, todavía sin rendimiento ARM64

Se comparó mediante **Unicorn x86 real** contra la versión **C compilada por `pcode2c.Gen`** el prólogo de 20 instrucciones del cuerpo caliente `0x0041B8F0`, hasta e incluyendo su primer `JE`. **1.024/1.024 casos** de entradas sintéticas compatibles sin diferencias en registros, CF/PF/ZF/SF/OF, memoria y PC; **512 saltos tomados y 512 no tomados**. Un PC incorrecto introducido artificialmente fue detectado. Hash del PE y p-code original fijado, blobs y DLL privados ignorados. **No** cubre x87, AF, la función entera ni garantiza FPS; pendiente ampliar el oráculo antes de activar fast paths. Sin hardware TECNO: **0/5**. [Informe](CPU_PHASE2_X86_PREFIX_ORACLE_2026-10-14.md).

## Diagnóstico Fase 2 posterior: candidato CPU y prueba fallida de ahorro de instrucciones

Se auditó el cuerpo original `0x0041B8F0` con p-code/Ghidra privados y sitios ARM64 reales: 553 instrucciones, 3.957 operaciones, 1.789 copias y rangos repartidos en un chunk compartido por 12 funciones. Se probó aisladamente una conversión `rd/wr`→`memcpy` para el desplazamiento de siete registros x87 de 80 bits: **20.000 casos equivalentes**, pero **29 instrucciones AArch64 en ambos núcleos** bajo Clang `-O1` y `-O2`. No cambiar el generador ni afirmar mejora por C más corto. Sin teléfono conectado no hay nuevo A/B ARM64 real; mantener 60 FPS como meta y **0/5**. [Informe fase 2](CPU_PHASE2_41B8F0_AUDIT_2026-10-14.md).

## Resultado posterior: A1/B/A2 completo en Camp Toccoa WSA, sin mejora de ANGLE (0/5)

Ensayo controlado de **gameplay 3D** con mismo save/cámara y 60-FPS host cap: **GL4ES A1 54,75**, **ANGLE/Vulkan B 55,15**, **GL4ES A2 55,20** FPS medianos (20 ventanas de ~1 segundo, 30 s/run); p10 respectivamente **50,2 / 47,6 / 54,6** FPS. CPU/frame **17,54 / 17,80 / 17,43 ms**. B solo +0,175 FPS (+0,318 %) frente a la media A, dentro de la variación A1–A2; p10 B inferior. El mismo PID confirmó ANGLE/Vulkan al inicio y al cierre de B. Imagen 3D con SSIM 0,995943 frente a GL4ES, capturas privadas no sincronizadas y no prueba exhaustiva. **Sin mejora demostrada: mantener GL4ES producción y estrategia de fases ARM64 vigente.** APK y saves idénticos tras rollback; el TECNO no estuvo conectado, por tanto **0/5 intentos válidos**. [Reporte completo](ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md).

## ANGLE: compatibilidad Vulkan confirmada en WSA, todavía sin A/B de gameplay

La fuente oficial ANGLE pinneada (`43140711d13063716fd32a15de829885d0bce469`) fue compilada en GitHub Actions Linux y el APK x86_64 pasó verificaciones de ABI, EGL/GLES, identidad, firma Android y SHA-256. La aplicación real **CallofRecomp** abrió `GameActivity` con el paquete ANGLE experimental y su propio PID reportó **Renderer Vulkan 1.3 AMD Radeon**; el menú original se mostró y no presentó diferencias visuales evidentes frente al menú nativo GL4ES. La APK experimental fue desinstalada y los ajustes revertidos. **No** se comprobó equivalencia 3D, FPS Camp Toccoa ni rendimiento ARM64/Mali. La fase CPU actual conserva prioridad: **no cambiar de renderer ni de estrategia sobre esta sola prueba**, contador **0/5**. [Informe de ejecución real](ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md).

## Resultado de investigación Mesa Zink (sin A/B del juego)

Se descargó e inspeccionó Mesa **26.2.4** y se midieron **capacidades Vulkan reales**, no FPS, en el WSA actual. Al menos cuatro requisitos obligatorios del perfil Zink GL2.1 están ausentes: `alphaToOne`, `VK_KHR_maintenance5`, `VK_KHR_swapchain_mutable_format` y `VK_EXT_border_color_swizzle`. Zink necesita un proveedor de OpenGL desktop Mesa/Gallium y un contexto Android apropiado; no se integra copiando un DLL/biblioteca sobre GL4ES. **Decisión: mantener GL4ES y no empaquetar Zink en WSA**. El TECNO Mali queda sin determinar hasta que se pueda consultar directamente. Se conserva estrategia original de perfilado CPU y contador **0/5** porque no existió A/B de gameplay. [Informe Mesa/Zink](MESA_ZINK_FEASIBILITY_2026-10-14.md).

## Hito posterior: transformaciones y proyección GL → Vulkan (sin A/B del juego)

La capa de observación tipada ahora reconoce las ocho llamadas de traslación, rotación, escala y proyección ortográfica/perspectiva, preservando el orden column-major de OpenGL y los slots dobles x86. El prototipo WSA `--scene matrix` usó el estado tipado para tres dibujos reales sobre Vulkan; validación visual y ejecución completa **75,024 FPS FIFO** (1.276 frames, 17,008 s; **no** FPS del juego ni demostración de aceleración). El renderer estable sigue siendo GL4ES; el próximo bloqueo es geometría real de vertex arrays/VBO, samplers y combiners. [Informe](WSA_GL_MATRIX_BRIDGE_2026-10-14.md). Estrategia original y contador **0/5** intactos.

## Hito de compatibilidad TexEnv y alpha test (sin A/B del juego)

El prototipo WSA implementa ahora `glTexEnv` MODULATE/REPLACE por unidad y un shader con descarte de fragmentos por prueba alfa; la captura de la escena muestra dos quads con texturas/colores correctos y huecos por alfa. **75,043 FPS FIFO** del prototipo independiente **NO equivalen al juego completo ni demuestran aceleración de CallofRecomp**. Captura del juego anterior (164 snapshots) no se repitió; el registro continúa advirtiendo estados sin traducir. [Informe](WSA_VULKAN_TEXENV_ALPHA_2026-10-14.md). Estrategia y contador 0/5 intactos.

## Diagnóstico GL→Vulkan del juego real, sin intento de optimización

Un observador optativo generado por `gen_gl.py` rastreó la partida GL4ES de WSA, entre menú y entrenamiento. El análisis de **164 muestras** encontró **0 estados declarados equivalentes en el subconjunto traducido** y máscara `0x19`: capacidades no traducidas, estado de texturas y API GL heredada. El traductor genera estructuras Vulkan válidas para depth/stencil, blending y culling, pero **no** es un renderer completo. El log es una captura de compatibilidad, no permite medir FPS nuevos ni atribuir aceleración a Vulkan. Se restauró la APK original exacta; el contador sigue en **0/5**. [Documentación y siguiente cobertura](GL_VK_STATE_BRIDGE_2026-10-14.md).

## Ejecución más reciente — diagnóstico sin consumo de intentos

[Informe de ejecución del perfil TECNO y selección de función](PERFORMANCE_STRATEGY_RUN_2026-10-14.md) — dos capturas reales de Simpleperf, ELF instalado verificado, top de geometría/visibilidad y diagnóstico ARM64 de `0x0041B8F0`. GPU hardware sigue sin contador accesible mediante ADB. La primera función para fase 2 está seleccionada, pero **no se ha habilitado optimización estructural nueva**. Fase 3 permanece pendiente. **Contador: 0/5**; el diagnóstico no constituye un experimento A/B válido.

## Modo temporal WSA y evaluación de Vulkan / DirectX 12 (2026-10-14)

El teléfono TECNO no está disponible. **Utilizar WSA `127.0.0.1:58526` exclusivamente mientras tanto**, para pruebas x86_64, diagnóstico de API, equivalencia funcional y prototipos seguros; **no extrapolar a FPS ARM64/Mali**. La meta y referencia física no cambian.

Se comprobó Vulkan 1.3 **mediante código NDK real ejecutado en WSA**, dispositivo AMD y extensión `VK_KHR_swapchain`. Posteriormente una aplicación independiente sí creó una superficie/swapchain Vulkan y presentó **1.276 frames a 75 FPS FIFO** (color sólido, NO render del juego). El control OpenGL del juego se mantuvo ~55 FPS; quitar únicamente el límite del host, sin cambiar GL4ES, dio **55,05 → 57,20 → 55,30 FPS** en A2/B/A3, sin reducir CPU/frame. La comparación real con Vulkan en el juego sigue pendiente. [Benchmarks WSA por etapas](WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md). DirectX 12 existe en Windows, no como API directa del proceso Android. **Se mantiene OpenGL/GL4ES como renderer de referencia**. Ver [auditoría de APIs y permisos GPU Mali](WSA_VULKAN_DX12_RENDERER_DECISION_2026-10-14.md).

**Contador de experimentos fallidos: 0/5, sin cambios.** Las pruebas WSA y Vulkan de capacidades no constituyen un intento válido de rendimiento en el TECNO.

**Cierre de mediciones WSA:** A1 GL4ES 55,20 FPS, B1 GL4ES sin cap 57,20, A3 GL4ES restaurado 55,30. Vulkan WSI aislado presentó ~75 FPS con color sólido; **no** es una mejora del juego. Se reinstaló la referencia A1 byte a byte y se verificó su SHA-256. Ver [informe completo](WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md). Contador oficial **0/5**, fases ARM64 sin cambios.

**Avance Vulkan de geometría:** el prototipo aislado WSA también soporta `VkGraphicsPipeline`, shaders SPIR-V y `vkCmdDrawIndexed` en malla de 4 vértices/6 índices, comprobada visualmente. 74,999 FPS de presentación FIFO 75 Hz **no representan FPS de CallofRecomp**. La fase aislada posterior ya soporta **`VkImage` texturizada RGBA8, staging y sampler/descriptor** (75,117 FPS FIFO del prototipo, no del juego); en un nuevo bloque aislado ya funcionan **depth/stencil y blending alfa**, con 5 attachments independientes, cuatro draws por frame y captura WSA validada a 75,005 FPS FIFO (no FPS del juego). Sigue **pendiente la traducción del estado OpenGL original** y toda comparación A/B/A de la partida. [Hito depth/stencil/blend](WSA_VULKAN_DEPTH_STENCIL_BLEND_2026-10-14.md). [Hito texturas](WSA_VULKAN_TEXTURE_2026-10-14.md). [Hito técnico](WSA_VULKAN_INDEXED_MESH_2026-10-14.md). Contador **0/5**.

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
