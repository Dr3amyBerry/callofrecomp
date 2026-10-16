# TECNO ARM64 — FLD32 exacto en CoDSP 0x005061B0

**16 de octubre de 2026 UTC. Estado: IMPLEMENTADO, verificado offline, opt-in OFF. FPS físicos: pendientes.**

## Qué cambia

La función original 0x005061B0 (58 instrucciones x86) contiene 39 conversiones de float32 a binary80. La ruta anterior pasa por double antes de codificar 80 bits. Un float32 **normal y finito** cabe exactamente en binary80: el nuevo helper codsp_x87_fld32_normal construye el exponente y significando con operaciones enteras. Para ceros con signo, subnormales, infinitos y qNaN/sNaN conserva literalmente la ruta previa d2f(f2d(raw,4),10).

El cambio mantiene el LOAD desde la RAM guest y las escrituras x87 **en su ubicación original**. No guarda valores R pendientes a través de posibles fallos de RAM ni modifica estado PC, CW, SW, TOP, tags, flags, otros módulos o calidad gráfica. Es equivalencia frente al runtime C actual; no afirma fidelidad completa frente a todas las excepciones del x87 real, que ese runtime todavía no implementa.

El parche tools/recomp/patch_codsp_x87_fld32.py verifica SHA del p-code, fuente y los 39 PC originales dentro del bloque; rechaza cambios ajenos, modifica una sola expresión por sitio, mantiene CRLF y número de líneas, y restaura byte por byte. El helper se define en tools/recomp/runtime/x87_fld32_normal.h; su declaración en recomp_rt.h no genera llamadas por defecto. El builder agrega --arm64-x87-fld32-normal, solamente arm64-v8a, incompatible con package-only y x87 stack outlining, **OFF por defecto**. El atajo incorrecto --hot-x87-transform sigue bloqueado.

Identidad del p-code CoDSP 1.5 SHA-256: 36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e.
Fuente p10 sin parche SHA-256: 629f468b39649875971ed02f18114390cdc7a12ff1871ac33fd9c30006635fd5.

## Verificaciones

- 4.096 casos, **8.192 ejecuciones reales AArch64 en Unicorn**, sin diferencias en R completo (8.192 bytes), x87 padding, PC guest, RAM, FPCR/FPSR y SP.
- **16 lecturas a RAM guest no mapeada**: ambas versiones fallan y conservan exactamente el mismo R y PC parcial al momento del fallo.
- El cambio deja intactos los valores especiales; NaN señalizadores pueden cambiar FPSR en el original y la candidata debe igualarlo exactamente.
- Conteo dinámico de una sola instrucción FLD m32 con siete copias de pila, LLVM O1 AArch64: **normal 55 → 52 instrucciones**; especiales mediana 54 → 59 instrucciones. No son ciclos CPU, FPS, ni una garantía para la mezcla real de datos.
- Suite Python **534 pruebas aprobadas y seis omitidas**; CTest **40/40**. Los siete nuevos tests de selección, reversible, oráculo normal y guardas aprobaron.
- APK A y B firmadas con NDK 30. **490 exportaciones definidas en ambas**; recursos, Dex y bibliotecas no cambiaron. Diferencias de entradas APK limitadas a lib/arm64-v8a/libmain.so y tres archivos META-INF de firma. Texto ELF candidato **+1.144 bytes**.
- Tras reconstruir la referencia normal, todas las fuentes C privadas generadas recuperaron sus SHA originales, igual que el archivo p10.

| Identidad de APK privada | SHA-256 |
| --- | --- |
| A nueva, normal (OFF) | 1aa66f0ea402c01121eec9fdee99a3b92afd4d91fc26fa67d8850945e7f5b991 |
| B con FLD32 (opt-in) | 9ef98fafc108c683d91ee58463996343abf044854ee2cb7c35d06a4c0a69b1bd |
| ELF B no stripped | 14c1ac046473828a9789d150532d6d9935daa62a65dc4081265d8abdf39e2fe1 |

## Intento físico

En el TECNO CK6n conectado (batería inicial 35 °C) se preparó A/B/A/B con misma configuración y checkpoint usando tools/recomp/diagnostics/android_abab.py. **A1 fue rechazada antes de registrar una pasada válida:** «Non-comparable baseline; stop before B». La candidata B **no se instaló** y no hay ningún FPS físico atribuible a este cambio. No sustituir esta referencia anómala por un promedio favorable.

El corredor informó failed/restored=true. Verificación adicional ADB de APK 0.2.4 original:
fb8647c34dfe8fd269c0902f34edcc4c0844b18c6aa13ff6006232678da25f70;
y partida training.svg:
efbc68e54fabc79946dfd3a9d188e5f6ba284b1aad99130bbe2726eb637f64f8.
Batería final 36 °C. No se borraron partidas ni se cambió calidad gráfica.

## Reproducibilidad y decisión

Estudio privado: .local/profiles/runs/tecno/2026-10-16/arm64-x87-5061b0-safe-state/20261016T025450Z-22804-00/

Archivos: raw/fld32-aarch64-full/result.json y disassembly.txt; reports/fld32_apk_builds.json, fld32_native_abi.json, abab-result.json; builds/A_restored_original.apk, B_fld32_39_sites.apk; logs de las dos compilaciones.

Para regenerar solo si hay datos privados y NDK:
- python -m unittest discover -s tests -p test_arm64_x87_fld32_normal.py
- python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d --arm64-x87-fld32-normal --jobs 3
- Luego reconstruir siempre sin la opción para restaurar fuentes y APK normales.

**Decisión: conservar la optimización como candidata ARM64 exacta en la región verificada, reversible y OFF por defecto. No anunciar FPS ni activar una release hasta completar A/B/A/B físico con referencias estables.**
