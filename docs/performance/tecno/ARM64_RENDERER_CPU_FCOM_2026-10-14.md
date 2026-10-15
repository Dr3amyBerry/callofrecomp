# CPU del renderizador en TECNO: auditoría GL4ES y comparaciones x87 (2026-10-14)

**Estado actualizado:** investigación con datos reales y experimento optativo **NO APROBADO PARA RENDIMIENTO SOSTENIDO**. Aunque B1 mejoró, B2 cayó fuertemente y A3 se recuperó. **No declarar 60 FPS ni mejora reproducible estable.**

## Por qué GL4ES no es el primer cuello de botella

Se reabrió el `perf.data` PRIVADO correspondiente a la APK x87 de referencia mediante el `simpleperf/report.py` del NDK 30, con `--sort dso -n --csv --percent-limit 0`. La captura real tiene 6.358 muestras de `task-clock:u` durante 18 segundos:

| Biblioteca | Muestras | % |
|---|---:|---:|
| `libmain.so` (runtime + código generado) | 5.476 | 86,13 |
| Driver `libGLES_mali.so` | 299 | 4,70 |
| `libc.so` | 250 | 3,93 |
| GL4ES `libGL.so` | 91 | 1,43 |
| Otras | 242 | 3,81 |

Son muestras de tiempo CPU user-space, **no** porcentajes de tiempo total por frame ni de carga GPU. El coste de la GPU sigue sin medirse con contadores específicos. Incluso eliminar el tiempo CPU muestreado de GL4ES+driver no reduciría los ~38 ms de CPU/frame a los 16,67 ms necesarios para 60 FPS.

El motor invoca ~103 dibujados indexados y ~31 pares Lock/Unlock por frame en una captura WSA previa, pero el temporizador GL del puente registró unos 2,64 ms/frame solo dentro de los Draw; esto es x86_64/WSA, **no** una medición directa del driver Mali. Los modos `LIBGL_BATCH=1` y `LIBGL_USEVBO=2/3` empeoraron las pruebas previas de WSA; no hay base para habilitarlos indiscriminadamente.

Referencias de proyectos examinados:
- [GL4ES/USAGE](https://github.com/ptitSeb/gl4es/blob/master/USAGE.md): modos batching y VBO; advierte que VBO 2/3 son experimentales y pueden ser más lentos.
- [GL4ES/MEDIA](https://github.com/ptitSeb/gl4es/blob/master/MEDIA.md): para motores ya optimizados tipo Quake3 el wrapper puede no mejorar frente al GLES directo.
- [ioquake3](https://github.com/ioquake/ioq3/blob/main/README.md): renderer OpenGL ES2+ nativo, pero no reemplaza sin más el CoDSP recompilado y sus dependencias de OpenGL antiguo.
- [Perfil de traducción del proyecto](../graphics/RENDER_TRANSLATION_AUDIT_2026-10-14.md) y [rendimiento ARM64](TECNO_CK6N_ARM64_PERF_2026-10-14.md).

## Nuevo objetivo: fusionar una comparación x87 completa y un pop FPU

Se correlacionaron direcciones originales x86 del perfil ARM64 con líneas del C generado y cuerpos Ghidra (datos **privados, fuera de Git**). Había 473 candidatos estructurales (234 en CoDSP p1 y 239 en p8) con operaciones p-code repetidas de `FLOAT2FLOAT`, dos `FLOAT_NAN`, `FLOAT_LESS`, `FLOAT_EQUAL`, estado C0/C1/C2/C3 y pop ST0. Se excluyeron formas de 64 bits y otros formatos no cubiertos. Los **448 bloques** de comparación `binary80` contra `binary32` que sí se verificaron por hash exacto de su cuerpo son: p1=226, p8=222.

La correlación original de los 473 candidatos con el perfil daba **305 muestras estimadas del total 5.476 de libmain** (141 p1 y 164 p8), una cota orientativa de impacto de pocas unidades porcentuales, **no** un porcentaje atribuible de FPS. No confundir muestras de instrucciones con tiempos exclusivos; el compilador puede mover líneas.

Implementación experimental:
- `tools/recomp/runtime/codsp_fcom.h`: una sola lectura binary80, una sola conversión binary32, cálculo exacto de las cuatro banderas de estado emuladas, `0x10a2`, guest PC `0x10ac` y un pop de 7 posiciones x87 de 10 bytes dejando el padding intacto. Si el flag está OFF, la macro no evalúa los parámetros ni altera la ruta original.
- `tools/recomp/patch_codsp_fcom.py`: solo p1/p8 de CoDSP 1.5, 3 hashes SHA-256 de cuerpos validados, preámbulos de direcciones estrictos, conteos exactos e idempotencia. Primero valida **ambos** archivos privados y solo luego escribe; no desplaza líneas DWARF. Solo modifica C privado ignorado.
- `python tools/recomp/build_android.py --hot-x87-transform --x87-fcom-fastpath --jobs 3`: compila la variante optativa. `CODRECOMP_X87_FCOM_FASTPATH` permanece OFF por defecto, solo habilitado en p1/p8. Sin el flag se ejecuta el p-code anterior incluso en los C privados parcheados.
- El clasificador NaN ya existente acepta la cabecera compuesta `codsp_fcom.h` **únicamente cuando valida** el conteo completo de guardas, evitando regresiones al combinar herramientas optativas.

## Validaciones y límites

- Ejecutado en TECNO CK6n ARM64: **151.638 casos diferenciales** contra la expresión de la traducción anterior, con comparación exacta byte a byte de toda la matriz de registros guest y la memoria de prueba; valores NaN, infinito, signados, ceros, subnormales y patrones no canónicos. Ninguna discrepancia.
- Suite local tras la incorporación: **103 pruebas Python correctas (4 omitidas)** y **31/31 CTest correctos**.
- La validación contrasta el runtime recompilado y no un Intel x86 independiente. Otros mapas, misiones, estados y fallos de memoria siguen sin validación completa.
- Se realizó A/B/A/B/A de FPS en el TECNO, con 40 ventanas tardías por corrida (detalles abajo). El objetivo final de 60 FPS sostenidos durante 60 ventanas y la validación de misiones/colisiones completas permanecen pendientes.

## Regla de decisión

No atribuir al cambio los FPS de menú (~53), microsintéticos ni el coste de GL4ES medido en WSA. Mantener OFF si la ganancia es inferior a la variación natural entre A1/A2 o si cualquier visual, colisión, misión o guardado falla. Registrar todos los resultados negativos sin eliminarlos.

**Meta de 60 FPS en el punto de aparición: ABIERTA.**


## A/B/A/B/A real en TECNO CK6n, Camp Toccoa (Equilibrado)

La cámara estática y el guardado original son los mismos. Se verificó por capturas que ambas APK llegan al punto de aparición con el terreno, las dos señales, NPC y HUD conservados. Cada corrida usa las **últimas 40 ventanas de ~1 segundo en gameplay**, excluyendo menú y cargas. `p10` es de **ventanas de resumen**, no de frames individuales.

| Corrida | Build | FPS mediana | p10 ventanas FPS | CPU mediana (ms/frame) | Swap mediana |
| --- | --- | ---: | ---: | ---: | ---: |
| A1 | x87 anterior, FCOM OFF | 24,90 | 23,9 | 38,590 | 2,035 |
| B1 | x87 + FCOM ON | **26,15** | **25,5** | **36,875** | **1,920** |
| A2 | x87 anterior reinstalada | 24,90 | 24,2 | 38,625 | 2,040 |
| B2 | x87 + FCOM ON, corrida posterior | **19,80** | **18,9** | **48,210** | **3,085** |
| A3 | x87 anterior reinstalada | 25,10 | 24,0 | 38,305 | 2,060 |

**Solo en B1:** +1,25 FPS (+5,02 %) y −1,715 ms CPU/frame respecto a A1. **En B2:** −5,1 FPS (−20,48 %) y +9,585 ms CPU/frame respecto a A2. A3, sin FCOM, se recuperó a 25,10 FPS / 38,305 ms. El cambio no demuestra mejora sostenible en sesiones sucesivas; las variaciones térmicas/escena/scheduler no quedaron totalmente controladas. La primera A/B/A sugería un ahorro local, **pero una segunda corrida B2 posterior contradijo su estabilidad**. No extrapolar el B1 a FPS sostenidos. No hay oráculo x86 independiente ni validación de campaña completa; **no habilitar FCOM por defecto**. No confundir ninguna corrida con 60 FPS.

Logs PRIVADOS, fuera de Git: `.local/profiles/tecno_fcom_A1_training.log`, `tecno_fcom_B_training.log`, `tecno_fcom_A2_training.log`, `tecno_fcom_B2_training.log` y `tecno_fcom_A3_training.log`; APKs `.local/profiles/tecno_renderer_fcom_A_reference.apk` y `.local/profiles/tecno_fcom_B_candidate.apk`. Comparar con `tools/recomp/analyze_frame_stats.py` y `--last 40`.

## Próximo bloque de impacto mayor

El coste CPU directo en GL4ES/Mali user-space **no** explica ~20 ms que aún hay que reducir. Priorizar eliminación de computaciones de EFLAGS innecesarias en el traductor *con análisis de vida de flags entre bloques* (comparar enfoques de [FEX-Emu](https://github.com/FEX-Emu/FEX/blob/main/FEXCore/Source/Interface/IR/Passes/RedundantFlagCalculationElimination.cpp)). Es peligroso eliminar flag writes por simple coincidencia textual; demostrar primero que no se leen en ningún sucesor o ruta de error e igualar registros/flags/RAM en un oráculo diferencial. Complementar con nuevo perfil Simpleperf después de FCOM para localizar funciones calientes que sigan consumiendo ciclos en el punto inicial.

**Conclusión: FCOM experimental OFF.** Para explicar B2 hay que reproducir con trace de frecuencia CPU, temperatura y muestreo CPU al mismo tiempo, y/o instrumentar frecuencia dinámica de invocación del guard y fallbacks. La siguiente medición final seguirá siendo 60 ventanas estables de gameplay a al menos 60 FPS; actualmente no se cumple.

## Tamaño del binario y estado térmico

Comparación con `llvm-size` del `libmain.so` ARM64 **extraído de las APK exactas**: sección `.text` referencia 41.779.524 bytes; FCOM 41.069.924 bytes, reducción de 709.600 bytes (~1,70 %). APK de referencia 49.656.636 bytes; candidata 48.939.836 bytes. Reducir tamaño **no demuestra** mejorar FPS y no aclara la regresión B2.

Tras B2, Android notificó `Thermal Status: 0`, piel ~42 °C, batería ~38 °C y CPU ~52,3 °C, sin dispositivo de refrigeración activo; una instantánea de cpu6 y cpu7 reportó 2 GHz. Estas lecturas aisladas no descartan variabilidad térmica, cambios de frecuencias durante la captura, scheduler o variación de la escena.

**Estado de cierre:** APK x87 previa restaurada en el TECNO y build local con FCOM OFF; código de la alternativa conservado únicamente como experimento para diagnósticos posteriores.
