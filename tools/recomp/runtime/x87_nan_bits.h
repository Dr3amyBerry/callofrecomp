// CoDSP original x87 FLOAT_NAN can be computed directly from binary80 bits.
// Equivalent to isnan(f2d(bits, 10)) in the CURRENT recomp_rt.h semantics:
// - nonzero exponent with explicit J bit clear -> unsupported encoding -> NaN
// - all-one exponent and nonzero fraction -> NaN
// - canonical infinity and finite/pseudo-denormal inputs -> not NaN
// Unlike numeric x87 arithmetic, this helper does not round or normalize.
// It does not model host floating-point exception status (neither does the
// guest register array for FLOAT_NAN).
#pragma once
#include "recomp_rt.h"

static inline int codsp_x87_isnan_bits(u128 bits) {
    const uint64_t sig = (uint64_t)bits;
    const unsigned exponent = (unsigned)(bits >> 64) & 0x7fffu;
    const uint64_t fraction = sig & UINT64_C(0x7fffffffffffffff);
    const int explicit_integer_bit = (sig >> 63) != 0;
    return (exponent && !explicit_integer_bit) ||
           (exponent == 0x7fffu && fraction != 0);
}

// The generated source uses this wrapper only at selected, verified original
// CoDSP 1.5 FLOAT_NAN p-code expressions. No private game code is published.
// OFF preserves precisely the former f2d/isnan sequence.
#if defined(CODRECOMP_X87_NAN_BITS)
#define CODSP_X87_ISNAN(v) codsp_x87_isnan_bits(v)
#else
#define CODSP_X87_ISNAN(v) isnan(f2d((v), 10))
#endif
