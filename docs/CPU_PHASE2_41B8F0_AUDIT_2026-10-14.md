# Fase 2 — Auditoría estructural de `0x0041B8F0` y ensayo x87 sin modificar el juego

**Fecha:** 2026-10-14. **Meta vigente:** 60 FPS sostenidos en Camp Toccoa, TECNO CK6n ARM64, Equilibrado. **Contador:** **0/5**. **Resultado:** se preparó y validó una auditoría del cuerpo caliente real, y se **descartó** una simplificación de copia x87 por falta de mejora demostrada en AArch64. No se modificó `libmain.so`, la APK estable, la configuración de Android ni los guardados.

## 1. Contexto medido y alcance

Según [la captura de Simpleperf del TECNO](PERFORMANCE_STRATEGY_RUN_2026-10-14.md), el cuerpo original de CoDSP `0x0041B8F0` recibió **270 muestras** en A1 y **196** en la segunda captura. La primera equivalía, bajo la metodología documentada, a aproximadamente **1,42 ms CPU/frame orientativos**, no tiempo exclusivo ni ahorro potencial medido. La referencia del juego físico es **24,70 FPS** y **38,895 ms CPU/frame**: una sola función no puede salvar por sí sola la brecha de ~22,23 ms de CPU/frame hacia 60 FPS.

**Hardware disponible ahora:** únicamente WSA Android 33 x86_64/AMD. No hay TECNO ARM64 conectado. Los resultados de microcódigo y de WSA **no se computan como intento válido de optimización en el teléfono**.

## 2. Cuerpo original delimitado usando datos privados

Nueva herramienta reproducible: `tools/recomp/diagnostics/audit_hot_function.py`. Solo lee el p-code/Ghidra privados que permanecen en `recomp_out/`, el mapa de cuerpos v2 y el muestreo previo del ELF ARM64; genera **estadísticas**, no publica instrucciones ni datos del juego. Rechaza conteos inconsistentes, intervalos solapados, entradas ausentes, propiedad ambigua del cuerpo, varnodes inválidos y muestras nativas duplicadas; no sobrescribe informes anteriores.

| Propiedad auditada | Resultado |
| --- | ---: |
| Función y rangos Ghidra | `0x0041B8F0–0x0041BCD8` y `0x0041BCE0–0x0041C094` |
| Instrucciones originales en su cuerpo | **553** |
| Operaciones p-code del cuerpo | **3.957** |
| Operaciones `COPY` | **1.789** |
| Operaciones `LOAD` del invitado | **187** |
| Operaciones `STORE` del invitado | **67** |
| Operaciones en coma flotante, por clasificación del auditor | **418** |
| Transferencias de control | **75**, de ellas **52** condicionales |
| Bloque generado que contiene la función | **chunk 19**, compartido por **12 funciones** |
| Muestras de Simpleperf del cuerpo (A1) | **270** |
| Muestras incluidas en la lista recortada de 100 sitios ARM64 más calientes | **127/270** |

El análisis encuentra dos ventanas de ocho instrucciones contiguas alrededor de `0x0041B94D–0x0041B96C` y `0x0041B96F–0x0041B98C`, que agrupan **41** y **48** muestras **dentro de la lista recortada** respectivamente. No se deben interpretar esos conteos como frecuencia de ejecución real, porcentaje de tiempo ni cobertura integral de la función. La primera ventana contiene lecturas de memoria y operaciones flotantes; la segunda también tiene escritura de memoria. **Ninguna está certificada para elevar registros a variables locales entre instrucciones**.

El generado actual ya maneja registros y RAM con punteros disjuntos donde está justificado; la compilación anterior eliminó 32.704 temporales de C sin reducir el `.text` nativo. Más `COPY` en p-code **no implica** que queden instrucciones de copia redundantes tras Clang.

**Identidad de entrada auditada:** SHA-256 de `codsp.pcode` privado `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e`; hash del mapa v2 `f6d56b4d167df2fb66a9f18ff8624e6b48fd363eadcbd05e62fa2598cd03ab4c`. El informe JSON resultante está en `.local/profiles/strategy_41b8f0_phase2_audit.json`, **fuera de Git**.

## 3. Experimento aislado x87: equivalencia sí; aceleración no probada

Al revisar la zona caliente se observó un patrón común de desplazamiento de siete registros x87 de **80 bits** (`10 bytes` cada uno, separados **16 bytes** en el estado virtual). Se preparó `tests/x87_stack_copy_lab.c`, **sin código comercial**, que compara:

- **Referencia:** `rd(...,10)` sobre un entero de 128 bits y `wr(...,10)` a los siete destinos.
- **Alternativa:** siete `memcpy` directos de diez bytes, conservando los **seis bytes de separación de cada registro**.

Un ejecutable CTest comparó **20.000 casos sintéticos** de estados completos, incluidos ceros, bytes `0xFF`, patrón secuencial y datos pseudoaleatorios, comprobando **todos los bytes**, no solo el valor numérico x87. **Resultado: equivalencia exacta** en el laboratorio.

Se compilaron los dos núcleos con **Android NDK Clang 30.0.16248370**, objetivo **aarch64-linux-android24**, y se inspeccionó `llvm-objdump`:

| Flag de compilación | Referencia `rd/wr` | Alternativa `memcpy` |
| --- | ---: | ---: |
| `-O1` | **29 instrucciones AArch64** | **29 instrucciones AArch64** |
| `-O2` | **29 instrucciones AArch64** | **29 instrucciones AArch64** |

En ambas variantes el patrón de loads/stores es comparable (8 + 2 bytes para cada registro). Las instrucciones pueden tener una planificación distinta, pero **el recuento nativo no mejoró**. Es un *microensayo sintético*, no la compilación de la función completa ni un perfil del hardware. No hay mejora verificable que justifique tocar el generador o intentar instalar una APK. **Se descarta el parche de memcpy simple por ahora.**

La compilación de laboratorio es opcional y no cambia el renderer ni el motor del juego. CMake solo compila y ejecuta este test si existe soporte para `unsigned __int128`. Los productos compilados quedan en `.local/`.

## 4. Riesgos que bloquean cachear registros globalmente

1. La función tiene dos intervalos de cuerpo y comparte el **chunk 19 con otras 11 entradas**; no se puede tratar el chunk como una sola función sin verificar aristas.
2. Existen accesos a memoria del invitado, operaciones flotantes y cambios de EFLAGS/x87. Los alias y las excepciones observables necesitan comprobación precisa.
3. Las primeras 100 ubicaciones ARM64 del perfil contienen solo parte de las 270 muestras, y el reparto está condicionado por muestreo. Un candidato elegido solo por número de copias estáticas carece de justificación suficiente.
4. El código de FCOM ya usa un guard de especialización optativa en el generado; no reutilizar ni cambiar esa ruta sin verificar sus condiciones de equivalencia y sin benchmarking físico.

## 5. Próxima intervención más lógica

- **Delimitar una sola ventana caliente**, incluyendo todas sus aristas entrantes/salientes, registros observables, EFLAGS y estados x87; conservar el resto del chunk sin alterar.
- Construir un oráculo diferencial **x86 independiente del traductor** para entradas válidas y casos límite: flags, NaN/80-bit, aliasing, lecturas y escrituras de RAM, PC y retorno. Si no hay oráculo suficiente, la transformación debe permanecer desactivada.
- Implementar únicamente una variante de laboratorio sobre el bloque acotado **si** se puede probar equivalencia de estado; compilar **antes/después** para ARM64, comparar `.text`/instrucciones y no aceptar una mera reducción del C.
- Con TECNO conectado, medir gameplay A/B/A/B/A con misma escena, temperatura y guardados, si supera todos los controles. Sin dispositivo físico no se comunica ninguna nueva ganancia de FPS ni se incrementa el contador **0/5**.

**Conclusión:** el cuello CPU sigue siendo la prioridad, pero ahora existe una auditoría de cuerpo real y una transformación descartada con evidencia. Se mantiene `main` estable.
