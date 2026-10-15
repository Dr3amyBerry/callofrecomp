# TECNO ARM64 — estabilidad de mediciones y conservación de pequeñas mejoras (15-10-2026)

## Propósito

**No descartar ganancias pequeñas por tamaño.** Una señal positiva de +0,5 %,
con dos pares favorables, debe conservarse, repetirse y validarse. Pero una
comparación que incluya pasadas con deriva temporal importante no demuestra
una ganancia de rendimiento, aunque el promedio agregado sea favorable.

Herramientas permanentes y no intrusivas:

- `tools/recomp/diagnostics/stable_frame_gate.py`: revisa orden temporal de las
  últimas 40 ventanas de un segundo de `frame stats`, sin convertirlas en
  percentiles de fotogramas individuales. Requiere suficientes ventanas previas
  de calentamiento, limita deriva de extremos/mitades, caída relativa del p10 y
  valida que las referencias A1/A2 y B1/B2 sean repetibles. Clasifica los
  experimentos en señal positiva **no confirmada**, sin señal consistente o
  inconcluso por mediciones inestables. No mide FPS por sí mismo.
- `tools/recomp/diagnostics/android_perf_environment.py`: lee sin root
  `dumpsys battery`, temperaturas actuales del HAL, estado térmico y relojes
  `scaling_cur_freq` de los núcleos 0/4/6/7. Un campo que no pueda leerse
  queda nulo; **no cambia** límites de potencia, governor, afinidad, reloj,
  brillo ni resolución.

Uso del evaluador sobre logs existentes:

```powershell
python tools/recomp/diagnostics/stable_frame_gate.py --a1 runs/A1.log --b1 runs/B1.log --a2 runs/A2.log --b2 runs/B2.log --out metrics/stability.json
```

El reporte es nuevo, falla si ya existe y mantiene toda la evidencia.

## Primeros hallazgos (sobre logs históricos reales del TECNO)

| Experimento | Pasadas válidas según el nuevo control | Anomalía | Interpretación |
| --- | --- | --- | --- |
| Copias x87 `--x87-stack-shift-outline` | A1, B1, B2 | A2: deriva de extremos **+35,35 %** y diferencia entre mitades **+13,11 %** | +0,57 % FPS observado en medias; **señal por repetir**, no ganancia validada |
| Enlace local `--arm64-local-guest-state` | B1, A2, B2 | A1: deriva de extremos **−22,40 %** y diferencia entre mitades **−21,97 %** | +13,03 % bruto contaminado; **no atribuirlo** al enlace local |

**Los umbrales iniciales** son orientativos y conservadores: 40 ventanas
medidas, al menos 10 anteriores, deriva máxima de extremos y mitades del 5 %,
p10 no más de un 12 % por debajo de mediana; repetición A1/A2 y B1/B2 con
menos de 5 % de diferencia. No son una prueba estadística formal; porcentajes
pequeños requieren suficientes repeticiones independientes.

## Repeticiones de la misma APK 0.2.4

Para conocer el ruido real del teléfono antes de reactivar optimizaciones:

- APK 0.2.4 exacta SHA-256:
  `fb8647c34dfe8fd269c0902f34edcc4c0844b18c6aa13ff6006232678da25f70`.
- Partida `training.svg` SHA-256:
  `efbc68e54fabc79946dfd3a9d188e5f6ba284b1aad99130bbe2726eb637f64f8`.
- R1 de control: 21,15 FPS, 45,335 ms CPU/frame, **no estable**;
  sus 40 ventanas subieron de ~16 a ~22 FPS, con deriva de extremos
  **+33,43 %**. Hubo 29 muestras de entorno, batería 38–39 °C,
  estado térmico 0 informado por Android y relojes CPU dinámicos.
- R2 se interrumpió al perder la conexión Windows, sin dato validado.
- Se preparó R3/R4 como **otra repetición idéntica**, ahora con una
  condición *previa* de estabilidad en gameplay: antes de medir requiere
  20 ventanas finales estables, 10 ventanas previas y cámara/escena
  compatibles. Esperar más a que termine la transición evita que los
  primeros segundos contaminen la muestra. Si no estabiliza en 140 s,
  aborta en lugar de publicar un FPS inventado.

Dos corridas de la MISMA 0.2.4: R3 21.70 FPS / 44.250 ms CPU y R4 21.65 FPS / 44.440 ms CPU; diferencia relativa -0.23 %. Veredicto: repetibilidad de referencia aceptable. No es una ganancia de optimización; son dos medidas del mismo código.

## Límites y próximos pasos

El test no garantiza cámara perfectamente idéntica, trabajo GPU equivalente,
número suficiente de réplicas para inferencia estadística ni ausencia de carga
de fondo. La telemetría ADB también puede introducir sobrecoste y se debe
comparar con una pasada sin monitor si la ganancia es pequeña. La temperatura
de batería no reemplaza las frecuencias efectivas de CPU.

Una vez que la misma APK mida de forma consistente, reensayar por separado:
`--x87-stack-shift-outline` y `--arm64-local-guest-state`; después,
una mejora de renderer o de dispatch en ARM64 a la vez. **Nunca** integrar
`--hot-x87-transform`: continúa bloqueado por divergencia con el x86
original. Conservar código experimental positivo hasta disponer de evidencia
de estabilidad, precisión y ventaja repetida.
