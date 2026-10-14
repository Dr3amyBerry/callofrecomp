# Estado consolidado y continuación — CallofRecomp (2026-10-14)

**Avance posterior de fase 2:** [auditoría `0x0041B8F0` y laboratorio de copias x87](CPU_PHASE2_41B8F0_AUDIT_2026-10-14.md). La función quedó delimitada, pero sustituir `rd/wr` por `memcpy` no redujo las instrucciones ARM64 en el experimento aislado. No se aceptó optimización ni se probó hardware TECNO.

**Hito posterior completado:** [A1/B/A2 de Camp Toccoa con GL4ES y ANGLE/Vulkan](ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md). Los 54,75 / 55,15 / 55,20 FPS medianos demuestran compatibilidad 3D básica, no una aceleración. WSA y guardados restaurados; próxima prioridad CPU ARM64.

**Punto de control verificado en `main`:** `1906ace6a75fb836ff58775fc4ef1dfdf6742ed6` al comenzar este bloque. Entorno: DESKTOP-O3DC9UA / workspace `callofrecomp`; única conexión ADB: WSA `127.0.0.1:58526`, Android 33, x86_64. Teléfono físico TECNO CK6n **no conectado**. Los registros de desarrollo y ensayos anteriores no demuestran FPS nuevos en ARM64.

## Meta y referencia que NO cambian

- **60 FPS sostenidos** en el spawn de entrenamiento **Camp Toccoa** del TECNO CK6n ARM64, perfil **Equilibrado**, sin reducir calidad, romper HUD panorámico, controles, colisiones, audio ni guardados.
- Referencia histórica del TECNO: **24,70 FPS mediana**, **23,30 FPS p10** de ventanas de aproximadamente 1 segundo; **38,895 ms CPU/frame mediana** en escena estática de la partida. No son cifras WSA ni nuevas mediciones.
- Presupuesto a 60 FPS = **16,67 ms/frame**. Falta reducir aproximadamente **22,23 ms de CPU/frame** frente a esa referencia, sin presuponer tiempo libre de GPU.
- La regla formal de intentos fallidos validados en TECNO está en **0/5**. Ninguna prueba de compatibilidad WSA consume un intento.
- Mantener el renderer GL4ES/GLES2 de producción como **A estable**. GPU ARM64/Mali, tiempos reales GPU y nuevo A/B físico siguen pendientes. [Política](PERFORMANCE_STRATEGY_CURRENT.md).

## Componentes comprobados

| Bloque | Qué funciona / qué se midió | Estado pendiente |
| --- | --- | --- |
| Recompilación x86→Android | CoD 1.5 single player arranca en Android; APK de referencia GL4ES preservada; rutas de menús, interacción y guardados son objetivos esenciales | La campaña completa y todas las escenas no están verificadas |
| Perfilado CPU TECNO | Simpleperf de dos capturas (~7.953 y 6.541 muestras); `libmain.so` ~83,93 % de muestras del proceso en A1; funciones geométricas/visibilidad más calientes incluidas `0x0041B8F0` (270 muestras A1) | Fase 2: optimización estructural acotada con oráculo y código ARM64 comparado, luego A/B físico |
| GPU Mali | Permisos no permiten leer frecuencias o contadores hardware completos; GPU time no medido | Obtener perfil GPU válido si el dispositivo/permissions lo permiten |
| Vulkan propio | Prototipo separado en WSA: WSI, swapchain, indexed draws, RGBA8/sampler, depth/stencil, alpha, matrices, proyecciones y subconjunto TexEnv | **No es renderer completo del juego**; captura de 164 estados reales, **0/164 equivalentes** en el subconjunto actual |
| Mesa Zink | Fuente Mesa 26.2.4 inspeccionada; cuatro requisitos del perfil Zink no presentes en Vulkan WSA | No integrar Zink para este WSA sin resolver capacidades y contexto |
| Google ANGLE | **ANGLE x86_64 compilado en GitHub Actions** (34m50s), APK verificable, seleccionado exclusivamente para CallofRecomp en WSA; `GameActivity` y `Renderer (Vulkan 1.3 AMD)` en mismo PID | Equivalencia del juego 3D y FPS comparables sin comprobar; Android ARM64 no construido |
| Pantalla del juego con ANGLE | Menú original visible y sin diferencias evidentes frente a captura GL4ES nativa; no pixel-diff | Captura y validación de **Camp Toccoa** con guardado/cámara repetibles |
| Regresión | En el bloque ANGLE `188` tests Python, `4` omitidos; `33/33` CTest; GitHub CI del commit `1906ace` **success** | Continuar exigiendo regresión completa por cada cambio |

## Evidencia de la build ANGLE y del ensayo real

- Fuente oficial fijada: commit `43140711d13063716fd32a15de829885d0bce469`; árbol `06315a7275a6cc870b55e2e32c6eab165604357d`.
- Build manual exitosa: [GitHub Actions #38591658796](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38591658796); artifact `angle-x86_64-43140711-experimental`, `AngleLibraries.apk` de **8.162.364 bytes**, SHA-256 `40a48ae3cb3ee6051768c6b7f9d23fea3e3eeea7e1876e4d833c950ab275baa3`.
- Paquete `org.chromium.angle`; ELF x86_64 de EGL y GLESv2, firma Android verificada. Certificado **CN=Unknown**: no atribuir firma a Google.
- Tres ensayos temporales WSA: el primero detuvo el clic porque `uiautomator` decía `JUGAR`, en lugar de `Jugar`; la comparación casefold corrigió el problema. En dos ejecuciones posteriores, los PID **9325** y **9657** emitieron selección `ANGLE debug package enabled` y `Renderer (Vulkan 1.3.0 (AMD Radeon Graphics))`; el tercero reportó `angle_vulkan_execution_verified=true`.
- Herramientas preparadas: `verify_angle_apk.py`, `angle_wsa_trial.py` (solo lectura por defecto), `angle_wsa_launcher.py` (clic optativo y verificado), Bash de build y workflow manual. Logcat ligado a hora de Android y PID, sin aceptar registros antiguos.
- Tras ensayos: ANGLE desinstalado, `angle_*` globales en `null`; APK del juego A1 intacta, hash de `libmain.so` **`403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde`**. Artefactos APK, logs, binarios recompilados y datos comerciales permanecen fuera de Git.
- Cuatro advertencias de shader coinciden con pruebas de capacidad internas de GL4ES (`testTextureCubeLod` y `testGLSL`), sin atribución absoluta. **No eliminar warnings sin inspección**. [Informe ampliado](ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md).

## Advertencias para interpretar progreso

La cadena probada es **OpenGL heredado del juego → GL4ES → GLES2/EGL vía ANGLE → Vulkan WSA/AMD**. Es una forma experimental de usar Vulkan, **no** demostrar que nuestro traductor Vulkan propio esté completo ni que el teléfono Mali sea más rápido. Los ~75 FPS FIFO del prototipo aislado Vulkan no son FPS de CoD. Una pantalla de menú bajo ANGLE tampoco equivale a renderizar una partida 3D de forma correcta.

## Próximo bloque de trabajo (orden)

1. **Escena 3D reproducible WSA:** revisar de modo no destructivo el estado de la partida instalada y la forma de entrar a Camp Toccoa; no sobrescribir guardados ni cambiar la configuración estable. Capturar los estados del juego con GL4ES y ANGLE.
2. **Verificación visual funcional:** misma cámara/escena, HUD panorámico, materiales, transparencias, texto, NPC, estabilidad; contrastar también logs y frametimes. Distinguir espera/carga de shader warmup.
3. **A/B/A en WSA:** únicamente si existe una escena idéntica y un muestreo confiable. Los resultados serán **exploratorios de WSA x86_64**, no de TECNO. Documentar si no se puede hacer.
4. **Rendimiento principal TECNO:** al conectar el teléfono, retomar optimización de la función geométrica `0x0041B8F0` con diffs de ARM64 y equivalencia completa; controlar CPU/GPU, temperatura y FPS según [la política](PERFORMANCE_STRATEGY_CURRENT.md).
5. **Cierre de cada fase:** escribir resultados verificables en `PROGRESS.md`, `ROADMAP.md` y documento técnico correspondiente; probar, publicar en `main` sin ramas adicionales y dejar dispositivo/driver estables.
