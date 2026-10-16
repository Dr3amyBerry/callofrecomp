# ARM64: cambio exacto del signo binary80 en tres FCHS de CoDSP

**Fecha de ejecución:** 2026-10-16 UTC (2026-10-15 hora local del proyecto).
**Estado:** CANDIDATA EXPERIMENTAL, **OFF por defecto**, compilada y verificada offline.
**Sin TECNO ni WSA** durante este trabajo. **Sin FPS nuevos.**

## Contexto y alcance exacto

La interrupción de Codex había dejado solo un estudio privado:
`.local/profiles/runs/tecno/2026-10-15/arm64-x87-sign-bits/20261015T234405Z-18860-00/`.
Su oráculo de las instrucciones originales `FABS/FCHS` pasó de nuevo
**65.536 casos** con valor, CW, bits definidos de SW, TOP, etiquetas y
otras ranuras de pila x87 en los estados ensayados. Esa prueba es
**x86 original**, no una medición de rendimiento ARM64.

El p-code `recomp_out/codsp.pcode` tiene SHA-256
`36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e`.
Se autoriza exclusivamente el `FLOAT_NEG r:1100:10 r:1100:10` de
los PC originales **`0x41975e`, `0x419c48`, `0x419e12`** de la
función geométrica `0x4196f0`, todos en `codsp_recomp_p0.c`.
Cada instrucción también contiene solo su actualización original de PC.

La forma generada anterior convertía binary80 -> `double` -> binary80:
`wr(ST0,10,d2f(-(f2d(rd(ST0,10),10)),10))`.
Esto puede redondear una fracción binary80, modificar un NaN o perder
su payload. La nueva opción `--arm64-x87-sign-bits` cambia **solo**
el bit 7 del byte `R[0x1109]` (`R[0x1109] ^= 0x80`).
Los otros 79 bits, las seis bytes de padding de la ranura de 16 bytes,
el resto del banco R y el código en otros PCs quedan intactos.
La selección es por PC y hash p-code; cualquier fuente inesperada falla.

**Limitación esencial:** esto implementa fielmente la operación
`FLOAT_NEG` sobre el **valor** binary80 generado, no toda la instrucción
física x87 `FCHS`: el p-code de esos PCs no modela escrituras a
`SW/C1` ni todos los casos de excepción por pila vacía.
El oráculo original x86 comprueba esos campos, pero su paso no equivale a
demostrar que la APK los reproduzca exactamente. El parche mantiene
las escrituras de estado definidas por el p-code preexistente y no
introduce nuevas escrituras CW/SW/TOP/tag. No afecta a RAM, otros
operandos o recursos. La precisión completa de la FPU general sigue
siendo un problema independiente.

## Implementación y pruebas

- `tools/recomp/patch_codsp_x87_sign.py`: parche reversible, único
  p0, tres sites, verificación estricta de origen, opción apply/restore,
  conserva numeración de líneas y revierte byte a byte.
- `tools/recomp/build_android.py`: nuevo flag
  `--arm64-x87-sign-bits`, solo `arm64-v8a`, OFF por defecto,
  incompatible con `--package-only`; restauración del C original
  en builds normales. El antiguo `--hot-x87-transform`
  sigue **BLOQUEADO**.
- `tests/test_arm64_x87_sign_bits.py`: 10 pruebas iniciales,
  incluyendo selección exacta de PCs, p-code, reversibilidad,
  guardas ABI, payload y valores especiales.
- `tools/recomp/diagnostics/verify_arm64_x87_sign.py`:
  compila **AArch64 real** mediante Android NDK/Clang `-O1` y lo
  ejecuta con Unicorn: **4.000 ejecuciones**, 16 alineaciones,
  registro R de 8.192 bytes completo, 6 bytes de padding x87,
  límites de escritura, LR/SP, FPCR/FPSR y memoria adyacente.
  Cero discrepancias frente al modelo de cambio exacto de signo.
- No se midieron milisegundos ni FPS en emulación. El original x86 y
  el oráculo Unicorn prueban aspectos **diferentes y limitados**.
- **Suite completa:** 527 pruebas Python, 6 omitidas, 0 fallos;
  **CTest: 40/40 aprobadas**. Catálogo: 130 documentos sin links rotos;
  verificador privado: 200 scripts archivados, 33 capturas y 7 builds
  históricos preservados, sin errores (una advertencia de sintaxis
  conocida en script legado que no se ejecuta).

## Construcción A/B ARM64 de APK

**A:** `--abi arm64-v8a --recomp-opt 1 --x87-normal-f2d`

**B:** mismos argumentos más `--arm64-x87-sign-bits`.

| Propiedad | A | B |
| --- | ---: | ---: |
| `.text` | 42.340.100 bytes | 42.339.068 bytes |
| ELF `libmain.so` no stripped | 230.970.440 bytes | 230.968.336 bytes |
| Símbolos públicos definidos | 490 | 490 |

Cambio del código: **−1.032 bytes de `.text`**;
ELF no stripped: **−2.104 bytes**. Sin cambios en
contratos (nombre, tipo, enlace, visibilidad, tamaño) de los
490 símbolos exportados. Únicamente varían
`lib/arm64-v8a/libmain.so` y firma `META-INF/` entre APK.
Los recursos y demás archivos empaquetados se conservaron por contenido.

SHA256 APK A:
`9ba61260ba04394db600f5d5feebc4a2df2a7f38948049fa8eb0e5fb7e217455`

SHA256 APK B:
`ae600919e507701f97b6b0b8f4c62d2720f827a88a0aeb5563bb6b96bdd87a2d`

La APK B y ELF B se guardaron **en privado**, sin publicar contenido
de juego. El builder reconstruyó A al cerrar, restauró p0 y los demás
11 archivos generados por SHA, comprobó que el ELF no stripped coincide
exactamente con el A y repuso el APK A por hash. La configuración normal
queda con el nuevo flag OFF.

**Esto demuestra una reducción de código estático y corrección del valor
sign-bit en pruebas, no una mejora demostrada de CPU/frame ni de FPS.**

## Reproducción offline autorizada

```powershell
python -m unittest discover -s tests -p test_arm64_x87_sign_bits.py
python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d --arm64-x87-sign-bits
python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d
```

El auditor Unicorn usa `--llvm-bin RUTA_NDK_LLVM` y
`--out RUTA_NUEVA_PRIVADA` (destino exclusivo en
`.local/profiles/runs/`). No usar datos reales del juego en tests públicos.

## Evidencia privada y próximos pasos

`.local/profiles/runs/tecno/2026-10-16/arm64-x87-float-sign-opt/20261016T011623Z-2084-00/`

- `reports/full_build_ab.json`, `reports/elf_size_and_abi.json`;
- `raw/arm64-sign-oracle-2/result.json`;
- `logs/A_build.log`, `logs/B_build.log`,
  `logs/A_restore_build.log`;
- `builds/A_original_profile.apk`, `builds/B_arm64_sign_bits.apk`,
  sus ELFs A/B y hashes.

**Próximo paso:** continuar optimizando otras transformaciones
binary80 solo con equivalencia demostrable; no generalizar este
parche a otras funciones y no reactivar la vía basada en double.
Cuando vuelva a estar disponible un teléfono ARM64 comparable, medir
A/B/A/B con el protocolo estable de escena y la misma calidad gráfica.
