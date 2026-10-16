# Catálogo completo de documentación

**Propósito:** localizar informes sin recorrer builds, perfiles privados ni repos externos. **No confundir archivos históricos con prioridades actuales.**

[Ruta de lectura corta](../INDEX.md) · [estado](../PROJECT_STATUS.md) · [objetivo TECNO vigente](../TECNO_REVALIDATION.md)

## Documentos operativos

- [INDEX.md](../INDEX.md) — CallofRecomp — entrada rápida de conocimiento
- [OPTIMIZATION_LEDGER.md](../OPTIMIZATION_LEDGER.md) — Registro acumulativo de optimizaciones — estado verificable
- [PERFORMANCE_STRATEGY_CURRENT.md](../PERFORMANCE_STRATEGY_CURRENT.md) — Estrategia vigente de rendimiento
- [PROJECT_STATUS.md](../PROJECT_STATUS.md) — Estado actual de CallofRecomp
- [ROADMAP.md](../ROADMAP.md) — Cola de trabajo del proyecto
- [TECNO_REVALIDATION.md](../TECNO_REVALIDATION.md) — TECNO ARM64 — objetivo vigente de 60 FPS, pendiente de revalidación
- [WORKSPACE.md](../WORKSPACE.md) — Entorno local de trabajo

## Guías técnicas

- [ANALYSIS_TOOLS.md](../guides/ANALYSIS_TOOLS.md) — callofrecomp
- [ANDROID_BUILD.md](../guides/ANDROID_BUILD.md) — Android build
- [ANDROID_PERFORMANCE.md](../guides/ANDROID_PERFORMANCE.md) — Android performance profiles
- [AUDIO_BRIDGE.md](../guides/AUDIO_BRIDGE.md) — Portable Miles boundary
- [CAMPAIGN_VERIFICATION.md](../guides/CAMPAIGN_VERIFICATION.md) — Campaign verification
- [FRAME_PACING.md](../guides/FRAME_PACING.md) — Desktop and Android frame pacing
- [LEGACY_FS_BRIDGE.md](../guides/LEGACY_FS_BRIDGE.md) — Puente conservador entre el ABI de archivos x86 y servicios nativos
- [LOCAL_ARTIFACTS.md](../guides/LOCAL_ARTIFACTS.md) — Organización privada y reutilización de scripts (ChatGPT + RigorCore Dev MCP)
- [MANUAL_PLAYTEST.md](../guides/MANUAL_PLAYTEST.md) — Pruebas de juego pendientes
- [PACKAGE_FORMAT.md](../guides/PACKAGE_FORMAT.md) — Paquetes de instalación `.codpack` (versión 1)
- [RECOMP_CLOCKS.md](../guides/RECOMP_CLOCKS.md) — Recompiled engine clocks
- [RECOMP_MEMORY.md](../guides/RECOMP_MEMORY.md) — Guest memory lifecycle
- [REFERENCE_SOURCES.md](../guides/REFERENCE_SOURCES.md) — Public reference sources and verification policy
- [SYMBOL_LEDGER.md](../guides/SYMBOL_LEDGER.md) — Symbol ledger

## Historial y releases

- [ARCHIVED_SCRIPT_ROLES_FIRST200.md](ARCHIVED_SCRIPT_ROLES_FIRST200.md) — Clasificación funcional de los primeros 200 scripts históricos
- [PERFORMANCE_DEEP_DIVE_2026-10-13.md](checkpoints/PERFORMANCE_DEEP_DIVE_2026-10-13.md) — Investigación profunda de rendimiento — CallofRecomp
- [PROJECT_STATUS_CHECKPOINT_2026-10-14.md](checkpoints/PROJECT_STATUS_CHECKPOINT_2026-10-14.md) — Estado consolidado y continuación — CallofRecomp (2026-10-14)
- [PROGRESS_LOG.md](PROGRESS_LOG.md) — Project Progress
- [README.md](README.md) — Historial preservado — no gobierna el trabajo actual
- [RELEASE_NOTES_v0.2.0.md](releases/RELEASE_NOTES_v0.2.0.md) — RELEASE_NOTES_v0.2.0
- [RELEASE_NOTES_v0.2.1.md](releases/RELEASE_NOTES_v0.2.1.md) — RELEASE_NOTES_v0.2.1
- [RELEASE_NOTES_v0.2.3.md](releases/RELEASE_NOTES_v0.2.3.md) — RELEASE_NOTES_v0.2.3
- [RELEASE_NOTES_v0.2.4.md](releases/RELEASE_NOTES_v0.2.4.md) — CallofRecomp 0.2.4

## Estrategias anteriores

- [PERFORMANCE_STRATEGY_CURRENT_BEFORE_CONSOLIDATION_2026-10-15.md](../archive/PERFORMANCE_STRATEGY_CURRENT_BEFORE_CONSOLIDATION_2026-10-15.md) — Estrategia vigente de rendimiento — CallofRecomp
- [ROADMAP_BEFORE_CONSOLIDATION_2026-10-15.md](../archive/ROADMAP_BEFORE_CONSOLIDATION_2026-10-15.md) — Recompilation roadmap

## Planes técnicos

- [2026-10-12-frame-cap-campaign.md](../superpowers/plans/2026-10-12-frame-cap-campaign.md) — 60 FPS and campaign progression verification
- [2026-10-12-menus-android.md](../superpowers/plans/2026-10-12-menus-android.md) — Menus and Android implementation plan
- [2026-10-13-crowded-scenes-performance.md](../superpowers/plans/2026-10-13-crowded-scenes-performance.md) — Crowded scene CPU performance
- [2026-10-13-runtime-performance.md](../superpowers/plans/2026-10-13-runtime-performance.md) — CPU and graphics translation performance implementation plan
- [2026-10-15-postopt-guest-state-binding.md](../superpowers/plans/2026-10-15-postopt-guest-state-binding.md) — Aplicar auditoría post-acumulativa: enlace del estado guest
- [2026-10-15-wsa-frame-limit.md](../superpowers/plans/2026-10-15-wsa-frame-limit.md) — WSA frame limit implementation plan
- [2026-10-15-wsa-native-binary80.md](../superpowers/plans/2026-10-15-wsa-native-binary80.md) — WSA: componente binary80 nativo y contrato pendiente
- [2026-10-12-menus-android-design.md](../superpowers/specs/2026-10-12-menus-android-design.md) — Original menus and Android build

## docs/performance

- [PHASE14_CFG_ARCHITECTURE_MASTER_PLAN_2026-10-14.md](../performance/cfg/PHASE14_CFG_ARCHITECTURE_MASTER_PLAN_2026-10-14.md) — Fase 14 — Arquitectura de recompilación por regiones CFG (plan maestro)
- [PHASE14_CFG_INITIAL_RECOVERY_2026-10-14.md](../performance/cfg/PHASE14_CFG_INITIAL_RECOVERY_2026-10-14.md) — Fase 14A — CFG de siete funciones originales y comprobación independiente de PC x86
- [PHASE14_CFG_REFERENCE_SOURCES_2026-10-14.md](../performance/cfg/PHASE14_CFG_REFERENCE_SOURCES_2026-10-14.md) — Fase 14 — Fuentes de referencia para CFG y sustitución estructural (2026-10-14)
- [PHASE14B_STATE_BOUNDARIES_ORACLE_2026-10-15.md](../performance/cfg/PHASE14B_STATE_BOUNDARIES_ORACLE_2026-10-15.md) — Fase 14B — Fronteras de estado por byte y oráculo x86 bifurcado (2026-10-15)
- [PHASE14B_X87_BINARY80_SHARED_EPILOGUE_2026-10-15.md](../performance/cfg/PHASE14B_X87_BINARY80_SHARED_EPILOGUE_2026-10-15.md) — Fase 14B — Estado x87 binary80 y epílogo compartido (15 de octubre de 2026)
- [PHASE14C_CFG_AB_OFFLINE_RESULTS_2026-10-15.md](../performance/cfg/PHASE14C_CFG_AB_OFFLINE_RESULTS_2026-10-15.md) — Fase 14C — Resultados A/B de regiones originales, offline (2026-10-15)
- [PHASE14C_CFG_REGION_EXPERIMENT_PLAN_2026-10-15.md](../performance/cfg/PHASE14C_CFG_REGION_EXPERIMENT_PLAN_2026-10-15.md) — Fase 14C — Plan de regiones CFG verificables (2026-10-15)
- [PHASE14C_REAL_X86_GUARDED_RUNTIME_2026-10-15.md](../performance/cfg/PHASE14C_REAL_X86_GUARDED_RUNTIME_2026-10-15.md) — Fase 14C — Oráculo x86 original y dispatcher CFG con fallback (2026-10-15)
- [PHASE14D_EPILOGUE_FAULT_SAFETY_2026-10-15.md](../performance/cfg/PHASE14D_EPILOGUE_FAULT_SAFETY_2026-10-15.md) — Fase 14D — Epílogo x86, fallos de página y bloqueo de la región CFG insegura
- [PHASE14E_PRECISE_CHECKPOINTS_AND_RESUME_2026-10-15.md](../performance/cfg/PHASE14E_PRECISE_CHECKPOINTS_AND_RESUME_2026-10-15.md) — Fase 14E — Checkpoints x86 precisos, fallback original y coste ARM64
- [PHASE14F_ANDROID_FAULT_RECOVERY_CONTRACT_2026-10-15.md](../performance/cfg/PHASE14F_ANDROID_FAULT_RECOVERY_CONTRACT_2026-10-15.md) — Fase 14F — Contrato de recuperación segura de fallos guest en Android ARM64
- [PHASE14F_MEMORY_FREE_SUPERREGIONS_2026-10-15.md](../performance/cfg/PHASE14F_MEMORY_FREE_SUPERREGIONS_2026-10-15.md) — Fase 14F — Superregiones CFG originales sin memoria y oráculo x86 independiente
- [CODSP_PCODE_TEMP_DCE_2026-10-14.md](../performance/cpu/CODSP_PCODE_TEMP_DCE_2026-10-14.md) — CoDSP p-code → C: eliminación de temporales muertos (2026-10-14)
- [FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md](../performance/cpu/FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md) — Function-entry mapping and next performance investigations — 2026-10-14
- [ANGLE_BUILD_PIPELINE_2026-10-14.md](../performance/graphics/ANGLE_BUILD_PIPELINE_2026-10-14.md) — ANGLE: compilación Linux reproducible y aislada (2026-10-14)
- [ANGLE_GLES_VULKAN_FEASIBILITY_2026-10-14.md](../performance/graphics/ANGLE_GLES_VULKAN_FEASIBILITY_2026-10-14.md) — ANGLE: viabilidad GLES a Vulkan en CallofRecomp (14 de octubre de 2026)
- [ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md](../performance/graphics/ANGLE_WSA_GAMEPLAY_ABA_2026-10-14.md) — ANGLE/Vulkan frente a GL4ES: A1/B/A2 de gameplay 3D en WSA — 2026-10-14
- [ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md](../performance/graphics/ANGLE_WSA_REAL_GAME_TRIAL_2026-10-14.md) — ANGLE Android x86_64 en CallofRecomp: ensayo real WSA (2026-10-14)
- [GL_VK_STATE_BRIDGE_2026-10-14.md](../performance/graphics/GL_VK_STATE_BRIDGE_2026-10-14.md) — Hito del puente OpenGL → estado tipado Vulkan (WSA, 2026-10-14)
- [HUD_WIDESCREEN_2026-10-14.md](../performance/graphics/HUD_WIDESCREEN_2026-10-14.md) — Native panoramic camera with aspect-correct HUD (2026-10-14)
- [MESA_ZINK_FEASIBILITY_2026-10-14.md](../performance/graphics/MESA_ZINK_FEASIBILITY_2026-10-14.md) — Investigación real: Mesa Zink para CallofRecomp (14 de octubre de 2026)
- [RENDER_TRANSLATION_AUDIT_2026-10-14.md](../performance/graphics/RENDER_TRANSLATION_AUDIT_2026-10-14.md) — Renderer and x86-to-ARM64 translation audit — 2026-10-14
- [WSA_GL_MATRIX_BRIDGE_2026-10-14.md](../performance/graphics/WSA_GL_MATRIX_BRIDGE_2026-10-14.md) — Hito Vulkan WSA: matrices OpenGL 1.x y proyección (2026-10-14)
- [WSA_VULKAN_DEPTH_STENCIL_BLEND_2026-10-14.md](../performance/graphics/WSA_VULKAN_DEPTH_STENCIL_BLEND_2026-10-14.md) — Hito Vulkan WSA: depth/stencil y blending alfa (2026-10-14)
- [WSA_VULKAN_DX12_RENDERER_DECISION_2026-10-14.md](../performance/graphics/WSA_VULKAN_DX12_RENDERER_DECISION_2026-10-14.md) — Evaluación de Vulkan nativo, DirectX 12 y entorno WSA — 2026-10-14
- [WSA_VULKAN_INDEXED_MESH_2026-10-14.md](../performance/graphics/WSA_VULKAN_INDEXED_MESH_2026-10-14.md) — Hito Vulkan: geometría indexada y shaders nativos en WSA — 2026-10-14
- [WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md](../performance/graphics/WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md) — Benchmark por etapas: WSA actual → superficie Vulkan → juego final
- [WSA_VULKAN_TEXENV_ALPHA_2026-10-14.md](../performance/graphics/WSA_VULKAN_TEXENV_ALPHA_2026-10-14.md) — Vulkan WSA: TexEnv MODULATE/REPLACE + prueba alfa (2026-10-14)
- [WSA_VULKAN_TEXTURE_2026-10-14.md](../performance/graphics/WSA_VULKAN_TEXTURE_2026-10-14.md) — Vulkan WSA: subida real de texturas RGBA8 con staging y sampler
- [ARM64_DISPATCH_ENTRY_CACHE_2026-10-15.md](../performance/tecno/ARM64_DISPATCH_ENTRY_CACHE_2026-10-15.md) — ARM64: cache local de entrada completa de dispatch
- [ARM64_NARROW_RIGHT_SHIFT_2026-10-15.md](../performance/tecno/ARM64_NARROW_RIGHT_SHIFT_2026-10-15.md) — ARM64: desplazamientos logicos derechos estrechos
- [ARM64_OFFLINE_READY_2026-10-15.md](../performance/tecno/ARM64_OFFLINE_READY_2026-10-15.md) — ARM64: candidatas y procedimiento A/B/A/B preparado
- [ARM64_PERF_EXPERIMENTS_2026-10-14.md](../performance/tecno/ARM64_PERF_EXPERIMENTS_2026-10-14.md) — TECNO CK6n ARM64: experimentos posteriores a x87 — 14 de octubre de 2026
- [ARM64_RENDERER_CPU_FCOM_2026-10-14.md](../performance/tecno/ARM64_RENDERER_CPU_FCOM_2026-10-14.md) — CPU del renderizador en TECNO: auditoría GL4ES y comparaciones x87 (2026-10-14)
- [ARM64_SAFE_ICF_2026-10-15.md](../performance/tecno/ARM64_SAFE_ICF_2026-10-15.md) — ARM64: deduplicación segura de código y copias x87
- [ARM64_WSA_LOCAL_STATE_BINARY80_2026-10-15.md](../performance/tecno/ARM64_WSA_LOCAL_STATE_BINARY80_2026-10-15.md) — TECNO ARM64: primera adaptación del enlace local de WSA y referencia numérica binary80 — 2026-10-15
- [ARM64_X87_FCHS_SIGN_BITS_2026-10-16.md](../performance/tecno/ARM64_X87_FCHS_SIGN_BITS_2026-10-16.md) — ARM64: cambio exacto del signo binary80 en tres FCHS de CoDSP
- [ARM64_X87_NAN_BITS_2026-10-14.md](../performance/tecno/ARM64_X87_NAN_BITS_2026-10-14.md) — CoDSP ARM64: detección binaria x87 NaN — 14 de octubre de 2026
- [ARM64_X87_NORMAL_F2D_2026-10-14.md](../performance/tecno/ARM64_X87_NORMAL_F2D_2026-10-14.md) — CoDSP ARM64: fast path de conversión x87 normal a double — 2026-10-14
- [CPU_PHASE10_TECNO_P4_PROFILED_ABA_2026-10-14.md](../performance/tecno/CPU_PHASE10_TECNO_P4_PROFILED_ABA_2026-10-14.md) — Fase 10 — Validación física A/B/A de la conversión x87 perfilada de p4
- [CPU_PHASE11_P4_INLINE_OVERLAP_OFFLINE_2026-10-14.md](../performance/tecno/CPU_PHASE11_P4_INLINE_OVERLAP_OFFLINE_2026-10-14.md) — Fase 11 — Solapamiento de muestras CPU inline de CoDSP p4 (solo offline)
- [CPU_PHASE12_X87_STACK_SHIFT_OUTLINE_OFFLINE_2026-10-14.md](../performance/tecno/CPU_PHASE12_X87_STACK_SHIFT_OUTLINE_OFFLINE_2026-10-14.md) — Fase 12 — Consolidación estructural de movimientos de pila x87 en ARM64 (sin TECNO)
- [CPU_PHASE13_HOT_BLOCK_COMPILER_AB_OFFLINE_2026-10-14.md](../performance/tecno/CPU_PHASE13_HOT_BLOCK_COMPILER_AB_OFFLINE_2026-10-14.md) — Fase 13 — Optimización de chunks calientes completos (ARM64, offline)
- [CPU_PHASE2_41B8F0_AUDIT_2026-10-14.md](../performance/tecno/CPU_PHASE2_41B8F0_AUDIT_2026-10-14.md) — Fase 2 — Auditoría estructural de `0x0041B8F0` y ensayo x87 sin modificar el juego
- [CPU_PHASE2_FCOM_CONDITION_ORACLE_2026-10-14.md](../performance/tecno/CPU_PHASE2_FCOM_CONDITION_ORACLE_2026-10-14.md) — Fase 2 — Oráculo independiente de bits de condición x87 FCOMP
- [CPU_PHASE2_X86_PREFIX_ORACLE_2026-10-14.md](../performance/tecno/CPU_PHASE2_X86_PREFIX_ORACLE_2026-10-14.md) — Fase 2 — Oráculo diferencial x86 real para el prólogo de `0x0041B8F0`
- [CPU_PHASE2_X87_WINDOW_ORACLE_2026-10-14.md](../performance/tecno/CPU_PHASE2_X87_WINDOW_ORACLE_2026-10-14.md) — Fase 2 — Oráculo x87 acotado con salida `float32` exacta
- [CPU_PHASE3_P0_REGISTER_CACHE_TECNO_2026-10-14.md](../performance/tecno/CPU_PHASE3_P0_REGISTER_CACHE_TECNO_2026-10-14.md) — Fase 3 — Caché de registros virtuales en CoDSP p0 (TECNO CK6n, 2026-10-14)
- [CPU_PHASE4_ARCH_REGISTER_DCE_TECNO_2026-10-14.md](../performance/tecno/CPU_PHASE4_ARCH_REGISTER_DCE_TECNO_2026-10-14.md) — Fase 4 — eliminación de escrituras arquitectónicas muertas (TECNO CK6n, 2026-10-14)
- [CPU_PHASE5_OFFLINE_DISPATCH_CACHE_2026-10-14.md](../performance/tecno/CPU_PHASE5_OFFLINE_DISPATCH_CACHE_2026-10-14.md) — Fase 5 — auditoría offline y caché experimental del despachador (2026-10-14)
- [CPU_PHASE6_X87_P4_OFFLINE_2026-10-14.md](../performance/tecno/CPU_PHASE6_X87_P4_OFFLINE_2026-10-14.md) — Fase 6 — ampliación x87 normal→double a p4, evaluación offline (2026-10-14)
- [CPU_PHASE7_P4_SELECTIVE_X87_OFFLINE_2026-10-14.md](../performance/tecno/CPU_PHASE7_P4_SELECTIVE_X87_OFFLINE_2026-10-14.md) — Fase 7 — CoDSP p4: conversión x87 selectiva por PC original, OFFLINE
- [CPU_PHASE8_P4_PROFILE_GUIDED_X87_OFFLINE_2026-10-14.md](../performance/tecno/CPU_PHASE8_P4_PROFILE_GUIDED_X87_OFFLINE_2026-10-14.md) — Fase 8 — selección x87 por muestras históricas y PC original (offline)
- [CPU_PHASE9_X87_INTEGER_PACK_OFFLINE_2026-10-14.md](../performance/tecno/CPU_PHASE9_X87_INTEGER_PACK_OFFLINE_2026-10-14.md) — Fase 9 — Auditoría offline del empaquetado x87: optimización descartada
- [PERFORMANCE_STRATEGY_RUN_2026-10-14.md](../performance/tecno/PERFORMANCE_STRATEGY_RUN_2026-10-14.md) — Ejecución de PERFORMANCE_STRATEGY_CURRENT — TECNO (2026-10-14)
- [PHASE15_TECNO_CPU_PROFILE_CROSSCUTTING_2026-10-15.md](../performance/tecno/PHASE15_TECNO_CPU_PROFILE_CROSSCUTTING_2026-10-15.md) — Fase 15 — Perfiles TECNO originales, presupuesto por fotograma y oportunidades transversales
- [README.md](../performance/tecno/README.md) — Investigación TECNO CK6n ARM64 — objetivo vigente
- [TECNO_ARM64_HOT_FLD32_2026-10-16.md](../performance/tecno/TECNO_ARM64_HOT_FLD32_2026-10-16.md) — TECNO ARM64 — FLD32 exacto en CoDSP 0x005061B0
- [TECNO_ARM64_MEM_DISPATCH_AUDIT_2026-10-16.md](../performance/tecno/TECNO_ARM64_MEM_DISPATCH_AUDIT_2026-10-16.md) — TECNO ARM64 — reducción de accesos a memoria y dispatch: resultados físicos y offline
- [TECNO_CK6N_ARM64_PERF_2026-10-14.md](../performance/tecno/TECNO_CK6N_ARM64_PERF_2026-10-14.md) — TECNO CK6n: medición real de CallofRecomp ARM64 — 2026-10-14
- [TECNO_FCHS_SIGN_ABAB_2026-10-16.md](../performance/tecno/TECNO_FCHS_SIGN_ABAB_2026-10-16.md) — TECNO CK6n — A/B/A/B físico para ARM64 FCHS sign-bit (2026-10-16 UTC)
- [TECNO_RELEASE024_ABAB_2026-10-15.md](../performance/tecno/TECNO_RELEASE024_ABAB_2026-10-15.md) — TECNO CK6n: revalidación física de 0.2.4
- [TECNO_STABILITY_GATE_2026-10-15.md](../performance/tecno/TECNO_STABILITY_GATE_2026-10-15.md) — TECNO ARM64 — estabilidad de mediciones y conservación de pequeñas mejoras (15-10-2026)
- [TECNO_X87_NORMAL_F2D_GAMEPLAY_ABAB_2026-10-14.md](../performance/tecno/TECNO_X87_NORMAL_F2D_GAMEPLAY_ABAB_2026-10-14.md) — TECNO CK6n ARM64 — A/B/A/B de x87 normal f2d y descarte de geometry -O2 (2026-10-14)
- [README.md](../performance/wsa/README.md) — Investigación WSA x86_64
- [WSA120_BASELINE_2026-10-15.md](../performance/wsa/WSA120_BASELINE_2026-10-15.md) — WSA 120 FPS: primera línea base y límites comprobados
- [WSA120_LIMITER_AND_RENDERER_PROFILE_2026-10-15.md](../performance/wsa/WSA120_LIMITER_AND_RENDERER_PROFILE_2026-10-15.md) — WSA 120 FPS: control reversible y perfil del renderer
- [WSA120_NATIVE_X87_STATE_2026-10-15.md](../performance/wsa/WSA120_NATIVE_X87_STATE_2026-10-15.md) — WSA: estado x87 y oráculo nativo x86
- [WSA120_OPTIMIZED_APK_CPU_PROFILE_2026-10-15.md](../performance/wsa/WSA120_OPTIMIZED_APK_CPU_PROFILE_2026-10-15.md) — WSA 120 FPS — Perfil de CPU de la APK acumulativa REALMENTE instalada
- [WSA_CUMULATIVE_2026-10-15.md](../performance/wsa/WSA_CUMULATIVE_2026-10-15.md) — Integración acumulativa WSA — 2026-10-15
- [WSA_POSTOPT_APPLICATION_2026-10-15.md](../performance/wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md) — Aplicación del perfil de la APK optimizada — 2026-10-15
- [WSA_X87_NORMAL_F2D_ABA_2026-10-14.md](../performance/wsa/WSA_X87_NORMAL_F2D_ABA_2026-10-14.md) — WSA — A/B/A de conversion x87 normal f2d (2026-10-14)
