# Fase 5 — auditoría offline y caché experimental del despachador (2026-10-14)

**Estado:** implementado, auditado y compilado **sin ADB ni TECNO**. La caché del último chunk queda **OFF por defecto** porque el microbenchmark demuestra regresiones bajo ciertos patrones de salto. **No hay datos nuevos de FPS del juego**, ni modificación del renderizado, la geometría, soldados, colisiones o los guardados. La meta de 60 FPS sostenidos sigue pendiente.

## Evidencia física histórica reinterpretada sin teléfono

Se reprocesaron dos perfiles Simpleperf anteriormente registrados, no se capturó nada nuevo. La herramienta reutilizable `tools/recomp/diagnostics/offline_dispatch_profile.py` verifica el Build ID almacenado en cada `perf.data` contra el ELF *unstripped* suministrado, localiza `guest_run` con `llvm-nm` y clasifica sus PCs con `llvm-addr2line` y los DWARF inlined.

| CPU task-clock histórico | Captura 1 | Captura 2 |
| --- | ---: | ---: |
| Total de muestras del proceso | 7.953 | 6.541 |
| Muestras dentro de `guest_run` | 506 | 432 |
| Parte de las muestras del proceso en `guest_run` | 6,362 % | 6,604 % |
| Muestras atribuidas a `dispatch_index_find` inlined | 90 | 77 |
| Parte de las muestras de `guest_run` atribuida a búsqueda | 17,79 % | 17,82 % |
| Muestras del proceso atribuibles a búsqueda | 1,132 % | 1,177 % |
| Muestras en `codsp_hot_transform_5061b0` inlined | 87 | 81 |

El Build ID confirmado en los **dos** archivos de muestreo y su ELF correspondiente es `80dc3884c64e395f87d7975f200d34edccf648fd`. Por ello se pueden localizar los puntos de CPU **de ese binario histórico**, pero no extrapolarlos a la APK x87+f2d actual ni al rendimiento futuro. Los porcentajes son de muestras **en usuario**, no tiempos exclusivos, 1%-low, GPU, número de llamadas ni `FPS`.

Un análisis privado de los C generados de los cuatro módulos CoDSP / cgamex86 / gamex86 / uix86 encontró **403 chunks, 560 páginas de 4 KiB ocupadas, 161 páginas con un chunk y 399 con dos; ninguna con tres o más**. Este es un inventario estático de esas fuentes, no una traza de saltos ejecutados. El buscador actual ya prueba el último chunk de cada página y su antecesor, por lo que cambiar indiscriminadamente la indexación no está justificado.

Las muestras `task-clock` almacenadas a 350 Hz mostraron símbolos de chunk iguales en muestras consecutivas filtradas solo un **5,94 % y 6,45 %** de las veces. Esta cifra **NO mide la tasa de aciertos de la caché**: los saltos del juego son órdenes de magnitud más frecuentes que el muestreo y las muestras sucesivas no representan dos iteraciones contiguas de `guest_run`.

Los informes JSON agregados y los perfiles/símbolos/PCs permanecen exclusivamente bajo `.local/profiles/`. La herramienta pública no publica trazas comerciales, rutas de archivo internas ni muestras por PC original.

## Optimización implementada, no activada

- `tools/recomp/runtime/dispatch_index.h`: introduce `dispatch_recent` para reutilizar el índice exacto del último chunk si el PC siguiente está en `[start,end)`. Revisa los límites **en cada acierto**. Si no coincide, usa exactamente el buscador anterior, sin alterar las reglas del motor.
- Cada llamada a `dispatch_index_build` incrementa una generación. Un `module_load`/`module_unload` invalida la caché anterior automáticamente. `dispatch_recent` es local a `guest_run`, por lo que ejecuciones anidadas no comparten un índice inseguro. El `dispatch_index` existente es un objeto global cero-inicializado; esa condición se documenta en la cabecera.
- `tools/recomp/runtime/guest.c` solo usa esta ruta cuando se compila con `CODRECOMP_DISPATCH_LAST_CACHE`.
- `android/CMakeLists.txt` define `CODRECOMP_DISPATCH_LAST_CACHE` con valor **OFF**. `tools/recomp/build_android.py` ofrece `--dispatch-last-cache` solo cuando se solicita explícitamente.
- `tests/dispatch_index_smoke.c` comprueba la igualdad con el buscador anterior en límites, huecos, más de dos chunks en la misma página, direcciones cercanas a `0xffffffff`, descarga y recarga de módulos, generaciones distintas y llamadas anidadas.

## Benchmarks y comparación nativa, sin TECNO

Se agregó `tests/dispatch_recent_bench.c` como binario de ejecución **manual** `codrecomp_dispatch_recent_bench`. Utiliza **403 chunks sintéticos** y 8.000.000 de consultas por corrida. No contiene activos del juego, ni es FPS. Se corrigió y volvió a ejecutar tras detectar un desbordamiento entero en el cálculo de nanosegundos; los resultados anteriores a esa corrección se descartaron.

| Patrón de PCs sintético | Índice actual, ns/consulta | Caché reciente, ns/consulta | Interpretación |
| --- | ---: | ---: | --- |
| Mismo chunk repetido | ~6,62 | ~4,28 | Caché más rápida |
| Ráfagas de 8 llamadas por chunk | ~7,91 | ~5,32 | Caché más rápida |
| Alternar entre 2 chunks | ~6,13 | ~9,82 | Caché **más lenta** |
| Saltos aleatorios entre 403 chunks | ~8,63 | ~14,59 | Caché **más lenta** |

Valores aproximados de dos ejecuciones con orden A/B/B/A en el **PC Windows**, sujetos a frecuencia CPU, compilador y distribución de entrada. **No se debe usar el beneficio en un patrón sintético para afirmar una mejora en el juego.**

Se compilaron dos APK ARM64 offline con los flags de referencia `--hot-x87-transform --x87-normal-f2d`, variando solo `--dispatch-last-cache`, firmadas correctamente V2/V3:

| Medida ARM64 | A flag OFF | B flag ON |
| --- | ---: | ---: |
| `.text` total de `libmain.so` | 42.339.912 bytes | 42.340.060 bytes |
| Símbolo `guest_run` nativo | 1.992 bytes | 2.164 bytes |

Diferencia B−A: **+148 bytes** de `.text` y **+172 bytes** en `guest_run`. Esto demuestra que la ruta llega a la compilación ARM64, pero no da información sobre su coste dinámico por frame. Ambos artefactos permanecen privados en `.local/profiles/dispatch_offline/`. El constructor se ejecutó finalmente **sin** `--dispatch-last-cache` y se verificó `CODRECOMP_DISPATCH_LAST_CACHE:BOOL=OFF` en su caché de CMake.

## Validación y siguiente bloque

El bloque completo pasó **243 pruebas Python (4 omitidas) y 34/34 pruebas CTest**. Las dos APK ARM64 se construyeron y firmaron localmente, sin instalar nada por ADB.

El nuevo diagnóstico verifica el Build ID y sus agregaciones mediante `tests/test_offline_dispatch_profile.py`. No puede sustituir a una captura nueva con el binario candidato. El smoke de `dispatch_index` contrastó el caché nuevo contra el índice actual y pasó. El benchmark devuelve resultados idénticos para todos los escenarios, independientemente de su velocidad.

**Decisión:** conservar el experimento reproducible **OFF**, sin despliegue ni instalación, porque no sabemos la tasa de reutilización real de chunks y hay penalizaciones serias cuando no se reutilizan. Cuando se pueda usar el TECNO, primero capturar una **traza o contador ligero del porcentaje de aciertos de despacho con el mismo juego/escena**, después benchmark A/B/A si justifica el cambio. Mientras tanto, seguir priorizando perfilado offline de grandes costes de CPU, sin tocar lógica gráfica ni otros fast paths previamente probados.

Ejemplos de reproducción offline:

```powershell
python -m unittest discover -s tests -p test_*.py
ctest --test-dir build --output-on-failure
cmake --build build --target codrecomp_dispatch_recent_bench
build\codrecomp_dispatch_recent_bench.exe

# A: normal; B: experimental, nunca instalar sin validación A/B física
python tools/recomp/build_android.py --abi arm64-v8a --hot-x87-transform --x87-normal-f2d --jobs 3
python tools/recomp/build_android.py --abi arm64-v8a --hot-x87-transform --x87-normal-f2d --dispatch-last-cache --jobs 3

# Perfil previamente capturado, sin ADB (con los paths privados correctos)
python tools/recomp/diagnostics/offline_dispatch_profile.py --perf <perfil.perf.data> --elf <libmain-con-simbolos.so> --ndk <directorio-NDK> --out <informe-privado.json>
```

**No confundir:** una optimización compilable, un microbenchmark aislado, una muestra histórica y una mejora real de FPS son cuatro evidencias diferentes. Solo una nueva comparación de gameplay puede aprobar el flag.
