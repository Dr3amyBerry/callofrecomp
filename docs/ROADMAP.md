# Cola de trabajo del proyecto

> **Prioridad actual: misión WSA 120 FPS.** [Perfil de la acumulativa anterior](WSA120_OPTIMIZED_APK_CPU_PROFILE_2026-10-15.md) y [aplicación medida sobre ella](WSA_POSTOPT_APPLICATION_2026-10-15.md); la cola TECNO de abajo queda como referencia histórica. No extrapolar sus perfiles a WSA.

## Cola WSA vigente — actualizada con perfil de la APK B instalada

El [perfil post-acumulativo](WSA120_OPTIMIZED_APK_CPU_PROFILE_2026-10-15.md) **ya se completó** en la APK acumulativa anterior: **12.695 muestras CPU** y **5.074 con stacks**, **67,2 FPS / 14,89 ms CPU/frame**. Ahora está instalada la candidata de enlace local; no resolver aquellos PC contra su nuevo ELF. La región binary80 `0x005061B0` **ya se integró en el preset experimental**; no presentarla nuevamente como no implementada. Continúan sin certificar recuperación SEH de excepciones sin máscara y pruebas prolongadas.

1. **P1 — coste transversal real de CPU:** [primer cambio aplicado y medido](WSA_POSTOPT_APPLICATION_2026-10-15.md): enlace local R/MEM/U/PC, fuentes guest idénticas, beneficio pequeño repetido. Continuar con conversiones/materialización restantes; distinguir MOV escalares de copias reales y exigir equivalencia x86 a cualquier transformación de instrucciones.
2. **P2 — renderer y transferencia de geometría:** medición realizada: ~103 draws y 153.365 índices/frame; CPU de Draw ~3,57 ms en APK instrumentada y cero uploads de buffer guest en esas ventanas. Falta cuantificar spans/bytes realmente reempaquetados y demostrar invalidación, especialmente durante Lock/Unlock. No se implementó una caché de geometría.
3. **P3 — frontera x87 nativa:** aclarada atribución: el símbolo final incluye FXRSTOR64 y postámbulo. Optimizar guardas, guardado/restaurado o retorno solo si no se pierde R/PC, CW/SW/TOP/tag, metadatos host de 64 bits ni seguridad ante faltas.
4. **P4 — prueba de impacto físico:** si se desarrolla una candidata segura, comparar A/B/A/B en Alta/misma partida y medir CPU/frame, presentación, FPS de motor y valores gráficos. Revertir ganancias que no se reproduzcan.
5. **P5 — escenario complejo y plataforma:** validar combate, rendimiento largo y corrección visual/sonora, investigar tiempo GPU y comprobar un modo real ≥120 Hz antes de afirmar 120 presentaciones visibles/s.

**Límites:** muestras estadísticas, no tiempo CPU exclusivo por microoperación. Nada de reducir calidad o desbloquear CFG14/atajos double. Se modificó y midió el enlace de estado; el diagnóstico GL se retiró de la APK normal instalada.

## Cola TECNO conservada

**Revisada:** 2026-10-15. [Estado actual](PROJECT_STATUS.md) · [Estrategia y política](PERFORMANCE_STRATEGY_CURRENT.md) · [Índice](INDEX.md).

| Orden | Trabajo | Termina cuando | Dependencia |
| --- | --- | --- | --- |
| P0 completado | Dependencias de oráculos de CI reparadas en `fbbf074` | Run 38727099017 aprobado | Mantener regresión en cada cambio posterior |
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
