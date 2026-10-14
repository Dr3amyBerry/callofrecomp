# Estrategia vigente de rendimiento — CallofRecomp

**Estado:** VIGENTE · **Desde:** 2026-10-14 · **Versión:** 1 · **Decisión:** no cambiar de estrategia sin evidencia nueva suficiente.

## Diagnóstico Fase 2 posterior: candidato CPU y prueba fallida de ahorro de instrucciones

Se auditó el cuerpo original `0x0041B8F0` con p-code/Ghidra privados y sitios ARM64 reales: 553 instrucciones, 3.957 operaciones, 1.789 copias y rangos repartidos en un chunk compartido por 12 funciones. Se probó aisladamente una conversión `rd/wr`→`memcpy` para el desplazamiento de siete registros x87 de 80 bits: **20.000 casos equivalentes**, pero **29 instrucciones AArch64 en ambos núcleos** bajo Clang `-O1` y `-O2`. No cambiar el generador ni afirmar mejora por C más corto. Sin teléfono conectado no hay nuevo A/B ARM64 real; mantener 60 FPS como meta y **0/5**. [Informe fase 2](CPU_PHASE2_41B8F0_AUDIT_2026-10-14.md).

## Resultado posterior: A1/B/A2 completo en Camp Toccoa WSA, sin mejora de ANGLE (0/5)

Ensayo controlado de **gameplay 3D** con mismo save/cámara y 60-FPS host cap: **GL4ES A1 54,75**, **ANGLE/Vulkan B 55,15**, **GL4ES A2 55,20** FPS medianos (20 ventanas de ~1 segundo, 30 s/run); p10 respectivamente **50,2 / 47,6 / 54,6** FPS. CPU/frame **17,54 / 17,80 / 17,43 ms**. B solo +0,175 FPS (+0,318 %) frente a la media A, dentro de la variación A1–A2; p10 B inferior. El mismo PID confirmó ANGLE/Vulkan al inicio y al cierre de B. Imagen 3D con SSIM 0,995943 frente a GL4ES, capturas privadas no sincronizadas y no prueba exhaustiva. **Sin mejora demostrada: mantener GL4ES producción y estrategia de fases ARM64 vigente.** APK y saves idénticos tras rollback; el TECNO no estuvo conectado, por tanto **0/5 intentos válidos**. [Reporte completo](ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md).

## ANGLE: compatibilidad Vulkan confirmada en WSA, todavía sin A/B de gameplay

La fuente oficial ANGLE pinneada (`43140711d13063716fd32a15de829885d0bce469`) fue compilada en GitHub Actions Linux y el APK x86_64 pasó verificaciones de ABI, EGL/GLES, identidad, firma Android y SHA-256. La aplicación real **CallofRecomp** abrió `GameActivity` con el paquete ANGLE experimental y su propio PID reportó **Renderer Vulkan 1.3 AMD Radeon**; el menú original se mostró y no presentó diferencias visuales evidentes frente al menú nativo GL4ES. La APK experimental fue desinstalada y los ajustes revertidos. **No** se comprobó equivalencia 3D, FPS Camp Toccoa ni rendimiento ARM64/Mali. La fase CPU actual conserva prioridad: **no cambiar de renderer ni de estrategia sobre esta sola prueba**, contador **0/5**. [Informe de ejecución real](ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md).

## Resultado de investigación Mesa Zink (sin A/B del juego)

Se descargó e inspeccionó Mesa **26.2.4** y se midieron **capacidades Vulkan reales**, no FPS, en el WSA actual. Al menos cuatro requisitos obligatorios del perfil Zink GL2.1 están ausentes: `alphaToOne`, `VK_KHR_maintenance5`, `VK_KHR_swapchain_mutable_format` y `VK_EXT_border_color_swizzle`. Zink necesita un proveedor de OpenGL desktop Mesa/Gallium y un contexto Android apropiado; no se integra copiando un DLL/biblioteca sobre GL4ES. **Decisión: mantener GL4ES y no empaquetar Zink en WSA**. El TECNO Mali queda sin determinar hasta que se pueda consultar directamente. Se conserva estrategia original de perfilado CPU y contador **0/5** porque no existió A/B de gameplay. [Informe Mesa/Zink](MESA_ZINK_FEASIBILITY_2026-10-14.md).

## Hito posterior: transformaciones y proyección GL → Vulkan (sin A/B del juego)

La capa de observación tipada ahora reconoce las ocho llamadas de traslación, rotación, escala y proyección ortográfica/perspectiva, preservando el orden column-major de OpenGL y los slots dobles x86. El prototipo WSA `--scene matrix` usó el estado tipado para tres dibujos reales sobre Vulkan; validación visual y ejecución completa **75,024 FPS FIFO** (1.276 frames, 17,008 s; **no** FPS del juego ni demostración de aceleración). El renderer estable sigue siendo GL4ES; el próximo bloqueo es geometría real de vertex arrays/VBO, samplers y combiners. [Informe](WSA_GL_MATRIX_BRIDGE_2026-10-14.md). Estrategia original y contador **0/5** intactos.

## Hito de compatibilidad TexEnv y alpha test (sin A/B del juego)

El prototipo WSA implementa ahora `glTexEnv` MODULATE/REPLACE por unidad y un shader con descarte de fragmentos por prueba alfa; la captura de la escena muestra dos quads con texturas/colores correctos y huecos por alfa. **75,043 FPS FIFO** del prototipo independiente **NO equivalen al juego completo ni demuestran aceleración de CallofRecomp**. Captura del juego anterior (164 snapshots) no se repitió; el registro continúa advirtiendo estados sin traducir. [Informe](WSA_VULKAN_TEXENV_ALPHA_2026-10-14.md). Estrategia y contador 0/5 intactos.

## Diagnóstico GL→Vulkan del juego real, sin intento de optimización

Un observador optativo generado por `gen_gl.py` rastreó la partida GL4ES de WSA, entre menú y entrenamiento. El análisis de **164 muestras** encontró **0 estados declarados equivalentes en el subconjunto traducido** y máscara `0x19`: capacidades no traducidas, estado de texturas y API GL heredada. El traductor genera estructuras Vulkan válidas para depth/stencil, blending y culling, pero **no** es un renderer completo. El log es una captura de compatibilidad, no permite medir FPS nuevos ni atribuir aceleración a Vulkan. Se restauró la APK original exacta; el contador sigue en **0/5**. [Documentación y siguiente cobertura](GL_VK_STATE_BRIDGE_2026-10-14.md).

## Ejecución más reciente — diagnóstico sin consumo de intentos

[Informe de ejecución del perfil TECNO y selección de función](PERFORMANCE_STRATEGY_RUN_2026-10-14.md) — dos capturas reales de Simpleperf, ELF instalado verificado, top de geometría/visibilidad y diagnóstico ARM64 de `0x0041B8F0`. GPU hardware sigue sin contador accesible mediante ADB. La primera función para fase 2 está seleccionada, pero **no se ha habilitado optimización estructural nueva**. Fase 3 permanece pendiente. **Contador: 0/5**; el diagnóstico no constituye un experimento A/B válido.

## Modo temporal WSA y evaluación de Vulkan / DirectX 12 (2026-10-14)

El teléfono TECNO no está disponible. **Utilizar WSA `127.0.0.1:58526` exclusivamente mientras tanto**, para pruebas x86_64, diagnóstico de API, equivalencia funcional y prototipos seguros; **no extrapolar a FPS ARM64/Mali**. La meta y referencia física no cambian.

Se comprobó Vulkan 1.3 **mediante código NDK real ejecutado en WSA**, dispositivo AMD y extensión `VK_KHR_swapchain`. Posteriormente una aplicación independiente sí creó una superficie/swapchain Vulkan y presentó **1.276 frames a 75 FPS FIFO** (color sólido, NO render del juego). El control OpenGL del juego se mantuvo ~55 FPS; quitar únicamente el límite del host, sin cambiar GL4ES, dio **55,05 → 57,20 → 55,30 FPS** en A2/B/A3, sin reducir CPU/frame. La comparación real con Vulkan en el juego sigue pendiente. [Benchmarks WSA por etapas](WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md). DirectX 12 existe en Windows, no como API directa del proceso Android. **Se mantiene OpenGL/GL4ES como renderer de referencia**. Ver [auditoría de APIs y permisos GPU Mali](WSA_VULKAN_DX12_RENDERER_DECISION_2026-10-14.md).

**Contador de experimentos fallidos: 0/5, sin cambios.** Las pruebas WSA y Vulkan de capacidades no constituyen un intento válido de rendimiento en el TECNO.

**Cierre de mediciones WSA:** A1 GL4ES 55,20 FPS, B1 GL4ES sin cap 57,20, A3 GL4ES restaurado 55,30. Vulkan WSI aislado presentó ~75 FPS con color sólido; **no** es una mejora del juego. Se reinstaló la referencia A1 byte a byte y se verificó su SHA-256. Ver [informe completo](WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md). Contador oficial **0/5**, fases ARM64 sin cambios.

**Avance Vulkan de geometría:** el prototipo aislado WSA también soporta `VkGraphicsPipeline`, shaders SPIR-V y `vkCmdDrawIndexed` en malla de 4 vértices/6 índices, comprobada visualmente. 74,999 FPS de presentación FIFO 75 Hz **no representan FPS de CallofRecomp**. La fase aislada posterior ya soporta **`VkImage` texturizada RGBA8, staging y sampler/descriptor** (75,117 FPS FIFO del prototipo, no del juego); en un nuevo bloque aislado ya funcionan **depth/stencil y blending alfa**, con 5 attachments independientes, cuatro draws por frame y captura WSA validada a 75,005 FPS FIFO (no FPS del juego). Sigue **pendiente la traducción del estado OpenGL original** y toda comparación A/B/A de la partida. [Hito depth/stencil/blend](WSA_VULKAN_DEPTH_STENCIL_BLEND_2026-10-14.md). [Hito texturas](WSA_VULKAN_TEXTURE_2026-10-14.md). [Hito técnico](WSA_VULKAN_INDEXED_MESH_2026-10-14.md). Contador **0/5**.

## Meta y referencia

**Meta no negociable:** al menos **60 FPS sostenidos** en el punto de aparición del entrenamiento de Camp Toccoa, en el **TECNO CK6n ARM64**, perfil **Equilibrado**, sin reducir calidad, alterar el HUD panorámico, colisiones, controles ni partidas. No confundir FPS del menú, WSA o microbenchmarks con FPS del juego.

**Referencia operativa:** compilación x87 estable anterior, aproximadamente **24,9–25,1 FPS medianos** y **38,3–38,6 ms CPU/frame** en la vista estática de training de los controles recientes. Conservar una APK A reproducible y el estado de Git/build exacto de cada comparación. Esos valores son históricos, no una nueva medición.

## Estrategia actual: tres fases en orden

### Fase 1 — Perfilado profundo del frame real (prioridad inmediata)

1. Capturar una escena *reproducible* en el TECNO: mismo guardado, cámara, perfil, HUD, duración y condición térmica; incluir también una escena concurrida para comprobar si el cuello cambia.
2. Muestrear con **Simpleperf** (CPU) y resolver PCs ELF a funciones originales mediante los mapas Ghidra v2, atribuyendo por separado geometría, visibilidad, lógica, x87, accesos de memoria, despacho, GL4ES y driver. Diferenciar tiempo inclusivo/exclusivo y no atribuir toda una partición a una sola función.
3. Complementar con un **perfil GPU real** (AGI/Mali si el hardware y permisos lo permiten), frame pacing, carga y frecuencias CPU/GPU, temperatura y memoria. Si hay contadores no accesibles, dejar el hueco documentado: nunca inventar métricas.
4. Entregable de fase: tabla de cuellos de botella en *milisegundos por frame medidos o estimados con metodología explícita*, ranking dinámico con evidencia y selección de un único objetivo para la siguiente fase. No desarrollar un parche costoso sin este fundamento.

### Fase 2 — Optimización estructural del recompilador (prototipo acotado)

1. Tomar **una sola función caliente** del perfil. Investigar la agrupación de operaciones x86, valores de registros virtuales mantenidos en variables ARM64, eliminación segura de movimientos `rd/wr` y estados que sobreviven a Clang, y simplificación de despacho/aliasing.
2. Medir **antes y después del código máquina ARM64**: tamaño y `llvm-objdump`/perfil de instrucciones ejecutadas. Un C más corto **no es un éxito** si la sección `.text` y la ejecución permanecen idénticas (resultado ya observado con DCE).
3. Comparar con oráculo independiente x86 cuando sea posible; además, contrastar registros, EFLAGS, x87, RAM, PC, aliasing, NaN, ramas y resultados del motor. Flag experimental **OFF** hasta superar todos los controles.
4. Solo generalizar a otras funciones cuando haya una mejora sostenida en el teléfono y ningún fallo de imagen, controles o partidas.

### Fase 3 — Fast paths ARM64 de funciones completas

1. Elegir por **coste dinámico acumulado**, no por cantidad de instrucciones estáticas ni por aparecer en una lista de «top functions».
2. Tomar como modelo la experiencia de `0x005061B0`, cuya especialización optativa mostró alrededor de **+19,58 %** en una escena; no trasladar esa ganancia a nuevas funciones sin pruebas.
3. Implementar rutas nativas **con fallback** ante entradas o estados no cubiertos, validar con equivalencia completa y medir A/B/A/B/A en el TECNO.
4. Documentar el ahorro por función, su cobertura y el coste agregado restante. Nunca declarar que una mejora aislada garantiza 60 FPS.

Las fases definen **prioridad**, no una prohibición de recoger perfiles adicionales durante las fases 2/3. Si el nuevo perfil invalida la hipótesis, se vuelve a la fase 1 para seleccionar un objetivo sin abandonar automáticamente esta estrategia.

## Regla de decisión: 5 intentos válidos consecutivos sin mejora

**Contador actual: 0 de 5.** Los experimentos históricos anteriores al establecimiento de esta política son *antecedentes*, **no** cuentan de manera retroactiva.

Un **intento válido** es un experimento de optimización bajo esta estrategia, con hipótesis específica, versión A/B identificable, métrica objetivo declarada, código ARM64 o comportamiento relevante verificable, pruebas funcionales y captura controlada del mismo escenario en el TECNO (idealmente **A/B/A/B/A**, mínimo A/B/A suficientemente comparable y documentado). Los datos deben registrar FPS medianos, percentil bajo de ventanas, CPU/frame, temperatura, frecuencias si es posible y cualquier regresión. El tamaño del código, un benchmark sintético o una captura del menú por sí solos **no** constituyen un intento válido de rendimiento.

**Éxito:** mejora reproducible de FPS y/o reducción de CPU/frame **superior al ruido observado entre las referencias**, repetida en las corridas candidatas, sin regresión significativa de FPS bajos, estabilidad, visuales ni jugabilidad. Los resultados deben ser compatibles con avanzar hacia 60 FPS; una ganancia transitoria como FCOM B1 seguida de una caída B2 **no** es éxito. Si el experimento es un diagnóstico de fase 1 y no propone una mejora de rendimiento, no consume intento.

**Sin éxito (suma +1):** experimento válido que no supera el control, queda por debajo del ruido, o presenta una regresión. **Inconcluso (no suma):** faltan mediciones o las condiciones no son comparables; corregir el protocolo y repetir sin alterar el contador. **Éxito confirmado (reinicia a 0)**, sin declarar cumplida la meta de 60 FPS.

**Al acumular 5 fracasos válidos consecutivos:** **detener nuevos parches de esa línea de optimización** y abrir una *revisión formal de estrategia* basada en CPU/GPU, coste de las fases, resultados negativos y alternativas. La revisión debe decidir explícitamente y documentar si se **mantiene, modifica o reemplaza** la estrategia. **No cambiar automáticamente** de dirección solo porque el contador llegó a 5. Antes de ese umbral, se prioriza completar las fases previstas; excepciones razonables: riesgo de corrupción de datos, regresión grave, barrera técnica demostrada o un perfil nuevo que invalide claramente la premisa. Cualquier excepción requiere justificación escrita.

## Registro de intentos de la estrategia vigente

| ID | Fase y objetivo | Experimento | Estado | Resultado TECNO | Contador tras prueba |
| --- | --- | --- | --- | --- | --- |
| — | — | *Aún no hay intentos válidos bajo esta versión* | Pendiente | — | **0/5** |

**Actualización obligatoria tras cada intento:** anotar fecha, ID, commit y flags A/B, enlace a evidencia privada (sin subir partidas/APK/binarios comerciales), escena, ventanas, FPS p10/mediana, CPU/frame, térmica, comportamiento de HUD/partidas, decisión y valor nuevo del contador. Si faltan datos, registrar «inconcluso». Cada revisión de estrategia crea una nueva versión de este documento, sin borrar el historial.

## Evidencia histórica (no suma al contador)

- Fast path x87 de `0x005061B0`: ganancia real en una vista controlada, optativo.
- `--x87-fcom-fastpath`: ganancia B1 no reproducida y regresión B2 (19,8 FPS); rechazado.
- `--prune-dead-temporaries`: 32.704 operaciones estáticas eliminadas del C, pero sección nativa `.text` idéntica; sin mejora de FPS.
- `-O2` / `-Oz`, GL4ES batching/VBO, copy32 y NaN: beneficio insuficiente o regresiones en los escenarios ensayados. No volver a probarlos a ciegas.

Referencias: [perfil real TECNO](TECNO_CK6N_ARM64_PERF_2026-10-14.md), [renderer y FCOM](ARM64_RENDERER_CPU_FCOM_2026-10-14.md), [DCE p-code](CODSP_PCODE_TEMP_DCE_2026-10-14.md), [análisis funcional](FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md).

**Esta página es la fuente autoritativa sobre la estrategia vigente y su contador.** El roadmap y el log de progreso enlazan aquí. No convertir hipótesis en logros de FPS antes de confirmarlos en hardware real.
