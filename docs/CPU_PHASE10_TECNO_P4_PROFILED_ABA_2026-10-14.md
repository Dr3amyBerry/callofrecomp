# Fase 10 — Validación física A/B/A de la conversión x87 perfilada de p4

**Fecha local:** 2026-10-14 (capturas entre 01:49 y 02:05 UTC del 15 de octubre).
**Dispositivo:** TECNO CK6n, Android ARM64 físico. **Objetivo:** Call of Duty 1.5, Camp Toccoa, punto de entrenamiento con cámara fija y calidad *Equilibrado*; alcanzar 60 FPS sostenidos sin recortes visuales ni funcionales.

**Decisión: NO aprobar la optimización experimental de la fase 8.** La variante B se pudo ejecutar en el juego real, pero el cambio de FPS/CPU es demasiado pequeño para atribuirlo a la optimización. El teléfono y el autoguardado fueron restaurados y verificados.

## Controles previos

La prueba se autorizó explícitamente después de las fases 5–9 realizadas sin usar el teléfono. Se seleccionó únicamente el dispositivo físico con identificador ADB específico, **nunca WSA**, y se archivó la APK original instalada antes de sustituirla.

- Referencia A: APK arm64 local de fase 6 sin extensión p4 (`phase6_p4_f2d/A_original.apk`), SHA-256 `cbb155170a3b64f9baf8eb06aff912cd3b27dc2eef42e4d54bba3f51d1c0597a`; conserva el fast path x87 previo de p1/p8.
- Candidata B: APK optativa de fase 8 con `--x87-normal-f2d-p4-profiled`, SHA-256 `dc79bbfc0c6c9711ada54cf4e6b53270b643a5e8eeea4c73513067b0bb712c53`.
- Se comparó el SHA-256 de cada recurso y clase del APK. **El único fichero de contenido que cambia entre A/B es `lib/arm64-v8a/libmain.so`**; no se modificaron texturas, modelos, NPC, efectos, HUD, geometría, distancia de dibujado ni recursos.
- Se respaldó el autoguardado `files/profile/main/save/autosave/training.svg`, **30.360 bytes**, SHA-256 `efbc68e54fabc79946dfd3a9d188e5f6ba284b1aad99130bbe2726eb637f64f8`. Todas las capturas verificaron que permaneció inalterado. Solo se usó `adb install -r`; nunca `pm clear`, borrado de datos, ni modificación del save.
- Se verificó el hash completo de cada APK **extraída de su instalación física** y su `libmain.so`, antes de iniciar la captura correspondiente.

## Procedimiento y resultados

Para cada ejecución se inició la misma partida guardada, se confirmó la carga real (`G_loadGame` y `CL_InitCGame`), se accedió a Camp Toccoa con la cámara inmóvil y se esperaron ventanas de actividad 3D real. Captura de **55 segundos por ejecución**, estadísticas sobre las **últimas 40 ventanas de aproximadamente un segundo**; se descartan carga, menú y briefing. Los procesos conservaron PID durante cada medición y se verificó el autoguardado sin diferencias.

| Ejecución | FPS mediana | FPS p10 de ventanas | CPU mediana ms/fotograma | Swap mediana ms | Temperatura de batería |
| --- | ---: | ---: | ---: | ---: | ---: |
| **A1**, referencia | **26,00** | 24,70 | **37,100** | 1,955 | 36 °C |
| **B2**, conversor x87 perfilado | **26,05** | 25,10 | **36,980** | 1,950 | 37 °C |
| **A2**, regreso a referencia | **25,90** | 24,60 | **37,145** | 1,960 | 38 °C |

Promedio de las dos medianas A: **25,95 FPS** y **37,1225 ms CPU/fotograma**. La candidata B presenta solo **+0,10 FPS (≈0,39 %) y −0,1425 ms CPU/fotograma (≈0,38 %)** con respecto a ese control, valores muy cercanos a la variación de medición y **no suficientemente grandes ni repetidos para demostrar causalidad**. El p10 de FPS se calcula sobre **medias de ventanas**, NO es un *1 % low* ni un percentil calculado fotograma por fotograma. Las ventanas consecutivas no son muestras independientes para una prueba estadística automática.

Se registró la temperatura de **batería**, no de los núcleos CPU/GPU. Las temperaturas 36/37/38 °C indican una deriva pequeña en batería, pero no permiten descartar cambios de frecuencia, scheduler, térmica interna, movimiento de NPC o variabilidad de carga entre escenas. Se conservó el mismo modo de calidad; sin reducción de resolución.

### Integridad visual

Se archivó una captura PNG del juego real en cada pasada. Las tres imágenes tienen **2400 × 1080** píxeles y muestran el mismo encuadre, escenario 3D, edificios, vegetación, soldados, carteles, brújula y HUD, sin elementos eliminados. La comparación de canales RGB entre A1/B2 da una diferencia media absoluta de solo **0,000434 niveles por canal**, con **0,04977 % de píxeles distintos**; entre las dos referencias A1/A2 cambia **0,05247 %**. Las imágenes **no son idénticas píxel a píxel**: pequeñas variaciones dinámicas y del HUD siguen siendo posibles. La comparación visual no sustituye una auditoría de todo el juego.

### Ensayos de navegación no válidos

El intento inicial **B1** solo llegó al menú porque los toques automatizados no sincronizaron correctamente el diálogo de confirmación; no hubo `G_loadGame` ni captura estable 3D, por lo que **no se le atribuyen FPS**. En una repetición visual, la confirmación `Sí` inició `G_loadGame` cerca del límite de espera y la automatización volvió a salir sin una medición de gameplay. No se encontró evidencia de un fallo fatal del renderizador en esos dos intentos.

Se corrigió la navegación de **B2**: esperar a que el diálogo esté preparado, confirmar `Sí`, exigir los marcadores `G_loadGame` y `CL_InitCGame`, y luego cinco ventanas consecutivas de carga CPU 3D antes de medir. **B2 cargó y se midió correctamente**. El intento fallido de automatización no debe interpretarse como regresión de la candidata.

## Restauración y estado final del teléfono

Tras A2, el controlador restauró **exactamente la APK que estaba instalada antes de todo el experimento**, distinta de la referencia A reconstruida localmente:

- APK original restaurada: SHA-256 `efaa575fffb223d47cc824e56f9fe0219c076ff0d55d9a9ed5e2632fe3e7243e`.
- Biblioteca `libmain.so` original restaurada: SHA-256 `6729aef7de75203ab2970adc9654d6aaf7e1fdef1299ad75ca3f037bc4585fb2`.
- Guardado original: SHA-256 `efbc68e54fabc79946dfd3a9d188e5f6ba284b1aad99130bbe2726eb637f64f8`, sin cambios, 30.360 bytes.
- Batería final: **60 %**, **38 °C**. Aplicación detenida y sin APK experimental instalada.

Evidencias privadas e ignoradas por Git bajo `.local/profiles/tecno_phase8_20261014/`: `preflight.json`, APK original, copias de guardado, `A1/B2/A2/stats.json`, ventanas `frames.log`, verificaciones de cada APK instalada, imágenes reales, diferencia visual, diagnósticos del menú y `final_restoration_retry.json`. **No publicar APK comerciales, guardados, registros privados, identificadores completos del dispositivo ni capturas privadas.**

## Conclusión para optimizaciones siguientes

**Conservar `CODRECOMP_X87_NORMAL_F2D_P4_PROFILED=OFF`.** La reducción del incremento de `.text` de fase 8 fue real en código nativo, pero **no se tradujo en un ahorro de CPU/frame significativo en el dispositivo físico**. La referencia sigue alrededor de 26 FPS, lejos de 60.

La prioridad pasa a buscar costes transversales de mayor magnitud: lecturas/escrituras `rd`/`wr`, copias `memcpy` inline y recomposición de estado, apoyándose en perfiles Simpleperf reales, pruebas diferenciales y A/B/A físico. No realizar optimizaciones a costa de geometría, personajes, textura, efectos, resolución, comportamiento del juego o precisión x87.
