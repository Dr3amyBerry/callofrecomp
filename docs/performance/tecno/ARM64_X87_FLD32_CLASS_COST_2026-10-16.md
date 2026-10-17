# ARM64 — coste dinámico por clase de binary32 en FLD32 (2026-10-16)

**Resultado:** instrumento offline mejorado y publicado; experimento especial de cero/infinito **rechazado y revertido**. No se cambia `libmain.so`, `recomp_rt.h`, `x87_fld32_normal.h`, CMake, opciones de build ni la calidad de juego. **Sin TECNO, nuevas APK o FPS reales.**

## Problema

Los perfiles físicos históricos de TECNO identifican instrucciones guest x87 muy frecuentes en regiones de geometría/visibilidad, pero no separan los ciclos reales de cada microoperación. El p-code original de CoDSP 1.5 (SHA `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e`) tiene **16.318** conversiones `FLOAT2FLOAT` de 4 a 10 bytes, no necesariamente ejecutadas por frame. No es legítimo extrapolar este número a ciclos o FPS.

Se auditó con **Android NDK 30 AArch64 y Unicorn**, reutilizando `tools/recomp/diagnostics/verify_arm64_x87_fld32.py`, que emite el mismo FLD m32 + movimientos x87 y compara estado completo de R (8192 bytes, incluido padding), guest PC, memoria, FPCR/FPSR y 16 casos de LOAD guest sin mapear.

## Prueba de una ruta adicional exacta para cero e infinito

Hipótesis: para bits IEEE754 `0x00000000`, `0x80000000`, `0x7f800000`, `0xff800000` es posible construir `binary80` exacto sin convertir primero a double. La versión provisional dejaba intacta la vía normal y el fallback original para subnormales, qNaN y sNaN; se activaba solo con macro experimental en el **harness privado**, sin commits.

Se repitieron dos ejecuciones con **las mismas 512 entradas sintéticas** y comprobación del estado R/FP/PC/RAM. Las cifras son **instrucciones AArch64 dinámicas por invocación bajo Unicorn**, no latencias ni ciclos:

| Tipo de entrada | Casos | Referencia original | Helper vigente normal-only | Variante cero/Inf |
| --- | ---: | ---: | ---: | ---: |
| Normal finito | 498 | 55 | 52 | 52 |
| Cero con signo | 2 | 49 | 54 | 53 |
| Subnormal | 4 | 55 | 60 | 65 |
| ±Infinito | 2 | 54 | 59 | 53 |
| qNaN/sNaN | 6 | 54 | 59 | 64 |

**Balance de la variante contra el helper vigente en estas entradas:** `−2 −12 +20 +30 = +36` instrucciones dinámicas; un resultado **peor**, no una aceleración. El baseline AArch64 normal-only siguió siendo 3 instrucciones menor por normal frente a la conversión original, pero la selección sintética contiene deliberadamente 498 normales de 512 y **no representa la distribución real de gameplay**. Las muestras de NaN y subnormales también son limitadas: este resultado es motivo para descartar la extensión, no prueba de rendimiento físico.

Identidad de los ELF Unicorn:
- Normal-only: SHA-256 `1873a17f25306a72c70fa6e64ff1391c999946377c52a3345e9bf1e01b881fe1`.
- Extensión cero/Inf provisional: SHA-256 `bc2fb487aab3e4b1ad58bb6b27115b03910bac56186bf27b5c70f5e9c98fd021`.
- El archivo sintético FLD32 usado en ambos ensayos tiene SHA-256 `5a97be4c63c8289926d8c55232f1d9f28dc8f4ba70487a6af7b2cfed00e71a1c`. A/B solo varían en definición de macro durante compilación. Se aplicó y deshizo la modificación en el header local antes del cierre; **no queda fuente experimental activa**.

## Segundo descarte: copiar directamente los registros x87

Se compiló una prueba AArch64 `-O1/-O2` con `wr(R+off,10,rd(R+off2,10))`, `memcpy(...,10)` y `memmove(...,10)` para offsets x87 separados por 16 bytes, otros offsets y un bloque de siete movimientos. El compilador produjo exactamente **20 bytes** para las copias individuales alineadas, **24** para desplazamientos desalineados y **116 bytes** para el bloque de siete, **sin diferencias entre los tres métodos** ni entre O1/O2. No se integró una sustitución: no hay ahorro nativo demostrado y una semántica de overlap incorrecta podría introducir regresiones.

## Mejora implementada y comprobable

Se amplió `tools/recomp/diagnostics/verify_arm64_x87_fld32.py` para:
- clasificar **normal, signed_zero, subnormal, infinity y nan** usando solo los bits IEEE754, preservando los signos;
- registrar para cada clase cantidad exacta de casos, mediana/min/max en referencia y candidata, sumas reales de instrucciones Unicorn para todo el conjunto y delta neto de las muestras (los histogramas individuales siguen acotados a 512 ejemplos);
- continuar verificando exactamente los estados R, guest PC/RAM, FPCR/FPSR, padding y fallos anteriores.

Se añadieron pruebas públicas `tests/test_arm64_fld32_class_telemetry.py` para todos los límites de exponentes, ±cero, ±infinito, subnormales y NaNs, invariancia ante bit de signo y rechazo de entradas fuera de 32 bits. La herramienta sigue siendo read-only y escribe sus artefactos solo en una carpeta `.local/profiles/runs`.

**Reproducción del modo normal en el PC autorizado**:
```text
python tools/recomp/diagnostics/verify_arm64_x87_fld32.py --llvm-bin <ruta-NDK-LLVM> --out <subcarpeta-nueva-bajo-.local/profiles/runs> --cases 512
```

El código de la variante provisional queda solo como investigación histórica; **el CLI público no ofrece la opción descartada**.

## Evidencia y siguiente paso

Evidencia privada con JSON, source sintético, disassembly y ELF:
`.local/profiles/runs/tecno/2026-10-17/arm64-exact-x87-copy-probe/20261017T020717Z-20264-00/`

`scripts/x87_copy_probe.c`, `scripts/x87_op_inventory.py`, `reports/copy_static_probe.json`, `reports/fld32_byclass_final/result.json`, `reports/fld32_baseline_classes/result.json`, `reports/fld32_zero_inf_classes/result.json`.

**Regresiones completadas:** `python -m unittest discover -s tests` ejecutó **556 pruebas, 6 omitidas, 0 fallos** (113,05 s). `ctest --test-dir .local/builds/build --output-on-failure` aprobó **40/40** (155,76 s). Catálogo: **140 documentos, sin enlaces rotos**. Auditoría privada: cero rutas de binarios, fuentes comerciales o partidas rastreadas; permanece únicamente la advertencia conocida de sintaxis en un script histórico no ejecutado. `git diff --check` y `py_compile` sin errores. La compilación AArch64/Unicorn nueva de 512 entradas y 16 fallos de LOAD fue aprobada; no se compiló ni instaló otra APK.

**CI pública:** se registra después del push del commit; los tests locales no deben presentarse como verificación de GitHub Actions hasta que termine.

Próxima optimización: diseñar un candidato que ahorre **instrucciones dinámicas en la ruta normal predominante** y demuestre equivalencia contra x86 original (incluidos binary80, flags, RAM y excepciones). Sin datos de frecuencia real de entrada o mediciones físicas TECNO no se debe activar FLD32 ni atribuir aumento de FPS.
