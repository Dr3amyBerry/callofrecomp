# TECNO CK6n: revalidación física de 0.2.4

**Resultado:** regresión de rendimiento frente a la APK experimental que estaba instalada. No se alcanzan 60 FPS. Comparación de APK completas, no aislamiento causal de normal-f2d ni de una única optimización.

## Identidad y procedimiento

- Dispositivo físico TECNO CK6n, ARM64; serie ADB comprobada al comenzar. WSA no interviene.
- A: instalación previa, versión 0.2.3, candidata histórica `--hot-x87-transform --x87-normal-f2d`. APK SHA256 `efaa575fffb223d47cc824e56f9fe0219c076ff0d55d9a9ed5e2632fe3e7243e`; libmain SHA256 `6729aef7de75203ab2970adc9654d6aaf7e1fdef1299ad75ca3f037bc4585fb2`.
- B: ARM64 pública 0.2.4, código `f493638`, normal-f2d y retirada del transform double bloqueado. APK SHA256 `fb8647c34dfe8fd269c0902f34edcc4c0844b18c6aa13ff6006232678da25f70`; libmain SHA256 `17e2f2ce4d0bc001375ad4619a2bd7ce29071317a4d3aa2805bf80edfc033b55`.
- Equilibrado, 1280×576, límite 60; mismo autosave de entrenamiento y cámara fija. Cada pasada recoge 55 segundos y analiza las últimas 40 ventanas nuevas del motor. PID estable y sin rotación de log durante cada captura.
- Orden A1/B1/A2/B2, actualización con `install -r` y downgrade de referencia con `-d`, sin desinstalar ni borrar datos. Hash del APK instalado comprobado tras cada cambio. Respaldo previo de APK, configuración y partida; hash de partida verificado en cada pasada.
- Se reutilizaron el analizador canónico y el procedimiento histórico. El script de sesión corrige la espera prematura: exige inicialización completa y cinco ventanas estables de menú antes de navegar. Las primeras capturas de diagnóstico fueron excesivas; A2/B2 usaron navegación por logs. Se guardó una captura de escena por pasada, sin abrir manualmente las posteriores. Suelo y cielo de A1/B1/A2/B2 coinciden exactamente en las dos regiones estáticas comparadas por script; esto comprueba encuadre parcial, no equivalencia visual completa.

## Medidas

| Pasada | FPS mediana | p10 de ventanas FPS | CPU mediana ms/frame | Batería °C antes/después |
| --- | ---: | ---: | ---: | --- |
| A1 | 26,05 | 25,4 | 37,115 | 38 / 38 |
| B1 | 22,15 | 21,6 | 43,450 | 39 / 40 |
| A2 | 25,90 | 25,4 | 37,175 | 40 / 41 |
| B2 | 21,90 | 20,5 | 43,910 | 41 / 41 |

Media de las dos medianas: **25,975 → 22,025 FPS (−15,21 %)**; CPU **37,145 → 43,680 ms/frame (+17,59 %)**. La referencia A2 recupera su rendimiento pese a estar más caliente que B1. La pérdida se repite, aunque no hubo control de frecuencia/temperatura de CPU ni aislamiento de cambios. USB conectado y batería al 97 % durante las cuatro capturas.

Son FPS de motor y CPU/frame de sus resúmenes; p10 corresponde a ventanas de aproximadamente un segundo, **no** a percentiles por frame. No se midieron GPU, presentación SurfaceFlinger, combate ni estabilidad prolongada.

## Decisión y siguiente paso

0.2.4 queda instalada y las partidas intactas. A se conserva como referencia privada y no se restaura como recomendación: contiene el transform double bloqueado por diferencias frente a x86. Esta comparación no justifica reactivarlo. La región x87 nativa y el enlace local de WSA requieren x86_64; no están presentes en esta APK ARM64.

Siguiente cuello de botella: perfilar el ELF ARM64 **actual**, separar el coste de retirar el transform inseguro de los demás cambios y diseñar una alternativa correcta antes de otro A/B. No atribuir el −15,21 % a normal-f2d aislado ni extrapolar las mejoras WSA.

Evidencia privada y script reproducible: `.local/profiles/runs/tecno/2026-10-15/release024-revalidation/20261015T192709Z-10216-00/`; métricas individuales en `metrics/`, agregado y comparaciones de regiones en `reports/summary.json`, logs en `logs/`, respaldos en `builds/` y `raw/`. Ningún recurso comercial ni captura privada se publica.
