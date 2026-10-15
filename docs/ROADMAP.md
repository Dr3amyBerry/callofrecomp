# Cola de trabajo del proyecto

> **Prioridad actual: misión WSA 120 FPS.** Seguir el [bloque de diagnóstico e implementación WSA](WSA120_BASELINE_2026-10-15.md#siguiente-bloque). La cola TECNO de abajo queda como referencia; no extrapolar sus perfiles a WSA.

**Revisada:** 2026-10-15. [Estado actual](PROJECT_STATUS.md) · [Estrategia y política](PERFORMANCE_STRATEGY_CURRENT.md) · [Índice](INDEX.md).

| Orden | Trabajo | Termina cuando | Dependencia |
| --- | --- | --- | --- |
| P0 | Reparar entorno de CI: falta Unicorn al importar dos tests CFG | Run Linux completo aprobado, sin ocultar tests por omisión | Dependencias de pruebas declaradas y verificadas |
| P1 | Atribuir coste nativo transversal de mantenimiento x87 | Un patrón repetido en varias funciones, ELF/Build ID comprobado, ensamblador y cobertura, con límites explícitos | Perfiles y ELF privados ya archivados; no requiere teléfono |
| P2 | Candidata con ahorro ARM64 plausible | Diferencial contra A y oráculo original, estados/fallos cubiertos, fallback y OFF | P1; corregir o aislar divergencias x87 conocidas |
| P3 | A/B/A/B en TECNO y perfil simultáneo | Ganancia repetida de CPU/frame sobre ruido, sin regresión funcional/visual | P2 y dispositivo físico disponible |
| P4 | Generalizar el ahorro y volver a perfilar | Mejora acumulada medida y coste restante identificado | P3; no asumir ganancias sumables |

La especificación del siguiente bloque y las puertas técnicas están en la [estrategia vigente](PERFORMANCE_STRATEGY_CURRENT.md). **60 FPS sostenidos sigue pendiente**.

## Trabajo de producto que sigue abierto

- Campaña completa, objetivos, transición, guardado y carga: ejecutar [verificación de campaña](CAMPAIGN_VERIFICATION.md) y [playtest](MANUAL_PLAYTEST.md), sin equiparar el recorrido estático de 33 mapas a campaña terminada.
- Compatibilidad Android, entrada, audio, HUD y empaquetado: conservar controles de regresión al optimizar; los cambios de HUD no cuentan como mejoras de FPS.
- GPU Mali: obtener tiempos si hardware/permisos lo permiten; documentar ausencia de datos en lugar de inferirlos de WSA.
- Recuperación de fallos Android de CFG14: trabajo bloqueado por contrato no implementado y beneficio insuficiente; no anteponerlo a una candidata con ahorro demostrado.

## Líneas pausadas

No repetir POPCOUNT por ancho, caché de pequeñas superregiones, p4, VBO/batching, `-O2` global o migración de renderer sin una hipótesis nueva respaldada por perfil. Véanse los resultados en el [índice de evidencia](INDEX.md).

El [roadmap anterior](archive/ROADMAP_BEFORE_CONSOLIDATION_2026-10-15.md) conserva los hitos fundacionales y las tareas históricas. Sus «siguientes pasos» reflejan su fecha, no esta cola.
