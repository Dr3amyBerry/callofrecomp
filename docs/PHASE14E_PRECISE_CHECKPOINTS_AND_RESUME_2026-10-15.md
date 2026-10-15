# Fase 14E — Checkpoints x86 precisos, fallback original y coste ARM64

**Fecha:** 2026-10-15 · **Repositorio:** `callofrecomp` · **Rama:** `main`

**Estado: PROTOTIPO OFFLINE VERIFICADO; NO IMPLEMENTADO COMO RECUPERACIÓN ANDROID.** El flag `CODRECOMP_CFG14_GEOM_REGION` permanece **bloqueado** tanto en CMake como en `build_android.py`. No se ha instalado ninguna APK experimental ni se han medido FPS nuevos.

## 1. Hallazgo y solución

El bloque de geometría original `0x0041C017` (29 instrucciones) contiene **24 accesos a RAM invitada**, incluyendo 16 p-code LOAD, 6 STORE y 2 lecturas directas absolutas desde varnodes `m` (`0x0041C044` y `0x0041C05A`). Una excepción puede ocurrir en cualquiera. La versión anterior tenía **15 de 18** fronteras de fallo con R/PC divergente por escrituras x86 retenidas en la caché, pese a aprobar las ejecuciones normales.

Se añadió al generador independiente `tools/recomp/cfg_region_lab.py` el modo optativo `fault_policy="checkpoint"`:

1. `may_fault_guest_memory` identifica LOAD/STORE **y también accesos de datos absolutos en `m`**, distinguiéndolos de targets de control `m` de BRANCH/CBRANCH.
2. Al comenzar cada **instrucción x86 con acceso guest a memoria**, el código vuelca al estado arquitectónico R **únicamente los registros modificados desde el checkpoint anterior** y escribe `PC=pc` de esa instrucción original. La memoria previamente escrita permanece comprometida.
3. En `0x0041C073`, el p-code de `xor ecx,[esp+0x4c]` adelantaba dos limpiezas de CF/OF antes de leer el operando. El modo seguro retrasa esos dos COPY de constantes cero **hasta después del LOAD**, para que si la lectura falla se conserven las banderas originales. Cualquier otro write arquitectónico previo al acceso, STORE previo a otro posible fallo dentro de la misma instrucción, dependencia de flags, o reordenamiento sobre un salto micro-CFG provoca `CFGError` y se rechaza.
4. Los cálculos entre instrucciones con memoria siguen utilizando la caché. La salida conserva el volcado habitual a R y el salto al epílogo original `0x00523CD9`.

**Contrato de recuperación del ensayo:** a la falta de memoria, `R` y `PC` reflejan exactamente el estado x86 anterior a la instrucción fallida. Una vez resuelto el fallo, se retoma en **ese PC original con el traductor A (sin caché)**, nunca desde el líder `0x0041C017`. Así no vuelven a ejecutarse los STORE de las instrucciones anteriores.

**Esto todavía no implementa un manejador real de señales o excepciones Android.** El `setjmp/longjmp` usado por el verificador solo intercepta la memoria en DLL privadas de laboratorio. La función `guest_run` y las fuentes de la APK **no se han modificado**.

## 2. Evidencia independiente: x86 original, memoria exacta y reentrada

Original legal CoDSP.exe 1.5 y p-code + mapa Ghidra B verificados por SHA-256; Unicorn x86 ejecuta los **bytes originales**. Memoria invitada mapeada exacta de **24 MiB**, 5 escenarios de alias de objetos, tablas y pila.

| Ensayo | Verificaciones | Resultado |
| --- | ---: | --- |
| Primeras páginas desmapeadas con checkpoint | 18 | **18/18 correctos**, frente a 3/18 antes |
| Desmapear realmente la página al entrar a **cada instrucción con acceso RAM** y verificar su estado | 24 | **24/24**, incluidos R completo, GPR, flags, PC, RAM y orden de accesos |
| Cinco escenarios, reanudar con **Unicorn x86 original** desde cada uno de los 24 PC fallidos | 120 | **120/120**, mismo RAM final, 8 GPR, 5 flags y acceso guest |
| Cinco escenarios, reanudar con **traductor A original de `pcode2c.Gen`**, política `all_entries` sin caché | 120 | **120/120**, igual PC, R completo y RAM que x86 original |
| Ejecutar sin excepciones el helper con checkpoint vs original x86 | 40 | **40/40** |
| Salida original de helper privado con `fault_policy="legacy"` | SHA-256 | **Byte a byte idéntica** a `dfd2655e497bbf8fa83ad434244f6a33d1afcccca5308bd413c523919cd19899` |

En cada falta de página, el verificador observa **los 8.192 bytes R completos**, RAM invitada afectada por las instrucciones anteriores, registros y PC. Compara la dirección y el orden de todos los accesos ya realizados. Tras mapear de nuevo la página, reinicia solo la instrucción fallida y compara el resultado final contra una ejecución x86 original ininterrumpida. En este bloque existen **6 guest STORE**: la **secuencia y cantidad de escrituras coinciden y cada una se ejecuta una sola vez**, no se repite el prefijo ya comprometido.

Se reconstruyen únicamente **CF/PF/ZF/SF/OF** para reanudar en el x86 simulado. No se inventa estado AF, TF, DF ni x87. Los cinco escenarios comprueban alias de memoria conocidos, no todas las direcciones de 32 bits.

Evidencia privada ignorada en Git:

- `.local/profiles/phase14e_checkpoint_faults_3seed_firstpages_v2/summary.json`
- `.local/profiles/phase14e_checkpoint_all_memory_dirty_1seed_v2/summary.json`
- `.local/profiles/phase14e_exact_fault_restart_with_A_5cases_v2/summary.json`
- `.local/profiles/phase14e_checkpoint_normal_and_ndk_dirty40_v2/summary.json`

## 3. Coste ARM64 de la seguridad (solo estático)

Objetos del mismo helper, Android NDK Clang `-O1` y FP estricto:

| Variante | ARM64 `.text` | Cargas | Escrituras |
| --- | ---: | ---: | ---: |
| Caché original sin checkpoints (insegura ante fallos) | **404 B** | 32 | 22 |
| Checkpoint ingenuo: volcar siempre cinco registros | 820 B | 33 | 143 |
| **Checkpoint con registro sucio incremental** | **652 B** | 32 | 62 |

La versión incremental elimina **81 escrituras y 168 bytes** frente al checkpoint ingenuo. Sin embargo, todavía añade **248 bytes y 40 escrituras** frente a la versión original *insegura*. **No es una medida de ejecución dinámica, consumo de CPU ni FPS**, por tanto no se activa.

## 4. Alternativa sin memoria guest

En las siete funciones calientes originales analizadas, se filtraron **68 bloques** sin LOAD/STORE ni operandos `m` usados como RAM (158 instrucciones originales en total). El bloque más largo encontrado contiene **5 instrucciones**. Dos muestras se compilaron de forma aislada a ARM64 con caché de 3 y 5 campos:

| Región | Pruebas A/B host | Objetos A y B: bytes/cargas/escrituras |
| --- | --- | --- |
| Geometría `0x0041BAB6`, cinco instrucciones | **120/120** por variante | **272 B / 15 / 17**, sin cambio |
| Visibilidad `0x004D6FD0`, cinco instrucciones | **120/120** por variante | **268 B / 16 / 17**, sin cambio |

Estos bloques cortos no muestran ganancias de calidad estática: el compilador parece eliminar ya las redundancias. **No se presume que su integración mejore los FPS.** La siguiente investigación útil es encontrar *superregiones* de varias ramas originales sin accesos guest RAM y con liveness y entradas/salidas controladas, antes de ampliar el mecanismo de caché.

## 5. Qué se ha modificado y qué sigue pendiente

Herramientas y pruebas públicas:

- `tools/recomp/cfg_region_lab.py`: política `checkpoint`, detección de memoria directa, CF/OF diferidos y flush incremental conservador.
- `tools/recomp/diagnostics/audit_cfg_region_fault_state.py`: nuevas opciones `--candidate checkpoint` y `--all-memory-ops`; páginas desmapeadas en el PC x86 original, R completo, RAM comprometida y prefijo de accesos.
- `tools/recomp/diagnostics/verify_cfg_fault_restart_unicorn.py`: oráculo de reanudación **con Unicorn x86 original y con el verdadero traductor A original**; exige PC interior y no repetir STORE.
- `tests/test_cfg_exception_checkpoint.py`: pruebas sintéticas de atomicidad de memoria, bandera prematura, escrituras parciales, micro-CFG, campos sucios y reconstrucción de flags/registros.

**No se cambió `android/CMakeLists.txt`, el constructor Android, el dispatcher ni el renderizador.** Ambas barreras que bloquean `CODRECOMP_CFG14_GEOM_REGION` siguen activas: el experimento de laboratorio no sustituye el helper privado pinneado por SHA ni implementa recuperación real del SO.

### Reproducción

Con el PE original privado, p-code original y mapa Ghidra B válidos:

```powershell
python tools/recomp/diagnostics/audit_cfg_region_fault_state.py --pe ".local/private/Call of Duty Deluxe Edition/CoDSP.exe" --candidate checkpoint --all-memory-ops --cases 3 --require-safe --out .local/profiles/mi_prueba_checkpoints
python tools/recomp/diagnostics/verify_cfg_fault_restart_unicorn.py --pe ".local/private/Call of Duty Deluxe Edition/CoDSP.exe" --cases 5 --out .local/profiles/mi_prueba_reentrada
```

Siempre usar carpetas nuevas **ignoradas en Git**; las DLL, la fuente C derivada y el ejecutable original no forman parte del repositorio.

**Validación final del repositorio:** `python -m unittest discover -s tests` ejecutó **355 pruebas, 4 omitidas, 0 fallidas**. La compilación host y `ctest --test-dir .local/builds/build --output-on-failure` aprobó **35/35 CTest**. `git diff --check` y `py_compile` de las herramientas actualizadas no reportaron errores. Las pruebas originales x86 de 120/120 y la comparación del helper C fueron independientes de la suite sintética.

## 6. Decisión y próxima prioridad

1. **Mantener el flag del juego BLOQUEADO.** No hay handler Android de excepciones ni señal segura que devuelva el control al dispatcher real. Tampoco se han modelado toda la memoria de 4 GiB, posibles accesos cruzando páginas, permisos, threading, x87, AF/DF ni interrupciones asíncronas entre checkpoints.
2. Si se integra recuperación real, comprobar también OS signal/SEH, guest stack, estado al fallo, reentrada en el **PC interior con traductor A** y que los efectos ya comprometidos nunca se repitan.
3. Reanalizar la calidad de código y medir el coste real de las barreras. El bloque tiene **24 instrucciones con memoria en solo 29 instrucciones**, por lo que probablemente sea poco atractivo para optimizar con caché extensa.
4. Priorizar superregiones sin accesos RAM invitada si ofrecen suficiente longitud y equivalencia completa del CFG. Solo después de construir un APK seguro y disponer de un TECNO ARM64, ejecutar A/B/A/B de ms de CPU/frame a idénticos gráficos.

**Objetivo de 60 FPS: pendiente. No hay nuevo aumento de FPS demostrado.**
