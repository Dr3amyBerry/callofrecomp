# ARM64: desplazamientos logicos derechos estrechos

**Estado: CANDIDATA EXPERIMENTAL, opt-in OFF.** Helper, oraculo y APK ARM64 A/B compilados y verificados. Reduccion neta de `.text`: 16 bytes; sin ganancia de rendimiento demostrada. Sin telefono, ADB, WSA ni nuevos FPS. No se modifica la calidad, el estado x87 ni los recursos del juego.

## Cambio y alcance

`--arm64-narrow-right-shift` activa `CODRECOMP_ARM64_NARROW_RIGHT_SHIFT` para ARM64. El builder y CMake rechazan otras ABI. Dentro de `shr`, `__builtin_constant_p(a >> 64)` permite usar un desplazamiento de 64 bits solo cuando Clang demuestra que la mitad alta del operando es cero. La cuenta conserva sus 128 bits hasta comprobar `b >= 64`, evitando tanto truncarla como ejecutar un desplazamiento C indefinido. Si no hay prueba constante, se conserva el helper original de 128 bits. No hay prueba dinamica adicional de la mitad alta.

El resultado completo sigue siendo `u128`, extendido con ceros. La semantica es la de `INT_RIGHT` de p-code; el enmascarado de la cuenta de la instruccion x86 pertenece al decodificador existente y no cambia. `INT_LEFT`, `INT_SRIGHT`, registros, flags y orden de accesos quedan intactos.

El [ranking historico del TECNO](PHASE15_TECNO_CPU_PROFILE_CROSSCUTTING_2026-10-15.md) incluye `0x0042B0A0`, con dos operaciones `INT_RIGHT` estrechas en su cuerpo. Las otras siete funciones seleccionadas no contienen esta operacion. El recuento estatico no demuestra frecuencia ni coste dinamico; se comprobara el chunk real `codsp_chunk_28_spaces`. La propuesta no se presenta como solucion aislada a 60 FPS.

## Equivalencia y codigo AArch64

`tests/recomp_shift_smoke.c` calcula una referencia independiente byte por byte. Ensaya anchuras de 1 a 16 bytes, fuente desalineada, resultado completo de 128 bits, cuentas en limites 0/31/32/63/64/127/128 y mayores, incluida una cuenta con mitad alta distinta de cero. Semilla `0x5a17cafe`, 512 casos por ancho: **8.192 casos por variante**.

Ambas variantes aprobaron compiladas por NDK 30 para AArch64 y ejecutadas en Unicorn. `tests/test_recomp_shifts.py` compila la misma prueba con y sin bandera en O0/O1/O2. Suite Python: 494 pruebas, cinco omitidas, ninguna fallida; 40/40 CTest. Revision independiente sin bloqueos de correctitud. Estas pruebas no certifican ejecucion integral del juego.

Comparacion de wrappers reales `-O1`, bytes de funcion referencia/candidata:

| Ancho del operando | Cuenta 1 byte | Cuenta 8 bytes | Cuenta 16 bytes |
| --- | ---: | ---: | ---: |
| 1, 2, 4 u 8 bytes | 40 / 28 | 36 / 28 | 44 / 36 |
| 10 bytes | 76 / 76 | 72 / 72 | 84 / 84 |
| 16 bytes | 68 / 68 | 64 / 64 | 76 / 76 |

Son dos o tres instrucciones estaticas menos en los ejemplos estrechos; no son ciclos ni FPS. La primera descomposicion alternativa de ambos shifts en mitades aumento el codigo y fue descartada antes de integrar. Se conserva exclusivamente la especializacion derecha demostrable.

## APK y chunks reales

A y B conservan normal-f2d, O1 y todas las otras candidatas OFF. B se compilo en un directorio independiente con las opciones de A, cambiando solo la nueva bandera. El ELF/APK normal A y la libreria de empaquetado se restauraron por SHA tras empaquetar B, incluso ante errores mediante `finally`.

| Funcion nativa | A bytes | B bytes | Delta |
| --- | ---: | ---: | ---: |
| `codsp_chunk_84_spaces` | 114.076 | 114.072 | -4 |
| `codsp_chunk_203_spaces` | 82.244 | 82.220 | -24 |
| `codsp_chunk_172_spaces` | 83.092 | 82.912 | -180 |
| `codsp_chunk_174_spaces` | 148.724 | 148.932 | +208 |
| `cgamex86_chunk_41_spaces` | 40.156 | 40.144 | -12 |
| `uix86_chunk_14_spaces` | 56.284 | 56.272 | -12 |

Los otros simbolos generados conservan tamano. El chunk 28 de la funcion perfilada conserva 645.136 bytes y su histograma de instrucciones; tampoco cambian esos recuentos en los chunks 18/88/152 seleccionados como controles calientes. El ahorro del wrapper no se traslada automaticamente a cada funcion. La suma de texto de los 28 objetos generados baja 24 bytes; el enlace completo baja 16 bytes, incluyendo su organizacion y alineacion.

En chunk 203 desaparecen cuatro `csel` y dos `tst`. Chunk 174 crece: no ocultar ese resultado ni inferir una mejora global a partir de las funciones que reducen codigo. En 172/174/84/203 se conservan los marcos de pila (240/144/112/96 bytes), los recuentos estaticos de accesos basados en SP (166/47/25/12) y cero `blr` dentro de esos cuerpos. Esto no mide spills ejecutados por frame, latencias, dependencia de datos ni efectos de cache reales. No se ha introducido NEON en este bloque.

| Medida del ELF/APK | A | B |
| --- | ---: | ---: |
| `.text` del ELF | 42.340.100 | 42.340.084 |
| `libmain.so` empaquetada | 47.493.704 | 47.493.688 |
| Exportaciones definidas | 490 | 490 |
| APK completa | 50.238.268 | 50.238.268 |

Exportaciones, tamanos de datos exportados, imports y dependencias dinamicas identicos. Las 28 fuentes C generadas conservan SHA. Solo cambian la libreria principal y las firmas META-INF del APK; recursos, DEX y demas librerias empaquetadas son identicos. Firma v2/v3 y alineacion verificadas por el builder. El tamano del ELF sin strip incluye debug de rutas distintas y no sirve para inferir coste de ejecucion.

| Artefacto privado | SHA256 |
| --- | --- |
| `shift-A.apk` | `5adb009e081811790ce368cb9b712c6a4236259b39cf818e9016fe6919c3cb67` |
| `shift-B.apk` | `7174a7c96a0a944b7d0aec128e417eccf0caf6a1bc0f47ed91cb49bfbc253880` |
| `shift-A.so` sin strip | `f81d228c73f4125e6d87a9f33d109a11f76e50a9054d20dba6cc1370a5956c8e` |
| `shift-B.so` sin strip | `9e8bf47724c848217bc223aefb9cf60415b2706738ff8b84425613be406a4319` |

## Evidencia privada y reproduccion

Sesion: `.local/profiles/runs/tecno/2026-10-15/arm64-native-integer-shifts/20261015T225801Z-8556-00`.

- `scripts/verify_shifts.py`: comandos NDK y ejecucion de ambas variantes, reutilizando el cargador ELF del verificador de dispatch.
- `reports/right-shift-final.json`: hashes de header/smoke, comandos, casos y tamanos; desensamblados `wrappers-reference.txt` y `wrappers-candidate.txt`.
- `reports/profiled-shift-opportunities.json`: inputs p-code/mapa verificados por SHA y presencia estatica en las ocho funciones.
- `scripts/audit_apk_pair.py`: comparacion ABI, recursos, fuentes y diez chunks; `reports/apk-pair-integrity.json` y `chunk-comparison.json` aprobados.
- `reports/all-generated-object-text.json`, `stack-and-indirect-calls.json`: todos los cambios de tamano y comprobacion de pila/llamadas indirectas.
- `scripts/package_candidate.py`, `builds/shift-A.*`, `builds/shift-B.*`, `builds/native-B/`, `logs/`: empaquetado reversible y ambas variantes. La configuracion normal conserva la bandera OFF.

```powershell
python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d --arm64-narrow-right-shift --jobs 3
python -m unittest discover -s tests -p test_recomp_shifts.py
```

La primera orden construye B; omitir la bandera construye A. Guardar cada ELF/APK en una sesion privada antes de cambiar de variante. No instalar hasta que se autorice la siguiente medicion fisica.

## Decision y siguiente comprobacion

Conservar el experimento trazable por su ahorro local verificado, sin imponerlo como mejora del juego: el efecto global es mixto y el ahorro neto estatico diminuto. Ejecutar el protocolo [A/B/A/B con guardas de estabilidad](TECNO_STABILITY_GATE_2026-10-15.md) cuando vuelva el telefono. Hasta entonces la bandera permanece OFF y no hay ganancia fisica atribuible. Mantener la referencia segura y no activar el transform double bloqueado.
