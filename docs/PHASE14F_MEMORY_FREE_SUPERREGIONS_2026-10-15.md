# Fase 14F — Superregiones CFG originales sin memoria y oráculo x86 independiente

**Fecha:** 2026-10-15 · **Repositorio:** `callofrecomp` · **Rama:** `main`

**Estado:** análisis, generador de superregiones y pruebas offline completados; **no se integra ninguna variante nativa experimental** porque no aparece un ahorro de código o accesos ARM64. No hay nueva APK ni nuevos FPS medidos.

## Actualización — Fase 15, CPU física y ROI

El ranking de superregiones de esta fase se contrastó con dos perfiles Simpleperf de TECNO del **mismo Build ID**. Ocho funciones originales seleccionadas representan ~19 % de las muestras del proceso; aun si se eliminara todo ese trabajo, la cota CPU idealizada rondaría 32 FPS, lejos de los 60. Las tres superregiones de 14F siguen correctamente **rechazadas** por tamaño/accesos ARM64 regresivos. Ahora se prioriza estudiar costos comunes de **estado y conversiones x87** sin alterar semántica. [Informe de perfil transversal](PHASE15_TECNO_CPU_PROFILE_CROSSCUTTING_2026-10-15.md).


## 1. Alcance y criterios conservadores

Se analizaron las **siete funciones originales calientes** que se habían perfilado previamente, utilizando el p-code de CoDSP.exe 1.5, el mapa Ghidra de cuerpos B v2 y el CFG independiente recuperado. Se fijaron por SHA-256 los insumos:

- CoDSP.exe PE SHA-256 `c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47`.
- p-code SHA-256 `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e`.
- mapa Ghidra B SHA-256 `f6d56b4d167df2fb66a9f18ff8624e6b48fd363eadcbd05e62fa2598cd03ab4c`.

La fase anterior había encontrado 68 bloques originales sin LOAD, STORE o referencia absoluta de datos `m` (158 instrucciones en total; máximo cinco instrucciones por bloque). La nueva herramienta `tools/recomp/cfg_superregion.py` conecta **bloques básicos originales completos** a través de las aristas CFG explícitas, no fragmentos elegidos por proximidad de direcciones.

Cada candidato exige que todos sus bloques sean enteros, sin memoria guest, sin x87, CALL, RETURN, CALLOTHER, saltos opacos, micro-CFG ambiguo ni propiedad Ghidra solapada. Solo se incluyen **aristas hacia delante**; un backedge interno invalida la región. Se respeta la fuente real de cada instrucción y cualquier salida hacia instrucciones no seleccionadas **delega al dispatcher original** con el PC preciso, sin añadir falsos fallthrough. La entrada nativa propuesta sería **solo el PC líder**: un PC interior o un salto externo a otro bloque continúa bajo el traductor anterior.

**Importante:** son *subgrafos compuestos de bloques completos*, no funciones completas. La existencia del subgrafo no demuestra que el dispatcher actual efectúe una llamada por cada bloque: los chunks generados pueden contener múltiples instrucciones x86. No reclamar una reducción de dispatch por el simple hecho de fusionar bloques.

### Resultado de descubrimiento

- **9 puntos de entrada** elegibles con al menos dos bloques y seis instrucciones originales, distribuidos entre las siete funciones calientes.
- Longitud máxima: **8 instrucciones, tres bloques**, en geometría `0x0041BAB2`.
- Segunda alternativa principal: **7 instrucciones, tres bloques** en `0x0041BC6D`.
- Alternativa de visibilidad: **7 instrucciones, dos bloques** en `0x004D78B6`.
- Las demás regiones son igual o más pequeñas. No se encontró una superregión lo bastante grande para justificar por sí sola la meta de rendimiento.

Reporte privado de descubrimiento: `.local/profiles/phase14f_strict_superregion_scan_v1.json`. No contiene bytes originales del juego ni instrucciones propietarios.

## 2. Compilación independiente y oráculo original x86

La nueva herramienta `tools/recomp/diagnostics/benchmark_cfg_superregion.py`:

1. Verifica PE, p-code y mapa oficiales por SHA-256.
2. Comprueba con Capstone el tamaño y las aristas originales de cada x86. Rechaza cualquier instrucción original con operandos de memoria, incluso una forma `LEA` no cargadora: en esta fase se prefiere un falso negativo antes que aceptar efectos sin probar.
3. Genera tres versiones C derivadas de `pcode2c.Gen`: sin caché (A), con 3 campos (B3), y con 5 (B5); todas con `entry_policy=start_only` y sin plegado de direcciones.
4. Compila los tres C como DLL host y como objetos Android NDK AArch64 `-O1` y `-O2`, manteniendo las mismas opciones.
5. Ejecuta con **Unicorn los bytes x86 originales**, no el p-code, y compara cada salida con A, B3 y B5: ocho GPR, cinco EFLAGS materializados `CF/PF/ZF/SF/OF`, **8.192 bytes completos de R**, PC exacto y ausencia de accesos a memoria guest.
6. Cuenta los destinos recorridos y **registra los dos resultados de cada salto condicional**, distinguiendo rutas realmente cubiertas de aristas estáticas no ejercitadas.

| Región | Bloques / x86 | Comprobaciones originales | Tamaño ARM64 `-O1` sin caché → 5 cachés | Loads sin caché → 5 | Stores sin caché → 5 |
| --- | --- | --- | --- | --- | --- |
| Geometría `0x0041BAB2` | 3 / 8 | **96/96** | 332 → **348 B** | 16 → 16 | 22 → **25** |
| Geometría `0x0041BC6D` | 3 / 7 | **96/96** | 224 → **240 B** | 14 → 14 | 17 → **20** |
| Visibilidad `0x004D78B6` | 2 / 7 | **96/96** | 360 → **368 B** | 16 → 16 | 22 → **25** |

Con `-O2` tampoco se identificó un candidato que reduzca conjuntamente código o accesos al estado arquitectónico. Es una medida **estática**, no de tiempo de CPU. Comparar textos sin conocer frecuencia del bloque y spills reales no demuestra FPS.

### Cobertura real de ramas

- `0x0041BAB2`: **2 caminos** y 2 salidas originales; el salto `0x0041BAC0` tomó **ambos** lados (50 / 46); el salto `0x0041BAC8` solo recorrió una dirección (46 / 0). **Cobertura incompleta**.
- `0x0041BC6D`: **1 camino**, salto `0x0041BCCE` solo por una dirección (96 / 0). **Cobertura incompleta**.
- `0x004D78B6`: **3 salidas**, los saltos `0x004D78C1` (45 / 51) y `0x004D78C9` (38 / 13) cubrieron **ambos resultados**. Esta muestra tiene cobertura completa de sus saltos condicionales observados, pero solo 96 estados y no un oráculo de ejecución de todo el juego.

**Ningún candidato pasó a producción.** La comparación con el x86 original demuestra equivalencia de estados de muestra, no una optimización.

Evidencias privadas bajo `.local/profiles/`:

- `phase14f_geom8_x86_branch_coverage_v2/summary.json`
- `phase14f_geom7_x86_branch_coverage_v2/summary.json`
- `phase14f_vis7_x86_branch_coverage_v2/summary.json`

## 3. Tests sintéticos, límites y uso

`tests/test_cfg_superregion.py` incluye el caso de un **diamante CFG auténtico de cuatro bloques completos** con dos caminos y una unión, entrada exterior a un bloque interior y salida exterior. Comprueba que el generador solo publica la entrada principal de la variante acelerada; todas las demás entradas siguen utilizando el dispatcher. También prueba rechazo de LOAD/STORE, operandos `m` de datos, x87, CALL/opaque, bucles internos, fuentes CFG no verificadas, límites de tamaño y conteo de cobertura de ramas.

Estos tests no utilizan instrucciones ni bytes propietarios. La herramienta emplea únicamente originales de CoDSP 1.5 que el usuario ya dispone legalmente en privado y **nunca escribe C derivado ni DLLs en el repositorio público**.

Ejemplo de reproducción con nuevas rutas privadas:

```powershell
python tools/recomp/diagnostics/benchmark_cfg_superregion.py --entry 0x0041B8F0 --start 0x0041BAB2 --pe ".local/private/Call of Duty Deluxe Edition/CoDSP.exe" --cases 96 --out .local/profiles/superregion_geom_nueva
```

**Validación final:** `python -m unittest discover -s tests` — **369 tests, 4 omitidos, 0 fallidos**. Compilación host y `ctest --test-dir .local/builds/build --output-on-failure` — **35/35 CTest**. El origen original de los reportes de 96 estados por superregión está fijado por SHA y es independiente de estos tests sintéticos. `py_compile` y `git diff --check` aprobaron.


## 4. Decisión

**No integrar un fast path basado en caché sobre estas superregiones**: los resultados son nulos o regresivos en las medidas ARM64 relevantes. El análisis no excluye otros bloques mayores ni algoritmos específicos de visibilidad/geometría, pero evita invertir tiempo en versiones cuyos beneficios no están fundamentados.

Próximos candidatos: recuperar regiones calientes **más grandes** con perfiles de ejecución reales y liveness por aristas; estudiar optimizaciones de algoritmo conservando equivalencia con el x86 original; explorar subgrafos *memory-pure* bajo una frontera original coherente en vez de forzar caches. Ninguna decisión de FPS hasta existir ejecución real con el TECNO en A/B.

El **contrato de recuperación de excepciones Android**, investigado en paralelo, está en [PHASE14F_ANDROID_FAULT_RECOVERY_CONTRACT_2026-10-15.md](PHASE14F_ANDROID_FAULT_RECOVERY_CONTRACT_2026-10-15.md). CFG14 continúa **OFF y BLOQUEADO**.
