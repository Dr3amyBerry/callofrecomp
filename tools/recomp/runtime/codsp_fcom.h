// Opt-in CoDSP x87 FCOM/FCOMP speed path for exact generated p-code shapes.
// Replaces one complete compare/status/FPU-pop block only after strict
// source-pattern verification. Preserves guest registers and memory state
// according to the CURRENT recomp_rt.h binary80 lowering, not an x86 oracle.
#pragma once
#include "x87_nan_bits.h"
#include <stdint.h>
#include <string.h>
#include <math.h>

#if defined(CODRECOMP_X87_FCOM_FASTPATH)
static inline int codsp_fcom_pop_float32(uint8_t *restrict regs,
                                          const uint8_t *restrict mem,
                                          uint32_t guest_pc,
                                          uint32_t address) {
    // Original p-code records the guest instruction address before LOAD.
    wr(regs + 0x10ac, 4, guest_pc);
    const double lhs = f2d(rd(regs + 0x1100, 10), 10);
    // The source is a binary32 load, widened to binary80 and compared.
    // All binary32 values (including nonfinite) yield the same x87 flags
    // as that conversion chain under current p-code semantics.
    const double rhs = f2d(rd(mem + address, 4), 4);
    const int unordered = isnan(lhs) || isnan(rhs);
    const uint8_t c0 = (uint8_t)(unordered || lhs < rhs);
    const uint8_t c1 = 0;
    const uint8_t c2 = (uint8_t)unordered;
    const uint8_t c3 = (uint8_t)(unordered || lhs == rhs);
    wr(regs + 0x1090, 1, c0);
    wr(regs + 0x1091, 1, c1);
    wr(regs + 0x1092, 1, c2);
    wr(regs + 0x1093, 1, c3);
    wr(regs + 0x10a2, 2,
       ((uint16_t)c0 << 8) | ((uint16_t)c1 << 9) |
       ((uint16_t)c2 << 10) | ((uint16_t)c3 << 14));
    // The translated instruction pops ST0 once; each ST slot has 16-byte
    // spacing but only 10 live bytes. Do not overwrite the padding.
    for (unsigned i = 0; i < 7; ++i)
        memcpy(regs + 0x1100 + 16 * i, regs + 0x1110 + 16 * i, 10);
    return 1;
}
#define CODSP_FCOM_GUARD(regs,mem,pc,addr) codsp_fcom_pop_float32((regs),(mem),(pc),(addr))
#else
// Macro, not function: don't evaluate operands in the OFF/default build.
#define CODSP_FCOM_GUARD(regs,mem,pc,addr) 0
#endif
