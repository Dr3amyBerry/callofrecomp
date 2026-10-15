# Clasificación funcional de los primeros 200 scripts históricos

Auditoría estática de **200 scripts reales**, comparados con sus dos manifiestos SHA256. No se ejecutó ningún script legado ni se modificó o eliminó su archivo original. Esta clasificación es una decisión de mantenimiento, no una garantía de compatibilidad de ejecución.

| Categoría | Cantidad | Tratamiento |
|---|---:|---|
| Patrón aprovechado en herramienta permanente | 3 | Extraer funcionalidad generalizable; conservar originales |
| Editor puntual | 103 | No reejecutar sobre fuentes actuales; mantener como historial |
| Experimento/inspección de entradas fijadas | 94 | Conservar con evidencia, oráculo y configuración |

## Herramienta canónica resultante

`tools/recomp/diagnostics/profile_evidence.py` cubre tres capacidades antes codificadas con rutas fijas de sesiones TECNO:

- `inventory --root .local/profiles`: inventario acotado de perfiles sin recorrer enlaces de terceros.
- `hash --root .local/profiles --files RUTA1 RUTA2`: huellas SHA256 de entradas explícitas.
- `hash ... --output runs/.../metrics/sha.json`: guarda manifiesto sin sobrescribir en una sesión existente.
- `verify --root .local/profiles --manifest runs/.../metrics/sha.json`: detecta evidencia alterada.
- `metadata --root .local/profiles --files A.json B.json --require-same-build`: lee campos acotados y comprueba Build ID; no estima FPS.

**Ninguno de los tres archivos antiguos se vuelve a ejecutar como una utilidad general.** El patrón se reimplementó con CLI, rutas de entrada, pruebas y validación. Las verificaciones x86/CFG/x87 específicas continúan sujetas al oráculo original o a las herramientas y tests canónicos del repositorio.

## Reglas para las otras IAs

- Scripts que modifican textos, código o pruebas una vez: escribir el cambio, revisar diff, hacer tests y conservar solo evidencia útil; no crear un editor reusable por párrafo.
- Scripts experimentales: fijar entradas, versión y resultados; no ejecutar un experimento viejo suponiendo que la ABI, el perfil o el Build ID siguen iguales.
- Para verificaciones nuevas, buscar primero en `tools/`. Si falta una capacidad repetida, crear una utilidad parametrizada con pruebas y rechazo seguro de entradas, no versiones `v2` y `final` de scripts temporales.
- Los dos archivos históricos de 100 deben conservarse íntegros. Esta catalogación no autoriza borrar, fusionar ni mover scripts nuevos.

## Inventario completo, clasificado por código

Las pistas de edición se derivan de llamadas AST de escritura y literales de rutas (revisión estática). Los demás scripts se guardan como estudios de escenario; algunas verificaciones podrían promocionarse en una auditoría futura, pero ninguna se declara portátil sin refactor y tests.

### Funciones extraídas para reutilización (3)

| Archivo (lote) | Qué hace / evidencia | Acción |
|---|---|---|
| `phase15_compare_capture_hashes.py` (L2) | Generalized into profile_evidence.py hash | CLI permanente |
| `phase15_inventory_existing_perf.py` (L2) | Inventory archived TECNO Simpleperf evidence; print paths/size only. | CLI permanente |
| `phase15_two_session_check.py` (L2) | Generalized into profile_evidence.py metadata | CLI permanente |

### Parches y ediciones puntuales (103)

| Archivo (lote) | Qué hace / evidencia | Acción |
|---|---|---|
| `add_final_apk_verification_phase4.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `add_recent_dispatch_bench_target.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `fix_dispatch_bench_overflow.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `fix_regcache_source_diff.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `fix_tecno_report_eof.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase10_clean_md.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase10_finalize_docs.py` (L1) | Finish already completed TECNO Phase 10 documentation, no device interaction. | No reejecutar |
| `phase11_link_docs.py` (L1) | Link Phase 11 offline sample analysis, without touching Android or builds. | No reejecutar |
| `phase11_note_tests.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase12_builder_guards.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase12_fix_builder_test.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase12_link_docs.py` (L1) | Register the verified Phase 12 structural ARM64 offline work. | No reejecutar |
| `phase12_patch_builder.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase12_patch_generator.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase13_exclude_visibility_o2.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase13_fix_comment.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase13_fix_width.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase13_hotcore_integrate.py` (L1) | Add one opt-in, profile-grounded whole-core ARM64 optimization switch. | No reejecutar |
| `phase13_link_docs.py` (L1) | Link Phase13 measured offline whole-hot-core experiment to roadmap. | No reejecutar |
| `phase13_note_tests.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase13_patch_chunk_cache.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase13_patch_codegen.py` (L1) | Phase13 opt-in CoDSP scalar temporaries across geometry/visibility/traversal. | No reejecutar |
| `phase14b_add_test.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14b_fix_oracle.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14b_negative_control.py` (L1) | Private-only negative control: corrupt translated branch PC, require oracle rejection. | No reejecutar |
| `phase14b_refine.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14c_add_start_entry.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14c_checkpoint_docs.py` (L1) | Append completed checkpoint notes without replacing unrelated project history. | No reejecutar |
| `phase14c_delegate_fix.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14c_delegation_test_patch.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14c_digest_fix.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14c_doc_checkpoint.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14c_finalize_docs.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14c_fix_epilogue_test.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14c_fix_probe.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14c_fix_x87_import.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14c_gate_patch.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14c_lab_fix.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14c_negative_flush.py` (L1) | Private mutation test: remove region cache writeback, reject altered R. | No reejecutar |
| `phase14c_patch_x87.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14c_x87_metadata_guard.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14d_cmake_patch.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14d_exact_memory_patch.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14d_finalize_counts.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14d_fix_alias1.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14d_fix_report_keys.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14d_integrated_negative.py` (L1) | Negative control: remove ESP writeback from PRIVATE integrated helper. | No reejecutar |
| `phase14d_oracle_fix1.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14d_runtime_compile.py` (L1) | Compile exact derived private helper as host DLL + NDK ARM64 object. | No reejecutar |
| `phase14d_runtime_guard_patch.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14d_runtime_verify40.py` (L1) | Independent original x86 comparison with production-shaped opt-in helper. | No reejecutar |
| `phase14d_update_docs.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_add_builder_reject_test.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_add_deep_tail_tests.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_add_memory_access_trace.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_add_original_A_fallback.py` (L1) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_allow_pinned_call.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_audit_select_checkpoint.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_block_cmake_unsafe.py` (L2) | Fail-closed: original guest memory faults leave 15/18 unsafe R/PC snapshots. | No reejecutar |
| `phase14e_block_microbranch_reorder.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_builder_fault_block.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_clear_tf.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_dirty_selective_patch.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_docs_checkpoint.py` (L2) | Persist phase14D epilogue + memory exception safety findings. | No reejecutar |
| `phase14e_epilogue_debug.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_epilogue_debug_bytes.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_expand_failure_path.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_extend_checkpoint_tests.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_fault_gate_patch.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_fault_positive_control.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_finalize_docs_v2.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_finalize_validation_docs.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_fix_direct_memory.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_fix_so_path.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_ip_shadow_fix.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_new_A_restart_paths.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_patch_every_guest_memory.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_patch_exception_checkpoint.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_progress_docs_v2.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_rdiff.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_rename_checkpoint_run.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_rename_dirty_evidence.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14e_tail_negative.py` (L2) | Private negative control: wrong shared error-target PC MUST fail Unicorn. | No reejecutar |
| `phase14e_test_cmake_guard.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14f_add_branch_outcome_report.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14f_add_coverage_tests.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14f_cfg_docstring.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14f_finalize_counts.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14f_fix_suite.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase14f_update_docs.py` (L2) | Update one authoritative Phase14F status and prior-phase pointers. | No reejecutar |
| `phase15_finalize_test_evidence.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase15_fix_buildid_script.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase15_fix_import_order.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase15_update_progress_docs.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase2_geometry_o2_experiment.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase2_x87_doc_links.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase6_add_p4_x87.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase6_complete_if_verified.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase6_fix_scan.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase6_oracle_debug_patch.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase6_oracle_finite_only.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase6_outofline_transform.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |
| `phase6_reject_nonline_p4.py` (L2) | Mutates source/docs/tests (static paths/call evidence) | No reejecutar |

### Experimentos y verificaciones contextuales (94)

| Archivo (lote) | Qué hace / evidencia | Acción |
|---|---|---|
| `tecno_live_screenshot.py` (L1) | Runs a pinned offline experiment/probe | Historial de experimento |
| `tecno_screen_small.py` (L1) | Runs a pinned offline experiment/probe | Historial de experimento |
| `add_hot_edge_cases.py` (L1) | Writes study evidence/fixtures | Historial de experimento |
| `fix_codsp_copy32_fixture.py` (L1) | Writes study evidence/fixtures | Historial de experimento |
| `phase12_all_generated_roundtrip.py` (L1) | Verify round-trip fusion on ALL existing generated CoDSP partition C sources; no writes. | Historial de experimento |
| `phase12_all_pcode_plan.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase12_compile_full_p4.py` (L1) | Compile the EXISTING complete private CoDSP p4 partition A/B on ARM64, offline. | Historial de experimento |
| `phase12_compile_hot_chunks.py` (L1) | Audit two real CoDSP hot generated chunks: ARM64 native size and shift candidates, offline. | Historial de experimento |
| `phase12_structural_hot_groups.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase12_x87_copy_patterns.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase13_check_ninja_order.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase13_chunk_registers.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase13_chunks_ab.py` (L1) | Compare full historical hot CoDSP chunks A/B, original and cached GPR/flags. | Historial de experimento |
| `phase13_cmake_validate.py` (L1) | Isolated Android-NDK CMake configure and native flag verification (no device). | Historial de experimento |
| `phase13_dce_compare.py` (L1) | Read-only ARM64 A/B of existing cross-instruction flag-driven dead unique pass. | Historial de experimento |
| `phase13_dce_hot.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase13_full_p4_o2.py` (L1) | Full production-shaped CoDSP p4 ARM64 offline -O1 vs -O2. | Historial de experimento |
| `phase13_one_reg_compare.py` (L1) | Compare one native cross-instruction register promoted per full hot chunk. | Historial de experimento |
| `phase13_opt_levels.py` (L1) | Offline codegen optimization levels on three complete hot CoDSP chunks. | Historial de experimento |
| `phase13_scalar_native_ab.py` (L1) | Compile broad profiled CoDSP geometry, traversal, and visibility samples to ARM64. | Historial de experimento |
| `phase13_scalar_unique_stats.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14b_arch_writes.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14b_compiler_probe.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14b_probe_branches.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14b_run_oracle.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14b_summarize_state.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14c_epilogue_probe.py` (L1) | Private static audit of shared CFG external exit and Ghidra ownership. | Historial de experimento |
| `phase14c_exact_eligibility.py` (L1) | Writes study evidence/fixtures | Historial de experimento |
| `phase14c_exit_structure.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14c_final_report_read.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14c_hot_regions_scan.py` (L1) | Phase 14C private structural scan: rank safe original CFG block regions. | Historial de experimento |
| `phase14c_report_digest.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14c_run_binary80.py` (L1) | Private Windows path-safe entrypoint to actual original binary80 audit. | Historial de experimento |
| `phase14c_run_binary80_v2.py` (L1) | Private rerun after independent FSTP m80 selftest. | Historial de experimento |
| `phase14c_run_epilogue.py` (L1) | Run private shared-epilogue verification against pinned CoDSP original. | Historial de experimento |
| `phase14c_run_strict.py` (L1) | Strict fail-closed x87 gate: a mismatch MUST reject candidate fidelity. | Historial de experimento |
| `phase14c_x87_physical_slots.py` (L1) | Synthetic Unicorn x87 state probe, no commercial executable. | Historial de experimento |
| `phase14d_builder_flag_smoke.py` (L1) | Direct CLI parser rejection smoke: no SDK or APK build invoked. | Historial de experimento |
| `phase14d_cmake_onoff_v3.py` (L1) | CMake OFF/ON CFG14 policy + isolated Android arm64 object build. | Historial de experimento |
| `phase14d_emit_helper.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14d_env_probe.py` (L1) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14d_oracle_block_probe.py` (L1) | Private CoDSP original CFG block instruction and guest memory inspection. | Historial de experimento |
| `phase14d_run_40cases.py` (L1) | Full 40-case independent x86 original geometry CFG validation. | Historial de experimento |
| `phase14d_verify_link_symbols.py` (L1) | Confirm OFF guest object excludes CFG14, ON linker symbols match exactly. | Historial de experimento |
| `phase14e_checkpoint_risks.py` (L2) | Private analysis: exception-atomicity risk for original CFG memory x86 insns. | Historial de experimento |
| `phase14e_epilogue_layout.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14e_explicit_m_operands.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14e_legacy_private_hash_regression.py` (L2) | Private provenance regression: normal OFF helper output is byte-identical. | Historial de experimento |
| `phase14e_link_progress.py` (L2) | Runs a pinned offline experiment/probe | Historial de experimento |
| `phase14e_locate_linked_so.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14e_memory_free_scan.py` (L2) | Find no-guest-memory original CFG blocks under phase14C's hot entries. | Historial de experimento |
| `phase14e_run_fault1.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14e_run_fault3.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14e_run_freegeom5.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14e_run_freevis5.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14e_run_strict_fault_gate.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14e_run_tail128.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14e_run_tail_firstcall64.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14e_verify_direct_cmake_gate.py` (L2) | Verify CMake itself refuses known-unsafe CFG14 ON even without builder. | Historial de experimento |
| `phase14f_branch_nodes.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14f_coverage_geom7.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14f_coverage_geom8.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14f_coverage_vis7.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14f_print_paths.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14f_print_readiness.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14f_read_branch_matrix.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14f_report_branch_coverage.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14f_run_geom7.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14f_run_geom8.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14f_run_strict_scanner.py` (L2) | Writes study evidence/fixtures | Historial de experimento |
| `phase14f_run_vis7.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14f_runtime_fault_context.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14f_runtime_guard_lines.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase14f_scan_superedges.py` (L2) | Writes study evidence/fixtures | Historial de experimento |
| `phase15_count_raw_samples.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase15_examine_hot_guest_pcs.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase15_find_translator_flags.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase15_hot_op_inspect.py` (L2) | Private-only pinpoint hot original PC and p-code micro-op taxonomy. | Historial de experimento |
| `phase15_inspect_profile_schemas.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase15_perf_id_recheck.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase15_popcount_probe.py` (L2) | Measure width-specialized POPCOUNT without changing real game code. | Historial de experimento |
| `phase15_popcount_widths.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase15_read_budgets.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase15_sampled_op_category_summary.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase6_archive_p4.py` (L2) | Archive A/B comparison of opt-in CoDSP p4 x87 conversion, offline only. | Historial de experimento |
| `phase6_build_process_inventory.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase6_compare_old_perf.py` (L2) | Offline compare available archived profiled ELFs to perf data, without ADB. | Historial de experimento |
| `phase6_count_f2d_codegen.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase6_memmove_callchains.py` (L2) | Inspect only archived 350Hz CPU profile for memmove caller frames. | Historial de experimento |
| `phase6_p4_insn_preview.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase6_p4_map_ranges.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase6_p4_symbol_delta.py` (L2) | Offline p4 ARM64 ELF static comparison; no device access. | Historial de experimento |
| `phase6_partition_hotspots.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |
| `phase6_simpleperf_stack_contract.py` (L2) | Reads/verifies pinned experiment inputs | Historial de experimento |

## Reproducibilidad

- Generar/revisar: `python tools/review_archived_scripts.py --check`; solo en caso de cambios deliberados en el catálogo: `--write`.
- Evidencia detallada privada con SHA256, invocaciones y referencias: `.local/catalog/archived_script_roles_first200.json`.
- Manifiestos inmutables: `.local/catalog/archived_legacy_scripts_2026-10-15.json` y `.local/catalog/archived_legacy_scripts_2026-10-15_batch02.json`.
