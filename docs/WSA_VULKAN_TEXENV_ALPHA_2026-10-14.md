# Vulkan WSA: TexEnv MODULATE/REPLACE + prueba alfa (2026-10-14)

**Estado:** Implementado, shaders SPIR-V validados y verificación visual real en **WSA x86_64**, como prototipo `org.rigorcore.vkswapbench`. **CallofRecomp sigue con OpenGL/GL4ES** y no existe todavía renderer Vulkan completo del juego. El TECNO físico sigue no disponible. Los datos privados, APK de pruebas y capturas no se publican.

## Cambios técnicos

Se abordaron los dos estados heredados GL seleccionados después de la primera captura del juego, que encontró 164 snapshots y ningún estado completamente traducible (máscara previa `0x19`). **Este desarrollo no convierte esa captura anterior en compatible de forma retroactiva**, pues hay muchas otras APIs sin traducir.

- `gl_vk_state.h/.c`: seguimiento por **unidad de textura** de `GL_TEXTURE_ENV/GL_TEXTURE_ENV_MODE`, con default GL **MODULATE (0x2100)**. Admite **MODULATE** y **REPLACE (0x1e01)** en `glTexEnvi`, `glTexEnvf`, `glTexEnviv`, `glTexEnvfv`. Los modos DECAL, BLEND, ADD y COMBINE, otras propiedades `glTexEnv` o punteros inválidos **no** se dan por compatibles: marcan incompatibilidad persistente. Se mantienen sin cambios estados de otra unidad.
- `gen_gl.py`: los cuatro wrappers anteriores se generan con `GL_VK_OBSERVE` **después** de sus llamadas originales a GL4ES. `glTexEnvf` conserva la representación de 32 bits del escalar float; los `glTexEnv*v` leen de la memoria invitada mediante `GP`. El generador se ejecutó contra `gl.xml` de Khronos disponible en la zona privada y produjo **486 wrappers**, sin editar cada uno a mano. El observador de juego es opcional, **OFF por defecto**, y no redirige dibujos a Vulkan.
- `--scene alpha` nuevo en `build_wsa_vk_bench.py`: compila un shader `wsa_alpha.frag` con acceso a `sampler2D` y parámetros enviados mediante push constants. El shader realiza **MODULATE / REPLACE** y compara la alfa resultante con el umbral `0.5` (`GL_GREATER`), usando `discard` si no supera la prueba. El shader incluye comparaciones para la familia GL `NEVER, LESS, EQUAL, LEQUAL, GREATER, NOTEQUAL, GEQUAL, ALWAYS` pero la ejecución visual presente verifica específicamente `GREATER`.
- La textura de **64×64 RGBA8** anterior continúa creada mediante staging buffer + `VkImage`. Solo en la escena `alpha` sus cuadros oscuros tienen alfa=0 y los claros alfa=1.
- Se dibujan **dos quads indexados** con la misma textura y descriptor: a la izquierda MODULATE (se colorea por los vértices), a la derecha REPLACE (amarillo original). Ambos presentan huecos reales por descarte de fragmentos, dejando ver el fondo azul. Se conserva el camino de muestra anterior (sin alfa) y los modos Vulkan anteriores.

### Prueba funcional WSA

La APK aislada `--scene alpha --present fifo` se compiló, firmó y ejecutó realmente en el subsistema Android de Windows. Logcat informó:

```text
VK_MESH_READY vertices=4 indices=6 draws_per_frame=2 procedural_checker=0
VK_TEXTURE_READY width=64 height=64 mip_levels=1 descriptor_sets=1 sampler=nearest transfer=staging image_layout=shader_read_only
VK_ALPHA_READY env_modes=modulate_replace alpha_func=greater alpha_ref=0.500 alpha_source=rgba8_texture draws_per_frame=2
VK_SCENE name=alpha, integration=standalone, gameplay=0
```

La captura de pantalla de la app, revisada visualmente, muestra la mitad MODULATE con gradiente de color y la mitad REPLACE en amarillo; los fragmentos de alfa cero no se pintan en ninguna de las dos. Prueba privada: `.local/profiles/wsa_vulkan_ab/alpha-fifo/preview.png`, `result.log`, `result.json` y APK experimental.

| Indicador del prototipo, **NO FPS de CallofRecomp** | Resultado |
| --- | ---: |
| Frames Vulkan presentados | **1.276** |
| Duración medida | **17,004 segundos** |
| FPS promedio FIFO | **75,043** |
| Mediana de ventanas (~1 segundo) | **74,9975 FPS** |
| FPS p10 de ventanas | **74,978** |
| CPU del hilo de prueba por frame | **1,99041 ms** |
| Swapchain | **1280×720, FIFO** |
| Draws indexados/frame | **2** |

Los FPS rondan 75 por la **frecuencia de presentación del WSA**, no por equivalencia con la carga geométrica/materiales del juego. Las cifras **no prueban aceleración** de CallofRecomp, ni un renderer Vulkan del juego. No se repitieron A1/A2/B1/A3 ni los benchmarks históricos clear/mesh/texture/depth.

### Validación de regresión y compatibilidad

- Pruebas C de defaults GL, unidad de textura independiente, `glTexEnv*I/F/IV/FV`, rechazo fail-closed de GL_DECAL/enum/punteros sin traducción y restauración de estado.
- Test del generador con XML Khronos sintético: llamadas host GL intactas y hooks nuevos de texenv generados sobre argumentos correctos.
- Analizador de logs Vulkan ampliado con escena `alpha`: exige marcadores coherentes de shader/texture y rechaza configuración ausente o inconsistencias de draw count.
- Sintaxis ARM64 validada con NDK Clang, sin ejecutar en el teléfono real.
- Recompilación de los modos Vulkan anteriores **texture y depth** sin reejecutar su benchmark: salida firmada correctamente.
- La APK CallofRecomp original instalada en WSA sigue siendo exactamente la referencia A1: hash SHA-256 `403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde`; la app de prueba Vulkan se detuvo.

## Resultado final de las pruebas y restauración

- **138 pruebas Python ejecutadas** (4 omitidas) sin fallos; **32/32 CTest** aprobadas.
- Comprobación NDK **ARM64** de la nueva escena y del generador de wrappers: correcta (sintaxis únicamente; el teléfono no estaba disponible).
- Las escenas Vulkan anteriores **texture y depth** siguen compilándose en APK firmada; no se repitieron sus pruebas de FPS.
- CallofRecomp **x86_64 con `--gl-vk-state-capture`** compiló y firmó correctamente, sin instalar ni iniciar ese nuevo build experimental del juego.
- CallofRecomp x86_64 **normal, sin captura**, también compiló y firmó correctamente. `CODRECOMP_GL_VK_STATE_CAPTURE:BOOL=OFF` en `CMakeCache.txt` al finalizar.
- La `libmain.so` instalada en WSA continúa idéntica **byte a byte** a la referencia A1, SHA-256 `403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde`. La app Vulkan de diagnóstico se detuvo; ningún dato de partidas modificado.
- El parser rechaza escenas `alpha` cuyos marcadores no confirmen el shader/estado esperado o cuyo número de draws sea inconsistente.

**Actualización posterior:** se implementaron las operaciones tipadas de `glTranslate/Rotate/Scale/Ortho/Frustum`, con el backend Vulkan aislado demostrando transformaciones correctas sobre tres quads WSA. La integración con la geometría real del juego sigue pendiente. [Informe del hito de matrices](WSA_GL_MATRIX_BRIDGE_2026-10-14.md).

## Próximos bloqueos reales

1. `GL_COMBINE` / `GL_ADD` / `DECAL` / `BLEND` en `glTexEnv`, y operación de múltiples unidades de textura en shaders; textura/alpha procedente del juego real, no solo checker artificial.
2. Estados de sampler en `glTexParameter*`, imagen y uploads `glTexImage2D` / `glTexSubImage2D` hacia `VkImage` y mipmaps; gestionar la vida de múltiples texturas.
3. Transformaciones `glTranslate/Rotate/Scale`, matrices/proyección, arrays de vértices y llamadas `glDrawElements`, sin reescribir a mano thunks generados.
4. Backend Vulkan **opcional con fallback GL4ES**, equivalencia visual escena completa con assets propios del usuario y finalmente A/B/A del juego, a igual escena y cap/VSync. Al volver el TECNO, verificar allí los 60 FPS sostenidos.

**Contador oficial 0/5:** este es un hito de compatibilidad, no un intento A/B de FPS del juego; la estrategia principal del perfil de geometría/visibilidad permanece vigente.
