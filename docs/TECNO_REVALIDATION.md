# TECNO ARM64 — objetivo vigente de 60 FPS, pendiente de revalidación

**Estado:** VIGENTE / EN ESPERA DEL DISPOSITIVO. **No es obsoleto, no está abandonado ni se considera una línea cerrada.** El desarrollo experimental actual se realiza en WSA x86_64 porque TECNO CK6n no está disponible. Una vez vuelva, la tarea prioritaria será comprobar en ese equipo el rendimiento del código ARM64 más reciente y de las mejoras portables que superen los oráculos.

## Dos plataformas, dos líneas base

| Plataforma | Objetivo | Última evidencia válida | Situación |
| --- | --- | --- | --- |
| WSA x86_64 | 120 FPS de motor sostenidos, calidad Alta | Conjunto acumulativo + enlace local: **65,75 → 68,15 FPS** entre variantes A/B, con **15,2125 → 14,675 ms CPU/frame**; [medición](performance/wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md) | Desarrollo y A/B activos; pantalla virtual observada 75 Hz, no acredita 120 presentaciones/s |
| TECNO CK6n ARM64 | 60 FPS sostenidos en entrenamiento, con misma calidad gráfica y jugabilidad | [Capturas físicas históricas](performance/tecno/TECNO_CK6N_ARM64_PERF_2026-10-14.md) y [normal-f2d A/B/A/B](performance/tecno/TECNO_X87_NORMAL_F2D_GAMEPLAY_ABAB_2026-10-14.md); ensayos adicionales ARM64 del 14–15/10 | **Revalidación pendiente**: no hay captura TECNO después de la nueva integración WSA |

La mejora de **WSA no demuestra automáticamente una mejora del TECNO**. Ni las opciones ni el ejecutable coinciden: `--native-x87-region`, `--wsa-cumulative` y `--local-guest-state` requieren x86_64; su versión ARM64 necesitará un diseño propio, no copiar banderas. Tampoco asumir que la APK ARM64 actual ya incluye toda la mejora WSA.

## Al recuperar el TECNO: protocolo práctico

1. Comprobar ADB, versión instalada, ABI ARM64, APK/ELF y Build ID. Respaldar partidas y configuración; registrar SHA de copia, sin publicar recursos comerciales.
2. Identificar los cambios ya incorporados a la **build ARM64 real**. Comparar código, flags y commit con el perfil físico anterior. No llamar "nueva" a una mejora presente desde octubre 14.
3. Establecer baseline actual **con la misma escena del entrenamiento, cámara, perfil gráfico, temperatura y condición de carga**. Separar FPS de motor, presentación y CPU/frame; registrar p10/p99 y estabilidad.
4. Priorizar portar solo mejoras **compatibles con ARM64** y con pruebas de precisión, estado x86 (R/PC/GPR/flags/memoria/x87) y guardados; la región nativa x87 WSA no es un parche ARM64 reutilizable directamente.
5. Repetir A/B/A/B de cada **ganancia candidata y del conjunto**. Conservar reducciones reales pequeñas; delta dentro del ruido es inconcluso/opt-in, no un incremento FPS confirmado. Retirar del conjunto activo lo regresivo o incorrecto.
6. Perfilar otra vez el ELF ARM64 instalado; las direcciones calientes anteriores pueden haber cambiado. Evaluar escenas con combate, no solo spawn.

## Qué documentación consultar

- [Registro global de optimizaciones y estados](OPTIMIZATION_LEDGER.md).
- [Estrategia de mejora acumulativa](PERFORMANCE_STRATEGY_CURRENT.md).
- [Fase 15, coste CPU transversal TECNO](performance/tecno/PHASE15_TECNO_CPU_PROFILE_CROSSCUTTING_2026-10-15.md).
- [Todas las investigaciones TECNO](performance/tecno/).
- [Estado operativo y siguientes decisiones](PROJECT_STATUS.md) y [cola](ROADMAP.md).

**No hacer:** declarar cerrada la meta de 60 FPS, extrapolar el +21,9 % del preset WSA a Mali/ARM64, comparar dos escenas distintas, activar rutas CFG14/double inseguras ni descartar por sí sola una optimización pequeña pero medida.
