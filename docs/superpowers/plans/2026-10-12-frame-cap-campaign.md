# 60 FPS and campaign progression verification

Goal: cap native PC/Android rendering at 60 FPS, preserve movement/interpolation,
and investigate progression across every original single-player level.

Use systematic-debugging and executing-plans. User authorizes implementation,
commit and push to main. No original scripts/assets/generated C enter Git.

- [x] Measure current frame times; reproduce uncapped config (`com_maxfps=0`).
- [x] Add a monotonic 60 FPS presentation limiter with regression coverage for
  fractional clock periods, slow frames and clock reset. Keep original simulation
  timing and cg_nopredict=0. Set Android's original maxfps to 60.
- [x] Build PC and both Android ABIs. Earlier PC/WSA timing measured; final
  gameplay measurements delegated to the user at their explicit request.
- [x] Audit owned campaign scripts, required map resources and mission exits.
  Keep static graph validation distinct from real mission completion.
- [x] Exercise all 33 map startups with private inputs and fix numerical blockers.
  A transition fixture exposed the DLL lifecycle blocker; implemented fixes.
  Final transitions/save/load and full objectives delegated to user flash-mode QA.
- [ ] Review, run regressions, commit/push, verify CI and report remaining
  playthrough coverage honestly. Loading all maps is not proof of completability.

Runtime investigation found incorrect ten-byte x87 storage consumed by the
original embedded CRT. Regression tests and native yaw comparisons cover the
fix; previously stalled Brecourt and Hurtgen now initialize normally. A private
forced-success training fixture reached victory and then `Server: us_intro`.
That isolates transition handling only, and does not complete training objectives.
