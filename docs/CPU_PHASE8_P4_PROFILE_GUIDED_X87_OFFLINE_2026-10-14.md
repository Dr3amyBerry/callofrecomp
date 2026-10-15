# Fase 8 — selección x87 por muestras históricas y PC original (offline)

**Fecha:** 2026-10-14
**Proyecto:** CallofRecomp / CoDSP 1.5 / recompilación x86 → Android ARM64.
**Estado:** implementado, oráculo diferencial aprobado en PC, APK ARM64 experimental compilada. **OFF por defecto, NO desplegado, no hay FPS nuevos.** No se usó el TECNO ni ADB.

## 1. Por qué no continuar expandiendo ciegamente la conversión x87

La fase 6 aplicó el convertidor `codsp_x87_normal_f2d` a toda CoDSP `p4` y elevó `libmain.so` `.text` **211.432 bytes**, con coste dinámico y de I-cache desconocido. La fase 7 restringió la conversión a **520 sitios C / 276 PCs x86** de cuatro funciones originales calientes, reduciendo el crecimiento a **34.196 bytes**. Ninguna variante se ha probado en gameplay físico.

En esta fase no se cambió el conversor, la precisión x87, la aritmética, el motor ni las texturas. Se seleccionó un subconjunto más concentrado, basándose en **CPU real previamente capturada**, sin capturas nuevas.

## 2. Reconstruir muestras x87 en sus instrucciones originales

Se reprocesaron los dos perfiles archivados `strategy_spawn_cpu_v1.perf.data` y `strategy_spawn_cpu_v2.perf.data`, ambos de un ELF `libmain.so` histórico con Build ID comprobado `80dc3884c64e395f87d7975f200d34edccf648fd`. No usar un `libmain.so` reconstruido recientemente para simbolizar las capturas antiguas.

Con `llvm-addr2line -a -f -C -i` se conservaron **los marcos de inline DWARF** (en lugar de la sola primera línea de `memcpy`, `rd`, `f2d`, etc.). La línea exterior de `codsp_recomp_p4.c` se correlacionó con la etiqueta previa `L_<guest PC>:` del C privado original, mediante una búsqueda ordenada de líneas. El análisis usa **PCs de guest x86**, nunca direcciones ARM64 como si fueran PCs originales.

| Conteo de muestras CPU atribuibles a chunks p4 examinados | Captura v1 | Captura v2 |
| --- | ---: | ---: |
| Muestras identificadas en los chunks nativos examinados | 1.017 | 889 |
| Con PC de instrucción original recuperado por DWARF inline | 974 | 840 |
| Muestras en `f2d` atribuidas a las cuatro funciones de fase 7 y llamadas `f2d(rd(...),10)` | 240 | 218 |
| PCs originales distintos con `f2d` observado | 141 | 131 |

En las dos capturas, **458 muestras** de esas conversiones corresponden a **190 PCs distintos** (82 PCs aparecen en ambas capturas). Con el criterio predefinido de **al menos 2 muestras combinadas por PC**, quedan **124 PCs** y **392 de 458 muestras (85,6 %)**. Es cobertura de muestreo histórico del subconjunto estudiado, **no una tasa de ejecución, de acierto, de ciclos ahorrados, ni de FPS**. Este criterio evita seleccionar direcciones vistas una sola vez, pero puede subestimar códigos que el muestreo de 350 Hz no registró.

Las rutas privadas de `perf.data`, las direcciones ARM64, los perfiles y los C propietarios originales permanecen ignorados en `.local/profiles/`. Se versiona solamente un manifiesto compacto de **124 identificadores numéricos de PC invitado** en `tools/recomp/codsp_p4_profiled_pcs.py`: ningún byte de PE, p-code, assets, mapas, texturas o guardados.

## 3. Código nuevo y protecciones

- `tools/recomp/patch_codsp_p4_f2d_selective.py` ahora soporta `--profiled` junto a `--apply`, `--restore`, `--analyze`; conserva intacta la opción de fase 7 (`--profiled` no está activo por defecto).
- La opción de esta fase reemplaza exactamente **277 llamadas `f2d(rd(...),10)` en 124 PCs invitados**. Las demás conversiones de p4 mantienen el `f2d` original. Se reutiliza el helper **inline** con fallback exacto; no se reintroduce la variante `noinline` de fase 6 rechazada por un caso de NaN.
- Se verifica el SHA-256 del p-code original `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e`, el C original p4 `ee9156183cc0410bf0641592f93d3d0efa4febc906cc014969ddb30d95a196d3` y el C perfilado `9b3d27670850fcdad26b7318374e7614102650e5d03825c4b28843e6be444b90`. No se reescriben versiones no reconocidas del juego.
- `tools/recomp/build_android.py` añade `--x87-normal-f2d-p4-profiled`: requiere ARM64 y `--x87-normal-f2d`, es mutuamente excluyente con `--x87-normal-f2d-p4` integral y `--x87-normal-f2d-p4-selective` de fase 7. La compilación normal restaura automáticamente **cualquiera de los dos parches existentes** antes de continuar.
- `android/CMakeLists.txt` añade `CODRECOMP_X87_NORMAL_F2D_P4_PROFILED=OFF` por defecto; exige ambos SHA-256 verificados y flags compatibles. No cambia p1, p8, el despachador, renderer o librerías gráficas.
- `tests/test_selective_p4_f2d.py` contrasta compatibilidad de modos, selección PC exacta, restauración reversible, entradas ajenas, hashes, idempotencia y errores seguros. `tests/test_build_android_profiles.py` prueba los rechazos de flags y la disponibilidad del opt-in.

## 4. Equivalencia sin teléfono y binarios construidos

Se extrajeron **22 instrucciones flotantes reales** de las cuatro funciones originales: seis de `0x00475D80`, seis de `0x00476070`, cuatro de `0x004766E0` y seis de `0x0047BD40`. Son únicamente instrucciones completas, válidas y seleccionadas por el nuevo manifiesto de PCs; no se inventó el p-code ausente en una instrucción de `0x0047BD40`.

Se comparó el traductor original vs la variante con el convertidor `binary80` inline selectivo: **22.000 estados con Clang `-O1` y otros 22.000 con `-O2`: 44.000 comparaciones completas de registros arquitectónicos `R`, RAM de prueba y `PC`, sin diferencias**, incluyendo entradas especiales x87 (NaN, infinito, subnormales). **No es un oráculo independiente de una CPU Intel x86**, ni certifica los 277 sitios completos.

La compilación ARM64 B se hizo exclusivamente con el NDK en el PC, se firmó (APK Signature Scheme v2/v3), y se archivó sin instalar bajo `.local/profiles/phase8_p4_profiled/`.

| Variante ARM64 | `libmain.so` sección `.text` | Crecimiento vs A |
| --- | ---: | ---: |
| Referencia A: fast path de p1/p8 ya aceptados | 42.339.912 bytes | 0 |
| Fase 6: conversión en todo p4 | 42.551.344 bytes | +211.432 |
| Fase 7: 520 conversiones | 42.374.108 bytes | +34.196 |
| **Fase 8: 277 conversiones en 124 PCs** | **42.359.988 bytes** | **+20.076** |

La fase 8 evita **14.120 bytes más que fase 7**, y **191.356 bytes del crecimiento de fase 6 (~90,5 %)**. Solo cambian **3 símbolos de chunk ARM64**, igual que en fase 7, con diferencia neta de tamaño de símbolos de **+20.140 bytes**, que no equivale exactamente a `.text` por alineación y otros detalles de enlace. **Estas cifras son código compilado, no instrucciones ejecutadas por frame ni mejoras de FPS comprobadas**.

SHA-256 APK experimental B: `dc79bbfc0c6c9711ada54cf4e6b53270b643a5e8eeea4c73513067b0bb712c53`. SHA-256 ELF sin strip: `b8e07e4fec218c2661949b5e68d5fef6447b53cdc667db52550a8994ccfd75c6`. No publicar archivos del juego, binarios/APK o perfiles.

## 5. Decisión y cierre seguro

**La opción perfilada sigue desactivada.** Aunque el muestreo y los resultados matemáticos respaldan una candidata más concentrada y un menor crecimiento de código, no se conoce su impacto dinámico sobre CPU/frame, caché de instrucciones, fotogramas ni jugabilidad. El objetivo de 60 FPS permanece pendiente.

**Controles de cierre aprobados:**

- Suite completa **253 pruebas Python (4 omitidas), 34/34 CTest** correctas.
- Recompilación normal con `CODRECOMP_X87_NORMAL_F2D_P4_PROFILED=OFF`, `CODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE=OFF`, `CODRECOMP_X87_NORMAL_F2D_P4=OFF`, `CODRECOMP_X87_NORMAL_F2D=ON`, `CODRECOMP_HOT_X87_FASTPATH=ON` y caché experimental de despacho OFF.
- C p4 restaurado al SHA original, ELF `libmain.so` nativo y biblioteca empaquetada idénticos **byte a byte a la referencia A** por SHA-256. ELF A `2c946984d2da41a5df31b48bb1bf3700f64fb6f801d043748332c619eac695e5`.
- La APK candidata B quedó en directorio privado ignorado; no se instaló, no se modificó guardado alguno. Git contiene solo código, pruebas, manifiesto numérico y documentación.

Al poder reutilizar el TECNO *solo cuando el usuario lo autorice*, preparar A/B/A/B en la misma escena y calidad, con seguimiento de temperatura y CPU real. Mientras tanto, continuar análisis offline y no activar optimizaciones sin resultados medibles.
