# Hito Vulkan WSA: depth/stencil y blending alfa (2026-10-14)

**Proyecto:** CallofRecomp, rama `main`.
**Aislamiento:** ejecutado **exclusivamente en una NativeActivity Android de diagnóstico WSA x86_64**, `org.rigorcore.vkswapbench`; no se cambia el backend OpenGL/GL4ES del juego, ni sus APKs, partidas o archivos comerciales.
**TECNO:** teléfono no disponible; no se hicieron pruebas físicas ARM64.
**Contador de estrategia oficial:** **0/5**. Esta es una prueba de capacidades, no un intento válido de mejorar FPS de la partida.

## Qué se implementó

- `--scene depth` añade una cuarta escena al banco de prueba Vulkan independiente, sin romper los modos anteriores `clear`, `mesh` y `texture`.
- `wsa_vk_depth.c/.h` selecciona mediante `vkGetPhysicalDeviceFormatProperties` un formato **con profundidad y stencil**: D24_UNORM_S8_UINT preferido, D32_SFLOAT_S8_UINT o D16_UNORM_S8_UINT si procede. WSA seleccionó **Vulkan format=130, D32_SFLOAT_S8_UINT**.
- Se crean **5 `VkImage` y `VkImageView` depth/stencil con memoria `DEVICE_LOCAL`**: una por framebuffer/imagen del swapchain, sin compartir un attachment de escritura entre frames en vuelo.
- El render pass ahora tiene dos attachments: color y depth/stencil, inicialización por clear (**depth=1.0, stencil=0**) y subpass con `pDepthStencilAttachment`. Barreras/dependencias incluyen `EARLY_FRAGMENT_TESTS`, `LATE_FRAGMENT_TESTS` y escritura de profundidad.
- Pipeline opaco: `VK_COMPARE_OP_LESS_OR_EQUAL` con `depthTestEnable` y `depthWriteEnable`, stencil `ALWAYS → REPLACE` y referencia dinámica `vkCmdSetStencilReference`.
- Pipeline superpuesto: stencil `EQUAL` con valor **2**, depth test activo con **escritura desactivada**, y blending `SRC_ALPHA / ONE_MINUS_SRC_ALPHA`. Usa el nuevo shader `wsa_overlay.frag` (rojo/anaranjado, alfa 0.47).
- Se ejecutan **cuatro `vkCmdDrawIndexed` por frame** con push constants y matrices distintas:
  1. Fondo texturizado, profundidad **0.78**, stencil=1.
  2. Objeto menor delante, profundidad **0.25**, stencil=2.
  3. Objeto pequeño detrás, profundidad **0.93**, oculto mediante depth test.
  4. Capa alfa en profundidad **0.10**, recortada al interior de stencil=2.
- Cleanup: `vkDeviceWaitIdle`, destruir framebuffers antes de attachments depth, y destruir pipelines opacos/translúcidos, imágenes y memoria; todas las rutas de error liberan recursos ya creados.
- Shader separado SPIR-V compilado con `glslc` y validado con `spirv-val` NDK. Los shaders de textura e índice anteriores se mantienen.

## Validación en WSA

La compilación de la APK `--scene depth --present fifo` fue correcta, firmada y verificada con el Android NDK. La app ejecutó realmente ambos pipelines. Logcat confirmó:

```text
VK_MESH_READY vertices=4 indices=6 draws_per_frame=4 procedural_checker=0
VK_TEXTURE_READY width=64 height=64 mip_levels=1 descriptor_sets=1 sampler=nearest transfer=staging image_layout=shader_read_only
VK_DEPTH_READY format=130 attachments=5 depth_test=less_equal depth_write=1 stencil=replace_equal blend=alpha_over draws_per_frame=4
VK_SCENE name=depth, integration=standalone, gameplay=0
```

Una captura visual de WSA muestra **fondo texturizado, objeto cercano recortado, objeto posterior tapado y overlay rojizo translúcido sin salirse del área del stencil**. Guardada en `.local/profiles/wsa_vulkan_ab/depth-fifo/preview.png`. Es una inspección visual y funcional, **no un test de equivalencia contra CoDSP ni un test de contadores de GPU Mali**.

Medición de la compilación instrumentada definitiva, tras corregir el marcador de draws:

| Parámetro | Resultado |
| --- | ---: |
| `VK_RESULT` | **75.005 FPS promedio** |
| Frames presentados | **1.276** |
| Intervalo medido | **17.012 segundos** |
| FPS mediana de ventanas ~1s | **74.996** |
| FPS p10 de ventanas ~1s | **74.971** |
| CPU del hilo de prueba por frame | **2.20648 ms** |
| Swapchain | **1280×720, FIFO, WSA 75 Hz** |
| Dibujos indexados por frame | **4** |
| Depth/stencil image attachments | **5 independientes**, formato D32_SFLOAT_S8_UINT |

La primera compilación de desarrollo de este mismo bloque alcanzó 75.096 FPS y 2.67362 ms CPU/hilo; se repitió **solo este nuevo bloque** para corregir el marcador de 4 draw calls. Las pruebas históricas del juego, mesh y texture **no se repitieron**.

**Precaución:** la presentación FIFO a 75 Hz oculta diferencias del tiempo de GPU de shaders. Estos FPS reflejan una **demostración aislada de 4 quads**, no geometría completa, materiales, HUD, simulación ni texturas comerciales de Call of Duty. No atribuir ninguna mejora del juego a Vulkan o DirectX 12.

## Archivos y pruebas

- `tools/recomp/diagnostics/wsa_vk_depth.c/.h`: selección de formato, VkImage, view y memoria por swapchain image.
- `tools/recomp/diagnostics/shaders/wsa_overlay.frag`: shader de color semitransparente.
- `tools/recomp/diagnostics/wsa_vk_mesh.c/.h`: dos pipelines, estado depth/stencil, blend alfa y cuatro draw calls con matrices distintas.
- `tools/recomp/diagnostics/wsa_vk_surface_bench.c`: render pass color+depth, attachments, draw condicional y marcadores.
- `tools/recomp/diagnostics/build_wsa_vk_bench.py`: `--scene depth` y compilación/validación/paquetizado de 3 shaders.
- `tools/recomp/diagnostics/summarize_wsa_vk_surface.py`: distingue `depth`, valida formato/número de attachments y estados, y se niega a declarar resultados cuando faltan marcadores.
- `tests/test_wsa_vk_surface.py`: nuevos tests de estructura y rechazo de instrumentación falsa; se conservan los tests previos.

Archivos APK, logs, JSON y PNG de resultados en `.local/profiles/wsa_vulkan_ab/depth-fifo/` (ignorados por Git). Ningún recurso comercial ni APK del juego entra en este commit.

## Validación de cierre

- **131 pruebas Python aprobadas (4 omitidas)**, incluyendo 9 pruebas del analizador Vulkan; errores deliberados en marcadores depth/stencil/blending son rechazados.
- **31/31 CTest** correctas, sin regresiones detectadas en el conjunto actual.
- APK independiente `--scene depth` compilada con NDK x86_64; `glslc` y `spirv-val` procesaron y validaron los 3 shaders SPIR-V; firma APK verificada.
- Regresión de compilación: las tres opciones antiguas `--scene clear`, `--scene mesh` y `--scene texture` también generaron APKs firmadas correctamente después de los cambios, **sin ejecutarlas ni repetir sus benchmarks**.
- Comprobación de sintaxis **ARM64** de los módulos `wsa_vk_mesh.c`, `wsa_vk_texture.c`, `wsa_vk_depth.c` y `wsa_vk_surface_bench.c` con `-Wall -Wextra -Werror`: correcta. **No es una prueba de ejecución ARM64 física.**
- Marcadores finales completos `VK_MESH_READY=4 draws` + `VK_DEPTH_READY=4 draws` y `VK_RESULT` validados por el analizador; captura visual examinada.
- La `libmain.so` de **CallofRecomp original instalada en WSA** se comprobó nuevamente idéntica a la referencia A mediante SHA-256 `403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde`. **No se han repetido benchmarks de gameplay ni tocado sus partidas.**

## Próxima etapa técnica

El prototipo demuestra attachments depth/stencil y blending alfa, pero **todavía no es un backend Vulkan compatible con OpenGL 1.x del juego**. Quedan funciones con coste e impacto visual real: mapeo de estados `glEnable(GL_DEPTH_TEST)`, stencil y alpha; blending de texturas, `glTexEnv`, multitexturizado, matrices `MODELVIEW/PROJECTION`, culling, wrap/filter, mipmaps y materiales. Priorizar una **captura y traducción tipada del estado del puente GL a Vulkan**, sin editar manualmente centenares de thunks generados, antes de intentar sustituir GL4ES.

Una comparación válida A/B/A necesitará **exactamente la misma escena y trabajo completo del juego**, calidad y política de VSync, no estos 75 FPS de un prototipo. El objetivo original del TECNO sigue siendo 60 FPS sostenidos y solo podrá probarse al disponer otra vez del teléfono.

### Reproducción, sin reejecutar experimentos históricos

```powershell
python tools/recomp/diagnostics/build_wsa_vk_bench.py --scene depth --present fifo
adb -s 127.0.0.1:58526 install -r .local/profiles/wsa_vulkan_ab/depth-fifo/wsa-vulkan-fifo-depth.apk
adb -s 127.0.0.1:58526 shell am start -n org.rigorcore.vkswapbench/android.app.NativeActivity
# Esperar VK_RESULT y guardar un NUEVO log, sin sobrescribir evidencia anterior
adb -s 127.0.0.1:58526 logcat -d -s RigorVkSurface:I > .local/profiles/wsa_vulkan_ab/depth-fifo/otra-sesion.log
python tools/recomp/diagnostics/summarize_wsa_vk_surface.py --log .local/profiles/wsa_vulkan_ab/depth-fifo/otra-sesion.log
```
