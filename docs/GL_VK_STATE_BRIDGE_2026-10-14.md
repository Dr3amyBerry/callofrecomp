# Hito del puente OpenGL → estado tipado Vulkan (WSA, 2026-10-14)

**Alcance:** avance de arquitectura y diagnóstico del renderizador de CallofRecomp 1.5. **El juego sigue dibujando con OpenGL/GL4ES; no existe todavía un renderer Vulkan completo ni un aumento demostrado de FPS de gameplay.** Esta fase no cuenta como intento A/B de optimización; la estrategia vigente permanece **0/5**. TECNO físico no disponible.

## Qué se ha construido

1. **Modelo OpenGL tipado** en `tools/recomp/runtime/gl_vk_state.h/.c`. Guarda flags de depth, stencil, blending, alpha, culling y scissor; funciones y máscaras de profundidad/stencil; factores de mezcla; textura activa, bindings de textura por unidad, matrices MODELVIEW/PROJECTION/TEXTURE column-major y pilas independientes. Arranca desde valores GL 1.x y sigue cambios de estado mediante `gl_vk_state_apply`.
2. **Traducción real de ese subconjunto a estructuras Vulkan** en `tools/recomp/diagnostics/wsa_vk_gl_state_map.h/.c`: `VkPipelineDepthStencilStateCreateInfo`, `VkPipelineColorBlendAttachmentState` y `VkPipelineRasterizationStateCreateInfo`. Convierte enums GL válidos de test y operaciones stencil a constantes Vulkan sin asumir equivalencia de lo no soportado.
3. **El prototipo depth/stencil/blend existente se recompiló con la nueva traducción**. Ejecutó en WSA la escena de quads texturizados, profundidad, stencil y alfa; captura comprobada visualmente. Es la misma aplicación Vulkan independiente de prueba `org.rigorcore.vkswapbench`, **no** CallofRecomp.
4. **Captura optativa en el generador de wrappers**: `tools/recomp/gen_gl.py` genera observaciones tipadas *después* de las llamadas GL4ES, sin sustituirlas ni editar manualmente `gl_thunks.c`. El nuevo flag de build `--gl-vk-state-capture` / `CODRECOMP_GL_VK_STATE_CAPTURE` está **OFF por defecto**. Afecta solamente al módulo de wrappers y al tick de ventana; `gl_vk_state.c` se excluye por completo del código normal cuando el flag está OFF.
5. **Fallos cerrados**: capacidades GL, funciones legadas, objetivos/unidades de textura y enums no traducidos acumulan flags de incompatibilidad. Los estados `GL_ALPHA_TEST` y scissor no se declaran listos para Vulkan aunque puedan observarse; tampoco multitexture combiners sin shader equivalente. `glAlphaFunc` ahora conserva su GLenum y el umbral de alfa (bits float x86), pero **falta implementar el discard de shader**.
6. **Diagnóstico por familias para futuras capturas**: agrupación de funciones sin traducción en textura/ambiente, upload, transformaciones, vértices, iluminación/niebla, VBO y otros. Esas cuentas solo se emitirán al ejecutar **una futura** APK compilada con la nueva instrumentación; el registro histórico no las contiene.
7. **Analizador reproducible, conservador**: `tools/recomp/diagnostics/analyze_gl_vk_capture.py`, con pruebas unitarias, calcula diferencias de contadores acumulados sin llamarlas FPS, valida errores de sesión y reporta la preparación del subconjunto y las familias si están presentes.

### Generación reproducible

El archivo fuente de wrappers `tools/recomp/runtime/gl_thunks.c` se regeneró con `gen_gl.py` sobre **486 nombres**. La versión pública de `KhronosGroup/OpenGL-Registry/main/xml/gl.xml` se descargó exclusivamente al directorio privado `.local/profiles/vk_bridge/gl.xml` y se verificó la generación previa frente al archivo original: la diferencia de partida era solo el orden de inicialización de dos diagnósticos. El registro externo **no** se publicó ni se integró como dependencia del APK; para repetirlo se necesita una copia compatible de `gl.xml`.

La observación se activa solo en builds de diagnóstico mediante el flag; la presencia de los wrappers generados no cambia el backend GL4ES en la compilación normal.

## Evidencia del juego real en WSA

Se usó **una sola ejecución del juego** con la variante diagnóstica: se inició CallofRecomp en WSA x86_64, se abrió la campaña y se vio la escena de entrenamiento. Se guardó su log como `.local/profiles/vk_bridge/game_gl_vk_capture_training_20261014.log` (privado); `gl_vk_training_summary.json` se derivó *sin repetir la partida*. El registro incluye fases de menú y gameplay, de modo que **no** deben atribuírsele todos los contadores únicamente al entrenamiento.

| Observación | Resultado |
| --- | --- |
| Muestras periódicas GL→estado | **164** |
| Instantes con estado declarable traducible | **0 de 164** |
| Flags de incompatibilidad vistos | **0x19** |
| 0x01 | Capacidades GL no contempladas |
| 0x08 | Unidad u objetivo de textura no contemplado |
| 0x10 | Operaciones OpenGL heredadas sin equivalencia |
| Diferencia de llamadas rastreadas entre primera y última muestra | **19.055.688** |
| Diferencia de eventos incompatibles entre primera y última muestra | **42.822.943** |
| Último estado observado | depth ON, blend ON, alpha test ON, stencil OFF; texturas 1201 y 1102 |
| Hash último MODELVIEW/PROJECTION | `5ee87785` |
| Prototipo Vulkan del juego | **NO** |

**Interpretación:** los dos contadores de millones representan llamadas/eventos **acumulados durante toda la sesión**. **No** son número de frames, coste por frame, FPS ni resultados comparables de rendimiento: observar estados añade trabajo de CPU. El mask 0x19 indica **tipos** de incompatibilidad, no su coste por familia; la versión capturada todavía no incluía el histograma detallado. Los datos verifican que no se puede habilitar un renderer Vulkan equivalente sin resolver estados adicionales.

Después se detuvo el juego y se reinstaló **la APK exacta de referencia A1**, conservando datos. `lib/x86_64/libmain.so` se verificó por hash SHA-256 en el dispositivo: `403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde`. No se repitieron A1/A2/B1/A3 ni los benchmarks WSI.

## Tests y controles

- Smoke C sintético de defaults, depth/stencil/blending, matrices (multiplicación OpenGL column-major), stack push/pop, texturas múltiples, captura de umbral `glAlphaFunc` y fail-closed.
- Tests Python de generador de thunks con registro XML mínimo sintético, garantizando que se invoca siempre primero al host OpenGL y que la observación se genera de forma uniforme.
- Tests Python del parser del log, incluidos contadores acumulados, máscaras, ausencia de datos, sesiones mezcladas y compatibilidad de formato con el histograma futuro.
- Compilación NDK del prototipo Vulkan con traductor y render confirmado visualmente en WSA, sin modificar el juego estable.

### Validación de cierre

- **136 pruebas Python** ejecutadas, **4 omitidas**, sin fallos; **32/32 CTest** aprobadas. Incluye smoke C del traductor de estados, tests del generador y parser de registro.
- Sintaxis del código de captura/traducción en **ARM64 NDK** verificada. Para el archivo generado se deshabilitó exclusivamente la advertencia preexistente de variables de tiempo sin uso (`-Wno-unused-variable`) porque `GL_TIME_START` es opcional; la compilación real x86_64 con todos los flags actuales también pasó.
- `python tools/recomp/build_android.py --abi x86_64 --gl-vk-state-capture` produjo APK diagnóstica **firmada y compilada** con la nueva captura por familias; **no fue ejecutada** en WSA, porque ya existía una captura de gameplay anterior suficiente para esta fase.
- Finalmente `python tools/recomp/build_android.py --abi x86_64` construyó nuevamente la variante normal **sin captura**. El dispositivo quedó con la **APK original A1**, distinta y verificada por hash, y no se realizaron nuevas mediciones.
- El histograma de familias recién instrumentado está disponible solo para ejecuciones futuras; el log histórico mantiene `legacy_family_totals_last=null` en el resumen y no puede desglosarse retroactivamente.

## Qué falta exactamente

1. **Identificar qué funciones reales explican el mayor volumen de flags** mediante histograma por familias en una captura futura; no asumir que todas las llamadas contadas son costosas.
2. Traducir `glTranslate/Rotate/Scale/Frustum/Ortho`, `glTexEnv*`, `glTexParameter*`, alpha test/discard, combiners multitextura y estado de vértices/buffers. La captura es solo el modelo de estado, no traduce geometría ni crea recursos del juego automáticamente.
3. Crear un **backend opcional con fallback GL4ES** y asegurar equivalencia visual en menú, entrenamiento, HUD y gameplay. Solo una escena completa y la misma política de frame pacing permitirán medir un A/B/A Vulkan real.
4. Validación ARM64 física en TECNO cuando vuelva a estar disponible; **60 FPS sostenidos permanece sin demostrar**. El contador de cinco intentos no cambia por pruebas de infraestructura.

**Principio:** no convertir los ~75 FPS de un prototipo FIFO de WSA en afirmaciones sobre FPS del juego. Nunca publicar logs privados ni activos comerciales.
