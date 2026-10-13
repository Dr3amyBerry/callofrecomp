# Crowded scene CPU performance

User reports Samsung falling to about 5 FPS near training wire, firing machineguns
and crawling soldiers. Work without phones or visual checks; build private local
APK, test automatically, commit and push. No claim that synthetic speed fixes FPS.

Evidence: prior sampled engine chunks contain many flag computations and binary80
conversions. Standard GLES2 draws already pass arrays directly; more geometry copies
or blind GL4ES switches are not justified by that source audit.

- [x] Compile differential float conversion reference and benchmark common values.
- [x] Keep a normal binary80 fast path only if exact results and speed are proven.
- [x] Analyze byte-level flag liveness with conservative external/unknown exits.
- [x] Integrate only proven dead flag writes while preserving p-code indices.
- [x] Compile baseline/optimized randomized full-state tests, including branches.
- [x] Measure owned crowded-work analogues; regenerate private native modules.
- [ ] Full host tests, independent review, ARM64 build and local APK verification.
- [ ] Update progress, commit and push; leave gameplay checks to user.

## Rulings

- Focus on CPU work matching existing hot chunk evidence. The scene report alone
  does not prove soldiers, particles or the GPU are the dominant cause.
- Preserve simulation, soldiers, objectives and profile quality. Do not trade
  mission correctness for performance or force unsafe VBO/batching switches.

## Evidence ledger

- User confirms Samsung runs the previously installed APK, not the later local separate-spaces build. New 0.2.3 includes both optimization phases.
- Flags owned benchmark pairs: 622/574/575 ms vs458/458/452 ms, identical full R and checksum. Float canonical benchmark 25/28/26 vs22/20/25 ms; small/noisy, no whole-game inference.
- 14 flag dataflow tests, compiled full-state O1/O2 test and 262144 raw binary80 cases pass; full CTest18 passes.
- Independent review found no production blockers. Fixed optional unsorted empty-block CFG mismatch and added regression.
- ARM64 full rebuild pending. No phones, visual checks or speculative graphics switches.

- Ruling: withdraw binary80 fast-path experiment after ARM64 hot chunk186 grew186724->201664 bytes (8%). Tiny host conversion gain does not justify added instruction-cache footprint. Final floating conversion remains unchanged; removed redundant comparison fixture/benchmark. Rebuilt host suite passes.
