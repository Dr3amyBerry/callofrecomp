# Evaluación de Vulkan nativo, DirectX 12 y entorno WSA — 2026-10-14

**Decisión actual:** NO reemplazar todavía el renderizador GL4ES/GLES; **explorar Vulkan como backend experimental Android** solo tras demostrar el coste de GPU o de la traducción GLES y establecer un alcance verificable. **NO implementar un renderizador híbrido «Vulkan + DirectX 12» dentro del proceso Android.** Mantener la estrategia de rendimiento v1 y el contador **0/5**.

**Actualización posterior:** una NativeActivity aislada creó de verdad `VkAndroidSurfaceKHR`, `VkSwapchainKHR` y presentó frames a ~75 FPS FIFO en WSA. Las menciones siguientes a presentación «no probada» documentan el estado anterior. [Resultados nuevos](WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md). **El juego aún no tiene un renderer Vulkan.**

## Situación de pruebas (teléfono temporalmente no disponible)

El usuario indicó que el TECNO físico **no está disponible**. En esta sesión **no se usó el teléfono**. El único dispositivo ADB conectado y utilizado fue **WSA `127.0.0.1:58526`, Android 13, x86_64**. WSA es válido para API/prototipos, validación funcional y A/B **dentro de WSA**, pero **NO predice FPS, frecuencias de GPU, drivers ni temperatura de la Mali ARM64**.

Se confirmó desde el proyecto:
- `tools/recomp/runtime/window.c`: SDL2 crea `SDL_WINDOW_OPENGL`, contexto `SDL_GL_CreateContext`, y utiliza `initialize_gl4es()` en Android.
- `tools/recomp/runtime/gl_thunks.c`: puente de OpenGL legado generado automáticamente desde Khronos `gl.xml`; no editar manualmente el archivo.
- Ruta actual: **OpenGL de Call of Duty 1.5 → thunks OpenGL → GL4ES (compatibilidad de fixed function/estado GL) → GLES 2.0 → EGL/controlador Android → GPU**.
- No se encontraron `SDL_WINDOW_VULKAN`, `vkCreateInstance`, D3D12 ni backend Vulkan dentro del runtime del juego.

Implementar Vulkan real exigiría rediseñar la capa que traduce el API OpenGL heredado a comandos gráficos modernos (sombras/shaders fixed function, matrices, luces, estados, combinadores de texturas, geometría inmediata/arrays, VBO, recursos, sincronización, presentación). No basta reemplazar EGL con `vkCreateInstance`; GL4ES no produce comandos Vulkan por sí mismo.

## Qué GPU, Vulkan y DirectX se han comprobado realmente

### Dentro de WSA (ADB; Android guest)

| Comprobación | Resultado |
| --- | --- |
| `getprop ro.hardware.egl` | `emulation` |
| `getprop ro.hardware.vulkan` | `ranchu` |
| `dumpsys SurfaceFlinger` | `Microsoft, Subsystem OpenGL ES Translator, OpenGL ES 3.0` |
| `pm list features` | Publica funciones Android Vulkan |
| Biblioteca Vulkan | `/vendor/lib64/hw/vulkan.ranchu.so` |
| `cmd gpu vkjson` | `{}` (consulta sin datos, NO prueba de que Vulkan falle) |
| **Prueba NDK real en WSA** | `vkEnumerateInstanceVersion=VK_SUCCESS`, API loader Vulkan **1.3.0** |
| **`vkCreateInstance` real** | **VK_SUCCESS** |
| **`vkEnumeratePhysicalDevices` real** | **VK_SUCCESS; 1 dispositivo** |
| GPU reportada | **AMD Radeon(TM) Graphics**, API **Vulkan 1.3.0** |
| Familias de colas | 3; al menos una con capacidad gráfica |
| `VK_KHR_swapchain` | Disponible entre extensiones de dispositivo |
| Superficie Vulkan Android, swapchain y presentación | **PROBADOS en NativeActivity aislada (~75 FPS FIFO); tiempo de GPU por draw NO medido** |

La prueba no usa assets del juego, se ejecutó únicamente en WSA (x86_64) y está implementada en [`tools/recomp/diagnostics/probe_android_vulkan.c`](../../../tools/recomp/diagnostics/probe_android_vulkan.c). Su salida privada exacta está bajo `.local/profiles/wsa_vulkan_probe_result.txt`. La presencia de una extensión no garantiza que una escena del juego pueda presentarse o que su rendimiento sea superior al de GLES.

### En el PC Windows host

- `vulkaninfo --summary`: GPU integrada **AMD Radeon(TM) Graphics**, Vulkan **1.3.260**, driver AMD propietario (informe local privado).
- `dxdiag`: **DirectX 12** instalado en Windows, Radeon con WDDM 2.7. Sin embargo, `dxdiag` reportó **`DDI Version: Unknown` y `Feature Levels: Unknown`**, por lo que **no se ha validado un `ID3D12Device` o nivel funcional concreto** en esta sesión.
- Los procesos Android de WSA no llaman directamente a la API Win32 Direct3D 12. Si WSA usa D3D12 internamente en el host, eso depende de su capa de virtualización. **No se ha demostrado ni medido su backend interno** a partir de las características de Vulkan del guest.

**No confundir tres APIs:** Vulkan (API nativa multiplataforma); Direct3D 12 (API nativa Windows); OpenGL ES (API utilizada actualmente dentro del proceso Android). Hacer un backend Android Vulkan y otro backend Windows D3D12 sería mantener **dos implementaciones independientes**, con costes de compatibilidad y pruebas muy altos.

## Qué significa «GPU pendiente de permisos» en el TECNO anterior

Las siguientes observaciones vienen del **perfil anterior cuando sí estaba conectado el teléfono**. No se intentó acceder a él hoy:

1. `adb shell cat /sys/class/devfreq/13040000.mali/cur_freq` devolvió **`Permission denied`**. El usuario ADB `shell` no tiene permiso de lectura sobre ese contador de frecuencia de la GPU Mali (restricción de sistema/driver; pueden intervenir permisos del nodo y SELinux).
2. `/sys/class/devfreq/13040000.mali/load` **no existía**. No es cuestión de activar permisos de Android para un archivo inexistente.
3. El servicio Perfetto expuso fuentes `android.gpu.memory` y SurfaceFlinger, pero **no** `gpu.counters` ni `gpu.renderstages` en esa configuración. No se puede inventar carga, tiempo de shaders ni ocupación de GPU.
4. Esto **NO** significa que falte permiso de cámara/archivos, que el juego no pueda utilizar GLES, ni que Vulkan esté prohibido en el TECNO. Para algunas métricas hardware se requiere soporte de fabricante/driver, un perfilador AGI/Mali compatible o un entorno de diagnóstico privilegiado. No proponer root ni cambios de seguridad al teléfono solo para investigar FPS.
5. El antiguo tiempo `swap` y las muestras de CPU del driver no equivalen al tiempo de GPU. **Estado de GPU física: no medido**, no «GPU libre».

## Datos de rendimiento existentes que condicionan la decisión

- **TECNO ARM64, spawn estático:** 24,70 FPS medianos, ~38,895 ms CPU/frame, ~83,93 % de muestras del proceso en `libmain.so`; GL4ES ~1,81 %, driver GLES Mali ~4,10 % de muestras CPU. Son muestras de tiempo de CPU, no porcentajes de GPU.
- **WSA x86_64, escena previa equivalente:** ~54,5 FPS medianos y ~17,86 ms CPU/frame. WSA corre código x86_64 y otro driver/controlador, **no** es evidencia de 60 FPS en TECNO.
- Experimentos previos de VBO interno GL4ES `LIBGL_USEVBO=2/3` en WSA redujeron FPS a 49,25/51,55 frente a 54,50. Ajustar backend sin perfiles GPU puede empeorar, no mejorar.
- El juego emite aproximadamente 103 llamadas indexadas y 116 cambios de textura **por frame de WSA** desde el puente original (no son necesariamente los draws reales GLES). Una capa Vulkan completa puede añadir trabajo de traducción de estados/copy si se implementa sin batching.
- Perfilado Simpleperf y controles térmicos reales del TECNO ya sustentan priorizar CPU recompilada. Se conserva la hipótesis Vulkan para escenarios donde la GPU se demuestre limitante o una sustitución de traducción concreta ahorre CPU medible.

## Plan WSA temporal y criterios para un piloto gráfico

1. **Mantener OpenGL/GL4ES como A estable.** WSA x86_64 es banco de pruebas; grabar escena, Build ID, perfil Equilibrado, HUD y 40–60 ventanas de FPS sin instrumentación.
2. **Viabilidad gráfica Vulkan aislada comprobada** (posterior al probe de enumeración): SDL2 Vulkan surface → `vkGetPhysicalDeviceSurfaceSupportKHR` → `vkCreateSwapchainKHR` → limpiar/color de fondo → `vkQueuePresentKHR`. Comparar tiempos CPU de presentación. Esto no es aún portar el renderizador ni demuestra FPS en CoDSP.
3. Antes de escribir todo el renderer, valorar un **backend ANGLE GLES→Vulkan** de forma optativa en una compilación aislada si la versión de SDL/EGL, GL4ES y WSA son compatibles; exige pruebas de compatibilidad visual y GL extensions, no es un simple cambio de variable universal.
4. Si hay ganancia reproducible en WSA y soporte de hardware futuro, decidir si merece la pena un **adaptador OpenGL heredado → Vulkan nativo**. Priorizar grandes bloques: recursos/estados/shaders, validación de menús, HUD widescreen, texturas, efectos, estabilidad y escenas concurridas. Planificar fuera de la rama estable.
5. **DirectX 12 no entra en el renderer Android.** Solo contemplar un backend D3D12 separado si en el futuro existe un ejecutable Windows nativo y una necesidad demostrada. No agregar dos renderers ahora.
6. Reanudar comparaciones finales de **60 FPS sostenidos en ARM64 físico** cuando el TECNO regrese. Cualquier mejora exclusivamente WSA se documenta como tal; no extrapolar a la Mali.

**Política de cinco intentos:** estos son diagnósticos y una prueba Vulkan aislada, sin candidato de optimización del juego ni A/B/A bajo hardware objetivo. El contador queda **0/5**. No se cambia de estrategia de rendimiento sin las condiciones establecidas.

### Comandos de reproducción (solo WSA)

```powershell
# Android NDK 30 instalado, x86_64, API 28; archivo C público sin assets
$clang = Join-Path $env:ANDROID_HOME 'ndk/30.0.16248370/toolchains/llvm/prebuilt/windows-x86_64/bin/x86_64-linux-android28-clang.cmd'
& $clang -O2 -Wall -Wextra tools/recomp/diagnostics/probe_android_vulkan.c -o .local/profiles/wsa_vulkan_probe -lvulkan
adb -s 127.0.0.1:58526 push .local/profiles/wsa_vulkan_probe /data/local/tmp/codrecomp_vk_probe
adb -s 127.0.0.1:58526 shell 'chmod 755 /data/local/tmp/codrecomp_vk_probe; /data/local/tmp/codrecomp_vk_probe'
```

Conservar los resultados, logs, APKs y capturas en `.local/profiles` (ignorados por Git). No publicar activos originales comerciales ni partidas.

## Validaciones de cierre

- Compilación real de `probe_android_vulkan.c` para Android **x86_64 API 28** usando Clang/NDK 30: correcta sin errores ni advertencias.
- Ejecución real en WSA: programa devuelve `exit 0` y todos los puntos de enumeración listados arriba pasaron.
- **117 pruebas Python aprobadas (4 omitidas)** y **31/31 CTest** del proyecto. No hay un renderer nuevo que necesite pruebas de imagen, porque no se ha integrado ninguno.
- No se invocó ADB del teléfono ausente, no se modificaron APK del juego, datos importados, configuración de gráficos ni guardados.

**Estado actualizado:** además del probe de enumeración, se añadió y ejecutó la prueba de superficie/swapchain/present independiente a ~75 FPS FIFO con un color sólido. **No existe backend Vulkan de CallofRecomp ni se ha medido su FPS**. El tiempo interno de GPU permanece sin medir; código jugable y partidas intactos.
