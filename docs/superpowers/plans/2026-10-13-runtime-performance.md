# CPU and graphics translation performance implementation plan

> **For agentic workers:** Use superpowers:executing-plans for the main CPU task; the independent graphics patch task is delegated under superpowers:dispatching-parallel-agents.

**Goal:** Reduce CPU work in recompilation and graphics translation without changing game state or requiring phones.

**Architecture:** Guest RAM is an OS-reserved mapping disjoint from register and temporary arrays. Expose that existing invariant to the compiler within supported generated chunks, preserving aliases within each space. Apply a minimal audited patch to the pinned GL4ES dependency to skip identity normalization of index arrays.

**Tech stack:** Python p-code generator, C11, LLVM/Android NDK, SDL2, pinned GL4ES, CTest.

**Spec:** User requests general CPU/GPU performance improvement without phones; all visual checks remain with the user. Previous phone diagnostics showed engine-thread CPU dominating frame time, including graphics translation work.

## Constraints

- No phones, screenshots, UI inspections or fabricated FPS claims.
- Original resources and private generated code remain ignored/local; public APKs omit original assets.
- Keep 60 FPS cap and image aspect ratio; preserve exact register/memory effects.
- Compiler optimization must retain a diagnostic baseline path and safe fallback for unsupported user operations.
- Graphics dependency must remain pinned with a reproducible, idempotent, fail-closed patch.

## Tasks

- [x] Save the measured negative Tecno outcome and detailed diagnostics with normal profiling default OFF.
- [x] Add compiled state-equivalence tests for separate register/RAM optimization, including aliasing within spaces, indirect guest addresses, float state, branches and unsupported fallback.
- [x] Implement scoped non-aliasing pointers in supported chunks; compare generated baselines with optimized code at O1 and O2 before retaining it.
- [x] Measure isolated CPU cost with identical inputs; regenerate all private modules and build final Android artifacts.
- [x] Patch zero-minimum index normalization; verify pinned source, exact output, idempotence and unexpected-source rejection with no GPU.
- [x] Integrate the patch into Android build tooling, run full host tests and review the changes.
- [x] Build/sign private local and public resource-free APKs, record limitations, commit and push.

## Review focus

- Byte-overlapping registers and guest RAM accesses must keep their original ordering.
- Host helpers accessing guest state must not violate scoped pointer assumptions.
- Unsupported operations retain the global-space diagnostic path.
- Empty indices preserve untouched min/max outputs; both 16-bit and 32-bit maximum indices remain exact.
- Improvements in microbenchmarks do not certify phone FPS or GPU frame time.

## Execution ledger

- Tests: 18 CTest targets pass; 9 recompilation tests include O1/O2 full-state equivalence; GL4ES 40k cases and protected buffers pass. Fresh review reports no blockers.
- Measurement: owned O1 benchmark 228-229 ms baseline vs 59-76 ms separated spaces; ARM64 static workload 337 vs 77 instructions. No FPS inference.
- Ruling: use restrict helper parameters rather than local restrict pointers, because local-pointer form showed no timing improvement while parameters produced compiler alias metadata and equivalent state.
- Ruling: build ARM64 artifacts for the requested phone target; no WSA/phone execution or x86 rebuild is necessary to validate this change.
- ARM64 compilation, public resource audit, private bundling, signature/alignment/CRC checks completed. Cache and native strings confirm CPU profiling OFF. Public/private native libraries match. No phones or visual checks used.
- Follow-up: CRLF fixture exposed Windows patch mismatch; stdin patch now follows target line endings, test passes. Builder invokes the patch CLI to preserve standalone module import used by the private packager.
