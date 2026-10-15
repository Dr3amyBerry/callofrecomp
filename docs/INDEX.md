# CallofRecomp — entrada rápida de conocimiento

- [ARM64: safe ICF, equivalencia AArch64 y APK experimental](performance/tecno/ARM64_SAFE_ICF_2026-10-15.md).

**Regla para todas las IAs:** leer primero este índice y los documentos de estado, no buscar recursivamente `.local/`, builds, Ghidra, fuentes generadas o repos externos. Los informes fechados preservan evidencia, **no son instrucciones operativas vigentes**.

## Catálogo funcional de scripts archivados

- [Análisis individual de los primeros 200 scripts (103 ediciones, 94 experimentos, 3 capacidades reutilizables)](history/ARCHIVED_SCRIPT_ROLES_FIRST200.md).
- [Protocolo vigente de sesiones y herramientas reutilizables](guides/LOCAL_ARTIFACTS.md).

## Empezar en menos de cinco lecturas

1. [Reglas de trabajo](../AGENTS.md) — contexto eficiente, pruebas y política de mejora acumulativa.
2. [Estado actual del proyecto](PROJECT_STATUS.md) — hechos comprobados y bloqueos actuales.
3. [Roadmap de ejecución](ROADMAP.md) — próximas tareas y criterios de cierre.
4. [Registro acumulativo de optimizaciones](OPTIMIZATION_LEDGER.md) — qué está implementado, experimental, medido, inconcluso o bloqueado.
5. [Estrategia actual](PERFORMANCE_STRATEGY_CURRENT.md) — **una mejora pequeña reproducible también es una mejora**, preservando la fidelidad.

## Objetivos VIGENTES separados

| Plataforma | Objetivo | Referencia principal | Estado |
| --- | --- | --- | --- |
| **WSA x86_64** | **120 FPS de motor sostenidos** sin bajar calidad | [última A/B/A/B](performance/wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md), [conjunto anterior](performance/wsa/WSA_CUMULATIVE_2026-10-15.md) | Desarrollo y mediciones ahora; pantalla virtual 75 Hz limita lo visible |
| **TECNO CK6n ARM64** | **60 FPS sostenidos** con equivalencia y calidad | [plan de revalidación](TECNO_REVALIDATION.md), [perfiles TECNO](performance/tecno/PHASE15_TECNO_CPU_PROFILE_CROSSCUTTING_2026-10-15.md) | **Objetivo activo en espera del teléfono**. Últimos resultados físicos son anteriores a las mejoras WSA recientes; no extrapolar |

**Política para nuevas IAs:** [artefactos privados, capturas y scripts reutilizables](guides/LOCAL_ARTIFACTS.md).

## Carpetas por función

| Carpeta | Qué contiene |
| --- | --- |
| [`guides/`](guides/) | Guías estables: recompilador, compilación Android, empaquetado, gráficos y pruebas |
| [`performance/wsa/`](performance/wsa/) | Perfiles, A/B/A/B, x87 y estado de la misión WSA |
| [`performance/tecno/`](performance/tecno/) | Investigación ARM64 y medidas físicas históricas aún relevantes para 60 FPS |
| [`performance/cpu/`](performance/cpu/) | Análisis y transformaciones de CPU transversales |
| [`performance/cfg/`](performance/cfg/) | Investigación CFG14, oráculos y **bloqueos de seguridad** |
| [`performance/graphics/`](performance/graphics/) | Renderer, GL4ES/ANGLE/Vulkan y HUD |
| [`history/`](history/) | Bitácora completa, checkpoints pasados, notas de versiones y catálogo |
| [`archive/`](archive/) | Estrategias y roadmaps anteriores a la consolidación; **no vigentes** |
| [`superpowers/plans/`](superpowers/plans/) | Planes de fases de ingeniería; verificar el estado antes de ejecutarlos |

[Catálogo documental completo por carpeta](history/DOCUMENT_CATALOG.md) · [Entorno y rutas privadas](WORKSPACE.md) · [Guía específica TECNO](TECNO_REVALIDATION.md).

## Dónde están las builds y las evidencias

Las **builds activas** están bajo `.local/builds/`; los ensayos de build archivados se clasifican en `.local/builds/history/`. Los perfiles históricos o actuales están en `.local/profiles/` con sus hashes y escenas; los binarios comerciales, APK privadas, fuentes recompiladas y partidas **no** se suben a Git. Existen junctions Windows por compatibilidad que **no deben borrarse ni moverse recursivamente**.

Para investigar una propuesta, usar primero el [registro de optimizaciones](OPTIMIZATION_LEDGER.md), después el informe fechado concreto y, solo si hace falta reproducirlo, la carpeta privada específica. No rehacer experimentos ya implementados ni convertir «no ganó FPS aislado» en «eliminar conocimiento».
