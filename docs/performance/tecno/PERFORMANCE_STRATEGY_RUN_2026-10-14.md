# Ejecución de PERFORMANCE_STRATEGY_CURRENT — TECNO (2026-10-14)

**Estrategia vigente:** [PERFORMANCE_STRATEGY_CURRENT.md](../../PERFORMANCE_STRATEGY_CURRENT.md) v1.
**Meta:** 60 FPS sostenidos en el spawn del entrenamiento Camp Toccoa, TECNO CK6n ARM64, Equilibrado, sin degradar gráficos, HUD, colisiones ni partidas.
**Estado:** fase 1 CPU ejecutada y contrastada en dos capturas; perfil hardware GPU incompleto por permisos del fabricante; fase 2 objetivo identificado, **sin modificación insegura del juego**; fase 3 aún no iniciada.
**Contador de la estrategia:** **0/5**. Son diagnósticos, NO intentos válidos de optimización A/B.

## 1. Identidad de la build y escena

- `main` estable con x87 existente ON; FCOM, NaN extra y normal-f2d OFF; **no se modificó el código jugable** en esta investigación.
- Se descargó la APK instalada solamente a `.local/profiles` (archivo privado) y se extrajo `lib/arm64-v8a/libmain.so`; **Build ID** instalado y ELF local con símbolos: `80dc3884c64e395f87d7975f200d34edccf648fd` (idénticos). Esta comprobación evita mapear PCs contra binarios diferentes.
- Partida existente en la misma vista del spawn con dos carteles y NPC; controles y HUD panorámico visibles. Captura inicial tomada después de cargar la partida, con cámara estática; no es la escena concurrida ni un benchmark de toda la campaña.
- Datos CPU Simpleperf, `task-clock:u` a 350 Hz: A1 **21,94 s, 7.953 muestras y cero pérdidas**; segunda captura, hecha con la herramienta reutilizable, **6.541 muestras** durante otra ejecución de 18 s. El nuevo perfil reafirma la clasificación de funciones calientes.
- Resúmenes de FPS en otra ventana de juego, sin perfilador intrusivo: últimas 40 ventanas ~1 s: **24,70 FPS mediana**, **23,30 FPS p10 de ventanas**, **38,895 ms CPU/frame mediana**, **2,070 ms swap**. No son percentiles de frames individuales ni un A/B.

## 2. Costes de CPU observados en el TECNO

| Componente / ELF (A1) | Muestras | % de muestras del proceso | CPU ms/frame orientativos* |
| --- | ---: | ---: | ---: |
| Código principal recompilado `libmain.so` | 6.675 | 83,93 % | ~35,19 |
| `libc.so` (runtime/C) | 344 | 4,33 % | ~1,81 |
| Controlador Mali GLES CPU `libGLES_mali.so` | 326 | 4,10 % | ~1,72 |
| Puente GL4ES `libGL.so` | 144 | 1,81 % | ~0,76 |
| Restantes | 464 | 5,83 % | ~2,45 |

*Estimación estadística, NO medición por función: `muestras / 350 [Hz] / (21,9412 [s] × 24,7 [FPS]) × 1000`. Aproxima tiempo CPU user-space por frame si el FPS se mantuvo similar durante el muestreo. No representa latencia GPU, tiempo de espera ni «tiempo exclusivo» por función; el perfil de CPU y el registro de FPS se tomaron separados.

Un hilo del proceso sumó **7.352 de las 7.953 muestras** y los dos núcleos rápidos 6/7 acumularon **7.345**. El diagnóstico apunta a carga alta en un hilo, pero por sí solo no prueba que sea posible paralelizar las operaciones por frame.

| Función original CoDSP | Muestras A1 | Muestras A2 | CPU ms/frame A1 orientativos* | Área probable |
| --- | ---: | ---: | ---: | --- |
| `0x0041B8F0` | 270 | 196 | ~1,42 | Geometría/colisiones |
| `0x004196F0` | 241 | 183 | ~1,27 | Geometría |
| `0x0047BD40` | 213 | 193 | ~1,12 | Estructuras/estado |
| `0x004D94C0` | 207 | 191 | ~1,09 | Visibilidad |
| `0x004D8280` | 167 | 128 | ~0,88 | Visibilidad |
| `0x004D8420` | 151 | 125 | ~0,80 | Visibilidad |
| `0x004D6BC0` | 142 | 111 | ~0,75 | Visibilidad |

Estos conteos dependen del mapeo nativo DWARF y los cuerpos recuperados por Ghidra v2; parte de las muestras no tiene atribución única. **No sumar estas funciones como una demostración del ahorro alcanzable**, ni confundirlas con conteos de llamadas.

El presupuesto de CPU/frame a 60 FPS es **16,67 ms**; la referencia usa **38,90 ms**, brecha aproximada de **22,23 ms** antes de estudiar la GPU. Una única función de ~1,42 ms estimados no podrá resolver todo el objetivo.

## 3. GPU y temperatura: resultados y limitaciones

- El teléfono reportó `Thermal Status: 0` antes/después de la primera captura. Lecturas **HAL actuales** de CPU/GPU de aproximadamente 53,6→55,5 °C y piel ~43 °C. En la segunda captura, piel ~44–45 °C. No se observó alarma formal, pero el estado normal NO excluye variabilidad por calor.
- CPU6/CPU7 se mantuvieron típicamente entre 1,95 y 2,0 GHz (13 muestras cada ~2 s durante A1; segunda captura también alrededor de 2 GHz).
- El GPU Mali **no expone `cur_freq` al usuario de ADB** (`Permission denied`); tampoco existe `load` legible en ese sysfs.
- `perfetto --query` muestra `android.gpu.memory` y pistas de SurfaceFlinger/FrameTimeline, **pero no** `gpu.counters` ni `gpu.renderstages`. Se consiguió una traza privada de ATRACE `gfx` de 3 s (~1,65 MB); NO incluye el tiempo real de ejecución de shaders en la Mali.
- Las configuraciones avanzadas Perfetto fallaron por permisos del sistema sobre archivos de configuración y una variante por stdin alcanzó timeout. No se alteró SELinux ni se rooteó el teléfono. **GPU hardware-time: NO MEDIDO.** Si AGI con permisos adecuados se habilita, capturarlo y agregarlo aquí.
- Los ~2 ms de swap y el ~6 % de muestras CPU de GL4ES+driver **no demuestran por sí solos que la GPU esté libre**.

## 4. Fase 2: una función seleccionada y examen de ARM64 real

**Función inicial:** `CoDSP.exe 0x0041B8F0`. Se inspeccionaron las 243 direcciones ARM64 distintas que recibieron 270 muestras (mismo ELF exacto). Clasificación aproximada por opcode de la instrucción muestreada:

| Tipo de instrucción ARM64 | Muestras |
| --- | ---: |
| Movimientos y operaciones de bits | 98 |
| Loads / stores | 81 |
| Aritmética entera | 46 |
| Punto flotante | 16 |
| Saltos y llamadas | 16 |
| Otros | 13 |

Es un argumento a favor de investigar el **materializado repetido de registros virtuales y escrituras entre instrucciones** antes de otra microoptimización x87. Sin embargo, no confundir esta distribución con dependencias exactas ni tiempos exclusivos.

**Hallazgo que evita repetir trabajo:** `pcode2c.py` ya separa `guest_regs` y `guest_mem` como `restrict` cuando se conoce que son disjuntos. Añadir ese mismo atributo otra vez no es una optimización nueva. Clang `-O1` ya eliminó por completo en ARM64 las 32.704 operaciones de temporales del experimento anterior. No enviar otro cambio de C si no produce un cambio nativo medible.

La siguiente intervención de fase 2 requiere **un solo bloque de esta función**, demostrar entradas/salidas y aristas del CFG, y comparar R, U, memoria, EFLAGS, x87 y PC con el traductor anterior (e idealmente un oráculo x86) antes de intentar cachear registros. Después, comparar instrucciones ARM64, cobertura y A/B/A/B/A en el TECNO. Aún **no se ha aceptado un parche estructural para instalar**. La fase 3 de funciones nativas completas continúa supeditada a las evidencias.

## 5. Herramientas incorporadas y reproducibilidad

- `tools/recomp/capture_android_strategy.py`: comprueba **Build ID** instalado/ELF, toma Simpleperf real, registra frecuencias y telemetría; rechaza sobrescribir un perfil existente; guarda todo bajo `.local/profiles`.
- `tools/recomp/strategy_analyze_perf.py`: agrupa muestras por ELF/hilo/núcleo y resuelve PCs ARM64 hasta cuerpos Ghidra originales v2; conserva muestras sin resolver.
- `tools/recomp/strategy_profile_report.py`: combina la captura con **40 ventanas reales** de gameplay y marca las estimaciones de milisegundos como orientativas, sin declarar mejoras de FPS o cambios de estrategia.
- Los perfiles concretos y sus mapas/TSV/JSON derivados permanecen **privados e ignorados**; no se agregan APKs, partidas ni binarios comerciales a Git.

Ejemplo para siguientes sesiones, con serial del teléfono elegido explícitamente:

```powershell
python tools/recomp/capture_android_strategy.py --serial <SERIAL_ADB> --unstripped build-android-native/lib/libmain.so --duration 20 --prefix spawn_A
python tools/recomp/strategy_analyze_perf.py --perf .local/profiles/spawn_A.perf.data --elf build-android-native/lib/libmain.so --generated recomp_out --maps recomp_out --out .local/profiles/spawn_A_analysis.json
python tools/recomp/strategy_profile_report.py --analysis .local/profiles/spawn_A_analysis.json --frames .local/profiles/spawn_A_frames.log --duration <DURACION_REAL_SIMPLEPERF_S> --rate 350 --output .local/profiles/spawn_A_report.json
```

Capturar el log de `frame stats` en una corrida estacionaria y **sin** perfilador para `spawn_A_frames.log`. No comparar distintas escenas, cámaras o APKs. La duración real se toma del informe Simpleperf (no solo del parámetro solicitado).

**Registro de la política:** estas pruebas son únicamente diagnóstico de fase 1 y selección de objetivo de fase 2. **No hubo variante B ni A/B/A validado: contador permanece 0/5.** No declarar aumento de FPS, resolución de cuello GPU ni 60 FPS.

## 6. Estado de validación y seguridad

- **117 pruebas Python correctas (4 omitidas)** y **31/31 CTest aprobadas** después de incorporar las herramientas.
- El profiler reutilizable completó una captura física con verificación automática del Build ID; el analizador reutilizable también reprodujo los puntos calientes en la segunda captura.
- Sin modificaciones de archivos de la campaña, HUD, guardados, compilación, ni APK instalada. No se habilitó FCOM, normal-f2d ni nuevos fast paths.
- El objetivo 60 FPS **no** se ha cumplido; queda por implementar y validar un cambio estructural real antes de consumir el primer intento de la política.
