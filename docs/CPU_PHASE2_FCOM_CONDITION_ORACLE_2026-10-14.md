# Fase 2 — Oráculo independiente de bits de condición x87 FCOMP

**Fecha:** 2026-10-14. **Resultado:** las condiciones C0/C1/C2/C3 del fast path experimental `codsp_fcom.h` coinciden con las observadas en Unicorn para un corpus limitado de operandos. **No se habilita el fast path de producción.** El objetivo TECNO continúa en **60 FPS sostenidos**, contador formal **0/5**.

## Procedimiento real

Se creó `tools/recomp/diagnostics/verify_fcom_condition_oracle.py`. Comprueba el ejecutable **CoDSP.exe privado** y el p-code Ghidra por sus hashes SHA-256 fijados, comprueba en Capstone el tamaño y mnemónico originales y, en un proceso de prueba host, sigue esta secuencia:

1. Unicorn ejecuta la instrucción x86 original **`FLD` en `0x0041B960`**, cargando el primer valor `float32` en la pila x87, con control word inicial `0x037F`.
2. Sin ejecutar el resto de la función, se invoca la instrucción x86 original **`FCOMP` en `0x0041B986`**, que compara con el segundo operando `float32` en memoria y realiza el pop. Se inspecciona su palabra de estado `FPSW`, pero se extraen **únicamente los bits C0, C1, C2 y C3** mediante la máscara `0x4700`.
3. En paralelo, una DLL de laboratorio (LLVM-MinGW) invoca el helper del proyecto `codsp_fcom_pop_float32`, con el fast path habilitado **solo en esa DLL**. Se comparan **los cuatro bits** citados con Unicorn; se rechaza discrepancia. La APK estable mantiene `CODRECOMP_X87_FCOM_FASTPATH` **OFF**.
4. Se ejecutan **13 pares especiales** (ceros con signo, igualdad, orden, infinito, NaN y subnormal) y **1.024 pares pseudoaleatorios de valores finitos**, reproducibles. Total **1.037/1.037 coincidencias de los bits de condición**.
5. **Control negativo:** se alteró intencionalmente C0 en una DLL privada, sin cambiar los fuentes reales. El verificador detectó **13/13 diferencias** en el corpus fijo.

El programa está sujeto a las mismas protecciones de los demás oráculos: el PE y p-code originales viven fuera de Git, solo admite fuentes de la versión auditada, exige salida nueva bajo `.local/profiles/` y comprueba que el macro original OFF continúe existiendo. El C y la DLL de laboratorio se conservan privados en `.local/profiles/phase2_fcom_real_flags_v1/`; la prueba negativa se conservó bajo otra ruta privada.

## Qué significa el resultado

El oráculo amplía los anteriores ensayos sintéticos `codsp_fcom_smoke`, que comparaban el helper con las operaciones del propio p-code: ahora existe un contraste **independiente contra bytes originales x86** para los **bits C0/C1/C2/C3**, no solo paridad de dos rutas de C.

Pero **no demuestra equivalencia completa de FCOMP**, por estas razones:

- **No compara el resto de FPSW**, incluidos TOP, las marcas de excepción y otras condiciones. Unicorn reportó IE sin activar en los casos observados, pero esto es **un dato de su emulación**, no prueba de que el hardware x87 real o toda entrada posible se comporte igual.
- El helper usa el formato virtual x87 del proyecto y opera sobre `double` en algunos pasos. No se cotejaron todos los registros internos `binary80` ni la semántica completa de la pila de ocho elementos tras el pop.
- La función completa `0x0041B8F0` tiene **553 instrucciones** y múltiples bloques y ramas. Los resultados de un único FCOMP no autorizan generalizar un fast path.
- No hay medición del tiempo CPU en **TECNO CK6n ARM64** ni ahorro observado en el código máquina AArch64. **0/5 intentos físicos válidos**.

Se añaden seis pruebas sintéticas offline en `tests/test_verify_fcom_condition_oracle.py`. La investigación no cambia el motor, las bibliotecas gráficas, la APK ni los guardados.

## Reproducción privada

Requiere host Windows con `unicorn`, `capstone`, `pefile` y LLVM-MinGW disponibles:

```text
python tools/recomp/diagnostics/verify_fcom_condition_oracle.py --pe ".local/private/Call of Duty Deluxe Edition/CoDSP.exe" --pcode recomp_out/codsp.pcode --compiler "RUTA/clang.exe" --output .local/profiles/fcom_nuevo_oraculo --random-cases 1024
```

**Próximo requisito antes de optimizar:** construir un oráculo que represente **el estado interno de pila x87 binary80, TOP, status/control words, banderas de excepción y NaN** en los mismos puntos de entrada/salida, y exigir después diferencias reales de instrucciones y tiempos ARM64. No habilitar FCOM en producción por la sola coincidencia de los cuatro bits.
