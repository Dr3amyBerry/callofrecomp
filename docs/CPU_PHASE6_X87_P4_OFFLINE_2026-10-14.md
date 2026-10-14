# Fase 6 — ampliación x87 normal→double a p4, evaluación offline (2026-10-14)

**Alcance:** trabajo realizado exclusivamente en Windows/NDK con perfiles físicos *archivados*. **No se conectó ni utilizó el TECNO, no se instaló ninguna APK nueva y no se realizaron medidas nuevas de FPS**. La versión previamente validada en el teléfono continúa sin cambios. Objetivo 60 FPS mantenido, sin recortar soldados, colisiones, geometría ni visibilidad.

## 1. Selección guiada por evidencia

El perfil histórico Simpleperf `strategy_spawn_cpu_v1_analysis.json` (7.953 muestras de CPU de proceso) se cruzó con las funciones recuperadas y los 223 chunks originales CoDSP en doce particiones de compilación. Agrupando *solo las entradas presentes entre las 40 funciones calientes enumeradas*:

| CoDSP | Muestras agrupadas de funciones calientes | Situación antes de esta fase |
|---|---:|---|
| p1 | 847 | La vía rápida `CODRECOMP_X87_NORMAL_F2D` ya funciona aquí |
| p8 | 827 | La misma vía rápida ya funciona aquí |
| **p4** | **789** | **La conversión normal x87 sigue sin vía rápida** |
| p0 | 279 | No intervenido |
| p7 | 244 | No intervenido |

Las cifras **no** son muestras exclusivas de toda la partición, frecuencias de llamada, operaciones `f2d` dinámicas ni milisegundos/frame. La partición p4 contiene 5.533 expresiones `f2d(...)` en C generado, de ellas aproximadamente 4.114 con argumento `n=10` (conteo estático, no ejecutado); representa una oportunidad para intentar la conversión exacta que mejoró el rendimiento físico en p1/p8. No significa que 4.114 conversiones sucedan por frame.

La función original `0x0047BD40` figura entre las más calientes, pero una de sus instrucciones tiene p-code sin operaciones en la exportación privada, por lo que **se excluyó de los oráculos específicos**. Se usaron otras funciones originales de p4, con instrucciones completas.

## 2. Cambio experimental, OFF por defecto

- `tools/recomp/build_android.py --x87-normal-f2d-p4` requiere `--x87-normal-f2d` y `--abi arm64-v8a`. El CLI rechaza usos parciales o en WSA.
- `android/CMakeLists.txt`: opción `CODRECOMP_X87_NORMAL_F2D_P4` **OFF por defecto**, activa la definición `CODRECOMP_X87_NORMAL_F2D` **únicamente** en `codsp_recomp_p4.c`; conserva exactamente la implementación comprobada de `codsp_x87_normal_f2d` y el fallback original `f2d`. En p1 y p8 no modifica nada.
- Protección fail-closed: exige p-code SHA-256 `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e` y el C generado original de p4 SHA-256 `ee9156183cc0410bf0641592f93d3d0efa4febc906cc014969ddb30d95a196d3`. No se incluye contenido del juego en Git.
- Sin cambios a las llamadas GL, shaders, x87 word/status, al comportamiento del guest dispatcher ni a los modelos/objetos de la escena. **Se preserva la variante inline comprobada.**

## 3. Pruebas de equivalencia sin el dispositivo

Se extrajeron **18 instrucciones `FLOAT_MULT/ADD/SUB` auténticas de CoDSP p4** en `0x00475D80`, `0x00476070` y `0x004766E0`, siempre con p-code completo y sin LOAD/STORE/CALL/BRANCH. Se generó el traductor normal y otro con la vía rápida **inline**, se compilaron por separado con Clang Windows `-O1` y `-O2` sin contraer expresiones de coma flotante, y se compararon, para **36.000 ejecuciones** en total, el registro arquitectónico x86 completo `R`, la RAM de la prueba y el `PC` de salida. Incluyen patrones normales, valores no representables y casos especiales `binary80`; las 36.000 comparaciones **coincidieron**.

La prueba no es un oráculo independiente que ejecute el CoDSP x86 original y no cubre la partición p4 entera. Sí valida la identidad observada entre dos variantes del traductor para esas instrucciones reales. El smoke público ya existente `x87_normal_f2d_smoke.c` también contrasta millones de patrones de bits contra el conversor original.

### Prototipo fuera de línea descartado

El primer intento de aplicar el helper inline a toda p4 incrementó mucho el código nativo. Se intentó aislar el helper como **una función `noinline` compartida** para reducir ese crecimiento. Una batería diferencial sobre operaciones reales **falló en `FLOAT_MULT`**, para una entrada de prueba con exponente x87 `0x7fff` (especial NaN/infinito). Al sustituir *solo ese conjunto de entrada* por un exponente finito, **36.000 comparaciones coincidieron** de nuevo con `-O1` y `-O2`. Esto apunta a una discrepancia de propagación/orden de resultados especiales, **sin demostrar la causa exacta ni su aceptabilidad en el juego**. **La implementación `noinline` se eliminó por completo del código de producción y de los flags experimentales**; no se debe reintroducir sin equivalencia completa.

## 4. Dos APK ARM64 construidas offline, no instaladas

Variantes compiladas con la misma base `--hot-x87-transform --x87-normal-f2d`, referencia A con extensión p4 OFF y B con el nuevo flag de p4 ON, cambiando el código generado que ve el compilador solo para p4. Firmadas v2/v3 localmente. Archivos privados ignorados en `.local/profiles/phase6_p4_f2d/`:

| Métrica | A: p4 OFF | B: p4 inline ON | Diferencia B−A |
|---|---:|---:|---:|
| `libmain.so` sección `.text` | 42.339.912 bytes | 42.551.344 bytes | **+211.432 bytes** |
| Chunks nativos recompilados y diferentes | — | 16 de p4 | — |
| Suma de tamaño de 16 símbolos cambiados | — | — | +211.372 bytes |

Los símbolos más grandes que cambiaron son `codsp_chunk_92_spaces` (+42.460 bytes), `codsp_chunk_88_spaces` (+36.304) y `codsp_chunk_86_spaces` (+30.676). El aumento corresponde a bytes `.text`, **no a las instrucciones ejecutadas por frame**; también podría provocar peor comportamiento de I-cache y superar cualquier ahorro en conversiones. **No se afirma ni se supone una mejora de FPS**.

APK A SHA-256: `cbb155170a3b64f9baf8eb06aff912cd3b27dc2eef42e4d54bba3f51d1c0597a`. APK B inline SHA-256: `c14f7444527256d049807bab5e4a2a9071abe573be0a956a7505d69d8d39284d`. Estos hashes son de pruebas **offline**, NO equivalentes al respaldo de APK B previamente aceptada en TECNO.

## 5. Decisión y continuación

**Decisión: p4 opt-in OFF; sin instalación.** La conversión inline es candidata **segura dentro del alcance diferencial comprobado**, no una optimización aprobada de rendimiento. El prototipo `noinline` está rechazado por diferencia real de estado en entradas especiales. La extensión p4 solamente debe medirse en el teléfono cuando el usuario lo permita, controlando el mismo escenario, versión, thermal, funciones CPU y partidas, y realizando A/B/A/B.

La inspección por p-code y muestreo **no basta para cuantificar la frecuencia real de conversiones x87 por frame**. Antes de proponer otras expansiones a p0/p7, sería útil un muestreo sin recorte o contador de llamadas a los bloques x87 en escenarios fijos. Mientras tanto se pueden diseñar optimizaciones con costes ARM64 medibles offline y validadores diferenciales, sin activar un perfil más lento o inexacto.

**Validación del cierre:** 244 pruebas Python correctas (4 omitidas), 34/34 CTest correctas. La reconstrucción NDK ARM64 normal terminó con `CODRECOMP_X87_NORMAL_F2D_P4=OFF`, `CODRECOMP_X87_NORMAL_F2D=ON` y `CODRECOMP_DISPATCH_LAST_CACHE=OFF`; se verificó que el ELF local y la `libmain.so` empaquetada coinciden **byte por byte** con la referencia A archivada. No se instaló ni ejecutó en TECNO. Los resultados de FPS de la anterior build x87 aceptada no se atribuyen a esta compilación local.
