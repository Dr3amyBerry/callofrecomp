# Fase 3 — Caché de registros virtuales en CoDSP p0 (TECNO CK6n, 2026-10-14)

**Resultado: prototipo implementado y verificado; FPS NO mejorados en el A/B/A físico. Mantener DESACTIVADO.** Meta de 60 FPS en el spawn de Camp Toccoa pendiente. No reducir geometría, visibilidad, NPC, calidad, efectos ni resolución.

## Código implementado

- `--cache-hot-registers` rechaza entradas que no coinciden con el SHA-256 de p-code verificado de CoDSP 1.5; se excluyen explícitamente divisiones potencialmente excepcionales.
- `tools/recomp/pcode2c.py` añade **`--cache-hot-registers`**, optativo y OFF por defecto. Se limita a la función original de CoDSP 1.5 **`0x004196F0`** dentro de la unidad privada `p0`, porque su código generado normal era idéntico byte a byte al generador. `p1` conserva otras modificaciones privadas previas (FCOM/NaN/copy32) y NO se reescribió.
- La planificación por instrucción de p-code comprueba **ausencia de saltos, llamadas, CALLOTHER y operaciones desconocidas**, rangos enteros de 1 a 16 bytes sin solapamientos, y al menos dos usos del mismo varnode arquitectónico. Las entradas leídas antes de escribir se cargan una sola vez, los cambios permanecen en variables temporales `u128` y el registro x86 se actualiza al **final de esa instrucción**. No cruza límites ni salidas de instrucciones, ni altera el espaciado de los registros x87 de 80 bits. Solo da a Clang la oportunidad de retenerlos en registros ARM64: no garantiza que nunca haya spills.
- Inspección estática: **719 instrucciones** potenciales en los dos grandes cuerpos geométricos auditados; **solo el cuerpo de `0x004196F0` (`p0`)** entró en la build probada. Los demás cuerpos/candidatos quedan desactivados por incompatibilidad con parches o por riesgo. `p2..p7,p9..p11` permanecieron idénticos a los originales, `p8` también sin modificar y `p1` no fue sustituido.
- Alcance real: cachear accesos exactos a registros dentro de instrucciones lineales. **No** implementar aún una fusión SSA entre varias instrucciones o reconstruir dependencias cruzadas de los 553/602 pasos de las funciones; esto exige invariantes, entradas CFG y pruebas de alias más amplias.

## Equivalencia probada, con limitaciones

- Prueba sintética `tests/test_hot_register_cache.py`: compara fuente C normal vs optimizada a `-O0/-O1/-O2` en 4.000 estados por compilación, comprobando **R completo, U, RAM y PC**, con operaciones enteras, conversiones binary80, escrituras x87 y superposición de registros. Tres pruebas nuevas aprobaron; opciones OFF no emiten caché.
- Oráculo diferencial compilado para **AArch64 y ejecutado en el TECNO**: 24 instrucciones auténticas de los cuerpos calientes, **49.152 casos**, estado arquitectónico completo `R` y PC idénticos frente al traductor actual; se seleccionaron bloques sin operaciones de memoria externa ni división y con temporales definidos. No representa un oráculo independiente Intel x86, no comprueba todas las ramas de campaña ni todos los estados de `fenv`. El archivo C generado queda privado y fuera de Git.
- Suite general: **235 pruebas Python, 4 omitidas**, **34/34 CTest correctas**. Compilación ARM64 y firma APK V2/V3 correctas.

## A/B/A de gameplay real: resultado desfavorable/inconcluyente

Ambas APK contenían las optimizaciones **ya demostradas anteriormente**, `--hot-x87-transform --x87-normal-f2d`; solo B1 añadió la caché `p0`. TECNO físico ARM64, GL4ES, calidad Equilibrado, mismo autosave y vista del spawn en Camp Toccoa, capturas de 55 s, últimas 40 ventanas estables por corrida. No hubo perfilador Simpleperf simultáneo.

| Corrida | Variante | FPS mediana | FPS p10 por ventana | CPU ms/frame mediana | Swap ms | Batería °C |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| A1 | Referencia x87 | **25,70** | **24,90** | **37,495** | 2,000 | 41→41 |
| B1 | Caché p0 + x87 | **25,15** | **19,70** | **38,200** | 2,035 | 42→42 |
| A2 | Referencia x87 restaurada | **25,20** | **19,30** | **38,130** | 2,030 | 43→43 |

La diferencia B1 vs A1 es -0,55 FPS, pero **A2 desciende casi hasta B1 sin caché** y su p10 es incluso menor. B1 vs A2 varía solo -0,05 FPS y +0,07 ms CPU: **no existe una mejora de rendimiento reproducible** y tampoco evidencia suficiente para atribuir la caída de p10 a la caché. La temperatura, actividad/NPC y frecuencias pueden introducir variabilidad. El p10 corresponde a las ventanas agregadas, NO al percentil individual de frames.

**Decisión:** rechazar la caché como optimización de FPS. No subir ni instalar el candidato como reemplazo de la APK B comprobada, y no anunciarlo como ganancia.

## Seguridad, compilación y reversión

- APK A exacta, conservada privadamente en `.local/profiles/tecno_f2d_B_candidate.apk`; SHA-256 APK `efaa575fffb223d47cc824e56f9fe0219c076ff0d55d9a9ed5e2632fe3e7243e`.
- APK B experimental, privada en `.local/profiles/regcache_out/experimental_p0_regcache_arm64.apk`; SHA-256 APK `f399856678f448bc9987015265193e92c426a492076823c9135ede054badb695`.
- Los fuentes C generados, APKs, mapas, resultados y guardados de prueba permanecen privados/ignorados. Registros comparables bajo `.local/profiles/tecno_live_20261014/RC_{A1,B1,A2}/`.
- La fuente privada `recomp_out/codsp_recomp_p0.c` se restituyó **byte a byte** mediante hash y se verificó `p1` sin modificar. Se borró **solo** el objeto NDK p0 experimental obsoleto y se forzó su reconstrucción normal: Ninja recompiló p0 y enlazó el binario normal, evitando falsos resultados por timestamps de `shutil.copy2`.
- En el teléfono se reinstaló la APK **A exacta** con `adb install -r`, sin limpiar datos. El guardado `autosave/training.svg` conservó su SHA-256 `efbc68e54fabc79946dfd3a9d188e5f6ba284b1aad99130bbe2726eb637f64f8` durante las tres corridas.
- `--cache-hot-registers` queda OFF por defecto. Código de experimento + tests se conservan para un rediseño con mejor asignación nativa, sin incluirlo en ninguna APK de referencia.

## Próximo bloque con posibilidad de impacto real

El compilador `-O1` ya optimiza muchas lecturas/escrituras dentro de instrucciones; un `u128` local para registros x87 de 80 bits puede presionar el conjunto de registros o llevar a spills. Es una **hipótesis**, no causa demostrada. La siguiente fase requiere comparar carga/almacenamiento ARM64 real por bloque, modelar liveness y aliasing **a través de múltiples instrucciones x86** y fusionar cadenas de conversión x87 solo si pasan equivalencia bit a bit y oráculos independientes cuando sean accesibles. El criterio de aceptación seguirá siendo A/B/A o A/B/A/B/A en el TECNO y ahorro significativo de ms/frame, no reducir líneas C.
