# CallofRecomp

**ES:** Proyecto experimental para llevar *Call of Duty* clásico de PC (versión 1.5) a Android mediante recompilación estática. Es necesario aportar una copia compatible del juego; **el repositorio y las APK no incluyen sus archivos comerciales**.

**EN:** Experimental static recompilation project bringing classic *Call of Duty* PC 1.5 to Android. Requires your own compatible PC installation. **The repository and APKs do not include copyrighted game assets.**

**Estado / Status:** versión de prueba (pre-release). Menús y componentes están en pruebas; **todavía no se ha verificado que toda la campaña pueda completarse en dispositivos Android reales**.

**Punto de control técnico:** [Progreso consolidado, resultados reales y próximos bloqueos (2026-10-14)](docs/PROJECT_STATUS_CHECKPOINT_2026-10-14.md).

**Enlaces / Links:** [Descargar APK / Download](https://github.com/Dr3amyBerry/callofrecomp/releases/tag/v0.2.3) · [Empaquetador web / Packager](https://callofrecomp-packager.mauvezebra128.chatgpt.site) · [Estado técnico / Progress](PROGRESS.md) · [Investigación de rendimiento](docs/FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md) · [Panorámico y HUD](docs/HUD_WIDESCREEN_2026-10-14.md) · [Reportar errores / Issues](https://github.com/Dr3amyBerry/callofrecomp/issues)

**Call of Duty clásico para Android, mediante recompilación estática de la versión PC 1.5.**

Proyecto independiente en desarrollo, centrado en la campaña de un jugador.
Usa los menús y recursos de tu instalación de PC, con controles táctiles
[RetroTouch](https://github.com/Andiweli/RetroTouch), pantalla panorámica y un
límite de 60 FPS. Necesitas tu propia copia del juego.

[**Descargar APK**](https://github.com/Dr3amyBerry/callofrecomp/releases/tag/v0.2.3)
· [**ANGLE: descarga verificada y viabilidad GL4ES→Vulkan**](docs/ANGLE_GLES_VULKAN_FEASIBILITY_2026-10-14.md)
· [**Oráculo x86 independiente: 1.024 casos sobre 20 instrucciones reales**](docs/CPU_PHASE2_X86_PREFIX_ORACLE_2026-10-14.md)
· [**CPU ARM64: auditoría Fase 2 y prueba x87 sin cambio nativo**](docs/CPU_PHASE2_41B8F0_AUDIT_2026-10-14.md)
· [**ANGLE: prueba A/B/A real 3D Camp Toccoa (sin ganancia de FPS)**](docs/ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md)
· [**ANGLE: prueba real del menú del juego sobre Vulkan en WSA**](docs/ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md)
· [**ANGLE: compilación Android reproducible (solo manual)**](docs/ANGLE_BUILD_PIPELINE_2026-10-14.md)
· [**Investigación Mesa Zink y requisitos Android/WSA**](docs/MESA_ZINK_FEASIBILITY_2026-10-14.md)
· [**Vulkan: matrices y proyecciones OpenGL**](docs/WSA_GL_MATRIX_BRIDGE_2026-10-14.md)
· [**Vulkan: TexEnv y descarte alfa**](docs/WSA_VULKAN_TEXENV_ALPHA_2026-10-14.md)
· [**Captura OpenGL → estado Vulkan del juego real**](docs/GL_VK_STATE_BRIDGE_2026-10-14.md)
· [**Vulkan: profundidad, stencil y transparencia**](docs/WSA_VULKAN_DEPTH_STENCIL_BLEND_2026-10-14.md)
· [**Texturas y sampler Vulkan**](docs/WSA_VULKAN_TEXTURE_2026-10-14.md)
· [**Geometría y shaders Vulkan**](docs/WSA_VULKAN_INDEXED_MESH_2026-10-14.md)
· [**Preparar los archivos del juego**](https://callofrecomp-packager.mauvezebra128.chatgpt.site)
· [Benchmarks Vulkan/WSA](docs/WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md) · [Decisión Vulkan/DirectX 12 en WSA](docs/WSA_VULKAN_DX12_RENDERER_DECISION_2026-10-14.md) · [Estrategia de rendimiento actual](docs/PERFORMANCE_STRATEGY_CURRENT.md) · [Estado técnico](PROGRESS.md)

## Empezar en Android

1. Descarga `callofrecomp-arm64.apk` del release e instálalo en tu teléfono.
2. En tu PC, abre el [empaquetador web](https://callofrecomp-packager.mauvezebra128.chatgpt.site).
3. Selecciona la carpeta de tu instalación **Call of Duty 1.5** y crea el archivo `.codpack`.
4. Copia ese archivo al teléfono. Abre CallofRecomp y pulsa **Importar paquete .codpack**.
5. Espera a que termine la importación y pulsa **Jugar**. Empieza por el entrenamiento.

La web procesa los archivos **en tu navegador**: no los sube a ningún servidor.
Para instalaciones grandes, usa Chrome o Edge en PC; escriben el paquete por
bloques directamente en el disco. Otros navegadores tienen un límite de descarga
de 512 MiB. No cierres la pestaña mientras se prepara el archivo.

También puedes copiar la instalación al teléfono y usar **Elegir carpeta del juego**.
La carpeta seleccionada debe tener esta estructura:

```text
Call of Duty/
├── CoDSP.exe
├── gamex86.dll
├── cgamex86.dll
├── uix86.dll
└── main/
    └── *.pk3
```

Importa todos los PK3 de tu instalación, incluidos los del idioma y los parches.
Los cuatro binarios deben coincidir con la revisión 1.5 compatible; el empaquetador
y Android comprueban sus SHA-256. Otras revisiones, ejecutables modificados,
United Offensive y Call of Duty 2 no son compatibles con esta build.

## Requisitos y rendimiento

| Requisito | Estado |
| --- | --- |
| Android | 8.0 o posterior, API 26+ |
| Procesador | ARM64 de 64 bits; APK x86_64 separado para WSA |
| Gráficos | OpenGL ES 2.0 o posterior |
| RAM | Mínimo real pendiente de medir; 4 GB como punto de partida provisional |
| Almacenamiento | Espacio para el APK, el paquete y los archivos extraídos; una reinstalación conserva temporalmente los anteriores |
| FPS | Tope de 60; el rendimiento sostenido depende del dispositivo |

El lanzador permite elegir **Ligero** (hasta 960×540), **Equilibrado** (hasta
1280×720) y **Alta** (resolución nativa). Se respeta la proporción de la pantalla;
el escenario usa una cámara panorámica sin estirar una imagen 4:3. El cambio de
perfil se aplica al iniciar el juego. Para teléfonos modestos, comienza en Ligero.

Durante el arranque y la carga de misiones aparece un indicador de actividad
que cambia con las fases del motor. No representa un porcentaje medido.

La opción de ocultar los controles permite interactuar con el menú. Las partidas
y la configuración se guardan por separado de los recursos importados. Después
de una importación correcta puedes borrar el `.codpack` para recuperar espacio.

## Qué funciona y qué falta comprobar

- Menús originales, carga de mapas y controles táctiles integrados.
- En PC, el usuario confirmó movimiento y apuntado fluido tras las correcciones.
- En WSA con la build nativa x86_64, el usuario confirmó el menú original.
- Hay comprobaciones automáticas del motor, importación, controles y perfiles gráficos.
- El análisis estático cubre la cadena de 33 mapas; **eso no demuestra que todos los niveles puedan completarse**.
- La progresión completa del entrenamiento y de la campaña, guardado/carga durante las misiones y el rendimiento en teléfonos ARM64 reales necesitan pruebas de juego.

Esta es una **versión de prueba**. No se promete 60 FPS en todos los teléfonos ni
una campaña completamente verificada. Para informar de un problema, indica el
modelo, versión de Android, perfil gráfico y mapa; adjunta el texto de **Ver registro**.

## Archivos y privacidad

El repositorio, la web y los APK del release no contienen los ejecutables de PC,
DLL, PK3 ni recursos originales del juego. Cada usuario aporta su instalación.
El APK con recursos preimportados preparado para uso privado permanece local y
no forma parte de los releases.

El contenedor `.codpack` tiene comprobación CRC32, límites de tamaño y nombres
permitidos. Android extrae a una carpeta temporal y valida la instalación antes
de activarla. Un paquete inválido conserva la instalación anterior y las partidas.
Consulta la [especificación del formato](docs/PACKAGE_FORMAT.md).

## Desarrollo

El proyecto combina análisis de PE y recursos, traducción de p-code a C, una capa
de compatibilidad para las llamadas del binario y hosts nativos para PC/Android.
No se dispone del código fuente original de Call of Duty.

Los binarios y fuentes generadas de la recompilación son entradas/salidas locales
ignoradas por Git. Clonar el repositorio permite ejecutar las pruebas sintéticas;
**no basta por sí solo para construir el motor jugable**. La documentación de
[análisis y recompilación](docs/ANALYSIS_TOOLS.md) explica las herramientas y los
artefactos privados necesarios.

Pruebas del host:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

Prueba del empaquetador web (Node.js 20+):

```sh
node tests/test_game_package.mjs
```

Construcción Android, con las fuentes privadas ya generadas:

```sh
python tools/recomp/build_android.py --sdk /ruta/Android/Sdk --ndk /ruta/ndk --java /ruta/jdk --abi arm64-v8a
```

El builder fija las dependencias SDL2, gl4es y RetroTouch, comprueba la firma y la
alineación de las librerías nativas. La build actual usa una clave local de
desarrollo. La web está en `web/dist/`, no necesita dependencias ni backend y
puede servirse con `python -m http.server 8080 --directory web/dist`.

El mapa de carpetas, las referencias descargadas y el acceso al perfilador están
en [Entorno local de trabajo](docs/WORKSPACE.md).

Call of Duty y sus recursos pertenecen a sus respectivos titulares. Este proyecto
no está afiliado a Activision. Las licencias de las dependencias se incluyen en
el APK y se detallan en el [registro técnico](PROGRESS.md).
