# ANGLE Android x86_64 en CallofRecomp: ensayo real WSA (2026-10-14)

**Evolución:** este documento recoge el primer arranque de ANGLE; el ensayo posterior en **mundo 3D con A1/B/A2** está documentado en [ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md](ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md). No se observó una mejora reproducible de FPS.

**Estado comprobado:** ANGLE→Vulkan 1.3 carga dentro del **proceso real de CallofRecomp** en WSA, llega a `GameActivity` y dibuja el menú de Call of Duty. La configuración del driver se restauró íntegramente tras los ensayos. **NO** hay medición A/B/A de FPS, equivalencia cuantitativa de imágenes, ni test de Camp Toccoa 3D. El renderer de referencia sigue siendo **GL4ES nativo**.

## 1. Build upstream y artefacto (sin redistribuir APK en git)

- Workflow Linux manual exitoso: [GitHub Actions #38591658796](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38591658796), `build-angle` en **34m50s**.
- Fuente ANGLE fijada: `43140711d13063716fd32a15de829885d0bce469`, Git tree `06315a7275a6cc870b55e2e32c6eab165604357d`.
- `AngleLibraries.apk` Android **x86_64**, **8.162.364 bytes**; SHA-256 `40a48ae3cb3ee6051768c6b7f9d23fea3e3eeea7e1876e4d833c950ab275baa3` igual al `AngleLibraries.apk.sha256` archivado; artefacto y logs en `.local/profiles/angle-research/angle-ci-build/` (ignorado).
- La verificación independiente con Android SDK Build Tools detectó `org.chromium.angle`, `libEGL_angle.so` y `libGLESv2_angle.so` ELF x86_64 válidas y firma Android válida. **El certificado dice CN=Unknown**, hash de certificado SHA-256 `32a2fc74d731105859e5a85df16d95f102d85b22099b8064c5d8915c61dad1e0`. Es una APK experimental compilada desde el código upstream, NO un binario firmado por Google.

## 2. Protocolo y resultados reales

| Control | Evidencia | Resultado |
| --- | --- | --- |
| Preparación WSA | Android 33, ABI x86_64, `org.callofrecomp` depurable, juego detenido, sin ANGLE ni prefs previas | PASS |
| Primera entrada | `uiautomator` devuelve el botón `JUGAR` en mayúsculas; el localizador anterior buscaba `Jugar` exactamente | **Bloqueo de herramienta**, rollback limpio |
| Corrección UI | Búsqueda de botón insensible a mayúsculas, pero sigue exigiendo package/clase/enable/clickable/bounds | PASS |
| Segunda entrada | `GameActivity` reanudada; PID **9325**; Logcat del mismo proceso registra `ANGLE debug package enabled: org.chromium.angle` y `Renderer (Vulkan 1.3.0 (AMD Radeon(TM) Graphics))` | **ANGLE/Vulkan confirmado** por inspección de logs; corrección posterior del analizador |
| Tercera entrada | PID **9657**, `game_activity_resumed=true`, `android_angle_package_selected=true`, `angle_vulkan_renderer_reported=true`, `angle_vulkan_execution_verified=true` | **PASS** en el informe automático |
| Captura de menú | Pantalla real: logo, fondo, textos y opciones del menú visibles bajo ANGLE; comparación visual posterior con captura GL4ES nativa del mismo menú | **Sin diferencias evidentes al inspeccionar las capturas**, no comparación píxel por píxel |
| Rollback | `rollback_errors=[]`, `configuration_restored=true`, ANGLE desinstalado, cuatro settings `null`, biblioteca `libmain.so` original A1 con SHA-256 `403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde` | PASS |
| Gameplay real / FPS TECNO | No hay captura controlada de Camp Toccoa bajo ANGLE ni contadores de FPS | **NO MEDIDO** |

Los informes JSON privados de los ensayos son `angle-wsa-trial2.json` y `angle-wsa-trial3.json` bajo el directorio ignorado citado arriba. El segundo tuvo un **falso negativo de analizador**: esperaba `ANGLE package enabled`, mientras Android registró `ANGLE debug package enabled`; la regla ahora reconoce **ambas variantes** y el replay offline del JSON confirmó de nuevo PID, fecha y Vulkan.

## 3. Avisos de compilación GLSL: atribución preliminar

Durante las pruebas de ANGLE, en el PID del juego aparecen cuatro líneas `ANGLE Warn:Shader.cpp:767`: una sobre `textureCubeLod` y tres con `'#' : unexpected token`. Se investigó la copia local de **GL4ES**, commit `ec16bedd8819c475326f4f1a3063772c6d986e06`, fuente `build-android-deps/gl4es/src/glx/hardext.c`:

- `testTextureCubeLod()` compila expresamente un shader sintético con `textureCubeLod` para decidir una capacidad (invocación próxima a la línea 372).
- `testGLSL()` compila tres sondas de soporte `#version 120`, `#version 300 es` y `#version 310 es` (llamadas próximas a las líneas 447–451) y contiene directivas `#extension` del test.
- **La cantidad, momento de arranque y expresiones coinciden con estas cuatro sondas de GL4ES.** Son compatibles con fallos de capacidad esperados, pero sin trazas de pila no se atribuye cada línea de forma absoluta ni se declara toda la imagen 3D correcta. No se modificó GL4ES para ocultar errores.

## 4. Pendiente y decisión

1. Obtener screenshot o captura reproducible de **Camp Toccoa 3D** bajo ambos drivers, igual cámara/guardado, y comprobar HUD, modelos, texturas, transparencias, controles y estabilidad.
2. Medir A/B/A de la **misma escena** con contadores reales de CallofRecomp y tiempos de CPU/swap; diferenciar shader warmup de ejecución sostenida. No usar FPS del menú.
3. Si A/B/Wsa justifica más trabajo, evaluar separadamente una build ANGLE ARM64 en **TECNO CK6n**, siempre que el teléfono esté conectado y se verifiquen capacidades Vulkan/Mali.
4. Objetivo oficial: **60 FPS sostenidos TECNO**, referencia ~25 FPS; CPU `libmain.so` domina el perfil. ANGLE puede redistribuir costes pero no demuestra por sí solo reducir el cuello de CPU.
5. **Decisión: mantener GL4ES estable.** Hito de compatibilidad WSA logrado, rendimiento y campaña aún pendientes. Contador de intentos válidos bajo política TECNO: **0/5**.
