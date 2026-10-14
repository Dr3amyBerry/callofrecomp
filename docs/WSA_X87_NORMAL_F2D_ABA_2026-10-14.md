# WSA — A/B/A de conversion x87 normal f2d (2026-10-14)

**Decision: rechazar para WSA.** La especializacion `CODRECOMP_X87_NORMAL_F2D` no mejoro el rendimiento 3D de CallofRecomp. Mantenerla optativa y **OFF** en el artefacto normal. La meta de 60 FPS en TECNO CK6n ARM64 sigue pendiente; contador oficial TECNO **0/5**, pues WSA x86_64 NO es una validacion fisica ARM64.

## Trazabilidad

- Nodo: `windows-pc`, workspace `callofrecomp`, rama `main`, commit inicial `1fb639bf339167a6cf6ac391247ad3df71fe3b11` y arbol Git limpio.
- Entorno: WSA Android 33 x86_64 `127.0.0.1:58526`, GL4ES normal, ANGLE no instalado y preferencias `angle_*` sin override. Limite del host de 60 FPS activo.
- Escena: Camp Toccoa Training, misma partida y punto de aparicion, camara inmovil, perfil Equilibrado. Se inspeccionaron capturas reales de ambas variantes (no hay un SSIM automatico de estas dos capturas).
- Medicion: `tools/recomp/diagnostics/capture_wsa_game_frames.py`, 30 segundos por corrida, ultimas 20 ventanas de ~1 segundo, rechazo de transicion menu/carga, comprobacion de PID y backend al inicio/final. El p10 es percentil de **FPS promediados por ventana**, no percentil de frames individuales.

| Metrica | A1 referencia GL4ES | B1 x87 f2d | A2 referencia GL4ES |
| --- | ---: | ---: | ---: |
| FPS mediana | 55,10 | 54,55 | 55,35 |
| FPS p10 por ventana | 51,60 | 51,30 | 54,90 |
| CPU ms/frame mediana | 17,310 | 17,765 | 17,290 |
| Swap ms/frame mediana | 0,84 | 0,92 | 0,84 |
| Pace ms/frame mediana | 0,78 | 0,605 | 0,79 |
| Ventanas seleccionadas | 20 | 20 | 20 |

**Calculo:** referencias A media=55,225 FPS y 17,300 ms CPU; B cae 0,675 FPS (aprox. -1,22 %) y consume +0,465 ms CPU/frame (+2,69 %). No se debe atribuir causalidad precisa con solo una B: la decision operativa es que **NO existe aceleracion demostrada** en WSA, y los resultados apuntan a regresion. Los p10 varian entre controles A1/A2: no extrapolar diferencias pequenas.

## Compilacion, integridad y rollback

1. Se recupero la tarea anterior `9247d3b4effc4a6183cec4694c0ec74b`: `python tools/recomp/build_android.py --abi x86_64 --x87-normal-f2d --jobs 3` exit 0; APK x86_64 firmada/verificada. CMake cache durante B: `CODRECOMP_X87_NORMAL_F2D:BOOL=ON`. La especializacion aplica solo a CoDSP p1/p8 y tiene fallback original.
2. Antes de la B, `check_exact_installed_reference.py` verifico `libmain.so` de la APK A **SHA-256 403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde**; ambos guardados de WSA coincidian con backup privado (sin modificar archivos).
3. APK B instalada mediante `adb install -r`, sin borrar datos; misma `GameActivity`, `Camp Toccoa`, GL4ES confirmado. Captura B: PID 11835. APK B preservada bajo `.local/profiles/phase2_perf_wsa_x87_f2d_candidate_B.apk`.
4. APK A de referencia restaurada mediante `adb install -r .local/profiles/wsa_vulkan_ab/reference_A_gl4es_x86.apk`; instalacion `Success`, comprobacion posterior de `libmain.so` **identica byte a byte** a la referencia A. Captura A2: PID 12138.
5. Evidencia privada no versionada: `.local/profiles/phase2_perf_wsa_x87_f2d_{A1,B1,A2}.json` y `.log`. **No subir** APK, saves ni recursos comerciales a Git.
6. El ensayo en WSA no demuestra ni refuta el rendimiento de la conversion en el TECNO ARM64. En la documentacion ARM64 existe un microbenchmark aislado favorable a esta funcion; solo un A/B/A de gameplay fisico puede resolver esa hipotesis. No alterar la estrategia oficial ni el contador 0/5.

## Siguiente bloque

En el TECNO, repetir A/B/A con el flag completo apropiado y muestras CPU/temperatura. Mientras no este conectado, analizar el mayor coste dinamico verificable en WSA, separar los ~17 ms de CPU de geometria/visibilidad, despacho y driver; **no** repetir cambios intuitivos en x87, GL4ES/VBO o Vulkan sin perfil nuevo.
