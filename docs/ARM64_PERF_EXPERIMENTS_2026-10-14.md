# TECNO CK6n ARM64: experimentos posteriores a x87 — 14 de octubre de 2026

**Repositorio:** `Dr3amyBerry/callofrecomp`, rama `main`. **Estado:** pruebas terminadas; **ningún aumento nuevo de FPS demostrado**. Las variantes quedan disponibles solo como experimentos explícitos y **desactivadas por defecto**. Los recursos originales, programas recompilados, perfiles de CPU y APK de prueba se conservan exclusivamente en rutas privadas ignoradas.

## Referencia que sí mejoró el rendimiento

Se mantiene el fast path matemático **optativo** `--hot-x87-transform`, aplicable a la función original `0x005061B0`. Su comparación A/B/A previa en el entrenamiento fue 21,45 → **25,65 FPS** (+19,58 %), acompañada de 44,745 → **37,495 ms de CPU/frame**. Está validado frente al p-code existente, no con una ejecución x86 original independiente. Las correcciones panorámicas/HUD están conservadas.

**Meta que sigue abierta:** alcanzar **60 FPS sostenidos en el punto de aparición de training** en el TECNO CK6n, sin sacrificar la calidad ni confundir el menú (~53 FPS) con el juego. A 60 FPS corresponde un presupuesto total de ~16,67 ms/frame; en las pruebas actuales el CPU del motor requiere alrededor de **38 ms/frame**. Los FPS de las tablas son medianas de **40 ventanas de resumen de ~1 segundo**; p10 es percentil de esas ventanas, no de cada frame.

## Experimento A: copia CoDSP.exe 1.5 `0x0042B0A0`

La decompilación privada mostró una rutina de copia por bloques de 32 bytes. En `L_42b100…L_42b13a` existen ocho cargas/escrituras de 4 bytes y el control del bucle sigue en `L_42b13e`. Se desarrolló:

- `tools/recomp/runtime/codsp_copy32.h`: una copia `memcpy` de 32 bytes que actualiza EAX/ESI como las últimas cargas originales. Si los dos bloques se solapan o una dirección se desborda en 32 bits, vuelve al flujo p-code sin tocar el estado.
- `tools/recomp/patch_codsp_copy32.py`: inserción reproducible y con validaciones de estructura únicamente en el **C generado privado** `recomp_out/codsp_recomp_p1.c`. Rechaza entradas que no correspondan al módulo/etiquetas esperados y es idempotente.
- `python tools/recomp/build_android.py --hot-x87-transform --fast-copy32 --jobs 3`: activa `CODRECOMP_CODSP_COPY32_FASTPATH=ON` **solo** para la unidad CoDSP p1. Sin el flag permanece OFF.

**Pruebas:** el CTest `codsp_copy32_smoke` verificó 110.000 casos sintéticos de copia, incluyendo solapamientos; las pruebas Python comprueban el parche. Además, se compiló un programa **ARM64 ejecutado en el teléfono** que contiene la traducción completa p-code de la función y la alternativa: **17.000 ejecuciones, 249.371 bloques acelerados**, con igualdad exacta de todos los registros, banderas, RAM simulada y PC final en las pruebas. La evidencia es frente a la traducción p-code, **no** un oráculo Intel x86 original; no cubre estados de memoria arbitrarios no probados.

| Corrida, training / Equilibrado | FPS mediana | p10 FPS | CPU ms/frame |
| --- | ---: | ---: | ---: |
| A1, APK x87 anterior | **25,45** | 23,6 | **37,795** |
| B, copia32 + x87 | **25,10** | 24,2 | **38,260** |
| A2, APK x87 reinstalada | **25,30** | 24,0 | **38,090** |

**Decisión:** rechazar como ganancia de rendimiento. B quedó **0,20 FPS por debajo** de A2; no se activó por defecto. Muestra que la equivalencia de un microbloque no basta para mejorar el tiempo de frame. Los archivos de datos están bajo los nombres privados `tecno_copy32_A_stable40.log`, `tecno_copy32_B_stable40.log` y `tecno_copy32_A2_stable40.log`.

## Experimento B: visibilidad CoDSP.exe `p8` compilado con `-O2`

El perfil Simpleperf posterior a x87 (6.358 muestras en el teléfono, cero pérdidas) identificó estos candidatos en la partición generada `codsp_recomp_p8.c` (~8,5 MB de C): `0x004D8280` (155 muestras), `0x004D94C0` (150), `0x004D8420` (143) y `0x004D6BC0` (139). La evidencia son muestras estadísticas, no milisegundos por función. Se probó `-O2 -ffp-contract=off` **solo** sobre p8, manteniendo el resto a la optimización anterior, sin `-ffast-math`.

Comando: `python tools/recomp/build_android.py --hot-x87-transform --visibility-o2 --jobs 3`. `CODRECOMP_VISIBILITY_O2` permanece OFF por defecto.

| Corrida, training / Equilibrado | FPS mediana | p10 FPS | CPU ms/frame |
| --- | ---: | ---: | ---: |
| A1, APK x87 anterior | **25,30** | 24,0 | **38,090** |
| B, p8 `-O2` + x87 | **25,50** | 25,1 | **37,725** |
| A2, APK x87 reinstalada | **25,45** | 24,7 | **37,785** |

**Decisión:** sin mejora significativa. B supera A2 por solo **0,05 FPS**, dentro de la variabilidad de la escena, temperatura y NPC. No se habilita normalmente. Archivos privados `tecno_visibility_O2_B_stable40.log` y `tecno_visibility_O2_A2_stable40.log`.

## Verificación y estado al cierre

- **96 tests Python** correctos (**4 omitidos**) y **28/28 CTest** correctos tras incorporar los tests nuevos.
- Se compilaron, firmaron e instalaron las APK ARM64 de ambos experimentos; el juego cargó el mismo guardado real y se capturaron estadísticas de gameplay; no se alteraron guardados ni contenidos comerciales.
- Tras cada prueba se reinstaló la **APK de referencia x87 con copy32 OFF y visibility-O2 OFF** en el TECNO, conservando el HUD panorámico de la versión anterior.
- Se restauró asimismo la configuración de compilación local de referencia, `--hot-x87-transform` y ambos flags experimentales OFF. Los experimentos y sus APK quedan en `.local/profiles/`, no en Git.
- Ambas opciones requieren habilitación manual y son **diagnósticas, no optimizaciones aceptadas**. Ninguna modifica la calidad, FOV, shaders, HUD ni la lógica de colisiones.

## Próximos trabajos con posibilidades más reales

1. **`0x0041B8F0` (247 muestras)** y **`0x004196F0` (158):** cálculos geométricos/colisiones. Identificar precondiciones, resultados y estado x86 completo antes de cualquier ruta nativa; no simplificar ramas a costa de colisiones o precisión.
2. **Familia de visibilidad 0x004Dxxxx (587 muestras sumadas entre cuatro funciones):** identificar subcálculos geométricos repetidos y propiedades invariantes; primero instrumentar/probar propiedades y construir oráculo diferencial, **no** reemplazar el recorrido completo ni alterar decisiones de descarte sin equivalencia.
3. En el teléfono, verificar cada candidato con el **mismo guardado**, al menos 40 ventanas estables por A/B/A y suficiente cobertura posterior de 60 ventanas consecutivas cercanas al techo de 60 FPS para el criterio final; controlar calentamiento, NPC, pantalla y calidad.
4. **Preservar de forma acumulativa** el fast path x87 demostrado (+19,58 %) y las correcciones completas del HUD. Ninguno de estos dos nuevos ensayos alcanza el objetivo de 60 FPS.

Información vinculada: [perfil original](TECNO_CK6N_ARM64_PERF_2026-10-14.md), [análisis de procedencia de funciones](FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md) y [plan](ROADMAP.md).

## Continuación: clasificador NaN binary80 (sin mejora aceptada)

Una nueva ruta de conversión/NaN en CoDSP `p1/p8` se comparó en TECNO ARM64 con el runtime existente: **955.360 casos idénticos**, 98 Python (4 omitidas), 29/29 CTest. Las cinco corridas A/B/A/B/A no confirman aumento real de FPS cuando la última referencia llega a **25,45 FPS**. Flag nuevo `--x87-nan-bits` **OFF por defecto**. [Investigación y datos](ARM64_X87_NAN_BITS_2026-10-14.md).
