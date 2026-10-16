# ARM64 — desplazamiento aritmético a la derecha estrecho (2026-10-16)

**Estado:** nueva optimización ARM64 experimental, **OFF por defecto**, sin TECNO/ADB. Rama main. **No hay medición nueva de FPS ni prueba completa de comportamiento del juego.** El cambio no activa ni altera el transform double/x87 bloqueado, gráficos, texturas ni calidad.

## Hipótesis y cambio

El helper actual `sar(a,b,n)` extendía en `s128` y ejecutaba un desplazamiento aritmético de **128 bits** para cada `INT_SRIGHT` del traductor, incluso cuando el ancho guest era 1, 2, 4 u 8 bytes. Para `1 <= n <= 8`, el valor ya extendido por `sx(a,n)` cabe exactamente en `int64_t`; desplazamientos con cuenta `b >= 64` tienen exactamente la saturación de signo del original, también para cuentas `u128` con mitad alta no nula. El resultado retorna mediante `(u128)(s128)shifted` para preservar sus **128 bits** (incluida toda extensión de signo).

`tools/recomp/recomp_rt.h` añade la ruta `#ifdef CODRECOMP_ARM64_NARROW_SAR` y deja **literalmente intacta** la expresión original como fallback para ancho 9..16 y todas las builds normales. No enmascara la cuenta x86 fuera del p-code; no desplaza C por 64, 128 o mayores. `android/CMakeLists.txt` añade bandera OFF y rechaza ABI diferente de `arm64-v8a`; `tools/recomp/build_android.py` expone `--arm64-narrow-sar` con validación de ABI. Tests de CLI y política de default.

## Oráculo independiente y emulación ARM64

- `tests/recomp_sar_smoke.c`: referencia independiente bit a bit, **sin** reutilizar `sar`, `sx` ni el operador nativo de desplazamiento con signo. Lee un input desalineado; compara **cada uno de los 128 bits** del resultado, anchos guest 1..16, signos, datos deterministas, cuentas 0/1/7/8/31/32/63/64/65/79/80/127/128/129, excesos, `u128` alto y 2^127. Semilla fija `0x93a728b45`.
- `tests/test_recomp_sar.py`: ambas versiones y `-O0/-O1/-O2`, 1.024 casos por ancho y versión, con compilador host; prueba default/ABI. `tests/test_build_android_profiles.py` rechaza el flag en x86_64.
- Android NDK 30 `-O1` compiló ambas rutas a **AArch64 real**, ejecutadas mediante Unicorn reutilizando el cargador ELF del verificador de dispatch: **4.096 casos por variante, 8.192 ejecuciones de prueba**; valor de retorno 0, LR/SP restaurados, cero divergencias bajo este oráculo. Informes privados: `reports/sar_unicorn.json`; fuentes y ELFs en la sesión privada.
- Wrappers compilados con `-O1` y `-O2`: **SAR ancho 1, 2, 4 y 8**, cada uno, pasa de 60/60/60/56 bytes a 36/36/36/32 bytes (**−24 B o seis instrucciones ARM64 estáticas por wrapper**). Anchos 10 y 16 no cambiaron.

**Alcance:** verificamos la semántica del helper y desplazamientos aritméticos, **no** el estado y excepciones de cada instrucción x86 original durante una partida. La aritmética binary80 general y el control x87 siguen como antes.

## Dos APK completas A/B, mismo NDK y opciones

Comandos:

```text
python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d --jobs 2
python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d --arm64-narrow-sar --jobs 2
```

En B, `CODRECOMP_ARM64_NARROW_SAR:BOOL=ON` confirmado en CMakeCache y Ninja. En A el flag estaba OFF. Ambas APKs firmadas v2/v3. Se preservaron inmediatamente los ELF sin strip y APK independientes.

| Propiedad | A sin SAR nuevo | B con SAR nuevo |
| --- | ---: | ---: |
| Sección ARM64 `.text` | 42.340.100 B | **42.339.916 B** |
| Delta `.text` | — | **−184 B** |
| Exportaciones definidas | 490 | 490 |
| APK SHA-256 | `ce8143c5fc7b5b493b6cb192f22c3d446658654c195dd570ec4742053f2e7fd4` | `91f97afc10fe4ac623d32f0972927cb249bc2da1e94a8db533fd73c10782fd9a` |
| ELF nativo sin strip SHA-256 | `fabe966fe381eb2f5043c236859184b5761562a72640b56abe3a51c523598d5c` | `bd8702b9e83fa85243e90d2ff7e93967e2cfbd92e08820eda7585a85e5464b7b` |

El comparador validó **idéntico nombre/tipo de los 490 símbolos**, y exactamente cuatro entradas ZIP distintas: `lib/arm64-v8a/libmain.so` y tres archivos de firma `META-INF/`. Recursos, Dex, manifiesto y otras bibliotecas no cambiaron.

Los únicos cinco chunks `codsp_chunk_72/153/158/199/200_spaces` cuyo tamaño varió redujeron **−40/−32/−32/−32/−40 bytes** (total **−176 B, −44 instrucciones AArch64 estáticas**); el cambio global enlazado es −184 B. Los recuentos de instrucciones y opcodes son **estáticos**, no ciclos medidos ni llamadas ejecutadas por fotograma. El resto de cambios pequeños en símbolos auxiliares no constituye un cambio ABI.

## Evidencia privada

`.local/profiles/runs/tecno/2026-10-16/arm64-narrow-sar-compiler-probe/20261016T112204Z-23016-00/`

- `scripts/sar_probe.c`, `scripts/sar_measure.py`, `scripts/verify_sar_aarch64.py`: probe sintético, compilación NDK y Unicorn.
- `reports/sar_probe_result.json`, `reports/sar_unicorn.json`, `reports/narrow_sar_elf_ab.json`, `reports/sar_chunk_opcode_ab.json`, `reports/narrow_sar_all_function_deltas.json`.
- `builds/A_narrow_sar_off.apk`, `builds/B_narrow_sar_on.apk`, ELF sin strip y ELF sintéticos.
- Los resultados de ELF se refieren a **estos hashes A/B**, no a direcciones PC de un perf.data histórico diferente.

## Decisión

Conservar `--arm64-narrow-sar` como **opt-in OFF**, por ahorro nativo limitado y sin evidencia física. No sumar ahorro por wrapper para inventar FPS. Al disponer del TECNO, repetir A/B/A/B con checkpoint, escena, calidad y guardados idénticos; comparar las 40 ventanas de FPS, CPU/frame, estabilidad y capturas, y restaurar referencia original. Revertir activación si hay regresión o divergencias reales x86/estado/partidas. Este bloque no modifica el teléfono ni datos comerciales.

## Regresiones completadas

- Suite Python completa: **539 pruebas, 6 omitidas, cero fallos**.
- CTest host: **40/40** aprobadas.
- Oráculo unitario específico `test_recomp_sar.py`: 2/2; pruebas de argumentos del builder: 15/15.
- Builder compiló y firmó ambas APK ARM64 sin fallos, A con flag OFF y B ON; ABI, entradas ZIP y código comparados sobre las copias privadas exactas.
- Verificador de artefactos privados: 200/200 scripts, 33/33 capturas y 7/7 builds anteriores; cero rutas privadas tracked. Hay una advertencia histórica preexistente de sintaxis en un script legado no ejecutado, fuera de esta modificación.
- Catálogo documental: **136 documentos** sin enlaces rotos. `git diff --check` limpio. GitHub Actions debe verificarse después del push.
