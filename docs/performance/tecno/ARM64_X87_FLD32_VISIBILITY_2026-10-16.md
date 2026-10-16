# ARM64 — conversión FLD32 normal en diez PCs de visibilidad (2026-10-16)

**Estado:** implementación optativa OFF por defecto, ensayos y compilaciones ARM64 offline. **No está integrada en una release ni mejora FPS demostrada**. Meta 60 FPS TECNO y calidad gráfica intactas.

## Hallazgo y selección de sitios

En dos perfiles Simpleperf históricos del TECNO, atribuidos al mismo ELF Build ID `80dc3884c64e395f87d7975f200d34edccf648fd`, aparecen repetidamente las funciones de visibilidad alrededor de `0x004d82xx` y `0x004d95xx`. Se consultó p-code **original** de CoDSP SHA-256 `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e` y fuente privada generada p8, SHA-256 `7532b4222eb40b37c5e8bb5491babe3250756f263f5cc2e9b73f2fba7501bdca`. Se eligieron exactamente **10 instrucciones** con un `LOAD` guest seguido de **una única conversión `FLOAT2FLOAT u:4→(r/u):10`**. PCs:
```text
004d82d4 004d82db 004d82f1 004d845b 004d8471
004d94f4 004d94fb 004d9505 004d950a 004d9511
```

No confundir conteos de instrucciones estáticas con ejecución por frame, tiempo CPU exclusivo o FPS: las etiquetas en DWARF y Ghidra pueden atribuir muestras de instrucciones vecinas.

## Cambio implementado

- `tools/recomp/patch_codsp_x87_fld32_visibility.py`: parcheador para la fuente generada privada `codsp_recomp_p8.c`, **no** convierte ni reescribe la RAM ni altera la instrucción LOAD guest, el PC guest o las escrituras x87. Verifica SHA de p-code y fuente, las 10 etiquetas y **una** ocurrencia de la expresión exacta `d2f((f2d(rd(T+...,4),4)),10)` en cada PC. La sustituye únicamente por `codsp_x87_fld32_normal(rd(T+...,4))`.
- Reutiliza `tools/recomp/runtime/x87_fld32_normal.h` ya existente. Para exponentes normales y finitos binary32 realiza la codificación exacta de binary80 usando bits; para cero con signo, subnormal, infinito y NaN mantiene la conversión original completa, sin modificar CW/SW/TOP/tags.
- Impide dobles aplicaciones, archivos desconocidos o parciales, mantiene saltos, padding de bytes x87 y finales LF/CRLF. Restituye al SHA original **byte por byte**.
- `tools/recomp/build_android.py`: `--arm64-x87-fld32-visibility` solo ABI `arm64-v8a`, no `--package-only`, no combina cambios de fuente x87 shift/NaN/FCOM; **OFF default**. Build normal ejecuta la restauración conservadora de p8; no modifica fuentes privadas de otros agentes con marcadores distintos ni genera artefactos rastreados en Git.

## Verificaciones de fidelidad

- `tests/test_arm64_x87_fld32_visibility.py`: **9/9 PASS**, p-code privado cuando existe, guardas/inputs erróneos, source private roundtrip sólo en memoria, fixtures LF/CRLF, ABI/build-flag. Pasa CI pública sin fuentes comerciales mediante skip solo de la parte dependiente de originales.
- `tests/test_arm64_x87_fld32_normal.py`: **7/7 PASS**, preservando los oráculos de conversión existentes.
- En **10 instrucciones reales** generadas desde el p-code pinned, test host C `tests/fld32_visibility_state_smoke.c` comparó el resultado **completo de R (8.192 bytes), U (4 MiB), RAM (16 KiB) y PC** entre A y B. **800 comparaciones A/B por nivel `-O0/-O1/-O2` (2.400 estados en total)**, incluyendo normales, signos, extremos, subnormales, Inf y NaN; **ninguna diferencia**. Test de lecturas guest mapeadas; **no** prueba equivalencia de interrupciones/SEH en RAM no mapeada ni fidelidad íntegra Intel x86.
- La prueba de mapeo inicial del harness detectó un acceso fuera de límites provocado por R4=1 en una instrucción con dirección R4-8 de **ambas variantes**. Corregido a una dirección guest válida antes de aceptar resultados; no fue fallo de runtime.

## Dos APK reales ARM64 (NDK 30; recursos y calidad intactos)

Compilaciones comparadas con el **mismo comando salvo el flag nuevo**:

```text
python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d --jobs 2
python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d --arm64-x87-fld32-visibility --jobs 2
```

| Propiedad | A referencia OFF | B candidato ON |
| --- | ---: | ---: |
| APK SHA-256 | `5c3d8d71f61a3c7b0fff82d6d0fc33421209f6a2c1900f85b964576078c25ee1` | `32e2ed327dc36e9a3755d5a9ea0ad89d72cc6808e281a303e0d6a3d2c4c12c0b` |
| ELF `libmain.so` SHA-256 (sin strip) | `fabe966fe381eb2f5043c236859184b5761562a72640b56abe3a51c523598d5c` | `a8adeb0383994d2139f31efe6e150b607233eb11927c88544f434160028256f7` |
| `.text` bytes | 42.340.100 | 42.340.528 |
| Delta `.text` | — | **+428 bytes** |
| Símbolos dinámicos definidos | 490 | 490 |

En ambos builds el manifiesto, DEX, assets, shaders y todas las demás entradas APK son iguales. Las únicas entradas ZIP distintas son `lib/arm64-v8a/libmain.so` y **tres** firmas `META-INF/`; los **490 nombres/tipos exportados** son idénticos. APKs firmadas v2/v3.

Auditoría de ensamblador de los dos chunks afectados, al comparar los ELF exactos:

| Símbolo | Delta de código | Delta instrucciones AArch64 estáticas |
| --- | ---: | ---: |
| `codsp_chunk_151_spaces` | +64 B | +16 |
| `codsp_chunk_152_spaces` | +356 B | +89 |
| Ambos | **+420 B** | **+105** |

Los otros 8 B del delta de `.text` pertenecen al resto del enlace. **No es una mejora de tamaño** y no se debe afirmar más FPS. La rama normal de cada helper puede usar menos instrucciones **dinámicas** en microensayo anterior FLD32; faltan recuento de llamadas reales, distribución de datos y comparación física controlada.

## Evidencia privada y política de publicación

Archivos ignorados, todos bajo la sesión:
`.local/profiles/runs/tecno/2026-10-16/arm64-fld32-visibility-10-sites/20261016T195551Z-25328-00/`

- `builds/A_visibility_original.apk`, `builds/B_fld32_visibility.apk`, los ELF ARM64 sin strip.
- `reports/full_state_oracle.json`, `reports/apk_elf_ab.json`, `reports/visibility_chunk_opcode_ab.json`.
- `scripts/verify_visibility_full_state.py`, `scripts/audit_apk_elf_ab.py` y auditorías de direcciones; no exportar código C original ni assets comerciales.
- Fuente privada `codsp_recomp_p8.c` **restaurada exacta a SHA-256 original** al terminar B. El build normal final debe quedar restaurado antes de cerrar.

## Cierre de verificación y restauración

- **Suite Python completa:** 548 pruebas, seis omisiones esperadas, **cero fallos**. Incluye nueve tests específicos de la nueva opción, siete del FLD32 anterior y equivalencia host A/B a tres niveles.
- **CTest host:** 40/40 tests correctos (127,77 segundos); regresión GL, RAM, flags, x87 y bibliotecas conservada.
- **Auditoría de artefactos privados:** `pass_with_warnings`, sin errores; 200 scripts históricos, 33 capturas y siete builds archivados verificados; cero rutas privadas rastreadas. Permanece una advertencia histórica de sintaxis en un script no ejecutado y ajeno al cambio.
- **Catálogo:** 138 documentos, cero enlaces rotos; `git diff --check` correcto.
- **Restauración:** `codsp_recomp_p8.c` exacto a SHA-256 `7532b4222eb40b37c5e8bb5491babe3250756f263f5cc2e9b73f2fba7501bdca`. Se reconstruyó con `--arm64-x87-fld32-visibility` OFF y el ELF `libmain.so` resultó **byte por byte igual** al ELF A archivado: SHA-256 `fabe966fe381eb2f5043c236859184b5761562a72640b56abe3a51c523598d5c`. Las 12 entradas internas del APK reconstruido son idénticas a A; el SHA del contenedor APK es distinto por diferencias del contenedor/ZIP y no se interpreta como cambio de código. Resultado privado: `reports/restored_default.apk.json`.
- **CI pública:** [tools-ci 38960304880 PASS](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38960304880) para el commit [`06fb120`](https://github.com/Dr3amyBerry/callofrecomp/commit/06fb1204cc4978344a88012f2c2bb6a1efc45936): análisis y host tests finalizados con estado success. Avisos de deprecación de GitHub Actions ajenos a las pruebas, sin fallos.

## Decisión

**Mantener OFF, disponible como experimento reversible**, sin inventar FPS ni sumar mejoras estáticas. Necesita oráculo x86 original para banderas/errores/estado y prueba física A/B/A/B con mismos guardado, estado, escena y calidad, sobre referencia estable (~22 FPS), antes de proponer la activación. No usar la vieja transformación x87 `double` bloqueada, ni mezclar FCOM/NaN sin nuevo análisis de alias/estado.
