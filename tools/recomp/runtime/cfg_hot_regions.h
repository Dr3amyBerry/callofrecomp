// Phase14C CoDSP 1.5 gated, PRIVATE p-code-derived CFG-region helper.
// Declaration only; implementation is generated into ignored recomp_out.
// Normal builds neither link it nor execute an extra dispatcher branch.
#pragma once

#ifdef __cplusplus
extern "C" {
#endif

// Return 1 only when PC=0x0041c017 was executed and R was flushed.
// Return 0 without mutation on any other PC, allowing original fallback.
int codsp_cfg14_geom_41c017(void);

#ifdef __cplusplus
}
#endif
