# Hito Vulkan WSA: matrices OpenGL 1.x y proyección (2026-10-14)

**Ámbito:** CallofRecomp 1.5 · nuevo bloque de compatibilidad gráfica, tras `TexEnv MODULATE/REPLACE` y `GL_ALPHA_TEST`.
**Estado:** modelo matemático implementado, testado en C y visualizado sobre geometría real en una **APK Vulkan independiente** ejecutada en WSA x86_64.
**No existe todavía renderizador Vulkan del juego completo:** CallofRecomp sigue con OpenGL/GL4ES, y sus FPS no se han vuelto a medir. El TECNO físico no está disponible. **Contador de intentos A/B válidos: 0/5**.

## Implementación

### 1. Matrices OpenGL — código de runtime tipado

`tools/recomp/runtime/gl_vk_state.c/.h` ahora modela estas operaciones sobre la matriz activa MODELVIEW, PROJECTION o TEXTURE de la unidad seleccionada:

| Llamada OpenGL heredada | Operación de estado | Regla comprobada |
|---|---|---|
| `glTranslatef`, `glTranslated` | `GLVK_OP_TRANSLATE` | `M ← M × T` |
| `glScalef`, `glScaled` | `GLVK_OP_SCALE` | `M ← M × S` |
| `glRotatef`, `glRotated` | `GLVK_OP_ROTATE` | Rotación Rodrigues, eje normalizado, grados, espacio dextrógiro |
| `glOrtho` | `GLVK_OP_ORTHO` | Proyección ortográfica GL, near/far y traslación |
| `glFrustum` | `GLVK_OP_FRUSTUM` | Proyección perspectiva GL con near/far positivos |

Las matrices se mantienen **column-major**, con multiplicación por la derecha (OpenGL): no se confunden `T×S` y `S×T`. `gl_vk_state_mvp` exporta `PROJECTION×MODELVIEW` para un vertex shader; las matrices de textura se mantienen separadas.

El código lee vectores de seis doubles por `memcpy`, tolerando alineación no garantizada de punteros en emulación. **Invalida en lugar de inventar un resultado** ante ejes de rotación nulos, NaN/infinito, frustum con near/far inválidos, planos coincidentes o resultados que excedan el rango float. Ante entrada no admitida, preserva la matriz anterior y fija la máscara de incompatibilidad persistente; su `state_ready` permanece false.

### 2. Generación de wrappers, sin parches manuales

`tools/recomp/gen_gl.py` añade `VK_MATRIX_CALLS` para las ocho funciones anteriores. Los hooks solo se emiten en la sección de observación **después de reenviar la llamada real a GL4ES**. Los `float` guest usan `F32(ARG(esp,i))`, y cada `double` guest usa `F64(esp, 0/2/4/6/8/10)`, respetando los **dos slots x86** de 32 bits que ocupa `GLdouble`. Los valores observados se convierten a un vector nativo `double[6]` seguro mientras dura el hook.

El código `gl_thunks.c` generado (**486 wrappers** desde el registro Khronos `gl.xml` privado ya existente) se actualizó mediante el **generador central**, nunca mediante cientos de modificaciones de instrucciones individuales. La captura **CODRECOMP_GL_VK_STATE_CAPTURE** sigue **OFF por defecto**; no modifica las llamadas ni el renderizado GL4ES de la app normal.

### 3. Prueba Vulkan independiente: `--scene matrix`

La APK `org.rigorcore.vkswapbench` genera tres dibujos indexados en WSA:

- Izquierda: `glOrtho` + translate(-0.56,0,0) + rotación de +23° en Z + escala no uniforme.
- Centro: `glOrtho` + rotación de -35° en Z + escala no uniforme.
- Derecha: `glFrustum` near=1/far=10 + traslación z=-3 + rotación en Y + escala.

Los tres usan **el estado GL tipado y `gl_vk_state_mvp`**, no matrices rellenadas manualmente. El shader `wsa_matrix.vert` multiplica por MVP y convierte el clip-space GL a Vulkan (`clip.y ← -clip.y`; `clip.z ← (clip.z+clip.w)/2`) para un viewport Android de altura positiva.

Se reutilizan la geometría de cuatro vértices y seis índices, el render pass, shaders de fragmento y el swapchain del prototipo. Las imágenes, registros y APK de prueba se guardan bajo `.local/profiles/wsa_vulkan_ab/matrix-fifo/` (ignorados por Git). No se incluyen materiales de Call of Duty.

**Incidente resuelto:** la primera compilación cargó una `libvk_swap_bench.so` con un símbolo matemático `hypot` sin resolver porque el empaquetador no enlazaba `libm`. Se reprodujo el fallo de carga en Logcat, se añadió `-lm` al enlazado del prototipo y la app inició correctamente. No afectó a la APK de CallofRecomp. El primer log parcial (6 ventanas) se descartó como medición; únicamente se tomó el `VK_RESULT` completo de una nueva ejecución de esta escena.

## Evidencia de WSA

La captura real de WSA mostró **tres quads de diferentes rotaciones, escalas y proyecciones** sobre fondo azul, incluido un quad con perspectiva. La ejecución completa produjo:

| Resultado exclusivamente del prototipo Vulkan WSA | Medición |
|---|---:|
| FPS promedio con FIFO | **75,024** |
| Frames | **1.276** |
| Segundos | **17,008** |
| FPS mediana de ventanas (~1 s) | **75,0005** |
| FPS p10 de ventanas | **74,938** |
| CPU del hilo de prueba/frame | **2,38144 ms** |
| Draws indexados/frame | **3** |
| Resolución | **1280×720** |
| `VK_MATRIX_READY` | `translate_rotate_scale_ortho_frustum`, `column_major`, `projection_modelview`, `y_flip_z_range` |

**Limitación de medición:** FIFO ronda la frecuencia de refresco WSA de 75 Hz; la prueba no contiene la geometría, texturas, shaders, lógica, AI, HUD ni frame pacing completo del juego. No determina tiempo real de GPU ni puede demostrar mejora alguna de CallofRecomp o FPS en ARM64/Mali. El parser `summarize_wsa_vk_surface.py` fue extendido para rechazar registros que no acrediten los recursos y transformaciones de la nueva escena, o los que contengan menos de diez ventanas.

## Validaciones

- `tests/gl_vk_matrix_transform_smoke.c`: ecuaciones independientes para `T×S` frente a `S×T`, rotaciones 90° y 180° con normalización de ejes, matriz ortográfica, matriz frustum y componente `w` del producto `P×M`; pilas de matrices MODELVIEW/PROJECTION/TEXTURE y casos inválidos que no mutan estado.
- `tests/test_gl_generator.py`: XML Khronos sintético garantiza slots x86 correctos en parámetros `float` y `double` y que los wrappers llaman primero a GL4ES.
- `tests/test_wsa_vk_surface.py`: nuevos casos para identidad de escena `matrix` e instrumentación inconsistente.
- Sintaxis C nativa ARM64 con NDK `-Wall -Wextra -Werror` aprobada para la nueva escena; el archivo de wrappers usa `-Wno-unused-variable` por temporales preexistentes del perfilador opcional.
- La escena matrix fue compilada en APK firmada, shaders compilados mediante `glslc` y comprobados mediante `spirv-val`. El antiguo modo depth sigue construyéndose sin repetir sus benchmarks.
- **140 pruebas Python (4 omitidas) y 33/33 CTest**, incluidos los casos nuevos.
- La compilación del juego en modo de observación y sin captura se valida por separado; al finalizar el modo normal debe permanecer **OFF**, y la APK instalada de referencia permanece sin cambios.

## Próximos pasos reales

1. **Matrices en renderizado de geometría de CallofRecomp:** traducir vertex arrays, VBO, `glDrawElements` y sus formatos a `VkBuffer`/vertex input. El prototipo actual solo usa quads sintéticos.
2. Ampliar `glTexEnv` a modos y combiners realmente usados, multitextura y samplers/carga de `glTexImage2D`.
3. Eliminar incompatibilidades `0x19` observadas en gameplay y demostrar equivalencia **visual completa** contra GL4ES antes de habilitar siquiera un backend opcional de juego.
4. Solo entonces A/B/A de la **misma** escena de entrenamiento en WSA; cuando vuelva el TECNO, medir en ARM64 si se llega a los 60 FPS sostenidos.

**Este hito no altera la estrategia vigente ni aumenta el contador de intentos fallidos (0/5).**
