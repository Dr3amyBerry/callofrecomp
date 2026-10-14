# TECNO CK6n: medición real de CallofRecomp ARM64 — 2026-10-14

**Resultado actualizado:** cuello de botella de CPU verificado y primera mejora de FPS reproducida en el entrenamiento mediante una ruta nativa x87 **optativa**; todavía no aprobada para activación general. Este documento registra pruebas en un teléfono real, no promesas de producción. No contiene número de serie, perfiles brutos, archivos comerciales ni partidas.

## Meta explícita: 60 FPS sostenidos en la zona inicial

**PENDIENTE**, aunque hubo una mejora real y verificada. El usuario no dará
la optimización por completada hasta medir **60 FPS sostenidos en el punto
donde aparece el personaje** al comenzar training en el TECNO CK6n,
calidad Equilibrado. No confundir la zona inicial con el menú o el
sector concurrido que está más adelante.

La mejora anterior **sí ocurrió**: **21,45 -> 25,65 FPS** de mediana
en 40 ventanas estables (**+4,20 FPS, +19,58 %**) y
**44,745 -> 37,495 ms de CPU/frame (-7,25 ms)**. Esa ganancia se
mantendrá registrada sin afirmar que ya son 60 FPS. Faltan **34,35 FPS**.
Para 60 FPS, el tiempo total por frame debe estar cerca de 16,67 ms;
el uso de CPU del motor actual todavía ronda 37,50 ms/frame.

Criterio de validación pendiente: capturar al menos 60 ventanas de
~1 segundo de gameplay consecutivo en el mismo spawn, sin cargas,
menús o pausas, con FPS bajos/medianos, CPU y estado térmico, y
comparaciones A/B/A. No aceptar los ~53 FPS del menú ni los ~25,65 FPS
del entrenamiento como objetivo final.

## Entorno y reproducibilidad

- TECNO CK6n, Android 14, MT6768, Mali-G52; 2 núcleos de hasta 2 GHz y 6 de hasta 1,8 GHz.
- APK de depuración nativa ARM64; compilación normal a -O1, herramientas invasivas desactivadas durante medición de FPS.
- Call of Duty PC 1.5 original del propietario: hashes de CoDSP.exe y las tres DLL coinciden exactamente con el manifiesto del proyecto; 17 archivos PK3 privados. Importación mediante lector codpack con CRC. Nunca publicados.
- Escena: entrenamiento Camp Toccoa, misma partida guardada en 00:00:03, cámara estática cerca de los carteles y la valla. El soldado/NPC y la temperatura pueden variar entre sesiones. No es el tramo concurrido ni toda la campaña.
- Datos de FPS: resúmenes del motor de aproximadamente un segundo; medianas y p10 son **de ventanas de resumen**, NO percentiles de frames individuales. Cada carga descarta sus transiciones antes de comparar. Las medidas Simpleperf se tomaron por separado.

## Comparaciones en el teléfono

| Prueba | Ventanas | Mediana FPS | CPU media por frame, mediana | Swap, mediana | Decisión |
| --- | ---: | ---: | ---: | ---: | --- |
| Normal -O1 / Equilibrado | 40 estables tardías | **21,55** | **44,585 ms** | **2,31 ms** | Referencia |
| -O2 solo CoDSP p10/p11 / Equilibrado | 40 tardías, con variación al inicio | 21,50 | 44,62 ms | 2,32 ms | Sin mejora demostrable |
| -O2 solo CoDSP p10/p11 / Equilibrado | Últimas 20 estables | 21,65 | 44,27 ms | 2,31 ms | Diferencia mínima; referencia últimas 20: 21,45 FPS |
| -Oz solo CoDSP p10/p11 / Equilibrado | 7 ventanas de juego posteriores a la carga | **12,4** (9,8–13,4) | No adoptado | 2–2,5 ms aprox. | Empeoró claramente; descartado |
| Normal -O1 / Ligero | 40 tardías, con variación y cambios de escena/NPC | **21,40** | **44,865 ms** | **2,37 ms** | Sin ganancia sostenida ni mejora visual |
| Normal -O1 / Equilibrado (A2, repetición posterior) | 40 estables | **21,45** | **44,745 ms** | **2,33 ms** | Reconfirmación |
| Fast path x87 0x005061B0 / Equilibrado (B) | 40 estables | **25,65** | **37,495 ms** | **2,02 ms** | Ganancia medible en esta escena; solo experimental |

La comparación de 20 ventanas estables de -O2 frente a la base fue
21,65 frente a 21,45 FPS: +0,20 FPS (+0,93 %). Esto no demuestra una
mejora al no superar la variación entre corridas y no existir un A/B/A
controlado térmicamente. El ensayo -Oz tuvo una pérdida inequívoca de
rendimiento desde las primeras siete ventanas: se revirtió pronto por
seguridad; **no es una muestra de 40 ventanas**. El modo Ligero redujo
resolución, LOD, detalle y cielo; varios intervalos estuvieron en 15–18
FPS y otros en 22–23 FPS: no se confirmó una ganancia sostenida.

El menú se mantenía cerca de 52–54 FPS con 6–8 ms CPU, pero esto no
representa el juego 3D. La espera de swap del entrenamiento es ~2,3 ms,
contra ~44,6 ms de CPU del motor: el problema observado es principalmente
la CPU, no la tasa de presentación del framebuffer.

## Perfil nativo con Simpleperf y función original prioritaria

Captura separada: 5.504 muestras CPU user-space en 14,946 segundos, 0
pérdidas. 4.661 muestras corresponden a libmain.so; 4.586 de ellas se
ejecutaron en los núcleos rápidos 6 y 7. Fijar afinidad de CPU no está
respaldado por estos datos.

| Chunk del CoDSP.exe recompilado | Muestras | Porcentaje del total |
| --- | ---: | ---: |
| 186 | 679 | 12,34 % |
| 152 | 339 | 6,16 % |
| 187 | 232 | 4,22 % |
| 19 | 231 | 4,20 % |
| 88 | 216 | 3,92 % |

Al resolver las direcciones nativas a líneas C, etiquetas x86 y rangos
discontinuos de Ghidra: 3.835 muestras tienen etiqueta x86, 3.439
tienen un cuerpo Ghidra único, 396 carecen de propiedad inequívoca y
826 no tienen línea C válida. Estas cifras reconcilian a 4.661 y son
**muestras estadísticas**, no tiempos exclusivos.

La función original más destacada es **CoDSP.exe 0x005061B0**:
656 muestras (14,1 % de muestras de libmain.so). Funciones siguientes:
0x0041B8F0: 166; 0x0047BD40: 162; 0x004D94C0: 150.
La inspección privada de Ghidra identifica transformaciones de dos
vectores por matrices 3D (posición y dirección) con operaciones x87.
En sus 58 instrucciones hay 506 operaciones p-code, incluidas
345 COPY, 45 FLOAT2FLOAT, 18 FLOAT_MULT y 15 FLOAT_ADD. Son
conteos estáticos, no frecuencia de ejecución.

Un ensayo de micro-ensamblado ARM64 a -O1, sin cambiar el juego,
comparó siete copias de registros x87 de 10 bytes implementadas
mediante rd/wr frente a memcpy: Clang ya genera cargas/almacenamientos
equivalentes. Esa modificación global fue descartada por falta de
evidencia de ahorro.

## Fast path x87 ARM64: comparación A/B/A reproducida en el teléfono

Tras revisar las pruebas anteriores sin borrar sus archivos ni modificar la
partida, se añadió la implementación `hot_x87_transform.h`, habilitada
únicamente mediante `--hot-x87-transform` en compilaciones Android privadas.
La ruta normal sigue desactivada por defecto. Solo intercepta la entrada
exacta de CoDSP.exe 1.5 `0x005061B0`; preserva el orden de las seis salidas
vectoriales, registros x87 modificados y ESP/retorno. Cuando los punteros
se solapan, están desalineados o las entradas no son finitas, vuelve a
ejecutar el código recompilado original.

Un programa ARM64 aislado, enlazado con la cabecera utilizada realmente por
el runtime, comparó **75.000 casos** contra los 58 pasos traducidos de
p-code: **69.152** entraron por la vía nativa y **5.848** por la original,
con igualdad bit a bit de todo el espacio de registros y la RAM simulada
tras cada llamada. Se probaron diferentes magnitudes, NaN, infinito,
solapamientos y rutas de fallback. Esto contrasta contra la **traducción
existente**, no contra la ejecución del binario en una CPU x86 real;
tampoco valida todas las misiones o estados del juego. El microbenchmark
aislado en el teléfono registró ~315 ms para 250.000 llamadas de referencia
frente a ~26 ms para la ruta rápida, **no** una ganancia extrapolable a FPS.

Una prueba A/B/A en la misma entrada del entrenamiento y mismo guardado,
calidad Equilibrado, con 40 ventanas de ~1 segundo estabilizadas por
ejecución, obtuvo:

| Corrida | FPS mediana | p10 FPS de ventanas | CPU ms/frame | Swap ms/frame |
| --- | ---: | ---: | ---: | ---: |
| A1 normal previa | 21,55 | — | 44,585 | 2,31 |
| B fast path nativo | **25,65** | **24,8** | **37,495** | **2,02** |
| A2 normal reinstalada | **21,45** | **20,4** | **44,745** | **2,33** |

La comparación directa B frente a A2 es **+4,20 FPS (+19,58 %)**
y **-7,25 ms de CPU por frame**. Los registros ignorados son privados
`.local/profiles/tecno_trial_native_transform_stable40.log` y
`.local/profiles/tecno_recheck_baseline_stable40.log`, comparables con:

~~~powershell
python tools/recomp/analyze_frame_stats.py --baseline .local/profiles/tecno_recheck_baseline_stable40.log --candidate .local/profiles/tecno_trial_native_transform_stable40.log --last 40 --json
~~~

La escena, el NPC, el estado térmico y la instrumentación hacen que esta
prueba sea específica de la entrada de Camp Toccoa en el TECNO CK6n.
No valida FPS en la zona concurrida de alambres, toda la campaña ni otros
teléfonos. La equivalencia independiente con ejecución Intel x86 y una
prueba visual/mecánica más amplia siguen pendientes.

Compilación normal y optativa verificadas separadamente:

~~~powershell
python tools/recomp/build_android.py --jobs 3
python tools/recomp/build_android.py --hot-x87-transform --jobs 3
~~~

La APK optativa firmada se conserva **fuera de Git** bajo
`.local/profiles/tecno_hot_transform_candidate_arm64.apk`
(y opcionalmente `recomp_out/callofrecomp-hot-x87-arm64-debug.apk`).
La APK normal de `recomp_out/callofrecomp-arm64-debug.apk` se reconstruyó
con `CODRECOMP_HOT_X87_FASTPATH=OFF`. El teléfono terminó con la APK
experimental instalada, el lanzador indicando «Instalación lista», calidad
Equilibrado y las partidas sin modificar. No publicar binarios del juego.

**Verificaciones:** 93 pruebas Python correctas (4 omitidas), 26/26 CTest,
compilación NDK ARM64 y firma APK V2/V3 correctas.

## Cómo repetir y continuar

La herramienta pública de comparación sin conexión es
[analyze_frame_stats.py](../tools/recomp/analyze_frame_stats.py).
Con archivos de registro privados bajo .local/profiles:

~~~powershell
python tools/recomp/analyze_frame_stats.py --baseline .local/profiles/tecno_baseline_stable.log --candidate .local/profiles/tecno_trial_O2_stable40.log --last 20
~~~

Para muestreo real usar el NDK Simpleperf app_profiler.py sobre
org.callofrecomp, guardar el libmain.so exacto **sin strip**, extraer
vaddr_in_file con simpleperf_report_lib y ejecutar
[resolve_guest_samples.py](../tools/recomp/resolve_guest_samples.py)
con los cuatro mapas Ghidra privados v2 y las fuentes C generadas
correspondientes. Comprobar siempre las identidades de compilación
y fuentes; line tables optimizadas no garantizan reconstruir la pila
de llamadas original.

**Siguiente fase:** mantener la mejora como optativa hasta verificar
la ejecución x86 original con un oráculo independiente, los casos de
redondeo/excepciones x87 que no representa el runtime actual, y partidas,
misiones y calidad visual en escenas variadas. Perfilar individualmente el
tramo concurrido de entrenamiento y repetir A/B/A en ese escenario.

**Estado de instalación tras esta continuación:** la corrida A2 volvió
temporalmente a la APK normal y confirmó la caída al valor de referencia.
Al terminar se reinstaló la APK experimental con el fast path, conservando
los originales, guardados y perfil Equilibrado. En el PC, la APK normal
también fue reconstruida y firmada con la opción **OFF por defecto**.
Ambas variantes quedan respaldadas de forma privada.
Los binarios originales/PK3, perf.data, sidecars de Ghidra y
demás datos privados quedan ignorados por Git. Solo se borró
el codpack temporal de Descargas tras su importación exitosa,
liberando alrededor de 1,26 GB sin tocar los recursos instalados.
