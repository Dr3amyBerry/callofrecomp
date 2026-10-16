# Cola de trabajo del proyecto

**Nueva opción ARM64 OFF (2026-10-16):** `--arm64-narrow-left-shift` transforma solo 16 shifts variables de los dos cuerpos seleccionados de CoDSP p0/p8, no 289 indiscriminados. Código global −44 B, ahorro local chunk 18 −4 B; visibilidad sin delta de tamaño. Pasa oráculos y restituye fuentes exactas; priorizar el perfil físico estable de 17 vs22 FPS y efectos de flags/visibilidad antes de activar nada. [Evidencia](performance/tecno/ARM64_NARROW_LEFT_SHIFT_SELECTIVE_2026-10-16.md).


**Próximo paso ARM64 (2026-10-16):** nueva opción experimental `--arm64-x87-fld32-visibility` (10 PCs p8) está OFF, fuente reversible, estados diferenciales aprobados. ELF B +428 bytes/105 instrucciones estáticas frente a A; posible ahorro dinámico de normales sin medir. No activar ni combinar con NaN/FCOM/stack shift. Validar con oráculo Intel x86 y A/B/A/B físico al volver TECNO. [Evidencia](performance/tecno/ARM64_X87_FLD32_VISIBILITY_2026-10-16.md).


**Investigación offline ARM64 (2026-10-16):** repetidos los dos perfiles físicos históricos con Build ID/huella originales, 16 PCs hot aparecen en ambos; predominan instrucciones relacionadas con x87, pero no es desglose exclusivo de tiempo CPU. La alternativa simple de `sx` emite exactamente los mismos tamaños ARM64 en 11 anchos con `-O1/-O2`, descartada. FCOM y NaN bits ya tienen opt-in con A/B físico inconcluso/regresivo, **no activarlos**. Prioridad próxima: análisis seguro de vida de flags/estado x87 y perfiles de la variación de escena/scheduler antes de otro cambio. [Informe](performance/tecno/ARM64_HOTPATH_RESEARCH_2026-10-16.md).


**ARM64 siguiente validación (2026-10-16):** experimental `--arm64-narrow-sar` implementado OFF, oráculos de bits y ARM64 aprobados; el ELF completo reduce 184 bytes y 44 instrucciones estáticas en cinco chunks CoDSP. No extrapolar a FPS: cuando vuelva el teléfono realizar A/B/A/B independiente a igual escena, calidad y guardados. [Evidencia](performance/tecno/ARM64_NARROW_SAR_2026-10-16.md).


**Siguiente paso ARM64 sin teléfono (2026-10-16):** selector experimental `--core-hot-o2-parts` ya permite A/B limpio de `p1`, `p0,p1` y perfil completo; está documentado el coste binario y los hashes. Mantener todas las opciones OFF, evaluar equivalencia y análisis nativo offline, y comparar A/B/A/B físico de `p1` cuando vuelva el TECNO. [Resultados](performance/tecno/ARM64_CORE_HOT_O2_PARTITIONS_OFFLINE_2026-10-16.md).


**ARM64 — resolución del A1 lento (2026-10-16):** CI ya aprobó (`517910e`, run 38846701351); nueva captura física A1 dio 17,10 FPS / 56,16 ms CPU con encuadre aparente compatible y distinta notificación transitoria de HUD, batería 35 °C, `thermal_status=0`. La referencia A1 no es comparable; B FLD32 NO instalada. Siguiente: contrastar perfilado de CPU/scheduler y estado real del guion en períodos de ~17 y ~22 FPS con la **misma APK** antes de otro A/B/A/B. [Informe](performance/tecno/TECNO_ARM64_CI_AND_BASELINE_DIAGNOSTIC_2026-10-16.md).


**ARM64, siguiente bloque (2026-10-16):** Verificar CI pública sin fuentes comerciales privadas y obtener una captura diagnóstica durante la referencia anómala 17 FPS usando el corredor A/B/A/B mejorado. No instalar la candidata FLD32 mientras A no cumpla referencia/escena; después medir A/B/A/B con una sesión y APK pinneadas por hash. [Criterios](performance/tecno/TECNO_ARM64_CI_AND_BASELINE_DIAGNOSTIC_2026-10-16.md).


**Próximo paso ARM64 tras FLD32 de 0x5061B0 (2026-10-16):**
39 conversiones FLD32 comprobadas y reversibles; el ahorro de tres instrucciones en una FLD aislada requiere verificación física. Reproducir escena y referencia ~22 FPS antes de acumular cambios o activar el flag OFF. No confundir Unicorn con FPS. [Pruebas](performance/tecno/TECNO_ARM64_HOT_FLD32_2026-10-16.md).


**Próximo objetivo ARM64 tras descarte de caché (2026-10-16):**
Priorizar accesos de estado de la función caliente CoDSP 0x005061B0 con pruebas que preserven x87 extendido, todos los PC, guardados y observabilidad en fallos de memoria. Las A/B actuales no prueban ganancia para caché de dispatch ni enlace local; resolver inestabilidad de escena antes de activar combinaciones. [Informe de controles](performance/tecno/TECNO_ARM64_MEM_DISPATCH_AUDIT_2026-10-16.md).


**ARM64 FCHS, medición física cerrada (2026-10-16):**
El parche de signo binary80 se conserva OFF: A/B/A/B válido en TECNO no produjo ganancia (−0,68 % FPS, +0,71 % CPU). Priorizar nuevos bloques de ahorro dinámico ARM64 con fidelidad verificada. [Mediciones](performance/tecno/TECNO_FCHS_SIGN_ABAB_2026-10-16.md).


**Siguiente fase ARM64 binary80 (2026-10-16):**
Conservar la candidata `--arm64-x87-sign-bits` para los tres FCHS validados [informe](performance/tecno/ARM64_X87_FCHS_SIGN_BITS_2026-10-16.md), pero no generalizar hasta modelar semantica de estado x87 (SW/C1/TOP/tags/excepciones/alias/faltas) y demostrar equivalencia con original x86. Sin telefono no declarar ganancias de FPS. Proseguir por bloques reversibles offline.


**ARM64-MET-03 / A/B/A/B reutilizable:** [candidatas y automatizacion preparada](performance/tecno/ARM64_OFFLINE_READY_2026-10-15.md). CLI offline + ejecucion separada; reutiliza logs, escena historica y guardas, una imagen por pasada. Tres planes con APK/SHA fijados, sin ADB ni capturas nuevas. Recuperacion por sesion de instalacion verificada con dobles; firmware fisico pendiente.

**ARM64-08 / shifts estrechos:** [helper, oracle y APK A/B](performance/tecno/ARM64_NARROW_RIGHT_SHIFT_2026-10-15.md). Opt-in OFF; `.text` neta -16 bytes, cambios mixtos por chunk y ninguna ganancia FPS demostrada. 8.192 casos AArch64 por variante; 494 pruebas Python y 40 CTest. Siguiente: preparar comparaciones fisicas de candidatas y continuar segun el coste real, sin activar rutas inseguras.

**ARM64-07 / dispatch:** [cache de entrada completa](performance/tecno/ARM64_DISPATCH_ENTRY_CACHE_2026-10-15.md), opt-in OFF. APK ARM64 A/B y oracle AArch64 preparados; menos instrucciones con localidad, mas con fallos frecuentes. Sin nuevos FPS. Siguiente: estado/memoria en chunks calientes y A/B/A/B fisico pendiente.

**ARM64-06 / trabajo offline vigente:** [safe ICF y copias x87](performance/tecno/ARM64_SAFE_ICF_2026-10-15.md). Candidata experimental OFF: -13.620 bytes de codigo sobre los mismos objetos; 12.000 llamadas AArch64 equivalentes. APK privada compilada, sin nuevos FPS ni ADB. Helpers externos descartados por aumentar instrucciones. Siguiente: coste dinamico de estado/dispatch, luego A/B/A/B fisico cuando se autorice.

**Siguiente objetivo TECNO: pequenas ganancias reproducibles (2026-10-15):**
Dos corridas de la MISMA 0.2.4: R3 21.70 FPS / 44.250 ms CPU y R4 21.65 FPS / 44.440 ms CPU; diferencia relativa -0.23 %. Veredicto: repetibilidad de referencia aceptable. No es una ganancia de optimización; son dos medidas del mismo código. Repetir por separado la optimizacion x87 de copias y enlace local ARM64 con el protocolo de docs/performance/tecno/TECNO_STABILITY_GATE_2026-10-15.md antes de acumular otras variantes.


**TECNO ARM64, siguiente prioridad tras WSA local-state (2026-10-15):**
[A/B aislado y estado del oraculo numeric binary80](performance/tecno/ARM64_WSA_LOCAL_STATE_BINARY80_2026-10-15.md): enlace local R/MEM/U/PC portado y probado, media bruta +13.03% FPS NO atribuible a la optimización por A1 anómala; veredicto INCONCLUSO POR VARIACION DE ESCENA/TIEMPO. Continuar con renderer/dispatch **una bandera por APK** y un backend de software binary80 completo (CW/SW/TOP/tags, excepciones, PC y fallos) verificado contra x86 original; no usar el helper double bloqueado.

**Actualizacion TECNO (2026-10-15):** dispositivo disponible y [TECNO 0.2.4 A/B/A/B](performance/tecno/TECNO_RELEASE024_ABAB_2026-10-15.md) completado. Proximo paso ARM64: perfilar el ELF actual y aislar el coste de retirar el transform double bloqueado. 60 FPS siguen pendientes; no reactivar rutas incorrectas.

> **Prioridad actual: misión WSA 120 FPS.** [Perfil de la acumulativa anterior](performance/wsa/WSA120_OPTIMIZED_APK_CPU_PROFILE_2026-10-15.md) y [aplicación medida sobre ella](performance/wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md); la cola TECNO sigue vigente, pero su primera revalidacion de 0.2.4 ya esta completada (ver corte superior). No extrapolar sus perfiles a WSA.

## Mantenimiento privado de scripts — tras primera tanda

- **Hecho:** dos tandas, **200 scripts Python** históricos organizados bajo `.local/profiles/history/scripts/` con manifiestos SHA256 separados (64 CFG14 + 36 CPU adicionales en la segunda); 33 capturas WSA y 7 builds anteriores ya verificados en sus archivos históricos. [Reglas canónicas para todas las IAs](guides/LOCAL_ARTIFACTS.md).
- **Hecho:** auditoría estática de 580 scripts privados; 579 sintácticamente válidos y uno de parche puntual defectuoso, **no ejecutado**. La validación completa se puede repetir con `tools/verify_local_artifacts.py --save`.
- **Hecho:** clasificados por código fuente real los 200 scripts archivados (103 ediciones puntuales, 94 experimentos de contexto, 3 patrones reutilizables). [Catálogo individual y criterios](history/ARCHIVED_SCRIPT_ROLES_FIRST200.md). El patrón de hash, inventario y metadatos ya es una herramienta permanente con tests en `tools/recomp/diagnostics/profile_evidence.py`.

- **Pendiente:** revisar por subfamilias los **353 scripts todavía sueltos**, clasificar entradas/salidas y eliminar duplicación de funcionalidad **mediante herramientas probadas**, no borrando snapshots A/B o antiguos perfiles TECNO. Cambios físicos siempre con nuevo manifiesto, sin romper rutas de scripts aún referenciados.
- **No confundir:** el objetivo TECNO 60 FPS sigue vigente y pendiente de nueva medición; organizar el historial no lo da por cerrado.

## Cola WSA vigente — actualizada con perfil de la APK B instalada

El [perfil post-acumulativo](performance/wsa/WSA120_OPTIMIZED_APK_CPU_PROFILE_2026-10-15.md) **ya se completó** en la APK acumulativa anterior: **12.695 muestras CPU** y **5.074 con stacks**, **67,2 FPS / 14,89 ms CPU/frame**. Ahora está instalada la candidata de enlace local; no resolver aquellos PC contra su nuevo ELF. La región binary80 `0x005061B0` **ya se integró en el preset experimental**; no presentarla nuevamente como no implementada. Continúan sin certificar recuperación SEH de excepciones sin máscara y pruebas prolongadas.

1. **P1 — coste transversal real de CPU:** [primer cambio aplicado y medido](performance/wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md): enlace local R/MEM/U/PC, fuentes guest idénticas, beneficio pequeño repetido. Continuar con conversiones/materialización restantes; distinguir MOV escalares de copias reales y exigir equivalencia x86 a cualquier transformación de instrucciones.
2. **P2 — renderer y transferencia de geometría:** medición realizada: ~103 draws y 153.365 índices/frame; CPU de Draw ~3,57 ms en APK instrumentada y cero uploads de buffer guest en esas ventanas. Falta cuantificar spans/bytes realmente reempaquetados y demostrar invalidación, especialmente durante Lock/Unlock. No se implementó una caché de geometría.
3. **P3 — frontera x87 nativa:** aclarada atribución: el símbolo final incluye FXRSTOR64 y postámbulo. Optimizar guardas, guardado/restaurado o retorno solo si no se pierde R/PC, CW/SW/TOP/tag, metadatos host de 64 bits ni seguridad ante faltas.
4. **P4 — prueba de impacto físico:** si se desarrolla una candidata segura, comparar A/B/A/B en Alta/misma partida y medir CPU/frame, presentación, FPS de motor y valores gráficos. Conservar ganancias reproducibles incluso pequeñas; si la señal está dentro del ruido, dejar opción opt-in y clasificar INCONCLUSO sin declarar FPS ni desechar el trabajo. Desactivar de la candidata activa solo regresiones o incompatibilidades.
5. **P5 — escenario complejo y plataforma:** validar combate, rendimiento largo y corrección visual/sonora, investigar tiempo GPU y comprobar un modo real ≥120 Hz antes de afirmar 120 presentaciones visibles/s.

**Política:** [conservar mejoras pequeñas verificadas y preservar experimentos inconclusos](PERFORMANCE_STRATEGY_CURRENT.md). [Matriz de funciones implementadas, opt-in, pendientes y bloqueadas](OPTIMIZATION_LEDGER.md). La antigua regla de cinco intentos queda histórica, no vigente.

**Límites:** muestras estadísticas, no tiempo CPU exclusivo por microoperación. Nada de reducir calidad o desbloquear CFG14/atajos double. Se modificó y midió el enlace de estado; el diagnóstico GL se retiró de la APK normal instalada.

## Cola TECNO vigente: dispositivo disponible

**Revisada:** 2026-10-15. [Estado actual](PROJECT_STATUS.md) · [Estrategia y política](PERFORMANCE_STRATEGY_CURRENT.md) · [Índice](INDEX.md).

| Orden | Trabajo | Termina cuando | Dependencia |
| --- | --- | --- | --- |
| P0 completado | Dependencias de oráculos de CI reparadas en `fbbf074` | Run 38727099017 aprobado | Mantener regresión en cada cambio posterior |
| P1 | Atribuir coste nativo transversal de mantenimiento x87 | Un patrón repetido en varias funciones, ELF/Build ID comprobado, ensamblador y cobertura, con límites explícitos | Perfiles y ELF privados ya archivados; no requiere teléfono |
| P2 | Candidata con ahorro ARM64 plausible | Diferencial contra A y oráculo original, estados/fallos cubiertos, fallback y OFF | P1; corregir o aislar divergencias x87 conocidas |
| P3 | A/B/A/B en TECNO y perfil simultáneo | Ganancia repetida de CPU/frame sobre ruido, sin regresión funcional/visual | P2 y dispositivo físico disponible |
| P4 | Generalizar el ahorro y volver a perfilar | Mejora acumulada medida y coste restante identificado | P3; no asumir ganancias sumables |

La especificación del siguiente bloque y las puertas técnicas están en la [estrategia vigente](PERFORMANCE_STRATEGY_CURRENT.md). **60 FPS sostenidos sigue pendiente; la misión no es obsoleta.** Al recuperar TECNO, [revalidar el código ARM64 más reciente y las mejoras portables](TECNO_REVALIDATION.md) antes de comparar con las capturas antiguas.

## Trabajo de producto que sigue abierto

- Campaña completa, objetivos, transición, guardado y carga: ejecutar [verificación de campaña](guides/CAMPAIGN_VERIFICATION.md) y [playtest](guides/MANUAL_PLAYTEST.md), sin equiparar el recorrido estático de 33 mapas a campaña terminada.
- Compatibilidad Android, entrada, audio, HUD y empaquetado: conservar controles de regresión al optimizar; los cambios de HUD no cuentan como mejoras de FPS.
- GPU Mali: obtener tiempos si hardware/permisos lo permiten; documentar ausencia de datos en lugar de inferirlos de WSA.
- Recuperación de fallos Android de CFG14: trabajo bloqueado por contrato no implementado y beneficio insuficiente; no anteponerlo a una candidata con ahorro demostrado.

## Líneas pausadas

No gastar nuevas mediciones en POPCOUNT por ancho, caché de pequeñas superregiones, p4, VBO/batching, `-O2` global o migración de renderer **sin una hipótesis nueva respaldada por perfil**. Mantener disponibles los resultados y variantes seguras; que no hayan demostrado aumento FPS aislado no borra su valor potencial en un conjunto acumulativo. Véanse los resultados en el [índice de evidencia](INDEX.md).

El [roadmap anterior](archive/ROADMAP_BEFORE_CONSOLIDATION_2026-10-15.md) conserva los hitos fundacionales y las tareas históricas. Sus «siguientes pasos» reflejan su fecha, no esta cola.
