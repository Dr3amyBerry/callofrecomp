# Fase 9 — Auditoría offline del empaquetado x87: optimización descartada

**Fecha:** 2026-10-14
**Proyecto:** CallofRecomp, CoDSP 1.5 → Android ARM64.
**Resultado:** no se encontró ninguna reducción de código en los chunks reales. **No se activa ni se incorpora ningún cambio al conversor del juego.** No se utilizó TECNO, ADB ni se instaló ninguna APK. La meta de 60 FPS sigue pendiente.

## 1. Por qué se investigó

En la fase 8 quedaron 277 llamadas de conversión `binary80` a `double` seleccionadas en 124 instrucciones originales de cuatro funciones calientes de CoDSP p4. La ejecución física de esta candidata **no ha sido medida**: solo tenemos perfiles históricos y comparaciones offline. Frente a la referencia A, el fast path de fase 8 añadió 20.076 bytes a la sección ARM64 `.text`, con coste en ciclos e I-cache sin comprobar.

Se intentó reducir una máscara y una combinación de bits de la ruta canónica mediante una equivalencia aritmética estrictamente entera. Bajo las mismas condiciones del helper actual, `E` está entre 15361 y 17406 y el significando `sig` tiene bit J=1 y 11 bits inferiores cero. Existe entonces `F` de 52 bits tal que `sig = 2^63 + (F << 11)`, por tanto `sig >> 11 = 2^52 + F`. Las expresiones

`((E - 15360) << 52) | F`

y

`((E - 15361) << 52) + (sig >> 11)`

producen el mismo valor entero. El signo y el fallback para entradas especiales permanecían intactos. El prototipo utilizaba solo una definición condicional para CoDSP p4, nunca para p1/p8.

## 2. Validación de equivalencia

- Se compararon **1.205.360 valores binary80** bit a bit con el convertidor original: 65.536 valores de exponente/signo × 10 patrones de significando, 250.000 patrones exactamente representables y 300.000 casos adicionales aleatorios/no canónicos. Se añadieron 20.000 comparaciones de binary32 y binary64.
- El ensayo diferencial privado con p-code real de las cuatro funciones CoDSP más calientes reprodujo **22 instrucciones × 1.000 estados × dos niveles Clang (`-O1` y `-O2`) = 44.000 comparaciones** del registro `R` completo, RAM sintética y `PC`, sin diferencias en los casos comprobados.
- El laboratorio aislado Windows C/ARM64 compiló `check_old` con **324 bytes** y `check_alt` con **320 bytes** de código ARM64, bajo `-O1` y `-O2`. Las mediciones host con `clock()` mostraron diferencias pequeñas y sensibles a la resolución del reloj: **no sustentan mejoras dinámicas**.

Estas pruebas no equivalen a un oráculo independiente de CPU Intel x86 ni cubren todas las instrucciones posibles del juego.

## 3. Resultado decisivo en el ejecutable real

Se compiló **exclusivamente en el PC** una APK Android ARM64 alternativa a la fase 8, con el mismo conjunto de 277 conversiones de p4, variando solo el empaquetado entero canónico. La APK firmada se archivó en `.local/profiles/phase9_packed_add/`, ignorada por Git. No se instaló en ningún dispositivo.

| Artefacto real | Fase 8 | Prototipo fase 9 | Diferencia |
| --- | ---: | ---: | ---: |
| `libmain.so` sección `.text` | 42.359.988 B | 42.359.988 B | **0 B** |
| `codsp_chunk_83_spaces` | 114.284 B | 114.284 B | 0 B |
| `codsp_chunk_84_spaces` | 116.396 B | 116.396 B | 0 B |
| `codsp_chunk_88_spaces` | 251.296 B | 251.296 B | 0 B |

La diseminación real de ARM64, comparada por **nombre exacto de símbolo** (no por dirección de un objeto relocatable), produjo el mismo número de instrucciones para cada chunk: 28.571, 29.099 y 62.824, respectivamente. También fueron idénticos los **histogramas de instrucciones ARM64 por mnemónico** en los tres chunks. Diferencias detectadas: **0 bytes, 0 instrucciones, 0 cambios de frecuencias de opcode**.

Esto demuestra que **el supuesto ahorro de tamaño del laboratorio aislado no se reprodujo en las funciones reales**. Histogramas iguales por sí solos no prueban bytes de máquina idénticos, equivalencia funcional completa ni idénticos ciclos en un dispositivo. El ELF no-stripped de fase 9 tiene SHA-256 diferente del de fase 8: no se equiparan indiscriminadamente ambos binarios. Pero no hay evidencia suficiente para justificar una opción experimental adicional.

## 4. Decisión de ingeniería: retirar el prototipo

**No se conserva la modificación de `recomp_rt.h` ni el nuevo flag del constructor Android.** Se revirtieron los cambios de producción y CMake Android del experimento. El fast path previamente validado en TECNO para p1/p8 y el experimento perfilado fase 8 (**OFF por defecto**) permanecen tal cual.

En cambio, se añadieron únicamente herramientas de validación para evitar repetir este tipo de falsos positivos:

- `tools/recomp/diagnostics/audit_arm64_native_symbols.py`: auditor de símbolos ARM64 offline con `llvm-nm` y `llvm-objdump --disassemble-symbols`, compara bytes/instrucciones/histogramas; funciona con ELF y objetos relocatables y deja claro que no mide FPS.
- `tests/test_audit_arm64_native_symbols.py`: pruebas deterministas de parser, símbolos filtrados, casos sin datos, conteos y diferencias.
- `tests/x87_packed_math_smoke.c`: preserva únicamente la demostración matemática del prototipo descartado, como caso de laboratorio separado. No modifica ningún código del motor, usa los mismos 1.205.360 + 20.000 patrones.
- `CMakeLists.txt`: un CTest host manualmente reproducible `x87_packed_math_smoke`. No cambia el APK ni el constructor de producción.

El auditor evita un fallo detectado al analizar objetos relocatables: varios `.text.*` comienzan en VA 0, por lo que no debe desensamblarse un `.o` solo con rangos de direcciones. El filtro exacto de símbolos resuelve el problema.

## 5. Restauración, pruebas finales y siguiente prioridad

### Comprobaciones de cierre aprobadas

- **257 pruebas Python correctas (4 omitidas) y 35/35 pruebas CTest**; incluye el nuevo auditor de ARM64 y la prueba matemática separada.
- La recompilación normal ARM64 finalizó. El C generado original de p4 regresó a su hash verificado y se restauraron por SHA-256 tanto el ELF nativo como la biblioteca contenida en la APK. SHA-256 de referencia A: 2c946984d2da41a5df31b48bb1bf3700f64fb6f801d043748332c619eac695e5.
- Se retiraron todos los cambios experimentales en el conversor, Android CMake, el constructor Android y las pruebas de flags. La caché CMake ya no contiene el flag temporal retirado; los tres perfiles experimentales de p4 y el despacho experimental están OFF, mientras el fast path x87 anterior se conserva.
- Los archivos APK candidatos, muestras CPU y C generado privado siguen solo en .local/profiles/, ignorados por Git. **No se conectó ni utilizó el TECNO.**

**Decisión final:** no incluir la variante compacta en el juego; no demuestra reducción de código nativo ni mejora de FPS.

**Nueva pista offline para la siguiente fase:** al atribuir los marcos DWARF inline de dos capturas históricas a las instrucciones x86 de los chunks p4 examinados, se recuperaron 974/1.017 y 840/889 muestras. Dentro de ese subconjunto, las muestras inclusivas fueron memcpy 409/353, rd 233/204, wr 154/123, f2d 366/329 y d2f 110/102, respectivamente. Las categorías se solapan (por ejemplo, memcpy puede estar dentro de rd/wr) y no son tiempos por frame ni mediciones actuales del teléfono. Esto orienta la siguiente investigación hacia lecturas/escrituras de estado arquitectónico sin eliminar comportamientos del juego.

**Próximo bloque sin TECNO:** orientar la investigación hacia el coste de lectura/escritura de estado arquitectónico generado (`rd`, `wr`, `memcpy` inline) en los PCs efectivamente muestreados, usando nuevos oráculos diferenciales y microbenchmarks de ARM64 compilado. No recortar geometría, NPC, renderización, efectos ni precisión numérica. La aprobación por FPS sigue dependiendo de un futuro A/B/A físico, solo cuando el usuario permita volver a usar el TECNO.
