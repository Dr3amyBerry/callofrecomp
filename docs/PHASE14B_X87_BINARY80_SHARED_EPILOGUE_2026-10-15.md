# Fase 14B — Estado x87 binary80 y epílogo compartido (15 de octubre de 2026)

**Estado:** auditorías independientes verificadas; la fase 14B todavía NO demuestra equivalencia completa ni permite sustituir una función original por ARM64. No se modificaron motor, APK, gráficos, guardados ni teléfono. **FPS y ms/frame nuevos: no medidos.**

## Por qué era necesario

El oráculo anterior de `0x0041B8F0` coincidía con el ejecutable x86 original en dos ramas de 20 y 27 instrucciones; terminaban antes de la FPU. La siguiente ventana tenía cinco operaciones x87 originales que el traductor actual baja mediante `f2d/d2f` y aritmética `double`. Un mismo resultado `float32` final no implica que se preserven los registros internos de 80 bits ni las decisiones derivadas de comparaciones.

### 1. Auditoría independiente de ST0 binary80

Herramienta nueva: `tools/recomp/diagnostics/verify_x87_internal_state.py`. Compila **cinco DLL privadas** desde el lowering vigente de `pcode2c.Gen`, una por punto de parada real después de cada instrucción x87 original. El ejecutable `CoDSP.exe` privado se ejecuta en Unicorn x86 con `FPCW=0x037F`; Capstone comprueba las direcciones, tamaños y mnemónicos antes de medir. El oráculo compara el valor numérico **binary80 crudo** de ST0 cuando existe, junto con los 8 registros generales, PC y tres regiones RAM observadas. Después de `FSTP`, ST0 queda vacío y solo se verifican RAM/GPR/PC; nunca se declara una coincidencia de ST0 en una pila vacía.

El método para leer la pila x87 se verificó **de forma independiente con once programas x86 sintéticos**: el valor devuelto por el registro físico `Unicorn FP[n]`, indexado mediante `TOP` de la palabra de estado, coincidió byte a byte con lo escrito por la propia instrucción `FSTP m80`. Esto valida el formato del oráculo y evita confundir registros físicos con ST0 lógico.

**Resultados medidos sobre 256 casos deterministas para cada uno de los cinco checkpoints:**

| Última instrucción ejecutada | Coincide ST0 binary80 | Difiere ST0 binary80 | GPR/RAM |
| --- | ---: | ---: | ---: |
| `FLD` (PC siguiente `0x0041B966`) | 256 | 0 | 256/256 |
| `FSUB` (`0x0041B968`) | 255 | **1** | 256/256 |
| `FMUL` (`0x0041B96C`) | 126 | **130** | 256/256 |
| `FSUB` (`0x0041B96F`) | 89 | **167** | 256/256 |
| `FSTP` (`0x0041B973`) | ST0 vacío | No comparable | 256/256 |

En las **167 divergencias** después del segundo `FSUB`, **signo y exponente coincidieron siempre**, mientras el significando de salida del traductor tenía sus **11 bits menos significativos a cero**. Entre esas 167 diferencias, 166 tenían bits bajos no nulos en el x87 original; 90 aún compartían la parte alta de 53 bits de significando. Esto es **evidencia de pérdida de precisión extendida**, consistente con la actual implementación del runtime basada en `double`. No demuestra por sí solo que una condición de juego o FPS hayan cambiado.

**Bloqueo de fidelidad (fail closed):** nueva opción de diagnóstico `--require-bitwise-st0` y función `st0_fidelity_gate`. Si difiere cualquier valor vivo de ST0, el comando produce un informe privado, imprime `ST0_BINARY80_GATE_FAILED` y devuelve **código 4**, en vez de aprobar equivalencia completa. Se ejecutó el control estricto sobre **96 casos**: 55 diferencias en el último checkpoint vivo; la prueba **rechazó correctamente** el candidato, manteniendo registro de la discrepancia.

**No comprobado todavía:** `FPCW/FPSW/FPTAG` del traductor frente al x86 original, registros físicos x87 distintos de ST0, flags AF, redondeos de palabra de control distintos del predeterminado, excepciones no enmascaradas, alias arbitrarios, ni toda la función de 553 instrucciones. Las palabras nativas de status/tag se leen pero **no tienen un mapeo demostrado** con el estado virtual `R`; por eso el informe siempre indica `full_fpu_state_equivalent=false`. La precisión extendida es un requisito de equivalencia, no una optimización de bajo nivel para perseguir a ciegas.

Reportes reales privados, excluidos de Git:
- `.local/profiles/phase14c_x87_binary80_verified_v2/summary.json` — 256 casos, cinco checkpoints, selftest FSTP m80.
- `.local/profiles/phase14c_x87_binary80_strict_negative_v1/summary.json` — 96 casos, gate rechazado.
- DLL y C derivados de las instrucciones privadas se guardan solo en sus carpetas locales; no se publican.

### 2. Las tres salidas no son retornos simples

Herramienta nueva: `tools/recomp/diagnostics/verify_shared_epilogue.py`. Una vez recuperado el CFG de `0x0041B8F0`, se comprobó sobre el PE original que los tres JMP en `0x0041C012`, `0x0041C07A` y `0x0041C090` saltan a **`0x00523CD9`**, una función Ghidra independiente.

El comienzo del destino original ejecuta una comparación de **ECX contra [0x00563940]**, toma una rama de fallo si los valores difieren y ejecuta `RET` cuando coinciden; la rama de fallo salta a `0x00523CA8`. El patrón es **compatible con un chequeo de cookie de seguridad**, pero se mantiene como hipótesis funcional: no es una prueba independiente de todos sus efectos ni de su ruta de error.

Se verificaron los tres saltos, la bifurcación, el retorno, el JMP de fallo y sus destinos usando **Capstone sobre bytes x86 originales** y el CFG de p-code verificado. El destino de salida **debe conservarse**: no puede reescribirse como `return` ARM64 ni omitirse sin demostrar el contrato completo de flags, ECX, ESP, pila, memoria y ruta de fallo.

Reporte privado: `.local/profiles/phase14c_shared_epilogue_v1.json`.

### 3. Pruebas y reproducibilidad

- `tests/test_verify_x87_internal_state.py`: little-endian 80 bits, signo/exponente, límites inválidos, ventanas/etapas de Ghidra, rechazo de p-code opaco, conteo correcto de divergencias y puerta estricta contra falsos PASS.
- `tests/test_verify_shared_epilogue.py`: grafos sintéticos, propiedad Ghidra B separada, rechazo de targets modificados, retornos y condiciones falsificadas, CALLOTHER opaco.
- **Suite de regresión final:** 315 pruebas Python ejecutadas, 4 omitidas, 0 fallidas; compilación host exitosa y **35/35 CTest** aprobados. El control negativo estricto de ST0 fue un rechazo esperado, no una prueba fallida.
- Los laboratorios requieren archivos originales privados por SHA-256, `capstone`, `unicorn`, `pefile` y LLVM-MinGW; toda salida se escribe bajo `.local/profiles` con creación exclusiva, sin sobreescribir evidencia.

Comandos de referencia desde la raíz del repo:

```powershell
python tools/recomp/diagnostics/verify_x87_internal_state.py --pe ".local/private/Call of Duty Deluxe Edition/CoDSP.exe" --pcode recomp_out/codsp.pcode --compiler "RUTA_AL_LLVM_MINGW_CLANG" --output .local/profiles/x87_audit_new --cases 256
python tools/recomp/diagnostics/verify_shared_epilogue.py --pe ".local/private/Call of Duty Deluxe Edition/CoDSP.exe" --out .local/profiles/epilogue_audit_new.json
```

Reemplazar `RUTA_AL_LLVM_MINGW_CLANG` por la ruta instalada localmente al compilador host. Para impedir que un candidato con diferencias se marque como equivalente, añadir `--require-bitwise-st0` al primer comando.

## 4. Decisión y siguientes trabajos

1. **Bloqueo de fidelidad validado:** los checkpoints de geometría con x87 no se consideran elegibles para transformación nativa que altere ST0. Mantener traducción actual como fallback, sin habilitar código acelerado inseguro.
2. La próxima fase de regiones deberá preservar el epílogo compartido y las entradas externas, y comprobar si hay **subgrafos enteros sin x87 ni efectos de RAM/alias peligrosos** para compilar a regiones nativas A/B. Esto evita repetir microoptimización por instrucción sin ahorro estructural.
3. Si se necesita una sustitución completa de geometría, antes habrá que implementar **semántica binaria80 real** y validar `FPCW/FPSW/FPTAG` y la ruta de verificación del cookie con un oráculo independiente extensivo.
4. El criterio posterior en TECNO sigue siendo **reducción reproducible de ms de CPU/frame** manteniendo el nivel gráfico y las físicas. Ningún número de FPS se infiere aquí.

**Conclusión:** 14B sigue parcial. Se ha descubierto y verificado un bloqueo real de precisión x87 y se ha esclarecido la dependencia compartida de salida que un optimizador por regiones debe preservar.
