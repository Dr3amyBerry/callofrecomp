# ANGLE: viabilidad GLES a Vulkan en CallofRecomp (14 de octubre de 2026)

**Estado:** fuente oficial descargada, identidad Git verificada y entorno Android/WSA auditado. **NO se ha compilado ni ejecutado ANGLE, ni se ha reemplazado GL4ES.** No se han repetido benchmarks del juego. Estrategia de rendimiento intacta: **0/5 intentos fallidos**.

## 1. Fuente descargada e integridad

| Dato | Verificación |
| --- | --- |
| Proyecto | ANGLE, implementación de OpenGL ES y EGL que puede usar Vulkan |
| Repositorio oficial | https://chromium.googlesource.com/angle/angle.git |
| Espejo Google GitHub | https://github.com/google/angle |
| Checkout | clone --depth 1 desde main; snapshot fijado por hash |
| Commit completo | **43140711d13063716fd32a15de829885d0bce469** |
| Árbol Git | 06315a7275a6cc870b55e2e32c6eab165604357d |
| Integridad | git fsck --full --no-reflogs **PASS**; working tree limpio |
| Coincidencia remota | Los dos remotos devolvieron el mismo commit para main |
| Ruta privada en Windows | .local/profiles/angle-research/angle-src/ |
| Registro JSON local | .local/profiles/angle-research/angle-readiness-wsa.json |

Se inspeccionaron los archivos DEPS, README.md, doc/DevSetupAndroid.md, doc/DevSetup.md, extensions/EGL_ANGLE_platform_angle_vulkan.txt y src/libANGLE/renderer/vulkan/DisplayVk.cpp. La extensión EGL documenta la selección explícita del backend Vulkan por EGL_PLATFORM_ANGLE_TYPE_VULKAN_ANGLE.

**Límite:** el clon contiene fuentes Git, NO un paquete Android ya construido ni todas las dependencias externas de Chromium. Falta ejecutar gclient sync. Se verificaron identidad/objetos del commit frente a repositorios oficiales, NO una firma de un APK inexistente. Todo el checkout está ignorado por Git y no se subirá al repositorio CallofRecomp.

Fuentes: https://chromium.googlesource.com/angle/angle/+/43140711d13063716fd32a15de829885d0bce469/doc/DevSetupAndroid.md y https://chromium.googlesource.com/angle/angle/+/43140711d13063716fd32a15de829885d0bce469/doc/DevSetup.md .

## 2. Encaje técnico con nuestro motor

Ruta actual:

    CoD 1.5 recompilado → gl_thunks (OpenGL clásico) → GL4ES → SDL2 GLES2/EGL → driver Android

Ruta ANGLE candidata:

    CoD 1.5 recompilado → gl_thunks → GL4ES → SDL2 GLES2/EGL de ANGLE → Vulkan → GPU

ANGLE implementa **OpenGL ES**, precisamente la API que GL4ES produce. En un ensayo depurable de Android podría reemplazarse el driver GLES a nivel de aplicación SIN reescribir inmediatamente 486 wrappers, ni las matrices/texture combiners clásicas de Call of Duty. En cambio Mesa Zink es un backend OpenGL de escritorio basado en Gallium y requiere una integración distinta de EGL/Mesa.

**No asumir rendimiento superior:** GL4ES→ANGLE añade una segunda traducción; podría reducir tiempo del driver o aumentar trabajo de CPU. Las incompatibilidades de Zink comprobadas en WSA no se pueden transferir sin más a ANGLE: sus requisitos son diferentes y únicamente una ANGLE build funcionando puede confirmarlos.

El juego usa una GameActivity Java basada en SDLActivity, y android/AndroidManifest.xml configura la app de desarrollo como depurable. Esto satisface dos requisitos de la guía ANGLE para su driver de desarrollo por aplicación. No constituye una solución distribuible para APKs release sin debug.

## 3. Auditoría de solo lectura del WSA actual

Herramienta reproducible: tools/recomp/diagnostics/angle_readiness.py. No modifica ajustes, instala APKs, ejecuta aplicaciones ni cambia drivers.

| Componente | Hallazgo real |
| --- | --- |
| Dispositivo | WSA Android API **33**, ABI **x86_64** |
| GPU, según diagnóstico Vulkan previo | AMD Radeon Graphics, Vulkan **1.3**, sin prueba ANGLE |
| CallofRecomp instalado | org.callofrecomp, DEBUGGABLE=true |
| Actividad Java | LauncherActivity inicia GameActivity (SDLActivity) |
| Paquete ANGLE de Google | **No instalado**: org.chromium.angle ausente |
| ANGLE de Android GPU Inspector | **No instalado**: org.chromium.angle.agi ausente |
| Selección angle_debug_package | null |
| Selección angle_gl_driver_selection_pkgs/values | null / null |
| Opción angle_gl_driver_all_angle | null |
| Herramientas GN, gclient y autoninja | **Ausentes** |
| Ninja de host | **Presente** |
| Distribución Linux bajo WSL | **Ausente** |
| Subdependencias de fuente ANGLE | Sin sincronizar |
| AngleLibraries.apk para WSA x86_64 | **No creado ni probado** |
| ANGLE activo, backend Vulkan y FPS del juego | **Sin comprobar** |

**Resultado:** es razonable probar ANGLE con esta app depurable en WSA **después** de conseguir una compilación verificable para x86_64. No sería honesto afirmar que ya funciona o que mejorará 55 FPS a 120 FPS.

La guía oficial fija Android 10+ para el paquete ANGLE de prueba, exige apps debuggable o root, y pide iniciar la aplicación mediante una Activity Java; esos requisitos del proyecto se cumplen. Pero **los binarios ANGLE faltan**.

**Actualización posterior:** se preparó un script reproducible de compilación Linux, un workflow manual y un verificador offline de APK/ABI/firma. Son herramientas preparatorias, no un APK compilado ni un cambio de rendimiento. Ver [proceso y bloqueos](ANGLE_BUILD_PIPELINE_2026-10-14.md).

## 4. Bloqueo para compilar y plan de validación

La versión de doc/DevSetupAndroid.md incluida en el commit fijado indica expresamente que **compilar ANGLE para Android requiere Linux**. El nodo disponible es Windows y wsl.exe NO tiene una distribución Linux instalada. La guía también requiere depot_tools, gclient, GN, Ninja y descargar dependencias de Chromium. No se instaló una distro/IDE sin autorización, ni se simuló que ANGLE se hubiera compilado correctamente.

Procedimiento futuro cuando exista Linux de desarrollo:

1. Preparar depot_tools y usar fetch angle; fijar el checkout al commit 43140711d13063716fd32a15de829885d0bce469.
2. Incluir Android en target_os de .gclient y ejecutar gclient sync. Reproducir también los commits de dependencias de ese snapshot.
3. Generar un build GN de Android (target_os=android, angle_enable_vulkan=true, is_component_build=false, is_debug=false, use_remoteexec=false). Para WSA experimentar con target_cpu=x64 y **verificar que GN lo acepta**; para el TECNO ARM64 usar target_cpu=arm64 y otra APK.
4. Compilar el target angle_apks mediante autoninja. Comprobar procedencia, firma y bibliotecas x86_64 del resultado AngleLibraries.apk **antes de instalarlo**.
5. Preservar los ajustes Android vigentes, instalar SOLO el paquete ANGLE de prueba verificado y activar ANGLE únicamente para org.callofrecomp, sin habilitarlo globalmente. Restaurar los ajustes después.

La documentación oficial propone estos comandos ADB **para una prueba futura, no ejecutada en esta investigación**:

    adb install -r -d --force-queryable AngleLibraries.apk
    adb shell settings put global angle_debug_package org.chromium.angle
    adb shell settings put global angle_gl_driver_selection_pkgs org.callofrecomp
    adb shell settings put global angle_gl_driver_selection_values angle

Al iniciar la Activity, verificar **en Logcat** tanto que Android selecciona ANGLE como que ANGLE reporta **Renderer (Vulkan ...)**. Un valor en settings no demuestra que se haya cargado el backend correcto. Restaurar los settings al terminar (en este WSA originalmente todos eran null, así que se pueden eliminar con settings delete global). No dejar cambios globales persistentes.

**Solo tras esa validación:** comparar gameplay real A/B/A en el entrenamiento de Camp Toccoa, misma escena, mismas opciones, resolución y frame pacing. El juego tiene límite de 60 FPS; cualquier ensayo sin cap debe ser diagnóstico y aplicarse igualmente a ambas variantes. Evitar comparar FPS de demos Vulkan con FPS de CallofRecomp.

## 5. Evidencia reproducible y seguridad

- El clon Git pasó fsck, está limpio y su hash coincide con los dos remotos oficiales.
- El auditor angle_readiness.py comprueba source/docs, hashes Git, SDK, ABI, actividad Java, flag DEBUGGABLE, paquetes ANGLE, settings y dependencias de host, sin mutar el dispositivo.
- tests/test_angle_readiness.py comprueba con escenarios sintéticos que una selección de ANGLE **no se presenta como Vulkan ejecutado**, que se rechazan Android demasiado antiguo, paquetes faltantes, apps no depurables y settings inconsistentes.
- La APK original instalada de CallofRecomp conservó exactamente la libmain.so de referencia A1, SHA-256 **403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde**.
- No se repitieron pruebas antiguas ni se compilaron aplicaciones Android nuevas.

## Validación final

- Checkout oficial ANGLE: ambos remotos concordantes en el commit `43140711d13063716fd32a15de829885d0bce469`; `git fsck --full --no-reflogs` PASS y árbol limpio. Ningún archivo externo dentro del commit CallofRecomp.
- Auditor WSA `angle_readiness.py` ejecutado: Android API33 x86_64, app DEBUGGABLE iniciada mediante SDLActivity, sin paquete ANGLE; GN, gclient y autoninja ausentes; sin distro Linux WSL. JSON de evidencia privado.
- **8/8 tests específicos del auditor** correctos; **153 tests Python del proyecto (4 omitidos)** correctos; **33/33 CTest** correctos.
- Verificador de estrategia de rendimiento y enlaces internos Markdown: PASS; `git diff --check` PASS.
- Referencia instalada `libmain.so`: SHA-256 original `403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde`, **idéntico** entre APK A1 y dispositivo. Ningún benchmark de gameplay repetido.
- **No se instalaron drivers, sistemas Linux, paquetes ANGLE ni APK nuevas** y no se modificaron preferencias de Android. **0/5** intentos formales.

## Decisión

**Priorizar ANGLE como el siguiente candidato existente** para probar GLES2→Vulkan por ser menos invasivo que integrar Mesa Zink. **Todavía no viable para A/B**: antes falta disponer de Linux, dependencias de Chromium y un APK ANGLE auténtico con ABI compatible (o acceder a una build oficial ya verificable).

Hasta entonces: mantener GL4ES de producción, mantener el prototipo Vulkan en modo experimental y continuar la estrategia CPU original cuando se investigue rendimiento del teléfono. **0/5 intentos formales consumidos**.

## Fuentes oficiales

- https://chromium.googlesource.com/angle/angle/
- https://chromium.googlesource.com/angle/angle/+/43140711d13063716fd32a15de829885d0bce469/doc/DevSetupAndroid.md
- https://chromium.googlesource.com/angle/angle/+/43140711d13063716fd32a15de829885d0bce469/doc/DevSetup.md
- https://chromium.googlesource.com/angle/angle/+/43140711d13063716fd32a15de829885d0bce469/extensions/EGL_ANGLE_platform_angle_vulkan.txt
