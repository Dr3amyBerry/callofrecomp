# Fase 2 — Oráculo x87 acotado con salida `float32` exacta

**Fecha:** 2026-10-14. **Estado:** laboratorio independiente terminado para una ventana pequeña de una función caliente. **APK/renderer/guardados:** intactos. **Objetivo TECNO:** 60 FPS sostenidos, **0/5 intentos físicos válidos**.

## Experimento ejecutado

Se añadió `tools/recomp/diagnostics/verify_x87_window_oracle.py`, complementario del [oráculo del prólogo x86](CPU_PHASE2_X86_PREFIX_ORACLE_2026-10-14.md).

El ensayo lee del ejecutable **CoDSP.exe original y privado** cinco instrucciones consecutivas del cuerpo `0x0041B8F0`, con intervalo **`[0x0041B960, 0x0041B973)`**:

1. Cargar un escalar `float32` a la pila x87.
2. Restar un escalar `float32`.
3. Multiplicar por otro escalar `float32`.
4. Restar un cuarto escalar `float32`.
5. Guardar y retirar el resultado como `float32`.

La referencia utiliza **Unicorn x86** con palabra de control inicial x87 **0x037F** (modo por defecto) y los bytes reales del ejecutable. La comparación utiliza el C que produce **`pcode2c.Gen`** a partir de las cinco instrucciones Ghidra privadas, compilado como DLL independiente del host. Se compara el valor escrito en memoria **bit por bit**, así como el área de pila cercana, los cuatro operandos de memoria, los ocho registros generales y el **PC** tras la quinta instrucción.

Se ejecutaron **1.024 estados deterministas**, incluyendo ceros con signo, valores finitos sencillos y escalares `float32` pseudoaleatorios de exponentes moderados. **1.024/1.024 coincidieron exactamente** en las salidas comprobadas.

**Control negativo:** al alterar a propósito **un byte del resultado en la DLL traducida privada**, el verificador rechazó esa ejecución. El experimento demuestra que este tipo de diferencia se detecta.

## Identidad y aislamiento

- Fuente original `CoDSP.exe`: SHA-256 `c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47`.
- Fuente Ghidra `codsp.pcode`: SHA-256 `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e`.
- Se exige coincidencia de ambos hashes, imagen base 0x400000, direcciones/tamaños de los cinco x86 y mnemónicos `fld/fsub/fmul/fsub/fstp`. Los ficheros deben permanecer en las rutas privadas conocidas; las rutas de salida deben estar **fuera de Git** en `.local/profiles/`.
- Informe local: `.local/profiles/phase2_x87_5insn_verified_v1/summary.json`. El C generado y la DLL quedan en ese mismo directorio privado y **no se publican**.
- `tests/test_verify_x87_window_oracle.py` añade cinco pruebas sintéticas de forma, rechazos, generador y entradas reproducibles, sin requerir ni ejecutar archivos comerciales en GitHub Actions.
- Herramienta de diagnóstico solamente; no se introdujeron cambios en `pcode2c.py`, `recomp_rt.h`, ni rutas Android. No es un nuevo fast path activado.

Ejemplo de reproducción en Windows con compilador LLVM-MinGW y dependencias opcionales `unicorn`, `capstone`, `pefile` instaladas:

```text
python tools/recomp/diagnostics/verify_x87_window_oracle.py --pe ".local/private/Call of Duty Deluxe Edition/CoDSP.exe" --pcode recomp_out/codsp.pcode --compiler "RUTA/clang.exe" --output .local/profiles/x87_oracle_nueva --cases 1024
```

## Límites importantes

- **No** se comparan los registros internos x87 de 80 bits, palabras de estado/control final, tags, excepciones ni redondeo no predeterminado. Una salida `float32` coincidente no demuestra que se preserve **todo** el estado x87. La palabra de control inicial se fija en el emulador, pero el traductor sigue usando `double` para varias operaciones internas.
- Quedan excluidos NaN, infinitos, denormales de entrada y estados de memoria con alias inesperados. **Los 1.024 casos no son una prueba exhaustiva de IEEE-754/x87.**
- Este ensayo verifica solo **cinco instrucciones** de las **553** del cuerpo; no reproduce una llamada completa, CFG/bucles, colisiones ni transiciones del juego.
- La coincidencia del oráculo **no implica mejora** del número de instrucciones ARM64, tiempo de CPU ni FPS. Se mantiene la decisión de no introducir una caché de registros o cambios del renderer hasta obtener evidencia independiente y mediciones físicas.

**Próxima tarea:** expandir el oráculo de x87 para comparar **estado binary80 y palabra de estado** de la pila, especialmente el FCOM posterior (`0x0041B986`) y sus casos NaN/excepción; reconstruir los límites de aliasing y flujo de control del bloque. Solo tras demostrar equivalencia global de un candidato y mejora de AArch64 deberá proponerse un flag optativo OFF por defecto para el TECNO.
