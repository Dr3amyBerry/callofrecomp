# ARM64 — investigación de rutas calientes y descarte de extensión de signo (2026-10-16)

**Estado:** investigación offline sin TECNO, ADB ni instalación; **ningún cambio de runtime ni nueva mejora de FPS**. Código `main` base `e380106`. Las capturas originales pertenecen a un ELF histórico de identidad fija, **no** a las APK candidatas posteriores; no confundir observaciones.

## 1. Comprobación del compilador: `sx` directo no mejora el código

La hipótesis era sustituir el sign-extend actual `sx(u128,n)` por casts explícitos `int8_t/int16_t/int32_t/int64_t` para anchos 1/2/4/8 bytes, conservando fallback para el resto.

Una prueba aislada de funciones nativas reales, Android NDK 30 Clang AArch64, compiló las dos implementaciones en `-O1` y `-O2` para tamaños de operando **1,2,3,4,5,6,7,8,9,10 y 16 bytes**. `llvm-nm -S` confirmó **delta 0 bytes en las 11 funciones, tanto con O1 como O2**. No se integró el cambio de código: no hay ahorro demostrado en el wrapper; el mismo tamaño tampoco garantiza ensamblado byte a byte idéntico o ausencia de efectos de presión de registros.

Evidencia en sesión privada:
`.local/profiles/runs/tecno/2026-10-16/arm64-sign-extend-cost-audit/20261016T192659Z-8632-00/reports/sx_probe.json`.

## 2. Perfiles físicos anteriores revalidados, sin mezclar Build IDs

Se volvieron a ejecutar `tools/recomp/diagnostics/prioritize_profiled_cpu.py` y `attribute_cpu_hot_microops.py` para las capturas `v1`/`v2` archivadas (capturas distintas). Los dos clasificadores verificaron huella de procedencia y el ELF original exacto:

- ELF Build ID **`80dc3884c64e395f87d7975f200d34edccf648fd`**.
- v1: **7.953** muestras del proceso, 6.675 de `libmain.so`; v2: **6.541** del proceso, 5.491 de `libmain.so`.
- Los ocho cuerpos x86 seleccionados reúnen **1.557** y **1.244** muestras (19,578 % y 19,018 % del proceso), respectivamente.
- Dentro de esos cuerpos, muestras atribuidas a una *instrucción x86 asociada* al estado x87: **1.255/1.557** y **1.005/1.244** (80,6–80,8 % del subconjunto). Las otras etiquetas exclusivas son memoria sin x87: 191/150, y resto entero: 111/89.
- **Importante:** muestra sobre PC host atribuida por línea a instrucción x86, no medida exclusiva de x87 ni ejecución de microoperaciones; las categorías de FLOAT/LOAD/flags se solapan.

`16` PC invitados aparecen simultáneamente en el top-20 de instrucciones etiquetadas de cada perfil. Se comprobó el p-code original de CoDSP SHA-256 `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e`.

| PC x86 repetido | Muestras v1 / v2 | P-code del sitio |
| --- | ---: | --- |
| `0x004d9511` | 55 / 35 | 30 microoperaciones; `FLOAT_NAN` ×2, `FLOAT_LESS`, `FLOAT_EQUAL`, `FLOAT2FLOAT`, 9 `COPY` y actualización de flags x87 |
| `0x004d82db` | 27 / 27 | `LOAD` guest + `FLOAT2FLOAT` + `FLOAT_MULT` |
| `0x004d82f1` | 27 / 25 | 30 microoperaciones, familia de comparación/NaN/copia x87 |
| `0x0042b11e` | 21 / 21 | entero puro con `LOAD` + `INT_MULT`, sin x87 |
| `0x004d94fb` | 24 / 19 | `LOAD` + `FLOAT2FLOAT` + `FLOAT_MULT` |
| `0x0041b986` | 17 / 18 | 28 microoperaciones, comparación/NaN/estado x87 |

Estos números identifican PCs donde examinar ensamblador en el ELF **correcto**; **no** certifican ahorro de ciclos por microoperación ni FPS.

## 3. Evitar duplicar optimizaciones ya investigadas

El patrón caliente de `0x004d9511` corresponde precisamente a familias cubiertas en proyectos experimentales previos:

- `--x87-nan-bits`: 1.178 sitios estáticos en CoDSP p1/p8 y 955.360 entradas binarias probadas contra el runtime anterior, pero A/B/A/B/A físico inconcluso (referencia posterior mejoró por sí sola). Ver [NaN](ARM64_X87_NAN_BITS_2026-10-14.md).
- `--x87-fcom-fastpath`: 448 bloques de comparación binary80/binary32 en p1/p8, 151.638 ensayos de estado contra el runtime anterior y aproximadamente **−709.600 bytes** de `.text`; **B1 26,15 FPS / B2 19,80 FPS**, contradicción física grave frente a A alrededor de 25 FPS. Mantener OFF; se verificó contra runtime, **no** un oráculo Intel x86 completo ni todos los estados de falla/SEH. Ver [FCOM](ARM64_RENDERER_CPU_FCOM_2026-10-14.md).
- **No** reactivar `--hot-x87-transform` inseguro en ningún build: la vía antigua aproximaba binary80 por `double` y no pasó la comparación contra x86 original. Los informes anteriores que lo utilizaron son historia, no permiso de activación.

## 4. Próxima hipótesis que sí merece inversión

Investigar eliminación de escrituras **realmente muertas** de flags/temporales (EFLAGS, estado x87, `R`, `U`) mediante un **análisis conservador de vida interbloques**, que modele side entries y callbacks, alias con MEM, lectura de estado por módulos, rutas SEH/fallos y checkpoints. Nunca eliminar escrituras de flags basándose solo en adyacencia textual o en porcentajes de muestra. Antes de un parche:

1. Elegir 1–2 PCs calientes repetidos, consultar p-code/CFG exactos y presentar prueba formal/estática de no lectura antes de sobreescritura en **todas** las salidas relevantes.
2. Oráculo independiente contra x86 original: GPR, EFLAGS, PC, RAM, todo binary80, TOP/CW/SW/tag, aliasing y comportamiento de fallos, no solo p-code C contra sí mismo.
3. Inspeccionar disassembly ARM64 actual y medir ahorro de cargas/stores y spills *del mismo símbolo, ABI, flags y ELF*. Si no hay ahorro, rechazar.
4. Con TECNO disponible, reproducir estado físico de referencia ~17 vs ~22 FPS de **la misma APK** antes de atribuir diferencias a un cambio, y realizar A/B/A/B con las guardas de escena, calidad y guardado.

No se realizaron nuevas pruebas físicas, ni se instaló APK, ni se cambiaron archivos privados del juego.

## Evidencia reproducible

Sesión privada:
`.local/profiles/runs/tecno/2026-10-16/arm64-sign-extend-cost-audit/20261016T192659Z-8632-00/`

`reports/sx_probe.json`, `reports/archived_rank.json`, `reports/archived_phys_v1.json`, `reports/archived_phys_v2.json`, `reports/hot_pcode_sites.json`; fuentes experimentales de solo análisis en `scripts/`. Historial comercial y perfiles raw permanecen fuera de Git. El estado de optimización sigue **sin cambio y opt-in/OFF**.
