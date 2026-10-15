# Investigación real: Mesa Zink para CallofRecomp (14 de octubre de 2026)

**Conclusión:** Se descargó y validó el código original de **Mesa 26.2.4**. Zink es un traductor de **OpenGL de escritorio → Vulkan**, pero la GPU de WSA utilizada en las pruebas **NO cumple el subconjunto de requisitos obligatorios comprobado** del perfil oficial **`VP_ZINK_gl21_baseline`**. Por tanto, **no se integra ni se instala en CallofRecomp**. El TECNO físico no está disponible: todavía no tenemos una decisión sobre su controlador Mali.

## 1. Descarga y procedencia verificadas

| Campo | Resultado |
| --- | --- |
| Proyecto | Mesa 3D, controlador Gallium Zink |
| Versión fuente | **Mesa 26.2.4**, lanzamiento estable del **2026-10-01** |
| Fuente preferida | https://archive.mesa3d.org/mesa-26.2.4.tar.xz |
| Fuente utilizada para descarga | https://sources.voidlinux.org/mesa-26.2.4/mesa-26.2.4.tar.xz |
| Tamaño | **68.613.948 bytes** |
| SHA-256 **verificado** | `bce5f7fbebb934373b86c999a064d52fb5065878dc57f287f95346648ec832e9` |
| Referencia oficial SHA | https://docs.mesa3d.org/relnotes/26.2.4.html |
| Tag oficial en GitLab | `mesa-26.2.4`, SHA commit `3c479d6ab629eb9f6e2219fc77173058798e9795` (consulta remota) |
| Archivo privado descargado | `.local/profiles/mesa-zink/mesa-26.2.4.tar.xz` |
| Extracción para análisis | `.local/profiles/mesa-zink/source-review/mesa-26.2.4/` |
| Archivos extraídos para revisión | **138**, incluyendo `VP_ZINK_requirements.json`, código Gallium/Zink, `meson.options` y documentación Android |

El `tar` incluido en el entorno Windows no dispone de un descompresor XZ externo, así que la extracción de la selección de código se efectuó con `Python tarfile` tras comprobar el hash SHA-256. Esto **NO** implica archivo dañado ni una instalación de Mesa.

**No se agregan bibliotecas ni archivos del código Mesa a Git o a la APK**, y no se descargaron activos comerciales del juego. La fuente completa está disponible en local en el tarball ignorado por Git. La firma GPG del archivo no se comprobó; la autenticidad evaluada se basa en hash publicado por Mesa sobre HTTPS.

## 2. Qué hace Zink y dónde encajaría

**Zink** es un controlador Gallium que implementa OpenGL de escritorio emitiendo llamadas Vulkan. El juego requiere OpenGL clásico con fixed-function, texturas, matrices, pruebas alfa y vertex arrays; Zink puede ahorrarnos la implementación manual de muchos de esos estados, **si el dispositivo cumple su perfil y si Mesa se integra correctamente**.

Arquitectura que utiliza **CallofRecomp hoy**:

```text
CoD 1.5 x86 recompilado
    → gl_thunks.c (486 wrappers)
    → funciones OpenGL de GL4ES
    → SDL2 EGL/OpenGL ES 2.0
    → GPU Android / WSA
```

Una implementación **Zink nativa** necesitaría otro camino:

```text
CoD 1.5 recompilado
    → proveedor de OpenGL escritorio Mesa/Gallium (contexto compatible)
    → Zink
    → Vulkan del dispositivo
```

El proyecto actualmente configura de forma explícita `SDL_GL_CONTEXT_PROFILE_ES` versión 2.0 en `tools/recomp/runtime/window.c` y ejecuta `initialize_gl4es()`. El `android/CMakeLists.txt` incorpora GL4ES como biblioteca y lo configura para Android. **Zink no reemplaza ese código cambiando un flag de Vulkan**: exige resolver la creación de contexto y la carga de OpenGL (Mesa/EGL/DRI) dentro de una APK Android. En especial, un binario Windows de Zink/Mesa no funciona como biblioteca Android.

Referencia upstream: https://docs.mesa3d.org/drivers/zink.html y https://docs.mesa3d.org/android.html .

### Coste real de integración

El código descargado confirma que Zink se construye como biblioteca estática `libzink` dependiente de Gallium, NIR→SPIR-V, generación de device info a partir de `vk.xml`, utilidades Vulkan y otras bibliotecas Mesa; requiere un frontend OpenGL/EGL/DRI, no simplemente `vkCreateDevice`. La compilación de Mesa usa **Meson+Ninja+NDK** (`-Dgallium-drivers=zink`, `-Dplatforms=android`), con una cross-file de Android y dependencias adicionales.

La guía oficial para **reemplazar drivers del sistema en Android** describe remount de `/vendor` y permisos elevados. **Ese camino no es aceptable como requisito para nuestra APK**: no se ha rooteado ni alterado WSA ni el teléfono. Una posible distribución de bibliotecas Mesa dentro de la APK necesita diseño y validación específicos del loader, y **no está implementada**.

**No se compiló ni se instaló Mesa/Zink en el dispositivo:** no serviría todavía como comparativa A/B, y la GPU actual no cumple el perfil mínimo verificado.

## 3. Auditoría Vulkan del WSA real contra el perfil de Mesa 26.2.4

El source tarball incluye:

`src/gallium/drivers/zink/VP_ZINK_requirements.json`

Se inspeccionó el perfil **`VP_ZINK_gl21_baseline`**: API base Vulkan 1.2.0, funciones core GL2.1 y **11 nombres de extensiones** en `gl21_baseline`, con dos rutas alternativas para características de líneas y extensiones de características según versión de Vulkan.

Se compiló un **censo de características Vulkan real**, de solo lectura, con el NDK para WSA Android x86_64, y se ejecutó sin root:

`tools/recomp/diagnostics/zink_vk_requirements_probe.c`

Datos observados:

| Dato / requisito | WSA real | Juicio |
| --- | --- | --- |
| GPU Vulkan expuesta | **AMD Radeon(TM) Graphics**, vendor 0x1002, device 0x1638 | Identificada |
| API Vulkan | **1.3.0** | Supera el mínimo de versión 1.2 del perfil |
| `robustBufferAccess`, `logicOp`, `fillModeNonSolid`, `shaderClipDistance` | **Sí** | Correctos |
| **`alphaToOne`** | **NO** | **Requisito faltante** |
| **`VK_KHR_maintenance5`** | **NO** (Vulkan 1.3; la promoción exige 1.4) | **Requisito faltante** |
| **`VK_KHR_swapchain_mutable_format`** | **NO** | **Requisito faltante** |
| **`VK_EXT_border_color_swizzle`** | **NO** | **Requisito faltante** |
| `VK_KHR_create_renderpass2` | No aparece como extensión, pero sí vía Vulkan 1.2 core | **Correcto, no falso negativo** |
| `VK_KHR_timeline_semaphore` | Cubierto por Vulkan 1.2 core | Correcto |
| `VK_KHR_dynamic_rendering` | Cubierto por Vulkan 1.3 core | Correcto |
| `VK_KHR_incremental_present` | Anunciada | Correcto |
| `VK_EXT_line_rasterization` | Anunciada, `bresenhamLines=1` | Una vía alternativa disponible |
| `VkPhysicalDeviceVulkan12Features`: scalarBlockLayout, timelineSemaphore, drawIndirectCount | Sí | Correcto |

**Resultado: 4 requisitos obligatorios comprobados ausentes**: una feature core y tres extensiones. Esos fallos son suficientes para rechazar la compatibilidad **del subconjunto examinado**, sin necesitar un benchmark. Otros aspectos (formatos Vulkan, límites, alternativas del perfil, EGL de Android) **no están verificados por este censo**.

El dato `borderColorSwizzleFromImage=1` leído mediante `vkGetPhysicalDeviceFeatures2` **no concede** acceso a `VK_EXT_border_color_swizzle` si el driver **no anuncia la extensión**. Análogamente, se trataron las extensiones promovidas al núcleo Vulkan 1.2/1.3 como cubiertas por su versión, evitando contarlas falsamente como ausentes.

**Nota:** el perfil oficial se extrajo de **Mesa 26.2.4** para evitar comparar con una página «latest» que puede variar después del lanzamiento. El test oficial completo es `zink_check_requirements` al compilar Mesa con `--tools=zink`; este censo parcial **no afirma** haberlo ejecutado, y tampoco prueba que Zink no pueda funcionar en un controlador diferente.

Evidencia privada:
- `.local/profiles/mesa-zink/wsa-zink-profile-26.2.4.txt` (Vulkan nativo observado).
- `.local/profiles/mesa-zink/wsa-gl21-compatibility.json` (comparación automática con JSON de Mesa).
- `.local/profiles/mesa-zink/source-review-index.json` (inventario de extracción).

El comparador `tools/recomp/diagnostics/analyze_zink_requirements.py` compara automáticamente features/extensiones (incluidas promociones al core) contra el perfil JSON, falla ante datos incompletos y **nunca emite FPS**. Hay tests unitarios sintéticos en `tests/test_analyze_zink_requirements.py`.

## 4. Decisión, impacto en la estrategia vigente y siguiente paso

**Decisión actual: Zink NO APTO en el WSA examinado**, por no cumplir cuatro requisitos confirmados del perfil GL2.1 de Mesa 26.2.4. **No** empaquetar Zink, ni cambiar el GL4ES de producción, ni intentar corregir esto modificando los drivers o `/vendor`. La posibilidad de usar Zink en el TECNO ARM64 **sigue abierta** hasta medir su controlador Vulkan real, pero no se puede asumir.

Para la próxima etapa:
1. Al recuperar el TECNO, compilar y ejecutar **este mismo censo para ARM64**; comprobar `VP_ZINK_gl21_baseline` y el perfil completo antes de discutir integración.
2. Para WSA, evaluar como alternativa **ANGLE** detrás de GL4ES (OpenGL ES → Vulkan), porque su arquitectura encaja mejor con el contexto GLES2 actual; verificar características y correr una comparación A/B de **la misma escena completa del juego**, no demos sintéticas. Esta vía también puede añadir overhead: no prometer más FPS.
3. Mantener el trabajo actual como prototipo no predeterminado y seguir la **estrategia de CPU** (geometría/visibilidad/dispatcher, x87, GPU medible) cuando se trate de rendimiento. Zink no ataca directamente el coste de recompilación x86→ARM64.
4. No cambiar la estrategia por esta prueba aislada. **Contador de intentos A/B fallidos = 0/5**, porque no se creó ni midió un renderizador alternativo dentro del juego.

### Reproducción segura, sin instalar Mesa en el sistema

1. Descargar el tarball fuente de Mesa 26.2.4 y comprobar SHA-256 oficial.
2. Extraer **solo para investigación** `VP_ZINK_requirements.json` y código de Zink a una carpeta ignorada.
3. Compilar el censo para la arquitectura Android adecuada, por ejemplo para WSA:
```bat
C:\Users\Admin\AppData\Local\Android\Sdk\ndk\30.0.16248370\toolchains\llvm\prebuilt\windows-x86_64\bin\x86_64-linux-android28-clang.cmd ^
  -std=c11 -O2 -Wall -Wextra -Werror ^
  tools\recomp\diagnostics\zink_vk_requirements_probe.c ^
  -o .local\profiles\mesa-zink\zink-probe-x86_64 -lvulkan
adb -s 127.0.0.1:58526 push .local\profiles\mesa-zink\zink-probe-x86_64 /data/local/tmp/zink-probe-x86_64
adb -s 127.0.0.1:58526 shell chmod 700 /data/local/tmp/zink-probe-x86_64
adb -s 127.0.0.1:58526 shell /data/local/tmp/zink-probe-x86_64
```
4. Comparar el log contra el perfil del source tarball:
```bat
python tools/recomp/diagnostics/analyze_zink_requirements.py ^
  --mesa-profile .local/profiles/mesa-zink/source-review/mesa-26.2.4/src/gallium/drivers/zink/VP_ZINK_requirements.json ^
  --probe-log .local/profiles/mesa-zink/wsa-zink-profile-26.2.4.txt
```
5. El censo consulta exclusivamente propiedades Vulkan; no abre superficies ni instala controladores. **No se obtienen métricas de rendimiento**.

## Verificación de cierre

- Descarga Mesa 26.2.4: SHA-256 oficial vuelto a comprobar con `certutil`, **PASS**.
- El fichero fuente de 68,6 MB y los 138 ficheros de inspección figuran ignorados por Git, **no incluidos en los cambios publicados**.
- El censo C se compiló con NDK Clang `x86_64-linux-android28-clang` (`-Wall -Wextra -Werror`), se ejecutó en WSA y registró un perfil Vulkan real. La **comprobación de sintaxis ARM64** con NDK también pasó; TECNO ARM64 no fue ejecutado.
- Comparación JSON del perfil real contra la captura: **4 incompatibilidades**, 11 extensiones de perfil examinadas, 5 core features examinadas; `full_profile_checked=false`.
- Tests unitarios del analizador: **5/5 aprobados**; estrategia vigente y enlaces internos comprobados, sin errores de `git diff --check`.
- Se retiró el binario temporal del dispositivo WSA. La biblioteca **`libmain.so` instalada de CallofRecomp** sigue teniendo el SHA-256 exacto de referencia `403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde`, verificada al cerrar.
- **No se compilaron ni ejecutaron los paquetes completos Mesa/Zink**. No se ejecutó `zink_check_requirements` de Mesa; los cuatro bloqueos confirmados por censo básico ya impiden declarar compatible ese WSA. **No hubo benchmark del juego ni cambios de rendimiento.**

## Fuentes externas primarias

- Fuente y SHA oficiales Mesa 26.2.4: https://docs.mesa3d.org/relnotes/26.2.4.html
- Zink, requisitos y herramienta checker: https://docs.mesa3d.org/drivers/zink.html
- Android NDK / Meson y limitaciones drivers: https://docs.mesa3d.org/android.html
- Código oficial y tags: https://gitlab.freedesktop.org/mesa/mesa
