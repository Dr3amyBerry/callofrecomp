// Restricted CoDSP 1.5 ARM64 experiment: exact ordinary float32 -> binary80.
//
// Only normal finite IEEE binary32 inputs use the bit mapping.  Every other
// pattern (signed zero, subnormal, +/-Inf, qNaN/sNaN and their payloads) takes
// the SAME pre-existing f2d/d2f route.  This does not write x87 status, TOP,
// tags, flags, guest PC or memory.  Include only after recomp_rt.h has defined
// u128, f2d and d2f.  Call only at 39 hash-verified FLD/m32 operands.
#pragma once
#include <stdint.h>

static inline u128 codsp_x87_fld32_normal(u128 raw) {
    const uint32_t bits = (uint32_t)raw;
    const unsigned exp32 = (bits >> 23) & 255u;
    if ((unsigned)(exp32 - 1u) < 254u) {
        const uint64_t significand =
            UINT64_C(0x8000000000000000) |
            ((uint64_t)(bits & UINT32_C(0x007fffff)) << 40);
        const unsigned sign_exponent =
            ((bits >> 16) & 0x8000u) | (exp32 + 16256u);
        return ((u128)sign_exponent << 64) | significand;
    }
    return d2f(f2d(raw, 4), 10);
}
