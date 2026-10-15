# Fase 11 — Solapamiento de muestras CPU inline de CoDSP p4 (solo offline)

**Fecha:** 2026-10-14. **Resultado:** clasificación de muestras archivadas completada; **ninguna optimización de producción ni mejora de FPS demostrada**. El TECNO no se utilizó en esta fase.

## Motivación y alcance

Tras el A/B/A físico de fase 10, el fast path x87 p4 perfilado no obtuvo una mejora convincente (B2 26,05 FPS frente al promedio A de 25,95 FPS). Los perfiles Simpleperf **anteriores y ya archivados** mostraban muchos marcos inline etiquetados `memcpy`, `rd`, `wr`, `f2d` y `d2f`. **Los recuentos inclusivos no son sumables**, pues una instrucción ARM64 puede pertenecer a varias capas inline simultáneamente.

Se reprocesaron las dos capturas preexistentes (v1/v2) sin ADB, sin compilar APK y sin volver a ejecutar el juego, usando el ELF simbolizado anterior y `llvm-addr2line -a -f -C -i`. Los samples se filtraron a `codsp_chunk_75..93_spaces` del módulo p4 y se atribuyeron a la etiqueta de PC x86 original de acuerdo con el generado ya auditado. Se exigió que las cantidades de muestras y su atribución coincidieran exactamente con las del análisis previo: **1.017/889 muestras p4** y **974/840 resueltas a PC invitado**, respectivamente. Quedaron 43/49 sin esa atribución.

## Resultado por perfil: muestras resueltas

| Etiqueta de marco inline más interno | Perfil v1, de 974 | Perfil v2, de 840 |
| --- | ---: | ---: |
| `memcpy` | **409 (42,0 %)** | **353 (42,0 %)** |
| `rd` | 0 | 0 |
| `wr` | 0 | 0 |
| `f2d` | 352 | 309 |
| `d2f` | 102 | 96 |
| Otras/ninguna de las cinco anteriores | 111 | 82 |
| **Total** | **974** | **840** |

**Importante:** `rd=0` y `wr=0` en esta columna NO significa que no consuman CPU. Sus muestras tienen un marco inline `memcpy` más interno en estas capturas. Recuento **inclusivo** para `rd`: 233/204; para `wr`: 154/123; `memcpy`: 409/353. La intersección `memcpy+rd` es exactamente 233/204 y `memcpy+wr` exactamente 154/123. Además, existen intersecciones `f2d+memcpy` de 14/20 y `d2f+memcpy` de 8/6 muestras. Por ello, **no se pueden contabilizar `memcpy` y `rd/wr` como cuellos de botella independientes**.

La etiqueta de marco más interno es solo una **clasificación de la pila DWARF**: no mide el tiempo exclusivo de funciones, ciclos por instrucción, bytes copiados, número de invocaciones por fotograma ni rendimiento de una variante futura. Tampoco mide en esta fase el 100 % de los samples del proceso o de la GPU.

Los PC originales `0x0047B487` (marco `memcpy`: 7/10 muestras en v1/v2) y `0x0047C3AA` (marco `f2d`: 9/7) se repiten entre perfiles, pero cada PC acumula una cantidad reducida; **no hay justificación para parchear una instrucción aislada basándose solo en estas cifras**.

## Decisión y siguiente experimento

La pista más coherente es investigar primero **las copias de estado arquitectónico asociadas a `rd`/`wr`** y su traducción ARM64 en conjunto, en lugar de contabilizar aparte las muestras de `memcpy`. El próximo candidato deberá demostrar, antes de usarse en un teléfono:

1. Qué instrucciones ARM64 y accesos de memoria elimina *realmente* en los chunks de mayor coste; no bastan menos líneas C.
2. Equivalencia diferencial completa en casos de aliasing, límites, GPR/EFLAGS, RAM, PC y valores especiales x87; nunca modificar el juego, el renderizado o el guardado para subir FPS.
3. Que el ensamblado ARM64 final sea mejor para un caso representativo, sin regresión en otros caminos. Solo una nueva comparación física controlada permitiría alegar más FPS.

El fast path **x87 p1/p8 previamente validado** permanece, mientras los flags experimentales **p4** no aprobados siguen **OFF**. No se cambió la compilación normal ni se volvió a instalar nada en el TECNO. La meta de 60 FPS queda pendiente.

## Reproducción y evidencia

- Herramienta pública sin dependencias del juego: `tools/recomp/diagnostics/inline_profile_overlap.py`. Separa etiquetas inclusivas, solapamientos y primera etiqueta de marco inline (no tiempo exclusivo).
- Pruebas sintéticas: `tests/test_inline_profile_overlap.py` (**3 pruebas aprobadas**). Suite completa Python: **260 pruebas ejecutadas, 4 omitidas, 0 fallidas** (`python -m unittest discover -s tests`).
- Extractor privado y datos de los dos perfiles antiguos: `.local/profiles/phase11_p4_hotspot_overlap.py` y `phase11_inline_overlap_private.json`, ignorados por Git. No publicar ELF privados, datos originales del juego, paquetes comerciales ni capturas del dispositivo.
