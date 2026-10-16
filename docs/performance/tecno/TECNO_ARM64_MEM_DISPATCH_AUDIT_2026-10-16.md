# TECNO ARM64 — reducción de accesos a memoria y dispatch: resultados físicos y offline

**16 de octubre de 2026 (UTC); estudio privado:**
`.local/profiles/runs/tecno/2026-10-16/arm64-memory-hot-block-optimization/20261016T022418Z-18012-00/`

**Resultado: ninguna ganancia nueva validada; no se integraron modificaciones de CPU ni se alteró la calidad del juego.** Todos los experimentos se realizaron en el TECNO CK6n físico o con LLVM/Unicorn AArch64. No se usó WSA para obtener FPS ARM64. Las opciones probadas siguen OFF por defecto.

## 1. Caché de entrada de dispatch `--arm64-dispatch-entry-cache`

Se reutilizaron, sin recompilar ni combinar cambios, los APK A/B SHA fijados del estudio [ARM64_DISPATCH_ENTRY_CACHE_2026-10-15.md](ARM64_DISPATCH_ENTRY_CACHE_2026-10-15.md). El procedimiento oficial `tools/recomp/diagnostics/android_abab.py` verificó guardado, APK, imagen de escena y 40 ventanas de FPS.

| Pasada | FPS mediana | CPU ms/frame | Estabilidad | Interpretación |
| --- | ---: | ---: | --- | --- |
| A1, sin caché | 22,00 | 43,625 | Aprobada | Referencia |
| B1, con caché | 21,55 | 44,555 | Aprobada | −0,45 FPS y +0,930 ms |
| A2, sin caché | 21,65 | 44,295 | Aprobada | Referencia repetida |
| B2, con caché | 17,00 | 56,585 | **Rechazada** | FPS cambió ~16,7→21,7 durante captura; deriva de extremos **+29,94 %**, deriva entre mitades **+29,64 %** |

**Veredicto:** `B2 stability gate failed: ['edge_drift', 'half_drift']`; A/B/A/B **inconcluso**. No calcular medias de cuatro pasadas ni presentar regresión o ganancia concluyente. El primer par tuvo un resultado desfavorable, pero no demuestra comportamiento sostenido. La caché puede ahorrar instrucciones cuando se repite un chunk, pero perjudica misses en el ensayo Unicorn ya documentado; faltan tasas de aciertos medidas físicamente.

El corredor terminó en `failed`, `restored: true`. Una comprobación independiente confirmó restauración del APK **0.2.4 original**
SHA-256 `fb8647c34dfe8fd269c0902f34edcc4c0844b18c6aa13ff6006232678da25f70`
y del guardado `training.svg`
SHA-256 `efbc68e54fabc79946dfd3a9d188e5f6ba284b1aad99130bbe2726eb637f64f8`.
La temperatura de batería llegó a **40 °C**, por lo que no se inició inmediatamente otro ensayo.

## 2. Enlace local de `R/MEM/U/PC`: intento de repetición

Se volvió a preparar una comparación con los APK ARM64 verificados de [ARM64_WSA_LOCAL_STATE_BINARY80_2026-10-15.md](ARM64_WSA_LOCAL_STATE_BINARY80_2026-10-15.md), de idéntico juego y calidad. La batería bajó a **38 °C** antes de comenzar.

**A1 falló la guarda de referencia externa**: `Non-comparable baseline; stop before B`. No se registraron ventanas válidas de 40 segundos ni se instaló B. El resultado anterior de **+13,03 % bruto** contenía una A1 muy inestable y **no debe anunciarse como mejora**.

El corredor terminó en `failed`, `restored: true`, sin pasadas completas; verificación independiente confirmó SHA originales de APK/partida. El motivo físico de pasar ocasionalmente de ~17 a ~22 FPS con la misma APK permanece **sin aislar**; no atribuir esas oscilaciones a compilación u optimización.

## 3. Prueba de reducción directa de lecturas de tabla de dispatch

Se probó un fast path AArch64 para la primera entrada válida de `dispatch_index_find`, con comparación unsigned por rango, luego una variante que lee conjuntamente `start/end` en un `uint64_t`. Ambas conservaron el contrato de rangos, gaps y callbacks en el smoke AArch64/Unicorn, pero **aumentaron el trabajo dinámico**. Resultados de 512 callbacks sintéticos por patrón, misma semilla/oráculo:

| Patrón | Baseline instrucciones / bytes tabla | Prototipo instrucciones / bytes tabla |
| --- | --- | --- |
| Mismo chunk | 18.482 / 9.796 | 19.284 / 11.400 |
| Rachas de 8 | 16.853 / 9.072 | 17.293 / 9.952 |
| Alternancia de 2 | 17.069 / 9.168 | 17.557 / 10.144 |
| Aleatorio 403 | 16.763 / 9.032 | 17.183 / 9.872 |

La segunda variante produjo los mismos conteos. **Ambas fueron descartadas, sin APK ni benchmark físico.** `tools/recomp/runtime/dispatch_index.h` quedó restaurado byte a byte al estado previo (sin diff Git). La reducción de comparaciones en C no implica menos cargas/instrucciones máquina.

## 4. Autocopias y áreas calientes

El p-code contiene **1.706 autocopias** `COPY(r→la misma r)` o de espacio único; en la función más caliente `0x005061B0` no se encontraron autocopias. Clang AArch64 `-O1` redujo un test de autocopia de 4 bytes al mismo `ret` que una función vacía; eliminarlas en el generador **no ahorraría instrucciones para ese caso**.

El perfil físico previo atribuyó ~**509 muestras** a `0x005061B0` (dentro de 3.692 de `libmain.so`). Allí hay 58 instrucciones originales, 57 con oportunidades de caché de registros, pero **46 involucran LOAD/STORE**. Hoisting de R o supresión de escrituras entre operaciones que puedan fallar puede dejar registros/x87/PC inconsistentes al ocurrir un fallo; los trabajos anteriores detectaron precisamente este riesgo en CFG14. No aplicar transformaciones agresivas sin prueba completa de excepciones y observabilidad.

**Siguiente bloque recomendado:** perfilar con el TECNO frío la causa de la alternancia entre estados estables ~17 y ~22 FPS antes de declarar ganancias inferiores al 1 %. Para rendimiento, reducir trabajo dinámico en `0x005061B0` mediante un backend binary80 **correcto** o una optimización de R no diferida a través de accesos/fallos; exigir oráculo x86 exacto y A/B/A/B físico. No reactivar `--hot-x87-transform`, bloquear vías que cambien jugabilidad, geometría o calidad.

## Evidencia y disposición

- Caché: `.local/profiles/runs/tecno/2026-10-16/arm64-memory-hot-block-optimization/20261016T022418Z-18012-00/reports/abab-result.json`, `metrics/*-stability.json`, `captures/` (privadas).
- Variante rango descartada: `raw/dispatch-range-fast-unicorn/` y `raw/dispatch-range-paired-v2-unicorn/`; nada de sus cambios queda en el árbol Git.
- Intento enlace local: `.local/profiles/runs/tecno/2026-10-16/arm64-local-guest-state-stable/20261016T024547Z-19724-00/reports/abab-result.json` (rechazo anterior a B).

**Estado final:** APK segura 0.2.4 y partida originales verificadas por SHA, `main` sin modificaciones de motor, todas las opciones experimentales OFF por defecto.
