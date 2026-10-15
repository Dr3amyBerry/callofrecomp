# WSA 120 FPS — Perfil de CPU de la APK acumulativa REALMENTE instalada

**Investigación:** 2026-10-15 · **Corte de Git antes de investigar:** `d6d6f8e` en `main` limpio.

**Alcance estricto:** solo investigación y documentación. **No se modificaron el recompilador, el runtime, el renderer, los assets, la APK, los ajustes, los guardados ni el limitador de FPS.** Las capturas, scripts de análisis privados y ELF copiados para cotejo permanecen **ignorados por Git** bajo `.local/profiles/wsa120_20261015/postopt_reprofile_20261015/`.

## 1. Identidad rigurosa del experimento

- **Dispositivo:** `127.0.0.1:58526`, WSA `windows_x86_64`. No se utilizó TECNO.
- **Paquete:** `org.callofrecomp`; se enfocó la ventana ya abierta en la escena de entrenamiento (no se cambió mapa, partida ni configuración).
- **APK leída desde su ruta instalada** con `adb pull`: SHA-256 **`a19ea65e30024f7f1f6f55d2be97ba99c854fd1e32e6c151bed6213194da1702`**, **idéntico** al APK acumulativo B archivado; ninguna instalación nueva.
- El `libmain.so` x86_64 del APK coincide por Build ID con el ELF **sin strip** `.local/profiles/wsa120_20261015/cumulative_unstripped.so`: **`23df3b5f896e4252304abd17a232e381b980b2e4`**. **Simpleperf también grabó ese mismo Build ID** en el perfil actual.
- **28/28** fuentes C originales generadas y utilizadas para resolver direcciones coinciden **byte a byte** por SHA-256 con `.local/profiles/wsa120_20261015/generated_source_fingerprints.json`. Si uno de estos hashes cambiase, la atribución PC ARM64/x86_64→línea C→PC guest dejaría de ser fiable.
- El log del proceso confirmó `frame limit guest=120 host=120`, `native x87 enabled=1`, GL4ES 1.1.7 y geometría de superficie **1280×720**. Se conserva la configuración anterior de calidad **Alta**; no se modificó.
- La presentación sigue en modo virtual **75 Hz**. **120 fotogramas visibles/s no son posibles en este modo**, aunque el motor pueda llegar a generarlos.

## 2. Fotogramas actuales: captura NUEVA, sin profiler simultáneo

Script ya existente, sin modificación: `tools/recomp/diagnostics/capture_wsa_presentation.py`.

Captura de **35,47 segundos** con **35 ventanas de ~1 s** del motor y **2.252 intervalos SurfaceFlinger**. Cobertura de timestamps completa, PID estable, sin indicios de carga/menú mezclados ni intervalos >50 ms.

| Indicador | Valor medido |
| --- | ---: |
| FPS motor, mediana de ventanas | **67,2 FPS** |
| FPS p10 de ventanas / mínimo de ventanas | 60,3 / 58,5 |
| Tiempo reportado como CPU/frame, mediana | **14,89 ms** |
| Swap, mediana / pacing, mediana | 1,03 / **0,00 ms** |
| Frecuencia de presentación observada | **63,48 presentaciones/s** |
| Intervalo de presentación, mediana | 13,333 ms |
| Intervalos de presentación p95 / p99 | **26,667 / 32,290 ms** |
| Refresco informado por compositor | **75 Hz** |

**Comparación correcta:** el acumulativo B anterior, sobre la misma configuración, obtuvo medias de medianas de **66,75 FPS y 14,985 ms/frame** en dos corridas. La medición nueva (67,2/14,89) **corrobora el mismo orden de rendimiento**, no demuestra una nueva ganancia ni es un nuevo ensayo A/B.

**Para 120 FPS de generación:** objetivo `8,333 ms/frame`; falta reducir ~**6,56 ms/frame**, es decir **44,0 % del valor reportado**. No afirmar que todo ese presupuesto sea CPU puro exclusivo; existen esperas, presentación y GPU sin medir.

Evidencia privada: `postopt_reprofile_20261015/present_current1.{json,log,timestamps.json}`.

## 3. Simpleperf NUEVO: perfil de la APK B exacta

Se capturó el mismo proceso en la escena ya cargada, **después** de la medición de fotogramas; NO se perfiló simultáneamente para evitar contaminar FPS.

- **Perfil de tareas:** `task-clock`, **500 Hz**, 25,0 s, **12.695 muestras, 0 perdidas**. La invocación inicial del shell genérico fue denegada por permisos; la válida se hizo con `run-as org.callofrecomp simpleperf` (UID normal de la app), **sin root ni modificar SELinux**.
- **Perfil adicional con callstacks DWARF:** `task-clock`, **200 Hz**, 25,0 s, **5.074 muestras, 0 perdidas**; **4.688** incluyen pila desenrollada. Ambos perfiles verifican identidad del ELF instalado. **No mezclar sus recuentos como si fueran una única captura**.
- Análisis read-only con `simpleperf_report_lib`, `llvm-readelf`, `llvm-addr2line`, fuentes C con hash fijado y mapas Ghidra B v2. De 9.465 muestras nativas en `libmain.so`, 6.936 se asociaron a etiquetas guest y **5.788** a un cuerpo original Ghidra de propiedad única. El resto **no se reasigna por suposición**.

### Distribución de la captura de 12.695 muestras

| Biblioteca/categoría host | Muestras | % de todas las muestras |
| --- | ---: | ---: |
| `libmain.so` — juego recompilado, helpers y runtime | **9.465** | **74,6 %** |
| `libc.so` | 1.292 | 10,2 % |
| `libOpenglSystemCommon.so` — transporte OpenGL | 809 | 6,4 % |
| `libOpenglCodecCommon.so` — preparación/codec | 228 | 1,8 % |
| `libGL.so` y `libGLESv2_enc.so` | 382 | 3,0 % |
| Kernel y resto de módulos | remanente | no atribuido en detalle |

**Los porcentajes representan muestras de PC nativo**, no fracciones garantizadas de los 14,89 ms, tiempo exclusivo de funciones ni duración de GPU.

## 4. Hallazgo 1 — el coste transversal dominante permanece en R/U y x87

**Origen real y líneas de código:**

- `tools/recomp/recomp_rt.h:19–20`: `rd()` y `wr()`, llamadas `memcpy()` sobre byte arrays para cada valor de registro/temporal/memoria.
- `tools/recomp/recomp_rt.h:84`: `f2d()`, interpretación de binary80/float como double.
- `tools/recomp/recomp_rt.h:115`: `d2f()`, materialización de representación float/binary80.
- `tools/recomp/recomp_rt.h:227–247`: opción `codsp_x87_normal_f2d` con fallback a conversión original; **no generalizarla sin oráculo**.
- `tools/recomp/pcode2c.py`: lowering de lectura/escritura de varnodes y operaciones flotantes; la ruta `Gen.rd`/`Gen.wr`/`Gen.op` es el sitio arquitectónico a investigar, pero **no se modificó**.

Dentro de **`libmain.so`**, DWARF identifica una familia dominante por PC de muestra (una familia etiquetada por PC nativo, categorías excluyentes **solo en esta clasificación de DWARF**):

| Etiqueta de helper | Muestras | Precaución |
| --- | ---: | --- |
| `memcpy` inline | **3.337** | Puede ser código escalar inlined de `rd/wr`; NO equivale a 3.337 llamadas libc |
| `f2d` | **1.769** | Familia de conversión, no tiempo de una única microoperación |
| `d2f` | **857** | Idem |
| `codsp_native_x87_region_try` | **208** | Guard y frontera de región x87 nativa |
| `nx87_5061b0_56` | **550** | Símbolo nativo de la última instrucción x87 del bloque acelerado, no coste aislado de esa instrucción |
| `nx87_5061b0_0` | **165** | Primera instrucción del bloque; cuidado con etiquetado de prólogo/epílogo |

Las tres primeras categorías contabilizan **5.963 de 12.695 muestras (~47 % de las muestras del proceso)** en **familias de puntos nativos de `libmain.so`**, pero **NO puede afirmarse que eliminar rd/wr/f2d/d2f ahorraría el 47 % del fotograma**. DWARF, inlining, alias, estados de x87 y organización de C pueden atribuir un PC a varias operaciones conceptuales. Se necesita observar el ensamblador en esos PCs y una comparación A/B antes de estimar ahorro causal.

La atribución por cuerpo original Ghidra muestra que las muestras **memcpy inline** se dispersan por muchas funciones: `0x004CC670` (136), `0x0041B8F0` (124), `0x0042B0A0` (116), `0x0047BD40` (98), `0x004196F0` (90), `0x0041CD60` (88). Las muestras **f2d** también aparecen ampliamente: `0x004196F0` (126), `0x00475D80` (90), `0x0047BD40` (70), `0x004D8280` (63).

**Por qué merece el bloque grande:** hay trabajo asociado al mismo modelo genérico de estado virtual en muchas funciones, no solamente una superregión de 6–8 instrucciones. Para una próxima optimización investigaría primero el ensamblador nativo de los PCs etiquetados como `memcpy/f2d/d2f`, liveness y escrituras de R/U entre instrucciones, y **únicamente después** una estrategia de fusión/mantenimiento de valores que conserve equivalencia arquitectónica.

**Prohibido como atajo:** convertir todas las operaciones x87 a double, ignorar CW/SW/TOP/tags, saltarse accesos RAM o reactivar CFG14. Hay divergencias de precisión y faltas guest conocidas. Cualquier cambio futuro requiere original i686/Unicorn cuando sea fiable, datos binary80 completos, memoria/alias, banderas, PC y fallos; ensayo A/B de ms/frame para aceptar.

## 5. Hallazgo 2 — PC originales concretos de geometría, visibilidad y copias

La resolución del **ELF acumulativo B actual** contra C **byte a byte** y Ghidra B da:

| Función x86 original | Muestras (perfil 500 Hz) | Punto concreto de inspección |
| --- | ---: | --- |
| `0x004196F0` — geometría | **304** | `recomp_out/codsp_recomp_p0.c:243297` |
| `0x0041B8F0` — geometría/colisiones | **273** | `recomp_out/codsp_recomp_p1.c:8413` |
| `0x0041CD60` — geometría/estado | **220** | `recomp_out/codsp_recomp_p1.c:25196` |
| `0x0047BD40` — estructuras/estado | **213** | Cuerpo original Ghidra B, incluido en el mapa privado |
| `0x004D8280` — visibilidad | **194** | `recomp_out/codsp_recomp_p8.c:41254` |
| `0x00475D80` — operaciones float/estado | **189** | Cuerpo original Ghidra B |
| `0x004D94C0` — visibilidad | **161** | Cuerpo original Ghidra B |
| `0x004CC670` — lecturas/estructuras | **160** | `recomp_out/codsp_recomp_p7.c`, PC puntual `0x004CC6E9` |

**Dos instrucciones especialmente reproducibles:**

1. **`0x0042B100`** → `recomp_out/codsp_recomp_p1.c:157616–157620`: fast path `codsp_copy32_step` y fallback original de ocho pares MOV. Definición **`tools/recomp/runtime/codsp_copy32.h:17`**: protección de cruces de 4 GiB, alias, solapamiento y páginas. La familia `memcpy` de este PC tuvo **72 muestras**. **No se sabe la tasa de aceptación del fast path**, por lo que no se debe afirmar que está fallando o acelerando ese PC sin un contador validado.
2. **`0x004CC6E9`** → `recomp_out/codsp_recomp_p7.c:135109–135112`: lectura indirecta RAM guest y escritura E/C register vía `rd/wr`, etiquetado `memcpy` con **72 muestras**. Es una ubicación útil para estudiar eliminación de materializaciones y alias, pero no cambiar el orden de faltas ni datos visibles.

Otras ubicaciones de interés:

- `0x004D82D4` → `recomp_out/codsp_recomp_p8.c:41424–41429`, preparación/copia de slots binary80 antes de una operación x87; **58 muestras en familia f2d** en ese PC.
- `0x004D96B0` → `recomp_out/codsp_recomp_p8.c:59131–59135`, lectura guest.
- `0x0041A793` → `recomp_out/codsp_recomp_p0.c:255095`, instrucción asociada a f2d.

**Advertencia de IP/lanzamiento:** los archivos `recomp_out/*.c`, los PE, mapas y símbolos no se agregan al GitHub público. Las rutas anteriores son **referencias locales para el agente**, no enlaces públicos a código original.

## 6. Hallazgo 3 — ruta concreta del renderer GL4ES/WSA

En el perfil no-simultáneo de 12.695 muestras aparecen:

- `libc.so memcpy`: **1.179 muestras**, pero **no se puede adjudicar todo a gráficos**.
- `libOpenglSystemCommon.so`: **809** (con `AddressSpaceStream::speculativeRead`, ring buffers y escritura de transporte).
- `libOpenglCodecCommon.so`: **228**, incluye `glUtilsPackPointerData` (**125**).
- `libGLESv2_enc.so`: **191**, incluye `GL2Encoder::calcIndexRange` (**161**).
- `libGL.so`: **191**, wrapper GL4ES y GL.
- `libmain.so` también contiene el coste de las llamadas GL, pero **no hay reparto exclusivo fiable** de esa porción.

La segunda captura con pilas DWARF, **5.074 muestras**, muestra caminos completos:

- `glDrawRangeElements` → `GL2Encoder::s_glDrawElements` → `sendVertexAttributes` → `glVertexAttribPointerData_enc` → **`glUtilsPackPointerData` / transporte**.
- `eglSwapBuffers` → `egl_window_surface_t::swapBuffers` → `createNativeSync_virtioGpu` → `rcCreateSyncKHR_enc` → `AddressSpaceStream::readFully` / `speculativeRead`. Muestras de pila con estos sufijos incluyen grupos de **143 y 91** PCs de hoja; **son rutas de pila, no tiempos exclusivos ni latencia GPU**.
- De **498** muestras `libc memcpy/memmove` en este perfil de stacks, **127** tenían `glUtilsPackPointerData` como primer caller fuera de libc; **371** quedaron sin caller fiable. **No adjudicar 371 a GL ni al recompilador**.

Puntos exactos del proyecto a inspeccionar:

- `tools/recomp/runtime/gl_thunks.c:1187–1191`: forwarding `glDrawRangeElements`, gestión de puntero índice.
- `tools/recomp/runtime/gl_thunks.c:4625–4629`: `glVertexPointer`, puntero de atributo.
- `tools/recomp/runtime/gl_buffer_pointers.h`: `gl_bridge_arg` separa offset de VBO si hay buffer vinculado de dirección guest si el buffer no está vinculado.
- `tools/recomp/runtime/gl_thunks.c` y `gl_perf_metrics.h`/`gl_call_timing.h`: **ya existe infraestructura opcional** para contar draws, índices, buffers y medir tiempo CPU dentro de thunks, sin confundirlo con GPU.

**Candidato de mejora REAL, no implementado aquí:** demostrar en una próxima compilación de diagnóstico si el mismo conjunto de índices/atributos se empaqueta en cada draw por usar client arrays sin VBO, y migrar/reutilizar **buffers GPU persistentes solamente cuando se conozcan las escrituras e invalidaciones**. El objetivo es reducir `glUtilsPackPointerData`, `sendVertexAttributes` y `AddressSpaceStream::type1Write` por fotograma, **sin suprimir draw calls, geometría, texturas ni efectos**. Un caché que no invalide cambios de animación o buffer sería incorrecto.

La biblioteca WSA `libOpenglSystemCommon.so` y el encoder son externas al proyecto: mejorar código de dispatch local o backend GL4ES no garantiza eliminar sus transferencias. Si el paso host↔WSA está impuesto por el dispositivo, distinguir límite de plataforma frente al coste del juego.

## 7. Orden recomendado para el siguiente BLOQUE GRANDE de desarrollo

**P1 — materialización y conversiones de datos virtuales en C generado.** Primero inspeccionar desensamblado de las direcciones nativas realmente muestreadas y trazar qué copias son escalares, cuáles son 10 B binary80, cuáles son 32 B y cuáles se repiten entre instrucciones. Evaluar una transformación con *liveness* comprobable y checkpoint de estado en fronteras seguras. Probar el original x86, U/R, alias, EFLAGS, FPU, memoria, PC y fault. **No reactivar regiones CFG14 con memoria mientras siga faltando reanudación segura Android**. No asumir un porcentaje de mejora a partir de los 3.337/1.769/857 samples.

**P2 — ruta de geometría hacia WSA OpenGL.** Medir con contadores de llamadas GL/perfil de buffers ya disponibles (requiere otra build de diagnóstico, **NO AUTORIZADA EN ESTA INVESTIGACIÓN**). Confirmar client arrays, frecuencia de actualización de vértices, número real de llamadas GL y rango de índices. Entonces evaluar VBO/index streaming o batch de comandos **solo con fidelidad visual y equivalencia garantizadas**. Medir tasa de presentación y reducción de CPU/frame, no solo muestras de driver.

**P3 — reducir coste de frontera de la región x87 nativa `0x005061B0`.** La ruta del runtime en `tools/recomp/runtime/guest.c:793–797`, el contrato en `tools/recomp/runtime/native_x87_bridge.h` y el emisor `tools/recomp/native_x87_region.py` protegen FPU/memoria/RET. Analizar por qué las etiquetas `nx87_5061b0_56`, `nx87_5061b0_0` y el guard `codsp_native_x87_region_try` reciben muestras; solo reducir guardas, import/export o FNSAVE/FRSTOR si el estado binario original y las faltas siguen siendo exactos. Una sola función no resuelve los 120 FPS.

**P4 — atribución de las `memcpy` externas y espera EGL.** Capturar perfiles con callstacks más fiables donde sea posible y métricas de driver. Identificar las 371 llamadas `memcpy` sin caller que quedaron indeterminadas y las rutas de sincronización WSA `AddressSpaceStream`. Evitar instalar backends Vulkan experimentales sin mejora física comprobada.

**Criterios de aceptación para TODAS:** misma APK/config A/B/A/B (o builds aisladas iguales salvo una opción), 35–60 ventanas gameplay tras calentamiento, FPS y CPU/frame, percentiles de presentación, hash de partidas, telemetría y original-x86 oracle para semántica. Solo retener optimizaciones que mejoren el frame real reproduciblemente.

## 8. Límites y reproducibilidad

- Los recuentos de dos capturas con 500 Hz y 200 Hz **no son directamente sumables**.
- No se midió **tiempo GPU** ni se descompuso causalmente cada microoperación C/GL en milisegundos por fotograma.
- Los atributos de origen C proceden de tablas DWARF optimizadas y Ghidra B; son aproximados incluso si los archivos y el ELF corresponden exactamente.
- Los marcadores `nx87_*` no ofrecen un coste por instrucción exacto; prólogo/epílogo e inlining pueden quedar atribuidos a una etiqueta adyacente.
- La imagen de una escena de entrenamiento no certifica toda la calidad visual ni situaciones de combate.
- Se ha mantenido CFG14 BLOQUEADO y el helper double original prohibido; **cero cambios de código, hardware, shaders, calidad o compilaciones**.

**Evidencia local bajo `.local/profiles/wsa120_20261015/postopt_reprofile_20261015/`:**
`installed_base.apk`, `installed_libmain.so` (copia para hash, no subir), `present_current1.json`, `present_current1.log`, `present_current1.timestamps.json`, `postopt_A.perf.data`, `postopt_A_analyzed.json`, `postopt_stacks_A.perf.data`, `postopt_stacks_A_analyzed.json`, `postopt_A_helper_guest_split.json`, y scripts privados de atribución. El lector debe tratar estos como **datos privados**, fuera de GitHub.

**Decisión:** el siguiente desarrollo debería investigar el coste transversal de R/U y de representación x87 **y** el reempaquetado de arrays OpenGL antes de volver a buscar pequeños subgrafos CFG. Se sabe con exactitud qué APK se midió, qué PC/archivos corresponden a varias zonas calientes y cuáles son los límites de atribución. **120 FPS aún no alcanzados.**
