# ARM64 — especialización selectiva de 16 desplazamientos dinámicos INT_LEFT (2026-10-16)

**Estado:** experimento implementado, opt-in **OFF por defecto**, pruebas del helper y compilación Android A/B completas. **No hay medición de FPS ni validación de una partida TECNO en esta sesión.** La calidad, shaders, texturas, archivos de guardado y assets del juego no se han editado.

## Cribado de la oportunidad (evitar trabajo inútil)

Código original: CoDSP.exe 1.5, p-code SHA-256 `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e`.

- Hay **9.869 operaciones `INT_LEFT`** en todo el CoDSP original, de las que **2.487** emplean desplazamiento **variable**.
- En las regiones de perfil histórico de geometría `[0x004196f0,0x00419ed6)` y visibilidad `[0x004d8000,0x004d9600)`, hay **289** `INT_LEFT`: **273** con cuenta constante (272 de 8/9/10/14 bits y una de 32 bits) y **16** con cuenta variable.
- Clang NDK 30 generó **delta 0 B** para los shifts constantes ensayados a `-O1/-O2`; no se modifican. Los wrappers dinámicos de resultado 1/2/4/8 bytes ahorraron **8–12 B** a `-O1/-O2`. No extrapolar ahorros de wrappers directamente al juego.
- El conjunto de 16 sitios reales se verificó exhaustivamente contra la fuente C generada: **4 p0 + 12 p8**, cada expresión original aparece exactamente una vez en su PC invitado. Los restantes miles de operaciones permanecen intactos.

## Cambio conservador

- `tools/recomp/recomp_rt.h`: helper sin efectos secundarios `codsp_arm64_narrow_shl(a,b,output_bytes)`. Cuando el resultado ocupa 1–8 bytes, descarta el overflow fuera del resultado, usa desplazamiento `uint64_t` solo para cuenta estrictamente menor que `8*output_bytes` y devuelve cero para overshifts; para otros anchos conserva `shl` original. La `mask(...,output_bytes)` y la operación guest emitida siguen en su lugar. Para estas 16 instrucciones, ninguno de los operandos es un acceso guest directo `m:` con orden de fallos que pudiera alterarse.
- `tools/recomp/patch_codsp_narrow_left_shift.py`: exige fuente privada original con SHA exacto **p0** `e0ed2e6a861104460f2413fae06b5074d5dddf2a95ba4896c6bef47552fffb02` y **p8** `7532b4222eb40b37c5e8bb5491babe3250756f263f5cc2e9b73f2fba7501bdca`, además del p-code fijado; valida PC, op, registro, ancho y expresión emitida exactos. Cambia una expresión por línea y agrega marcador, sin mover labels, índices p-code o números de línea. Rechaza cambios desconocidos, dobles aplicaciones y restauraciones parciales, usa archivos staging y recupera hashes originales **byte por byte**.
- `tools/recomp/build_android.py`: flag experimental `--arm64-narrow-left-shift`, exclusivamente `arm64-v8a` y build completo; rechaza mezclar parches de fuente x87 sobre los mismos p0/p8. En builds sin el flag intenta restaurar cualquier estado marcado antes de aplicar otros parches. El valor por defecto no cambia fuentes privadas.

## Oráculos y límites

- `tests/recomp_left_shift_smoke.c` + `tests/test_arm64_narrow_left_shift.py`: **12.288 casos por nivel de compilación**, `-O0`, `-O1`, `-O2` (**36.864 casos host**) con valores de entrada de 128 bits, conteos 0/1/7/8/15/16/31/32/63/64/65/80/127/128/129/255, grandes y con mitad alta no cero. Oráculo independiente, reconstruye bit a bit cada resultado, conserva bytes de registro fuera del ancho escrito. Pruebas del parcheador y CLI también pasan.
- Compilación AArch64 real con NDK 30 y ejecución bajo **Unicorn**: **8.600 llamadas emuladas** para referencias y candidatos, 1.075 pares de inputs en 4 anchos de resultado; PC y SP de retorno comprobados, sin discrepancias. Funciones candidatas de ejemplo ahorraron 8 B cada una. Esto **no** equivale a un oráculo integral original Intel x86 de PC/RAM/EFLAGS/x87/SEH para una partida.
- Transformación y reversión exactas de fuentes originales verificadas primero en memoria; no se incluyeron C comerciales en Git.

## Comparación de APKs ARM64 reales (mismo comando salvo un flag)

```text
A: python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d --jobs 2
B: python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d --arm64-narrow-left-shift --jobs 2
```

A reutiliza la APK/ELF original de la sesión anterior, validada por SHA antes de B. Ambas firmadas v2/v3.

| Medida | A sin SHL nuevo | B experimental |
| --- | ---: | ---: |
| Sección ELF `.text` | **42.340.100 B** | **42.340.056 B** |
| Cambio `.text` | — | **−44 B** |
| Exportaciones dinámicas | 490 | 490 |
| APK SHA-256 | `5c3d8d71f61a3c7b0fff82d6d0fc33421209f6a2c1900f85b964576078c25ee1` | `ee7675ee972706adaf5852712e1c4a20c9dca30c1484de75d2daa4675b9ae099` |
| ELF `libmain.so` SHA-256 | `fabe966fe381eb2f5043c236859184b5761562a72640b56abe3a51c523598d5c` | `0daeaf6b8d9e5863bcf059cd69fef79cf8701ea83d47264f6be70240cf637fda` |

Manifest, DEX, recursos y otras bibliotecas: **idénticos**. Únicamente cambia `lib/arm64-v8a/libmain.so` y tres entradas de firma `META-INF/`; los 490 símbolos dinámicos definidos (nombre/tipo) son iguales.

| Chunk con sitios hot | Delta código AArch64 | Delta instrucciones estáticas |
| --- | ---: | ---: |
| `codsp_chunk_18_spaces` (geometría) | **−4 B** | **−1** |
| `codsp_chunk_151_spaces` (visibilidad) | 0 B | 0 |
| `codsp_chunk_152_spaces` (visibilidad) | 0 B | 0 |

Los otros **−40 B** de `.text` corresponden al resto del enlace/disposición de símbolos, **no** a 40 B probados de código caliente; solamente uno de los cuerpos nativos inspeccionados redujo una instrucción. Histograma de opcodes estáticos p8 sin cambios; aun con histograma igual no se asegura código byte idéntico. No es una ganancia de FPS ni suficiente para el objetivo de 60 FPS.

## Evidencia privada

Sesión ignorada: `.local/profiles/runs/tecno/2026-10-16/arm64-narrow-left-shift-audit/20261016T202854Z-8176-00/`

`reports/narrow_shl_audit.json` (conteo + NDK O1/O2), `reports/hot_shl_line_proof.json`, `reports/narrow_left_unicorn.json`, `reports/arm64_narrow_left_ab.json`, `reports/narrow_left_hot_chunks.json`, `reports/native_symbol_size_deltas.json`; C y scripts específicos solo en `scripts/`, APK y ELF B en `builds/`. La APK A archivada en la sesión privada inmediatamente anterior permanece sin cambio.

## Veredicto

**Conservar la implementación reversible OFF**. Se ahorran unos pocos bytes nativos, con correctness de aritmética y ABI bajo los oráculos disponibles; las dos rutas de visibilidad no reducen de tamaño y el runtime global sigue muy lejos de 60 FPS. No convertir ahorro de código en ciclos/FPS inferidos. Si vuelve el TECNO, priorizar resolver la alternancia ~17 vs ~22 FPS con la misma APK antes de nuevas pruebas A/B/A/B, protegiendo guardados, gráficos y equivalencia x86.

La reversión de fuentes p0/p8 se ejecutó al finalizar B y ambas volvieron **exactamente** a los SHA originales. La reconstrucción Android sin el flag terminó `exit_code=0` con firma v2/v3. **La sección ejecutable `.text` de la ELF restaurada (42.340.100 B) coincide byte por byte** con A: SHA-256 `b5b0867a08b4e9247b654d1ca422c8098ea5d6eaf9db3f7a10a6a505227f45e0`. El hash del ELF completo restaurado es distinto (`0882cb331cb6f04f66984bb75da843aaf8fa8277a2591fbcce8b0efee56ac14f`) por diferencias **fuera de `.text`**, sin atribuirlas a una causa concreta. Recursos/manifiesto/dex idénticos; cambian `libmain.so` y tres firmas META-INF del APK reempaquetado. `reports/restored_default_check.json`.

**Regresiones locales completas:**
- `python -m unittest discover -s tests`: **553 tests, 6 omitidos, 0 fallos** (108,278 s).
- `ctest --test-dir .local/builds/build --output-on-failure`: **40/40 aprobados** (147,61 s).
- Auditoría de artefactos privados: `pass_with_warnings`, cero errores y **cero rutas privadas rastreadas**. Advertencia preexistente: script Python histórico no ejecutado con sintaxis inválida.
- Índice documental: **139 documentos y 0 enlaces rotos**. `git diff --check` aprobado.
- GitHub Actions: verificar el nuevo commit público después del push; la CI anterior no valida automáticamente esta modificación.
