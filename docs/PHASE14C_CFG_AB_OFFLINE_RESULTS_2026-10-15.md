# Fase 14C — Resultados A/B de regiones originales, offline (2026-10-15)

**Estado: PROTOTIPO OFFLINE VERIFICADO; NO INTEGRADO EN EL JUEGO.** No se modificaron el motor, `pcode2c.py`, CMake, Android, la APK, los gráficos ni el TECNO. Ningún ahorro nuevo de FPS o de ms CPU/frame queda demostrado.

## Hallazgos y alcance

Partiendo de siete funciones calientes Ghidra B del ejecutable CoDSP 1.5, se detectaron **227 bloques básicos / 855 instrucciones x86 originales / 4.469 operaciones p-code** cuya traducción no requiere x87 ni CALL, RETURN, CALLOTHER, BRANCHIND o p-code ausente. El filtro conservador también impide usar el estado de la FPU (`R+0x1000…0x11ff`) y divisiones que pueden generar excepciones. Los bloques con guest LOAD y STORE requieren preservar estrictamente orden y alias; **no son automáticamente elegibles para la producción**.

| Función | Bloques | Instrucciones |
| --- | ---: | ---: |
| `0x0041B8F0` geometría | 34 | 156 |
| `0x004196F0` geometría | 18 | 58 |
| `0x0047BD40` recorrido | 48 | 227 |
| `0x004D8280` visibilidad | 17 | 63 |
| `0x004D94C0` visibilidad | 15 | 53 |
| `0x004D8420` visibilidad | 42 | 143 |
| `0x004D6BC0` visibilidad | 53 | 155 |
| **Total** | **227** | **855** |

**Implementado:** `tools/recomp/cfg_region_lab.py` genera desde el mismo `pcode2c.Gen` dos variantes privadas de un bloque CFG completo: original A y caché de registros R disjuntos B. La variante B carga los valores a la entrada, retiene las vistas exactas sin solapamientos y **vuelca R en cada salida**, sin reordenar ni fusionar LOAD/STORE. Conserva el PC invitado. `tools/recomp/diagnostics/benchmark_cfg_region.py` prueba el diferencial del C con LLVM-MinGW y compila ambas variantes a AArch64 Android NDK Clang -O1, FP estricto, para comparar el código nativo.

**Dos políticas de entrada:**

- `all_entries`: recarga campos desde R ante cualquier entrada de PC interior, preservando todos los PC de la región de forma autocontenida. Correcto en las pruebas A/B, pero suele **agrandar** el ARM64.
- `start_only`: un camino rápido para **solo el líder del bloque**; cualquier entrada interior se delega, **en el simulador de dispatcher host**, a la versión original. El dispatcher real Android **NO** contiene aún este mecanismo. La comparación demuestra un ahorro estático de código sobre el camino rápido, sin demostrar que ese camino se ejecute con frecuencia en juego real.

## A/B ARM64 nativo y diferencia completa de estado en host

Las cifras siguientes son **instrucciones/bytes ESTÁTICOS de objetos ARM64**, obtenidos con llvm-size y llvm-objdump; **no** son instrucciones ejecutadas ni rendimiento de un dispositivo.

| Bloque start_only | Instrucciones x86 | Caché R | A→B .text | A→B cargas | A→B escrituras |
| --- | ---: | ---: | ---: | ---: | ---: |
| Geometría `0x0041C017` | 29 (97 ops) | 5 campos | **976→804 B (−172; −17,6 %)** | **51→40 (−11)** | **48→31 (−17)** |
| Recorrido `0x0047BD40` | 15 (53 ops) | 4 campos | **648→616 B (−32; −4,9 %)** | **39→31 (−8)** | **37→33 (−4)** |

**Validez de la comparación A/B host:** por cada PC de cada bloque, se compararon los **8.192 bytes de R**, los **65.536 bytes de memoria simulada** y el PC resultante usando múltiples semillas. Geometría: **696/696 casos iguales** (24 camino rápido y 672 delegados). Recorrido: **360/360 casos iguales** (24 camino rápido y 336 delegados). Se añadieron **96 casos fast-path anteriores por cada bloque**, también iguales. El laboratorio usa RAM plegada de 64 KiB para evitar reservar 4 GiB; **esto no representa todos los alias de memoria real del juego ni equivale a un oráculo x86 independiente**. Los casos delegados usan literalmente el traductor A; la igualdad de los mismos es esperada, no evidencia de velocidad.

Se compiló y ejecutó un control negativo **real**, retirando deliberadamente el volcado `wr(R+0x10,4,reg_10_4)` de una DLL privada B. El verificador rechazó el estado incorrecto; **un volcado de registro perdido se detecta**.

### Alternativas rechazadas por regresión

| Bloque | Política/variante | Cambio estático frente a A |
| --- | --- | --- |
| Geometría de 29 instrucciones | Todas las entradas; 2 registros R | **+240 B** .text, **+26** cargas, −10 escrituras |
| Geometría de 29 instrucciones | Todas las entradas; 4 campos R | **+328 B**, **+45** cargas, −17 escrituras |
| Geometría de 29 instrucciones | Todas las entradas; 5 campos R | **+324 B**, **+58** cargas, −18 escrituras |
| Recorrido de 15 instrucciones | Todas las entradas; 2/4 campos | **+64/+132 B**, **+18/+31** cargas |
| Recorrido `0x0047C052` (10 instrucciones) | Todas las entradas, 4 campos | −16 B, pero **+10** cargas |
| Visibilidad `0x004D8420` (10 instrucciones) | Todas las entradas, 2 campos | **+20 B**, **+9** cargas |

Todas las variantes descartadas pasaron igualdad A/B host para los PC y estados simulados probados; **igualdad no implica reducción de coste nativo**.

## Trazabilidad y reproducción

Las herramientas públicas añadidas son exclusivamente un **laboratorio desligado del motor**. Todo C derivado de CoDSP, DLL host, objeto AArch64, registro de semillas y resultados detallados permanece ignorado bajo `.local/profiles/`. Ningún código GPL externo se vendorizó.

`tests/test_cfg_region_lab.py` valida entradas arbitrarias, branches, flush en salida, fallback simulado, rechazo de metadata x87, CALLOTHER, saltos extraños, vistas R solapadas, división potencialmente excepcional y una mutación negativa de memoria.

Reproducir, desde la raíz de la copia legítima con Ghidra B y p-code pinneados por SHA:

```powershell
python tools/recomp/diagnostics/benchmark_cfg_region.py --entry 0x0041B8F0 --block 0x0041C017 --cache-count 5 --seeds 24 --entry-policy start_only --output .local/profiles/phase14c_geom_new
python tools/recomp/diagnostics/benchmark_cfg_region.py --entry 0x0047BD40 --block 0x0047BD40 --cache-count 4 --seeds 24 --entry-policy start_only --output .local/profiles/phase14c_walk_new
```

Cada salida debe usar una carpeta **nueva**; las herramientas no sobrescriben evidencia anterior.

**Validación del repositorio VERIFICADA:** **325 pruebas Python** ejecutadas, 4 omitidas, ninguna fallida; compilación host correcta y **35/35 CTest** aprobados. Además de pruebas del generador, el laboratorio original produjo dos objetos ARM64 A/B para cada comparación y control negativo de flush de registro.

## Decisión y próxima etapa

**14C OFFLINE ha producido una arquitectura candidata, pero la fase 14C para producción sigue INCOMPLETA.** No integrar aún el fast path con un flag Android, ni usar lo anterior para afirmar mejoras de FPS. El camino recomendable:

1. Crear un **oráculo Unicorn x86 independiente** del bloque entero `0x0041C017` con RAM/alias representativos, flags, entradas/salidas y el salto final al epílogo de cookie `0x00523CD9`.
2. Diseñar y demostrar la integración del **guardia por PC líder** en el dispatcher original: cualquier PC interior continúa por el recompilador previo, sin trampas ni carga de registros incorrecta. Desactivar por defecto.
3. Validar en ARM64 el módulo real y medir después CPU ms/frame en el TECNO con A/B/A/B a idéntica configuración gráfica antes de habilitarlo.

**Límites formales:** solo se compararon estados de la traducción A/B sobre RAM simulada, no se validó independencia frente a x86 original de los 29/15 caminos completos; tampoco tráfico dinámico o perfiles de CPU del dispositivo. La arquitectura no es apta todavía para entregar como optimización productiva.
