# Vulkan WSA: subida real de texturas RGBA8 con staging y sampler

**Fecha:** 2026-10-14
**Estado:** implementado y demostrado en la APK **independiente** `org.rigorcore.vkswapbench`, escena `--scene texture`.
**El juego sigue usando OpenGL/GL4ES; no hay backend Vulkan completo para CallofRecomp ni mejora medida del juego.**
**Equipo:** WSA x86_64, Android 13; TECNO físico no disponible. Sin cambios en archivos comerciales, APK del juego ni guardados.

## Funcionalidad añadida

La ruta `texture` extiende la malla indexada de la fase anterior, sin romper las escenas `clear` y `mesh`.

1. La CPU genera **64×64 píxeles RGBA8** propios (azul/amarillo, cuadros de 8 píxeles), sin utilizar texturas ni activos de Call of Duty.
2. `wsa_vk_texture.c` crea un **VkBuffer de staging**, selecciona una memoria HOST_VISIBLE + HOST_COHERENT, escribe píxeles con `vkMapMemory`.
3. Crea **VkImage R8G8B8A8_UNORM óptima**, uso `TRANSFER_DST|SAMPLED`, 1 mip y memoria DEVICE_LOCAL.
4. Graba en un buffer de comandos temporal: `UNDEFINED → TRANSFER_DST_OPTIMAL`, `vkCmdCopyBufferToImage`, `TRANSFER_DST_OPTIMAL → SHADER_READ_ONLY_OPTIMAL`. Barreras `TOP_OF_PIPE→TRANSFER` y `TRANSFER→FRAGMENT_SHADER` con accesos correspondientes.
5. Envía copia por la misma cola gráfica (`vkQueueSubmit`), espera un fence **antes** de liberar el staging y el command pool. El camino de error no espera fences no enviados.
6. Crea **VkImageView, VkSampler nearest/repeat**, layout `COMBINED_IMAGE_SAMPLER` set=0 binding=0, descriptor pool + set y actualiza `VkDescriptorImageInfo`.
7. El pipeline reserva un descriptor set layout solo cuando la escena es `texture`. Antes de `vkCmdDrawIndexed`, vincula `vkCmdBindDescriptorSets`.
8. `wsa_texture.frag` lee realmente **`texture(sampler2D, uv)`**, modulando el color de los vértices. El shader SPIR-V se compila con `glslc`, se valida con `spirv-val` y se empaqueta como asset en la APK de prueba.

**No hay:** mipmaps, formatos comprimidos del juego, sampler anisotrópico, depth/stencil, blending del motor, gestión de múltiples texturas, sincronización entre frames de texturas actualizadas en caliente ni traducción de fixed-function OpenGL. Este hito solamente establece la ruta correcta de subida + sampleo de **una** textura.

## Validación real WSA

El proyecto de diagnóstico `--scene texture --present fifo` compiló, firmó y se instaló sin modificar la app CallofRecomp. Logcat de la ejecución:
- `VK_MESH_READY vertices=4 indices=6 draws_per_frame=1 procedural_checker=0`.
- `VK_TEXTURE_READY width=64 height=64 mip_levels=1 descriptor_sets=1 sampler=nearest transfer=staging image_layout=shader_read_only`.
- `VK_SCENE name=texture, integration=standalone, gameplay=0`.
- `VK_RESULT fps=75.117 frames=1277 seconds=17.000 thread_cpu_ms_per_frame=1.98872 ... present_mode=FIFO resolution=1280x720`.

Una captura real en WSA muestra una malla con cuadros azules/amarillos **sampleados de la textura**, distintos del checker procedural anterior. Archivos privados: `.local/profiles/wsa_vulkan_ab/texture-fifo/result.json`, `result.log`, `preview.png` y la APK firmada. **No** publicar la APK del juego, los guardados ni perfiles privados en Git.

| Prueba aislada | Trabajo | FPS presentados (promedio) | CPU del hilo/frame |
| --- | --- | ---: | ---: |
| Vulkan clear previo | Un color sólido | 75,014 | 1,902 ms |
| Vulkan mesh previo | Malla con checker procedural | 74,999 | 1,918 ms |
| **Vulkan texture nueva** | **Malla con VkImage RGBA8 / sampler / descriptor** | **75,117** | **1,989 ms** |

Las tres rondan los **75 Hz** de presentación FIFO en WSA. Esto **NO** significa una mejora del motor ni permite estimar cuánto tardaría un frame real de CoDSP en Vulkan. CPU del hilo medido no es latencia GPU, y las cifras están afectadas por el límite de presentación. No repetir benchmarks antiguos por este hito.

## Archivos modificados

- `tools/recomp/diagnostics/wsa_vk_texture.c`, `.h`: carga de píxeles, VkBuffer staging, VkImage, transición de layout, descriptor y cleanup.
- `tools/recomp/diagnostics/shaders/wsa_texture.frag`: shader de muestreo de textura.
- `tools/recomp/diagnostics/wsa_vk_mesh.c`, `.h`: extiende pipeline indexado con descriptor opcional, carga de módulo SPIR-V y binding.
- `tools/recomp/diagnostics/wsa_vk_surface_bench.c`: nuevos marcadores de escena y estado de la textura.
- `tools/recomp/diagnostics/build_wsa_vk_bench.py`: `--scene texture`, compilación/validación SPIR-V y empaquetado, manteniendo `--scene clear` por defecto.
- `tools/recomp/diagnostics/summarize_wsa_vk_surface.py`: distingue `clear`, `mesh` y `texture`, rechaza resultados sin `VK_TEXTURE_READY` o configuración incoherente.
- `tests/test_wsa_vk_surface.py`: tests de marcadores de textura, fallos cerrados y protección contra atribuir FPS al juego.

## Reproducción (únicamente si se necesita repetir la prueba)

```powershell
python tools/recomp/diagnostics/build_wsa_vk_bench.py --scene texture --present fifo
adb -s 127.0.0.1:58526 install -r .local/profiles/wsa_vulkan_ab/texture-fifo/wsa-vulkan-fifo-texture.apk
adb -s 127.0.0.1:58526 shell am start -n org.rigorcore.vkswapbench/android.app.NativeActivity
# Esperar VK_RESULT en logcat (~20 s, incluye 2 s de calentamiento).
adb -s 127.0.0.1:58526 logcat -d -s RigorVkSurface:I > .local/profiles/wsa_vulkan_ab/texture-fifo/otro.log
python tools/recomp/diagnostics/summarize_wsa_vk_surface.py --log .local/profiles/wsa_vulkan_ab/texture-fifo/otro.log
```

## Validación y cierre

- **129 pruebas Python correctas (4 omitidas)** y **31/31 CTest**; los 7 tests especializados en parsing Vulkan cubren ausencia de descriptores y escenas mal clasificadas.
- `glslc` y `spirv-val` validaron shader de vértices y nuevo fragment shader para Vulkan 1.0; el NDK compiló/firmanó la APK de prueba x86_64.
- Comprobación de sintaxis nativa con **NDK Clang ARM64** (`-Wall -Wextra -Werror`) aprobada para `wsa_vk_texture.c`, `wsa_vk_mesh.c` y `wsa_vk_surface_bench.c`; no se ejecutó ARM64 físico.
- El prototipo mostró la textura visualmente en WSA y se detuvo al cerrar la prueba.
- Se verificó de nuevo la **identidad SHA-256** de la biblioteca del juego instalada en WSA frente a la referencia GL4ES original: `403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde`. **No se reinstaló, recompiló ni volvió a medir el juego.**
- Los logs, PNG y APKs experimentales permanecen privados en `.local/profiles` y no se incluyen en este commit.

**Actualización posterior del mismo día:** el prototipo aislado ahora demuestra depth/stencil y blending alfa reales, sin alterar la prueba anterior de texturas. [Hito de profundidad/transparencia](WSA_VULKAN_DEPTH_STENCIL_BLEND_2026-10-14.md). El texto siguiente conserva el plan histórico antes de completar ese bloque.

## Siguiente desarrollo

**Bloque recomendado:** depth/stencil y blending, para después representar múltiples estados del OpenGL heredado (texturas dinámicas, filtros, depth test, alpha, culling, matrices). Diseñar la traducción en la capa generadora/puente y no editar manualmente cientos de thunks. Habilitar el backend Vulkan para el juego **solo cuando** se preserve visualmente el entrenamiento, menú, HUD, controles y texturas de la referencia GL4ES. Después A/B/A con las mismas condiciones, primero WSA y por último TECNO físico.

**Estrategia oficial:** tres fases conservadas, **0/5** intentos válidos fallidos. Prueba aislada de capacidades no cuenta como optimización real.
