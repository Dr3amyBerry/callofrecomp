# Índice documental

**Revisión:** 2026-10-15. Empezar por [estado actual](PROJECT_STATUS.md), seguir con [cola de trabajo](ROADMAP.md) y [estrategia de rendimiento](PERFORMANCE_STRATEGY_CURRENT.md).

**Misión activa:** [120 FPS reales en WSA: línea base, límites y siguiente bloque](WSA120_BASELINE_2026-10-15.md). [Reglas de eficiencia](../AGENTS.md).

**Último bloque:** [Limitador configurable, comparación física y perfil del renderer](WSA120_LIMITER_AND_RENDERER_PROFILE_2026-10-15.md).

## Responsabilidad de cada documento

| Documento | Qué mantener aquí |
| --- | --- |
| PROJECT_STATUS | Estado comprobado, bloqueos, GitHub/CI y límites de evidencia |
| PERFORMANCE_STRATEGY_CURRENT | Decisión de optimización, puertas de validación y política de intentos |
| ROADMAP | Cola pendiente y criterios de cierre; no copiar resultados de experimentos |
| PROGRESS | Bitácora por fecha; no usar sus colas antiguas como estado actual |
| Informes fechados | Métodos, resultados y siguientes pasos propuestos en esa fecha |
| analysis | Evidencia de ingeniería inversa; no certifica integración ni juego completo |
| archive / superpowers / release notes | Planes, decisiones o entregas históricas; conservar contexto temporal |

## Auditoría de redundancia

El inventario inicial cubrió **98 Markdown versionados**. Un análisis de párrafos normalizados >220 caracteres no encontró duplicados literales entre archivos. El problema principal era **duplicación semántica**: estrategia (~41 KB), roadmap (~31 KB), bitácora (~194 KB) y checkpoint repetían resultados y distintas prioridades.

Se separaron sus responsabilidades; los originales de estrategia y roadmap se preservan en `archive/` con enlaces relativos ajustados. El checkpoint anterior lleva aviso histórico. El README deja de enumerar experimentos. Los informes fechados conservan sus rutas y secciones. El estudio privado `.local/profiles/PERFORMANCE_REVIEW_2026-10-13.md` queda como antecedente privado; sus ~95 ms y sus propuestas preceden a las capturas y fases nuevas.

Los siguientes catálogos enumeran toda la documentación versionada y la añadida en esta revisión. Dentro de cada grupo el orden es por ruta; **no representa prioridad**. Para decidir el próximo trabajo usar únicamente el roadmap y la estrategia vigente.

## Entrada y guías

- [README.md](../README.md) — CallofRecomp
- [ANALYSIS_TOOLS.md](ANALYSIS_TOOLS.md) — callofrecomp
- [ANDROID_BUILD.md](ANDROID_BUILD.md) — Android build
- [ANDROID_PERFORMANCE.md](ANDROID_PERFORMANCE.md) — Android performance profiles
- [AUDIO_BRIDGE.md](AUDIO_BRIDGE.md) — Portable Miles boundary
- [CAMPAIGN_VERIFICATION.md](CAMPAIGN_VERIFICATION.md) — Campaign verification
- [FRAME_PACING.md](FRAME_PACING.md) — Desktop and Android frame pacing
- [HUD_WIDESCREEN_2026-10-14.md](HUD_WIDESCREEN_2026-10-14.md) — Native panoramic camera with aspect-correct HUD (2026-10-14)
- [LEGACY_FS_BRIDGE.md](LEGACY_FS_BRIDGE.md) — Puente conservador entre el ABI de archivos x86 y servicios nativos
- [MANUAL_PLAYTEST.md](MANUAL_PLAYTEST.md) — Pruebas de juego pendientes
- [PACKAGE_FORMAT.md](PACKAGE_FORMAT.md) — Paquetes de instalación `.codpack` (versión 1)
- [PERFORMANCE_STRATEGY_CURRENT.md](PERFORMANCE_STRATEGY_CURRENT.md) — Estrategia vigente de rendimiento
- [PROJECT_STATUS.md](PROJECT_STATUS.md) — Estado actual de CallofRecomp
- [RECOMP_CLOCKS.md](RECOMP_CLOCKS.md) — Recompiled engine clocks
- [RECOMP_MEMORY.md](RECOMP_MEMORY.md) — Guest memory lifecycle
- [REFERENCE_SOURCES.md](REFERENCE_SOURCES.md) — Public reference sources and verification policy
- [ROADMAP.md](ROADMAP.md) — Cola de trabajo del proyecto
- [SYMBOL_LEDGER.md](SYMBOL_LEDGER.md) — Symbol ledger
- [WORKSPACE.md](WORKSPACE.md) — Entorno local de trabajo

## Investigación CPU, x87 y CFG

- [ARM64_PERF_EXPERIMENTS_2026-10-14.md](ARM64_PERF_EXPERIMENTS_2026-10-14.md) — TECNO CK6n ARM64: experimentos posteriores a x87 — 14 de octubre de 2026
- [ARM64_RENDERER_CPU_FCOM_2026-10-14.md](ARM64_RENDERER_CPU_FCOM_2026-10-14.md) — CPU del renderizador en TECNO: auditoría GL4ES y comparaciones x87 (2026-10-14)
- [ARM64_X87_NAN_BITS_2026-10-14.md](ARM64_X87_NAN_BITS_2026-10-14.md) — CoDSP ARM64: detección binaria x87 NaN — 14 de octubre de 2026
- [ARM64_X87_NORMAL_F2D_2026-10-14.md](ARM64_X87_NORMAL_F2D_2026-10-14.md) — CoDSP ARM64: fast path de conversión x87 normal a double — 2026-10-14
- [CODSP_PCODE_TEMP_DCE_2026-10-14.md](CODSP_PCODE_TEMP_DCE_2026-10-14.md) — CoDSP p-code → C: eliminación de temporales muertos (2026-10-14)
- [CPU_PHASE10_TECNO_P4_PROFILED_ABA_2026-10-14.md](CPU_PHASE10_TECNO_P4_PROFILED_ABA_2026-10-14.md) — Fase 10 — Validación física A/B/A de la conversión x87 perfilada de p4
- [CPU_PHASE11_P4_INLINE_OVERLAP_OFFLINE_2026-10-14.md](CPU_PHASE11_P4_INLINE_OVERLAP_OFFLINE_2026-10-14.md) — Fase 11 — Solapamiento de muestras CPU inline de CoDSP p4 (solo offline)
- [CPU_PHASE12_X87_STACK_SHIFT_OUTLINE_OFFLINE_2026-10-14.md](CPU_PHASE12_X87_STACK_SHIFT_OUTLINE_OFFLINE_2026-10-14.md) — Fase 12 — Consolidación estructural de movimientos de pila x87 en ARM64 (sin TECNO)
- [CPU_PHASE13_HOT_BLOCK_COMPILER_AB_OFFLINE_2026-10-14.md](CPU_PHASE13_HOT_BLOCK_COMPILER_AB_OFFLINE_2026-10-14.md) — Fase 13 — Optimización de chunks calientes completos (ARM64, offline)
- [CPU_PHASE2_41B8F0_AUDIT_2026-10-14.md](CPU_PHASE2_41B8F0_AUDIT_2026-10-14.md) — Fase 2 — Auditoría estructural de `0x0041B8F0` y ensayo x87 sin modificar el juego
- [CPU_PHASE2_FCOM_CONDITION_ORACLE_2026-10-14.md](CPU_PHASE2_FCOM_CONDITION_ORACLE_2026-10-14.md) — Fase 2 — Oráculo independiente de bits de condición x87 FCOMP
- [CPU_PHASE2_X86_PREFIX_ORACLE_2026-10-14.md](CPU_PHASE2_X86_PREFIX_ORACLE_2026-10-14.md) — Fase 2 — Oráculo diferencial x86 real para el prólogo de `0x0041B8F0`
- [CPU_PHASE2_X87_WINDOW_ORACLE_2026-10-14.md](CPU_PHASE2_X87_WINDOW_ORACLE_2026-10-14.md) — Fase 2 — Oráculo x87 acotado con salida `float32` exacta
- [CPU_PHASE3_P0_REGISTER_CACHE_TECNO_2026-10-14.md](CPU_PHASE3_P0_REGISTER_CACHE_TECNO_2026-10-14.md) — Fase 3 — Caché de registros virtuales en CoDSP p0 (TECNO CK6n, 2026-10-14)
- [CPU_PHASE4_ARCH_REGISTER_DCE_TECNO_2026-10-14.md](CPU_PHASE4_ARCH_REGISTER_DCE_TECNO_2026-10-14.md) — Fase 4 — eliminación de escrituras arquitectónicas muertas (TECNO CK6n, 2026-10-14)
- [CPU_PHASE5_OFFLINE_DISPATCH_CACHE_2026-10-14.md](CPU_PHASE5_OFFLINE_DISPATCH_CACHE_2026-10-14.md) — Fase 5 — auditoría offline y caché experimental del despachador (2026-10-14)
- [CPU_PHASE6_X87_P4_OFFLINE_2026-10-14.md](CPU_PHASE6_X87_P4_OFFLINE_2026-10-14.md) — Fase 6 — ampliación x87 normal→double a p4, evaluación offline (2026-10-14)
- [CPU_PHASE7_P4_SELECTIVE_X87_OFFLINE_2026-10-14.md](CPU_PHASE7_P4_SELECTIVE_X87_OFFLINE_2026-10-14.md) — Fase 7 — CoDSP p4: conversión x87 selectiva por PC original, OFFLINE
- [CPU_PHASE8_P4_PROFILE_GUIDED_X87_OFFLINE_2026-10-14.md](CPU_PHASE8_P4_PROFILE_GUIDED_X87_OFFLINE_2026-10-14.md) — Fase 8 — selección x87 por muestras históricas y PC original (offline)
- [CPU_PHASE9_X87_INTEGER_PACK_OFFLINE_2026-10-14.md](CPU_PHASE9_X87_INTEGER_PACK_OFFLINE_2026-10-14.md) — Fase 9 — Auditoría offline del empaquetado x87: optimización descartada
- [FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md](FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md) — Function-entry mapping and next performance investigations — 2026-10-14
- [PERFORMANCE_DEEP_DIVE_2026-10-13.md](PERFORMANCE_DEEP_DIVE_2026-10-13.md) — Investigación profunda de rendimiento — CallofRecomp
- [PERFORMANCE_STRATEGY_RUN_2026-10-14.md](PERFORMANCE_STRATEGY_RUN_2026-10-14.md) — Ejecución de PERFORMANCE_STRATEGY_CURRENT — TECNO (2026-10-14)
- [PHASE14B_STATE_BOUNDARIES_ORACLE_2026-10-15.md](PHASE14B_STATE_BOUNDARIES_ORACLE_2026-10-15.md) — Fase 14B — Fronteras de estado por byte y oráculo x86 bifurcado (2026-10-15)
- [PHASE14B_X87_BINARY80_SHARED_EPILOGUE_2026-10-15.md](PHASE14B_X87_BINARY80_SHARED_EPILOGUE_2026-10-15.md) — Fase 14B — Estado x87 binary80 y epílogo compartido (15 de octubre de 2026)
- [PHASE14C_CFG_AB_OFFLINE_RESULTS_2026-10-15.md](PHASE14C_CFG_AB_OFFLINE_RESULTS_2026-10-15.md) — Fase 14C — Resultados A/B de regiones originales, offline (2026-10-15)
- [PHASE14C_CFG_REGION_EXPERIMENT_PLAN_2026-10-15.md](PHASE14C_CFG_REGION_EXPERIMENT_PLAN_2026-10-15.md) — Fase 14C — Plan de regiones CFG verificables (2026-10-15)
- [PHASE14C_REAL_X86_GUARDED_RUNTIME_2026-10-15.md](PHASE14C_REAL_X86_GUARDED_RUNTIME_2026-10-15.md) — Fase 14C — Oráculo x86 original y dispatcher CFG con fallback (2026-10-15)
- [PHASE14D_EPILOGUE_FAULT_SAFETY_2026-10-15.md](PHASE14D_EPILOGUE_FAULT_SAFETY_2026-10-15.md) — Fase 14D — Epílogo x86, fallos de página y bloqueo de la región CFG insegura
- [PHASE14E_PRECISE_CHECKPOINTS_AND_RESUME_2026-10-15.md](PHASE14E_PRECISE_CHECKPOINTS_AND_RESUME_2026-10-15.md) — Fase 14E — Checkpoints x86 precisos, fallback original y coste ARM64
- [PHASE14F_ANDROID_FAULT_RECOVERY_CONTRACT_2026-10-15.md](PHASE14F_ANDROID_FAULT_RECOVERY_CONTRACT_2026-10-15.md) — Fase 14F — Contrato de recuperación segura de fallos guest en Android ARM64
- [PHASE14F_MEMORY_FREE_SUPERREGIONS_2026-10-15.md](PHASE14F_MEMORY_FREE_SUPERREGIONS_2026-10-15.md) — Fase 14F — Superregiones CFG originales sin memoria y oráculo x86 independiente
- [PHASE14_CFG_ARCHITECTURE_MASTER_PLAN_2026-10-14.md](PHASE14_CFG_ARCHITECTURE_MASTER_PLAN_2026-10-14.md) — Fase 14 — Arquitectura de recompilación por regiones CFG (plan maestro)
- [PHASE14_CFG_INITIAL_RECOVERY_2026-10-14.md](PHASE14_CFG_INITIAL_RECOVERY_2026-10-14.md) — Fase 14A — CFG de siete funciones originales y comprobación independiente de PC x86
- [PHASE14_CFG_REFERENCE_SOURCES_2026-10-14.md](PHASE14_CFG_REFERENCE_SOURCES_2026-10-14.md) — Fase 14 — Fuentes de referencia para CFG y sustitución estructural (2026-10-14)
- [PHASE15_TECNO_CPU_PROFILE_CROSSCUTTING_2026-10-15.md](PHASE15_TECNO_CPU_PROFILE_CROSSCUTTING_2026-10-15.md) — Fase 15 — Perfiles TECNO originales, presupuesto por fotograma y oportunidades transversales
- [TECNO_CK6N_ARM64_PERF_2026-10-14.md](TECNO_CK6N_ARM64_PERF_2026-10-14.md) — TECNO CK6n: medición real de CallofRecomp ARM64 — 2026-10-14
- [TECNO_X87_NORMAL_F2D_GAMEPLAY_ABAB_2026-10-14.md](TECNO_X87_NORMAL_F2D_GAMEPLAY_ABAB_2026-10-14.md) — TECNO CK6n ARM64 — A/B/A/B de x87 normal f2d y descarte de geometry -O2 (2026-10-14)
- [WSA_X87_NORMAL_F2D_ABA_2026-10-14.md](WSA_X87_NORMAL_F2D_ABA_2026-10-14.md) — WSA — A/B/A de conversion x87 normal f2d (2026-10-14)

## Renderer y alternativas gráficas

- [ANGLE_BUILD_PIPELINE_2026-10-14.md](ANGLE_BUILD_PIPELINE_2026-10-14.md) — ANGLE: compilación Linux reproducible y aislada (2026-10-14)
- [ANGLE_GLES_VULKAN_FEASIBILITY_2026-10-14.md](ANGLE_GLES_VULKAN_FEASIBILITY_2026-10-14.md) — ANGLE: viabilidad GLES a Vulkan en CallofRecomp (14 de octubre de 2026)
- [ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md](ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md) — ANGLE/Vulkan frente a GL4ES: A1/B/A2 de gameplay 3D en WSA — 2026-10-14
- [ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md](ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md) — ANGLE Android x86_64 en CallofRecomp: ensayo real WSA (2026-10-14)
- [GL_VK_STATE_BRIDGE_2026-10-14.md](GL_VK_STATE_BRIDGE_2026-10-14.md) — Hito del puente OpenGL → estado tipado Vulkan (WSA, 2026-10-14)
- [MESA_ZINK_FEASIBILITY_2026-10-14.md](MESA_ZINK_FEASIBILITY_2026-10-14.md) — Investigación real: Mesa Zink para CallofRecomp (14 de octubre de 2026)
- [RENDER_TRANSLATION_AUDIT_2026-10-14.md](RENDER_TRANSLATION_AUDIT_2026-10-14.md) — Renderer and x86-to-ARM64 translation audit — 2026-10-14
- [WSA_GL_MATRIX_BRIDGE_2026-10-14.md](WSA_GL_MATRIX_BRIDGE_2026-10-14.md) — Hito Vulkan WSA: matrices OpenGL 1.x y proyección (2026-10-14)
- [WSA_VULKAN_DEPTH_STENCIL_BLEND_2026-10-14.md](WSA_VULKAN_DEPTH_STENCIL_BLEND_2026-10-14.md) — Hito Vulkan WSA: depth/stencil y blending alfa (2026-10-14)
- [WSA_VULKAN_DX12_RENDERER_DECISION_2026-10-14.md](WSA_VULKAN_DX12_RENDERER_DECISION_2026-10-14.md) — Evaluación de Vulkan nativo, DirectX 12 y entorno WSA — 2026-10-14
- [WSA_VULKAN_INDEXED_MESH_2026-10-14.md](WSA_VULKAN_INDEXED_MESH_2026-10-14.md) — Hito Vulkan: geometría indexada y shaders nativos en WSA — 2026-10-14
- [WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md](WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md) — Benchmark por etapas: WSA actual → superficie Vulkan → juego final
- [WSA_VULKAN_TEXENV_ALPHA_2026-10-14.md](WSA_VULKAN_TEXENV_ALPHA_2026-10-14.md) — Vulkan WSA: TexEnv MODULATE/REPLACE + prueba alfa (2026-10-14)
- [WSA_VULKAN_TEXTURE_2026-10-14.md](WSA_VULKAN_TEXTURE_2026-10-14.md) — Vulkan WSA: subida real de texturas RGBA8 con staging y sampler

## Ingeniería inversa original

- [engine_vm_findings.md](../analysis/engine_vm_findings.md) — Engine VM boundary findings
- [filesystem_vfs_phase.md](../analysis/filesystem_vfs_phase.md) — Primera fase del sistema de archivos virtual (VFS) y lectura de PK3
- [fs_modes_and_searchpath_evidence.md](../analysis/fs_modes_and_searchpath_evidence.md) — Evidencia: modos FS y lista de búsqueda en Call of Duty 1.5 SP
- [game_syscall_edges_20_43.md](../analysis/game_syscall_edges_20_43.md) — SP game syscall dispatcher: direct edges for IDs 20–43
- [game_syscall_findings.md](../analysis/game_syscall_findings.md) — Single-player game syscall findings
- [initial_findings.md](../analysis/initial_findings.md) — Initial static-analysis findings
- [installation_inventory.md](../analysis/installation_inventory.md) — Supplied installation inventory
- [localization_searchpath.md](../analysis/localization_searchpath.md) — Call of Duty 1.5 SP — localización y nodos de búsqueda
- [module_syscall_wrapper_provenance.md](../analysis/module_syscall_wrapper_provenance.md) — SP game syscall wrapper provenance (IDs 21, 22, 23, 36, 37, 40, 41)
- [opengl_loader_findings.md](../analysis/opengl_loader_findings.md) — Dynamic OpenGL loader findings
- [renderer_api_inventory.md](../analysis/renderer_api_inventory.md) — Renderer API inventory
- [searchpath_insertion.md](../analysis/searchpath_insertion.md) — Deterministic model of an SP searchpath insertion routine
- [searchpath_startup_scan.md](../analysis/searchpath_startup_scan.md) — CoD 1.5 SP startup searchpath helper: indexed scan
- [sp_game_syscall_signatures_20_43.md](../analysis/sp_game_syscall_signatures_20_43.md) — SP game syscalls 20–43: conservative ABI shape recovery
- [static_recompilation_prototype.md](../analysis/static_recompilation_prototype.md) — Static recompilation prototype (Ghidra p-code → C)
- [ui_touch_cursor.md](../analysis/ui_touch_cursor.md) — Absolute touch mapping for the verified SP UI
- [vm_abi_findings.md](../analysis/vm_abi_findings.md) — vmMain / dllEntry ABI probe

## Planes e historial

- [2026-10-15-wsa-frame-limit.md](superpowers/plans/2026-10-15-wsa-frame-limit.md) — Plan y verificación del control reversible WSA.

- [PROGRESS.md](../PROGRESS.md) — Project Progress
- [PROJECT_STATUS_CHECKPOINT_2026-10-14.md](PROJECT_STATUS_CHECKPOINT_2026-10-14.md) — Estado consolidado y continuación — CallofRecomp (2026-10-14)
- [RELEASE_NOTES_v0.2.0.md](RELEASE_NOTES_v0.2.0.md) — Instalar
- [RELEASE_NOTES_v0.2.1.md](RELEASE_NOTES_v0.2.1.md) — Descargar
- [RELEASE_NOTES_v0.2.3.md](RELEASE_NOTES_v0.2.3.md) — Menos trabajo de CPU y APK ARM64 más pequeño
- [PERFORMANCE_STRATEGY_CURRENT_BEFORE_CONSOLIDATION_2026-10-15.md](archive/PERFORMANCE_STRATEGY_CURRENT_BEFORE_CONSOLIDATION_2026-10-15.md) — Estrategia vigente de rendimiento — CallofRecomp
- [ROADMAP_BEFORE_CONSOLIDATION_2026-10-15.md](archive/ROADMAP_BEFORE_CONSOLIDATION_2026-10-15.md) — Recompilation roadmap
- [2026-10-12-frame-cap-campaign.md](superpowers/plans/2026-10-12-frame-cap-campaign.md) — 60 FPS and campaign progression verification
- [2026-10-12-menus-android.md](superpowers/plans/2026-10-12-menus-android.md) — Menus and Android implementation plan
- [2026-10-13-crowded-scenes-performance.md](superpowers/plans/2026-10-13-crowded-scenes-performance.md) — Crowded scene CPU performance
- [2026-10-13-runtime-performance.md](superpowers/plans/2026-10-13-runtime-performance.md) — CPU and graphics translation performance implementation plan
- [2026-10-12-menus-android-design.md](superpowers/specs/2026-10-12-menus-android-design.md) — Original menus and Android build
