# Fase 7 — CoDSP p4: conversión x87 selectiva por PC original, OFFLINE

**Fecha:** 2026-10-14
**Repositorio:** Dr3amyBerry/callofrecomp, rama `main`
**Estado:** experimento reproducible y verificado *offline*; **desactivado por defecto**; pendiente de medición de FPS en gameplay. **No se usó TECNO/ADB ni se instaló ninguna APK.** No se alteraron texturas, soldados, mallas, calidad Equilibrado, visibilidad, colisiones ni guardados.

## Motivo y alcance exacto

La fase 6 aplicaba el fast path ya probado `codsp_x87_normal_f2d` a toda la partición CoDSP `p4`. Aunque funcionaba en el oráculo parcial, esa aplicación elevó la sección ARM64 `.text` **211.432 bytes**, con efectos de I-cache desconocidos. Las muestras CPU previas del dispositivo apuntan a cuatro funciones originales dentro de la partición: `0x0047BD40` (213 muestras), `0x00475D80` (114), `0x004766E0` (105), `0x00476070` (85). Suma **517 muestras históricas** dentro del subconjunto analizado; **no significa que esas 517 muestras ejecutaran un `f2d`, ni que sean muestras nuevas o milisegundos por frame**.

De las aproximadamente **4.114 expresiones `f2d(...,10)`** detectadas estáticamente en el generado original `p4`, el nuevo parche selecciona **520 sitios**, ubicados en **276 instrucciones originales** y exclusivamente en cinco intervalos disjuntos que representan esos cuatro cuerpos originales:

- `[0x00475D80, 0x00475EBD)`
- `[0x00476070, 0x004760FB)`
- `[0x004766E0, 0x00476DE2)`
- `[0x0047BD40, 0x0047BD6C)` y `[0x0047BD70, 0x0047C419)`

El hueco entre los dos últimos intervalos permanece intacto; no se infiere la propiedad de una instrucción a partir de su proximidad. La selección se hace por etiquetas de PC x86 y llamadas exactas `f2d(rd(...),10)`, **no** por nombres de chunk como si fueran funciones originales. La cobertura completa del cuerpo de `0x0047BD40` todavía está condicionada por una instrucción que falta en la exportación privada de p-code; no se inventa.

## Código y seguridad

- Nuevo `tools/recomp/patch_codsp_p4_f2d_selective.py`: aplicación, análisis sin escritura y restauración **reversible**. Reescribe solo las 520 invocaciones comprobadas del C privado `recomp_out/codsp_recomp_p4.c`. El parche deja disponible el helper existente y cancela con `#undef f2d` su sustitución global, por lo que todas las instrucciones no seleccionadas usan exactamente el conversor anterior.
- Protección SHA-256 de p-code CoDSP 1.5: `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e`. SHA-256 del C original `ee9156183cc0410bf0641592f93d3d0efa4febc906cc014969ddb30d95a196d3`; con parche `b9a667ba9f467be99d94e3ca6ce6464b8a3e1ddfaf04c1ff17715beeb70fe284`. Cualquier input desconocido con parche se rechaza.
- Opción optativa `--x87-normal-f2d-p4-selective` en `tools/recomp/build_android.py`, solo ARM64, requiere `--x87-normal-f2d`, es incompatible con `--x87-normal-f2d-p4` integral. La compilación normal detecta y restaura la variante privada si estaba aplicada; otras versiones sin este parche no se reescriben.
- `android/CMakeLists.txt` añade `CODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE=OFF` de forma predeterminada, comprueba el código parcheado y el p-code por hashes, así como los flags requeridos; solo la unidad `p4` recibe el nuevo guard. P1/p8 conservan sus mejoras anteriores sin ninguna modificación.
- No se reintrodujo la versión fuera de línea `noinline` rechazada en fase 6 por diferencias de propagación con valores x87 especiales. La variante aquí evaluada utiliza la función **inline** existente con fallback al `f2d` original.
- Tests sintéticos `tests/test_selective_p4_f2d.py`: límites exactos de PC, hueco no recuperado, conversiones de otros tamaños, detección de etiquetas duplicadas, rechazo de fuentes ajenas, modo idempotente, control por hash, CRLF y restauración byte a byte. `tests/test_build_android_profiles.py` cubre las nuevas restricciones CLI.

## Equivalencia y artefactos offline

Con instrucciones x87 reales extraídas del p-code privado de las **cuatro funciones originales** se compararon **24 instrucciones independientes**, seis por cuerpo. La instrucción de `0x0047BD40` que carece de p-code se omitió explícitamente; solo se probaron instrucciones válidas. El oráculo compara el registro arquitectónico `R` entero, RAM de prueba y PC, también con patrones especiales x87 (incluidos NaN/infinito), bajo Clang `-O1` y `-O2`: **24.000 × 2 = 48.000 comparaciones de estado completo, sin diferencias**. Esto prueba identidad *entre variantes del traductor* para esos casos, **no** equivalencia independiente contra el CPU x86 original, ni la totalidad de las 520 conversiones, ni FPS.

Las pruebas globales del repositorio finalizaron con **250 pruebas Python correctas (4 omitidas) y 34/34 CTest**.

Se compiló y firmó una APK ARM64 **solo offline** con los mismos flags anteriores de la referencia, sumando el selectivo `--x87-normal-f2d-p4-selective`. La comparación sobre `libmain.so` despojado de falsas atribuciones de funciones originales:

| Binario ARM64 | `.text` bytes | Crecimiento frente a A |
|---|---:|---:|
| A original: x87 ya comprobado en p1/p8; p4 sin modificación | 42.339.912 | — |
| B fase 6: fast path en todo p4 | 42.551.344 | **+211.432** |
| **B fase 7: solo 520 sitios de p4** | **42.374.108** | **+34.196** |

Frente a aplicar la optimización a toda `p4`, el selectivo **evita 177.236 bytes de código nativo adicional (83,8 % del aumento)** y modifica únicamente **3 símbolos de chunk ARM64** (`codsp_chunk_83_spaces`, `codsp_chunk_84_spaces` y `codsp_chunk_88_spaces`) en vez de 16. Los chunks recompilados contienen instrucciones de diferentes funciones x86; no son equivalentes a tres funciones originales. **La reducción es de crecimiento estático, no reducción absoluta respecto a A; no se conocen instrucciones dinámicas ahorradas ni FPS.**

Los artefactos privados están ignorados en `.local/profiles/phase7_p4_selective/`. APK experimental B SHA-256: `a2c9116b922c27566348a0ba24640ac81f55e5c483a35df60473a92d95b648df`. No compartir ni publicar fuentes C generadas, PE/p-code, APK, `perf.data` ni guardados.

### Restauración final

Una compilación local posterior sin `--x87-normal-f2d-p4-selective` restauró automáticamente el C original `p4` **byte a byte**. Verificación: `CODRECOMP_X87_NORMAL_F2D=ON`, `CODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE=OFF`, `CODRECOMP_X87_NORMAL_F2D_P4=OFF`, `CODRECOMP_DISPATCH_LAST_CACHE=OFF`, `CODRECOMP_HOT_X87_FASTPATH=ON`. El ELF `libmain.so` reconstruido y la biblioteca dentro de la APK normal coinciden **por SHA-256 con A**. SHA-256 ELF restaurado: `2c946984d2da41a5df31b48bb1bf3700f64fb6f801d043748332c619eac695e5`.

## Veredicto y próximo bloque

**Mantener OFF.** Se redujo significativamente el tamaño del experimento y se aprobaron las pruebas disponibles, pero no existe una mejora nueva de FPS demostrada. Cuando el usuario autorice expresamente a reutilizar el TECNO, ejecutar A/B/A/B en la misma escena y calidad, con guardado/cámara/estado térmico controlados y verificación de jugabilidad. Hasta entonces, solo continuar auditoría, microbenchmarks y equivalencia offline, sin suponer tasas de conversión por frame.
