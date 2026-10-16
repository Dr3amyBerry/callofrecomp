# Investigación TECNO CK6n ARM64 — objetivo vigente

**Prueba física ARM64 FCHS (2026-10-16):**
[A/B/A/B de la opción de signo binary80](TECNO_FCHS_SIGN_ABAB_2026-10-16.md): cuatro pasadas válidas; sin mejora de FPS, APK original y partida verificadas.


**ARM64, signo binary80 en FCHS (2026-10-16):**
[Candidato offline de tres instrucciones](ARM64_X87_FCHS_SIGN_BITS_2026-10-16.md), APK y equivalencia de valor; -1.032 bytes de `.text`, OFF por defecto, sin TECNO/WSA ni nuevos FPS.


**Control de estabilidad TECNO (2026-10-15):**
Dos corridas de la MISMA 0.2.4: R3 21.70 FPS / 44.250 ms CPU y R4 21.65 FPS / 44.440 ms CPU; diferencia relativa -0.23 %. Veredicto: repetibilidad de referencia aceptable. No es una ganancia de optimización; son dos medidas del mismo código. [Informe tecnico](TECNO_STABILITY_GATE_2026-10-15.md).


**WSA port a ARM64 (2026-10-15):**
[enlace local R/MEM/U/PC y precision x87](ARM64_WSA_LOCAL_STATE_BINARY80_2026-10-15.md): prueba A/B/A/B 19.57->22.12 FPS (+13.03%), INCONCLUSO POR VARIACION DE ESCENA/TIEMPO. Sin integrar native x87 de WSA ni reactivar el transform double incorrecto.

**Objetivo:** 60 FPS sostenidos con fidelidad y la misma calidad gráfica. El teléfono no está disponible ahora: el trabajo WSA progresa en paralelo, pero **no reemplaza** la meta ni convierte estas capturas en obsoletas.

**Primero leer:** [plan de revalidación TECNO](../../TECNO_REVALIDATION.md), [registro global de cambios](../../OPTIMIZATION_LEDGER.md) y [fase 15 de CPU ARM64](PHASE15_TECNO_CPU_PROFILE_CROSSCUTTING_2026-10-15.md). Los experimentos y medidas de octubre 14–15 siguen siendo útiles para priorizar, pero no son el rendimiento de una APK recompilada después de las optimizaciones WSA.

Al reconectar el TECNO: A/B/A/B del APK ARM64 actual, medir baseline nuevo con hashes/ELF/escena/temperatura, probar solo transformaciones portables con oráculos y actualizar esta fuente. **No extrapolar mejoras x86_64 ni confundir menús con gameplay.**
