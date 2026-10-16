# TECNO CK6n — A/B/A/B físico para ARM64 FCHS sign-bit (2026-10-16 UTC)

## Conclusión

**Sin mejora de rendimiento demostrada.** La opción experimental
`--arm64-x87-sign-bits` pasa la ejecución física y los cuatro controles
de estabilidad/encuadre, pero las dos parejas A/B muestran FPS y CPU
ligeramente peores en B. Conservar el experimento reversible, **OFF por
defecto**. Los márgenes son pequeños y no justifican inferir una
regresión estadísticamente concluyente.

El bloque de código previo y sus límites de equivalencia están descritos en
[ARM64_X87_FCHS_SIGN_BITS_2026-10-16.md](ARM64_X87_FCHS_SIGN_BITS_2026-10-16.md).
Los resultados offline de tamaño/Unicorn no se interpretan como FPS.

## Condiciones reproducibles

- Dispositivo físico: TECNO CK6n, Android `arm64-v8a`; serie autorizada
  comprobada. WSA x86_64 **no** se usó.
- Escenario: checkpoint de entrenamiento de Camp Toccoa; calidad
  **Equilibrado** y mismos archivos de guardado/configuración.
- Captura: 55 segundos por pasada y últimas 40 ventanas de un segundo,
  registradas en orden. Rechazo de deriva temporal, caídas de p10 o
  contaminación por menú/carga. Una imagen privada por pasada permite
  comprobar un encuadre aproximado (diferencia de huella visual
  0,3071–0,3077 % frente a referencia fija). No implica identidad completa
  de escena/cámara, FPS p10 por fotograma o ruta de GPU.
- Batería antes/después: A1 36/37 °C, B1 38/38 °C,
  A2 38/38 °C, B2 39/39 °C.
- APK normal A del estudio, SHA-256:
  `9ba61260ba04394db600f5d5feebc4a2df2a7f38948049fa8eb0e5fb7e217455`.
- APK candidata B, único cambio `--arm64-x87-sign-bits`, SHA-256:
  `ae600919e507701f97b6b0b8f4c62d2720f827a88a0aeb5563bb6b96bdd87a2d`.
- APK de restauración 0.2.4 original SHA-256:
  `fb8647c34dfe8fd269c0902f34edcc4c0844b18c6aa13ff6006232678da25f70`.
  Las tres APK compartían hash de manifiesto y ABI ARM64.
- La partida protegida `training.svg` SHA-256:
  `efbc68e54fabc79946dfd3a9d188e5f6ba284b1aad99130bbe2726eb637f64f8`.

## Mediciones físicas

| Pasada | FPS mediana | CPU ms/frame mediana | FPS p10 de ventanas | Deriva extremos | Control |
| --- | ---: | ---: | ---: | ---: | --- |
| A1 normal | 22,10 | 43,585 | 21,20 | −0,23 % | Aprobado |
| B1 FCHS | 22,00 | 43,675 | 21,40 | −0,89 % | Aprobado |
| A2 normal | 22,10 | 43,415 | 20,80 | +1,13 % | Aprobado |
| B2 FCHS | 21,90 | 43,945 | 21,10 | −3,36 % | Aprobado |

Diferencias relativas de cada pareja:

- **B1 respecto de A1:** FPS −0,4525 %, CPU +0,2065 %.
- **B2 respecto de A2:** FPS −0,9050 %, CPU +1,2208 %.

Media de medianas A1/A2: **22,10 FPS**, **43,500 ms CPU**.
Media de medianas B1/B2: **21,95 FPS**, **43,810 ms CPU**.

Por tanto, comparación agregada **−0,68 % FPS**, **+0,71 % CPU**.
Son medias descriptivas de solo dos parejas: **no** constituyen
un intervalo de confianza, FPS p10/p99 por fotograma ni prueba estadística.
La cámara aparente fue comparable y la referencia A fue muy repetible;
la temperatura ascendió ligeramente entre pasadas y otras variables de
núcleo/GPU no están controladas por completo.

**Veredicto del auditor:** `no_consistent_positive_signal`.
Ambas parejas muestran un efecto desfavorable muy pequeño: no activar
la candidata por defecto ni anunciar ganancias de velocidad.

## Integridad y límites funcionales

Tras B2, el corredor oficial
`tools/recomp/diagnostics/android_abab.py` terminó con:
`completed_abab`, `restored=true`, cuatro pasadas completadas.

Se realizó una **segunda verificación independiente** mediante ADB:
la APK instalada coincide exactamente con la 0.2.4 original
(`fb8647...`) y `training.svg` coincide con
su SHA-256 original (`efbc68...`). No se borraron partidas,
no hubo `adb uninstall`, ni cambios de calidad gráfica.
Se conservaron APK A/B, perfiles, capturas, métricas y registros
de instalación solo en el estudio local privado.

La prueba de juego en este checkpoint no demuestra equivalencia
integral x87 (`SW/C1`, excepciones, TOP/tags, estados NaN especiales)
ni estabilidad de todos los mapas: **mantener experimental y OFF**.

## Evidencia privada

`.local/profiles/runs/tecno/2026-10-16/arm64-fchs-sign-abab/20261016T015754Z-8824-00/`

- `reports/abab-plan.json`, `reports/abab-result.json`,
  comprobantes de instalación con cierre de sesión.
- `metrics/A1-stability.json`, `B1-stability.json`,
  `A2-stability.json`, `B2-stability.json` y mediciones del entorno.
- `captures/a1-scene.png` ... `b2-scene.png` (privadas).
- `scripts/preflight_scene_apks.py` y
  `scripts/verify_after_abab.py` (segunda comprobación de integridad).

**Próxima prioridad:** optimizaciones ARM64 de instrucciones ejecutadas
dinámicamente y accesos redundantes. No buscar una mejora fingida
con este cambio de signo; conservar el arreglo de precisión como
candidato semántico únicamente después de verificar el estado completo
x87 con casos adversos.
