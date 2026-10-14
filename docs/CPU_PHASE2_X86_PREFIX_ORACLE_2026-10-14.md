# Fase 2 — Oráculo diferencial x86 real para el prólogo de `0x0041B8F0`

**Fecha:** 2026-10-14. **Estado:** implementado y probado en el host Windows (no en la APK). **Decisión:** conservar el recompilador y la compilación ARM64 de producción sin cambios. **Contador formal TECNO: 0/5.**

## Qué se verificó

Se desarrolló `tools/recomp/diagnostics/verify_x86_prefix_oracle.py` para ejecutar, de manera **independiente**, el tramo de la función original CoDSP `0x0041B8F0` que comprende las primeras **20 instrucciones x86**, direcciones `[0x0041B8F0, 0x0041B941)`.

No se trata de dos implementaciones que utilicen el mismo p-code como referencia:

- **A / referencia independiente:** Unicorn en modo **x86 de 32 bits** ejecuta los **bytes auténticos del ejecutable privado** aportado por el usuario, con estado y páginas de RAM sintéticas y controladas.
- **B / traducción existente:** se toman las operaciones Ghidra p-code privadas del mismo tramo, se pasan por el **`pcode2c.Gen` real del proyecto**, se compila el C generado a DLL de host con LLVM-MinGW y se ejecuta exactamente una vez por caso.
- Cada corrida compara **EAX, ECX, EDX, EBX, ESP, EBP, ESI, EDI**, los indicadores modelados **CF, PF, ZF, SF y OF**, todos los bytes de tres regiones observadas (pila, datos referenciados desde ECX y dato estático) y el **PC** de salida de ambas rutas del primer salto condicional.
- **Casos de prueba:** **1.024** estados de entrada reproducibles y distintos; **512** hacen que el salto `JE` vaya a `0x0041BCE0` y **512** continúan en `0x0041B941`. **1.024/1.024 pasaron**, con coincidencia exacta de todas las salidas comparadas. No se omiten casos fallidos ni se declara tolerancia numérica.

**Prueba negativa adicional:** se generó una **DLL privada manipulada intencionalmente** cambiando la dirección de continuación del salto. El comparador la rechazó por **diferencia de PC**. Esto comprueba que el oráculo detecta al menos esa clase concreta de alteración (no garantiza detectar cualquier fallo arbitrario).

## Identidad y seguridad del ensayo

- `CoDSP.exe` original: SHA-256 `c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47`.
- `codsp.pcode` generado por Ghidra, privado: SHA-256 `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e`.
- Ambos hashes deben coincidir **antes de compilar o ejecutar**; también se cotejan imagen base PE, límites, tamaño de instrucciones, decodificación Capstone y el destino del salto original con el p-code. Se rechazan instrucciones desconocidas y transferencias no previstas.
- Se exige PE bajo `.local/private/`, p-code bajo `recomp_out/` y **salida nueva** bajo `.local/profiles/`, directorio ignorado por Git. La DLL, el C derivado del juego, los bytes del ejecutable, los datos de entrada y los perfiles nunca se publican.
- `tests/test_verify_x86_prefix_oracle.py` incorpora **7 pruebas sintéticas offline**; estas no dependen del ejecutable comercial ni de Unicorn, Capstone o del compilador.
- Las ejecuciones locales verificadas se guardan en `.local/profiles/phase2_real_prefix_oracle_v4/summary.json` (informe); los scripts de reproducción y la prueba de inyección de fallo permanecen igualmente en `.local/profiles/`.
- No se abrió ni modificó la APK del juego, ni se cambió el renderer, los guardados, WSA, el p-code privado o el binario fuente.

## Reproducción (requiere los archivos privados compatibles)

En un host Windows con Python, `pip` (dependencias instaladas previamente: `unicorn`, `capstone`, `pefile`) y compilador LLVM-MinGW `clang`, ejecutar desde la raíz del repositorio:

```text
python tools/recomp/diagnostics/verify_x86_prefix_oracle.py --pe ".local/private/Call of Duty Deluxe Edition/CoDSP.exe" --pcode recomp_out/codsp.pcode --compiler "RUTA/clang.exe" --output .local/profiles/phase2_differential_nueva --cases 1024
```

La ruta `--output` no debe existir. El proceso produce `translated_private.c`, `translated_private.dll` y `summary.json` **únicamente fuera del control de versiones**. En CI se ejecutan las pruebas sintéticas y no este comando dependiente del juego comercial.

## Extensión posterior: oráculo aislado de cinco instrucciones x87

La primera prueba de salida x87 se amplió en un ensayo independiente: **1.024/1.024 valores finales `float32` idénticos bit a bit** en `[0x41B960,0x41B973)` con Unicorn y la traducción compilada; también se comprobó que un byte de salida alterado es detectado. **No** implica equivalencia de `binary80` ni del estado FPU completo. [Informe independiente](CPU_PHASE2_X87_WINDOW_ORACLE_2026-10-14.md).

## Límites: qué NO se ha probado

1. **No equivale a las 553 instrucciones de la función.** Solo se verificaron las primeras **20**, hasta el primer salto; las ramas posteriores, bucles, colisiones y la zona caliente de coma flotante aún necesitan oráculos delimitados.
2. **No se verificó AF** porque la traducción p-code actual no lo materializa como estado arquitectónico observable. Los flags restantes sí se compararon.
3. **No se verificó x87 de 80 bits**, su palabra de control, excepciones, NaN y precisión intermedia. No puede afirmarse equivalencia completa del punto flotante.
4. **No se midió ARM64** ni mejora de FPS. La DLL C es una herramienta host de equivalencia, no un candidato de optimización ni un renderer.
5. El espacio de entradas se centró en pila/datos válidos y memoria mapeada de forma controlada. No representa todas las condiciones de excepción o páginas inaccesibles del juego.

## Próximo bloque lógico

Ampliar un oráculo independiente a **una ventana de coma flotante posterior a `0x0041B94D`**, con captura explícita del estado FPU x87 y memoria, y distinguir discrepancias de precisión `binary80` frente a `double`. Antes de aceptar cualquier optimización estructural se deben demostrar equivalencia de **entradas, salidas, flags, memoria y PC** y mejora de **código máquina AArch64** con la misma versión de Clang. La ganancia en el **TECNO CK6n** solo puede afirmarse con medición A/B/A/B/A en el teléfono, aún no conectado.

**Referencias:** [auditoría de la función](CPU_PHASE2_41B8F0_AUDIT_2026-10-14.md), [estrategia vigente](PERFORMANCE_STRATEGY_CURRENT.md), [perfil original del TECNO](PERFORMANCE_STRATEGY_RUN_2026-10-14.md).
