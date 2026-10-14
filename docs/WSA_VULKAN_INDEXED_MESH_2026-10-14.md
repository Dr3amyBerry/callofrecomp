# Hito Vulkan: geometría indexada y shaders nativos en WSA — 2026-10-14

**Estado:** IMPLEMENTADO Y EJECUTADO en una APK Android de diagnóstico independiente, compilada para **WSA x86_64**. **No** está integrado en el juego CoDSP y **no** se ha sustituido GL4ES.

## Alcance real del código

La prueba anterior `wsa_vk_surface_bench.c` solo creaba una superficie, limpiaba un color y presentaba. Esta nueva fase agrega una ruta alternativa optativa `--scene mesh`:

1. `glslc` del **NDK 30** convierte `wsa_mesh.vert` y `wsa_mesh.frag` a SPIR-V para Vulkan 1.0. `spirv-val` valida ambos binarios antes de empaquetarlos.
2. Los módulos SPIR-V se incluyen como **assets privados de la APK de diagnóstico**, se cargan mediante Android `AAssetManager` y se convierten en `VkShaderModule` usando `vkCreateShaderModule`.
3. `wsa_vk_mesh.c` crea `VkGraphicsPipeline`, `VkPipelineLayout` y un buffer combinado de vértices e índices `VkBuffer`. Aloja y escribe memoria `HOST_VISIBLE|HOST_COHERENT` con `vkMapMemory`, sin pasar por archivos de Call of Duty.
4. Usa atributos de posición (vec2), color (vec3), UV (vec2), push constant con matriz 4×4, `VkPipelineVertexInputStateCreateInfo`, `vkCmdBindVertexBuffers`, `vkCmdBindIndexBuffer`, `vkCmdPushConstants` y **`vkCmdDrawIndexed`**.
5. Dibuja una **malla de 4 vértices y 6 índices** (dos triángulos) con un fragment shader que genera un patrón de cuadros coloreado a partir de las coordenadas UV.
6. Reutiliza el mismo swapchain, semáforos y fences Vulkan de la prueba WSI, destruyendo pipeline, layout, buffer y memoria antes de destruir el device. No necesita permisos especiales ni modificar la APK del juego.

**Importante:** el patrón de cuadros es **procedural**. Todavía **no** utiliza `VkImage` con texturas subidas desde RAM, sampler, descriptor sets, depth/stencil, matrices del juego ni shaders de iluminación del fixed-function OpenGL. Esta es la primera etapa de rasterización con shaders, no un motor gráfico completo.

## Medición nueva: Vulkan mesh frente a referencia WSI anterior

| Métrica | WSI anterior, color sólido | Nueva prueba con malla indexada |
| --- | ---: | ---: |
| Trabajo realizado | Solo `vkCmdBeginRenderPass` + clear | `vkCmdDrawIndexed`, atributos y shaders |
| Frames presentados | 1.276 | **1.276** |
| Duración medida | 17,01 s | **17,013 s** |
| FPS promedio de presentación | 75,014 | **74,999** |
| FPS mediana de ventanas de ~1 s | ~75 | **74,993** |
| FPS p10 de ventanas de ~1 s | ~74,922 | **74,910** |
| CPU del hilo de prueba por frame | 1,902 ms | **1,918 ms** |
| Resolución del swapchain | 1280×720 | **1280×720** |
| Present mode | FIFO | **FIFO** |

La imagen capturada muestra la malla coloreada con cuadros. Evidencia privada: `.local/profiles/wsa_vulkan_ab/mesh-fifo/preview.png`, `result.log`, `result.json` y APK bajo el mismo directorio, todos ignorados por Git.

**Interpretación:** ambas cargas rondan 75 FPS porque **WSA presenta a 75 Hz en FIFO**, no porque la malla tenga el mismo coste GPU que un clear. La CPU reportada corresponde al hilo de la app de diagnóstico y no mide tiempo GPU. La prueba no permite inferir rendimientos del CoDSP real, ni proclamar que «Vulkan es 36 % más rápido que GL4ES».

## Archivos y reproducción

- `tools/recomp/diagnostics/wsa_vk_mesh.c` y `.h`: módulo de buffers, atributos y pipeline.
- `tools/recomp/diagnostics/shaders/wsa_mesh.vert` y `wsa_mesh.frag`: shaders fuente GLSL (no vender o incluir material comercial).
- `tools/recomp/diagnostics/wsa_vk_surface_bench.c`: integra **solo si `VK_BENCH_MESH_SCENE`** está activo; clear continúa como antes.
- `tools/recomp/diagnostics/build_wsa_vk_bench.py`: nuevo `--scene mesh` o `--scene clear` (default); construye y firma APK independiente, compila/valida shaders.
- `tools/recomp/diagnostics/summarize_wsa_vk_surface.py` identifica el tipo de escena de prueba y rechaza marcadores de malla incompletos; mantiene `gameplay_fps_comparable=false`.
- `tests/test_wsa_vk_surface.py`: tests de las dos rutas e inconsistencia de marcadores.

```powershell
python tools/recomp/diagnostics/build_wsa_vk_bench.py --scene mesh --present fifo
adb -s 127.0.0.1:58526 install -r .local/profiles/wsa_vulkan_ab/mesh-fifo/wsa-vulkan-fifo-mesh.apk
adb -s 127.0.0.1:58526 shell am start -n org.rigorcore.vkswapbench/android.app.NativeActivity
# Esperar ~20 s hasta que aparezca VK_RESULT en logcat
adb -s 127.0.0.1:58526 logcat -d -s RigorVkSurface:I > .local/profiles/wsa_vulkan_ab/mesh-fifo/nueva-medicion.log
python tools/recomp/diagnostics/summarize_wsa_vk_surface.py --log .local/profiles/wsa_vulkan_ab/mesh-fifo/nueva-medicion.log
```

**No ejecutar estas órdenes para reproducir pruebas antiguas salvo necesidad concreta**; todos los resultados previos se conservaron.

## Validación y controles al cerrar el hito

- **127 pruebas Python aprobadas (4 omitidas)**, incluyendo el parser específico `mesh`, y **31/31 CTest**.
- La prueba `--scene mesh` compiló con NDK Clang x86_64, generó y validó ambas etapas SPIR-V con `spirv-val` y produjo una APK firmada y verificada.
- El código nativo `wsa_vk_mesh.c` y la prueba de swapchain **pasaron la comprobación de compilación ARM64** con NDK `aarch64-linux-android28-clang`, `-Wall -Wextra -Werror`, sin ejecutarse en dispositivo ARM64.
- WSA ejecutó realmente el prototipo, emitió `VK_MESH_READY` y `VK_RESULT`, y una captura de pantalla evidenció una malla coloreada con cuadros. La app de diagnóstico se detuvo al terminar; no se modificó la APK de CallofRecomp instalada.
- No se repitieron mediciones históricas de la partida ni la prueba `clear`. No se ha comparado la escena de CoDSP con Vulkan ni se han confirmado 120 FPS.

**Actualización posterior (misma fecha):** la subida y el sampleo de una textura Vulkan RGBA8 real ya funcionan en el prototipo WSA. Ver [hito de textura y medición aislada](WSA_VULKAN_TEXTURE_2026-10-14.md). Los otros bloques de esta lista siguen pendientes.

## Trabajo pendiente para llevarlo a CallofRecomp

1. Subir y samplear **texturas reales** con `VkImage`, layout transitions, staging buffers y descriptor sets. Validar mipmaps, filtros y formatos.
2. Añadir depth/stencil, blending, culling, interpolación correcta y sincronización de recursos; después transformar matrices y estados del OpenGL heredado a pipeline/descriptors Vulkan.
3. Diseñar un adaptador tipado que capture/compruebe `glDrawElements`, arrays y estados del puente GL, sin editar a mano los thunks generados. Asegurar paridad visual y de control.
4. Solo entonces integrar un backend optativo con fallback GL4ES en una APK del juego y medir Camp Toccoa A/B/A **con el mismo frame cap y recursos**. Con WSA a 75 Hz no se podrán confirmar 120 frames presentados en modo FIFO actual.
5. Validación definitiva en TECNO ARM64 al volver a estar disponible. El objetivo del teléfono continúa en 60 FPS sostenidos; no extrapolar WSA.

**Política de estrategia:** este es un test aislado de compatibilidad Vulkan, no un intento válido de optimización de la partida; el contador **permanece 0/5**. La APK comercial original de CallofRecomp y los guardados no se cambiaron.
