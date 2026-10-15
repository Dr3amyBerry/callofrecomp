# ANGLE/Vulkan frente a GL4ES: A1/B/A2 de gameplay 3D en WSA — 2026-10-14

**Estado:** ensayo real completado en la partida **Camp Toccoa**, usando el mismo guardado, cámara de aparición estática, calidad **Equilibrado**, límite normal del host a 60 FPS y pantalla WSA x86_64/AMD. **Resultado: no se demostró ganancia reproducible de FPS con ANGLE**; GL4ES permanece como backend estable.

El ensayo no representa una validación de 60 FPS ni una medida del TECNO CK6n ARM64/Mali. El contador formal de intentos válidos del teléfono continúa **0/5**.

## 1. Baselines y alcance de la prueba

- Juego: recompilación original de CoD 1.5 instalada en WSA, con biblioteca `libmain.so` de referencia SHA-256 `403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde`; **ninguna recompilación, cambio de APK del juego ni modificación de archivos comerciales**.
- **A1:** EGL/GLES nativo y GL4ES; **B:** GL4ES→GLES/EGL de ANGLE → Vulkan 1.3 AMD Radeon; **A2:** GL4ES restaurado.
- B utilizó el APK ANGLE x86_64 compilado desde upstream en [GitHub Actions #38591658796](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38591658796), hash `40a48ae3cb3ee6051768c6b7f9d23fea3e3eeea7e1876e4d833c950ab275baa3`.
- Guardados presentes: `quicksave.svg` (30.418 bytes) y `autosave/training.svg` (30.367 bytes); **respaldados localmente en carpeta ignorada de Git** y verificados por SHA-256 **antes y después** de las pruebas. El proceso de respaldo es de **solo lectura para el dispositivo** y no restablece archivos automáticamente.
- Se abrió el menú, se seleccionó **Continuar Partida**, se confirmó y se entró en la misión. El mismo spawn 3D mostró dos carteles, NPC, edificios, terreno, brújula y barra de vida. No se tomó una pantalla de menú o de carga como una medición de gameplay.
- Cada run capturó unos **30 segundos** de registros del proceso; se utilizaron las **últimas 20 ventanas de aproximadamente un segundo** y se descartaron cargas y CPU/frame sospechosamente bajos.
- B quedó **verificado antes y después** de la medición por selección del paquete `org.chromium.angle` y entrada `Renderer (Vulkan 1.3.0 (AMD Radeon(TM) Graphics))` del **PID 10539**. En ambos extremos coincidieron el backend y el PID; ni siquiera un Android setting por sí solo era suficiente para etiquetarlo Vulkan.

## 2. Resultados observados

| Métrica | A1: GL4ES | B: ANGLE/Vulkan | A2: GL4ES |
| --- | ---: | ---: | ---: |
| FPS mediana | **54,75** | **55,15** | **55,20** |
| FPS p10 de ventanas ~1 s | **50,20** | **47,60** | **54,60** |
| CPU/frame mediana | **17,54 ms** | **17,80 ms** | **17,43 ms** |
| Ventanas analizadas | 20 | 20 | 20 |
| Duración total captura | 30,03 s | 30,30 s | 30,16 s |
| Gráficos y spawn | visible | visible | visible |
| Driver esperado | GL4ES / GLES nativo | ANGLE sobre Vulkan confirmado | GL4ES / GLES nativo |

El promedio de las medianas A1/A2 es **54,975 FPS**; B difiere **+0,175 FPS**, aproximadamente **+0,318 %**, **dentro de la variación de las dos referencias A** (54,75–55,20). CPU/frame de B fue **+0,315 ms** respecto a la media de A1/A2. El p10 de B (**47,6**) fue inferior a ambos controles; además, el p10 de los controles varió de 50,2 a 54,6, por lo que se requieren más repeticiones antes de atribuir significación estadística. No inventar intervalos de confianza ni etiquetar ese p10 como percentil de frames individuales.

**Decisión:** ANGLE funciona en el mundo 3D, pero **no aporta aceleración demostrable** en esta escena de WSA y podría tener peor comportamiento de ventanas lentas. **No sustituir GL4ES de producción** ni consumir intento del plan de 5 experimentos TECNO.

## 3. Evidencia visual y sus límites

Se conservaron **tres capturas PNG privadas**, nunca incluidas en Git. En una región 3D del mundo de **1.280×540 píxeles** (x160..1439, y105..644), la imagen GL4ES A1 y la imagen ANGLE B obtuvieron:

- **SSIM = 0,995943** (escala 0 a 1).
- Error absoluto medio RGB ≈ **0,337** valores de canal.
- **0,078 %** de píxeles de esa región con al menos un canal que difiere más de 32 valores.

Es una comparación de capturas *no sincronizadas*; NPC, cámara, animaciones y tiempo de presentación pueden diferir. La concordancia visual es una señal favorable en ese spawn, **no una prueba de equivalencia de todos los shaders, transparencias, controles o la campaña completa**.

## 4. Verificaciones de reversibilidad

- B: `angle_wsa_trial.py` terminó con `rollback_errors=[]` y `configuration_restored=true`; ANGLE quedó **desinstalado**, sin sobreescribir ninguna aplicación.
- A2: comprobada la ausencia de ANGLE y los cuatro settings Android en `null` antes de capturar. El juego fue detenido al finalizar.
- Chequeo final: ambos archivos de guardado SHA-256 idénticos al backup privado y binario `libmain.so` instalado idéntico al APK A1.
- Las únicas modificaciones del repositorio asociadas al bloque son herramientas de diagnóstico, protección de guardados, sus pruebas y documentación; el juego estable no recibió código de producción nuevo.

## 5. Herramientas reproducibles (artefactos privados, no comerciales)

- `tools/recomp/diagnostics/wsa_save_guard.py`: `backup` y `verify` sin escritura al dispositivo, rechaza rutas fuera de `.local/profiles/` y nunca sobrescribe un backup existente.
- `tools/recomp/diagnostics/capture_wsa_game_frames.py`: `--backend gl4es|angle` con comprobación de ajustes, paquete ANGLE y Logcat Vulkan por PID; rechaza cambio de PID, ventanas de menú/carga y etiqueta falsa ANGLE.
- `tools/recomp/diagnostics/summarize_wsa_driver_ab.py`: compara A1/B/A2 y rechaza diferencias de escena/perfil, warmup evidente, FPS cap, ausencia de Vulkan o controles configurados incorrectamente.
- Los logs `ab3d-gl4es-A1.json`, `ab3d-angle-B.json`, `ab3d-gl4es-A2.json`, imágenes, perfiles y summary permanecen bajo `.local/profiles/angle-research/` fuera de Git. La captura A1 es anterior al parámetro nuevo `--backend`; su identidad GL4ES está documentada por estado limpio de WSA, ruta del controlador y metadatos originales, mientras A2 y B tienen verificación automática completa.

## 6. Siguiente prioridad

El backend Vulkan propio sigue incompleto y la evaluación de Zink sigue desfavorable en WSA. Con ausencia de una ganancia de ANGLE, priorizar la estrategia vigente de optimización **CPU ARM64**: análisis aislado de la función caliente CoDSP `0x0041B8F0`, equivalencia de registros/EFLAGS/x87/memoria y revisión del AArch64 realmente generado, sin activar fast paths hasta probarlos en el **TECNO físico** con A/B/A/B/A. Cuando se disponga de hardware, medir de nuevo GPU Mali con los permisos disponibles y no extrapolar desde WSA.

**Referencias:** [estrategia vigente](../../PERFORMANCE_STRATEGY_CURRENT.md), [ejecución ANGLE inicial](ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md), [punto de control anterior](../../history/checkpoints/PROJECT_STATUS_CHECKPOINT_2026-10-14.md).
