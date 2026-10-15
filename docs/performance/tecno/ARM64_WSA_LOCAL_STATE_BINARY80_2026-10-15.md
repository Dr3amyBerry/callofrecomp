# TECNO ARM64: primera adaptación del enlace local de WSA y referencia numérica binary80 — 2026-10-15

## Contexto y alcance

**No equivaler WSA x86_64 con TECNO ARM64.** En WSA el A/B/A/B de
`--local-guest-state` mejoró 65,75 → 68,15 FPS sobre un paquete que
**ya contenía la región x87 nativa x86_64**. Esas instrucciones x86 no se
ejecutan en la CPU ARM del teléfono. El TECNO 0.2.4 físico medía
22,03 FPS (43,68 ms de CPU por frame), frente a 25,98 FPS en una APK
anterior **con atajo matemático x87 bloqueado**. Esa regresión no autoriza
reactivar el atajo.

Fuentes:
- [Regresión física 0.2.4](TECNO_RELEASE024_ABAB_2026-10-15.md).
- [A/B/A/B de WSA y sus límites](../wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md).
- [Por qué se bloqueó x87 basado en double](../wsa/WSA120_LIMITER_AND_RENDERER_PROFILE_2026-10-15.md).

## 1. Cambio compatible trasladado a ARM64: enlace local

Nueva opción experimental **`--arm64-local-guest-state`**, solo
`--abi arm64-v8a`, **OFF por defecto**, independiente del argumento
WSA x86_64 `--local-guest-state` y de `--wsa-release`.

Usa el mismo mapa ELF `android/guest_state.map` para que únicamente
los objetos **R, MEM, U, PC** no puedan interponerse desde fuera
de `libmain.so`. No crea registros ARM64 persistentes, no elimina
operaciones originales, no modifica generated C, flags x87, aliasing,
guest RAM, renderer, texturas ni configuraciones gráficas. El enlazador
puede reducir carga de GOT, pero ello **no implica una ganancia FPS** sin
medición física. El auditor
`tools/recomp/diagnostics/audit_local_guest_state.py` falla si cambia
otro símbolo dinámico público.

**Compilación ARM64 real / auditoría con LLVM readelf:**
- APK base 0.2.4 SHA256:
  `fb8647c34dfe8fd269c0902f34edcc4c0844b18c6aa13ff6006232678da25f70`.
- APK B experimental SHA256:
  `cf1bc16e72b3a702fbb6d1e2f720115e149196006a57f0b389d55b8532b9a96f`.
- Exportaciones ELF definidas **490 → 486**. Se ocultaron exactamente
  **MEM, PC, R, U**; los demás **486** conservaron nombre, tipo,
  binding, visibilidad y tamaño, sin otras bajas ni altas.
- El APK B solo cambia `lib/arm64-v8a/libmain.so` y
  `META-INF/` de firma; no cambia el contenido de otros archivos.
- Las 12 particiones CoDSP generadas conservaron sus SHA-256.
- Tras construir B se restauró el APK y ELF base, y se puso
  `CODRECOMP_ARM64_LOCAL_GUEST_STATE=OFF` en CMake.

**Reproducir solo en entorno con datos privados autorizados:**

~~~powershell
python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d --arm64-local-guest-state
python -m unittest discover -s tests -p test_arm64_local_guest_state.py
~~~

Estas pruebas de enlace **no** prueban todavía equivalencia funcional
de runtime (incluida posible interposición mediante plugins no previstos),
ni estabilidad extensa, FPS, latencia de GPU o una ruta binary80 ARM64.

## 2. Diferencial físico aislado A/B/A/B

**A:** APK 0.2.4 original, `--x87-normal-f2d`, sin enlace local.

**B:** mismo código/particiones/configuración y firma de depuración;
solo se activa `--arm64-local-guest-state`.

TECNO CK6n físico, juego Equilibrado, Camp Toccoa 1280×576, límite 60,
mismo autosave y cámara fija, 55 s de telemetría tras cada entrada y
últimas 40 ventanas estables por pasada. Instalaciones `adb install -r`;
el script debe restaurar el APK 0.2.4 y comprobar los hashes de partida.
No se necesitan fotos de navegación; se reutiliza un script guiado por
marcadores de arranque y `frame stats`.

**Resultado A/B/A/B:**

| Pasada | FPS | CPU ms/frame | Temperatura inicial | Inicio -> final FPS |
| --- | ---: | ---: | ---: | --- |
| A1 | 17.40 | 55.295 | 39.0 C | 22.5 -> 16.1 |
| B1 | 22.00 | 43.675 | 40.0 C | 22.4 -> 21.5 |
| A2 | 21.75 | 44.110 | 40.0 C | 22.3 -> 21.3 |
| B2 | 22.25 | 43.165 | 40.0 C | 22.7 -> 21.9 |

**Media de medianas A->B (solo descriptiva; NO ganancia validada):** 19.575 -> 22.125 FPS (+13.03 %); CPU 49.703 -> 43.420 ms/frame (-12.64 %). A1 fue anómala: cayó 22.5 -> 16.1 FPS durante sus 40 ventanas; A2 volvió a 21.75 FPS.
**Decisión:** INCONCLUSO POR VARIACION DE ESCENA/TIEMPO. Desviación máxima inicio/final de las 40 ventanas medidas: 6.4 FPS; una media no equivale a FPS estables ni a los 60 FPS objetivo.
La APK instalada al finalizar debe ser la 0.2.4 original y se recomprueban su SHA256 y el hash del guardado aparte.

La batería, núcleo/temperatura CPU, GPU, tiempos p99 y combate no quedan
completamente controlados por esta prueba; las medias de medianas no
demuestran mínimos de FPS.

## 3. Objetivo x87: precisión binary80, NO otro double rápido

La región original `0x005061B0` concentró **509 de 3.692** muestras
`libmain.so` de un perfil físico 0.2.4 a 350 Hz, 12 segundos;
la atribución de PC/linea source es aproximada, no tiempo exclusivo.
Su C generado aún muestra `f2d(...,10)`, aritmética double
y `d2f(...,10)`. Es crucial distinguir:

- El atajo `--hot-x87-transform` **continúa bloqueado** por
  **20/23** diferencias ante el x86 original (CW 0x037f).
- La ruta native binary80 usada en WSA compila ensamblador x86_64;
  no existe una traducción automática de ella para AArch64.
- La fusión exacta de siete copias x87 se midió en TECNO:
  **21,95→22,075 FPS (+0,57 %)** y
  **43,7725→43,480 ms/frame (−0,67 %)**; insuficiente para
  recuperar el rendimiento, **OFF por defecto**.
- Se ha creado el oráculo numérico **offline**
  `tools/recomp/diagnostics/binary80_arithmetic_reference.py`:
  usa fracciones racionales exactas, significando de 64 bits,
  redondeo ties-to-even, para sumas, restas, productos y divisiones
  de **entradas finitas**, únicamente CW `0x037f`, sin
  redondear intermedios a double. Sus tests cubren cancelación y el
  contraejemplo `1 + 2^-24 + 2^-54` cuyo almacenamiento float32
  original es `0x3f800001`.
- El oráculo **NO es un backend x87**: carece de bits SW/C1,
  TOP/tags, flags pegajosos, todos los CW, NaN/Inf, desbordamientos,
  precisiones alternativas, memoria/fallos y excepciones no enmascaradas.
  Rechaza esos casos; no se enlaza a libmain, no promete FPS.

**Condiciones para una futura implementación ARM64:** operaciones
binary80 correctas (p. ej. aritmética software auditada), excepciones,
estado x87, fallos y PC guest exacto, comparación independiente con las
58 instrucciones originales hasta RET y pruebas con distintos CW,
entradas de cancelación, NaN, subnormales, alias e interrupciones.
Solo entonces generar B y medir; **nunca** sustituir por double por
aumento aparente de FPS.

## 4. Resto del paquete WSA que se debe separar

`--render-o2`, `--fast-copy32`, `--visibility-o2`,
`--dispatch-last-cache`, `--x87-nan-bits` y
`--x87-fcom-fastpath` ya tienen rutas experimentales portables
o específicas en el builder. **No equivalen por sí solas** al preset
`--wsa-cumulative` x86_64. Algunas aisladas en TECNO no dieron una
mejora robusta; no deben reactivarse juntas en una release sin verificar
interacción y equivalencia.

Siguiente fase tras el enlace local: comparar opcionales en **APK
diferenciadas por una sola bandera**, ABI y calidad iguales; priorizar
renderer y dispatch con perfiles actuales y controles de guardado,
temperatura, estabilidad y límites de precisión.

## Evidencia y privacidad

APK A/B, ELF, pruebas, salida del auditor, evidencia perf.data y
script A/B se quedan privados en
`.local/profiles/runs/tecno/2026-10-15/arm64-port-wsa-link-state/`.
Perfil previo original se mantiene en
`.local/profiles/runs/tecno/2026-10-15/arm64-release024-cpu-hotspots/`.
No publicar binarios, recursos comerciales, archivos generated C ni
identificadores ADB.
