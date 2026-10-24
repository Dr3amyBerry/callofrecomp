/* Compiled twice (reference and CODRECOMP_ARM64_X87_CONV_FAST) with a
   different CONV_PREFIX; linked with x87_conv_fast_main.c. Host-only oracle. */
#include "recomp_rt.h"
#define CAT2(a, b) a##b
#define CAT(a, b) CAT2(a, b)
uint64_t CAT(CONV_PREFIX, _f2d10)(uint64_t lo, unsigned se) {
    double d = f2d(((u128)se << 64) | lo, 10);
    uint64_t b; memcpy(&b, &d, 8); return b;
}
void CAT(CONV_PREFIX, _d2f10)(uint64_t bits, uint64_t *lo, unsigned *se) {
    double d; memcpy(&d, &bits, 8);
    u128 r = d2f(d, 10);
    *lo = (uint64_t)r; *se = (unsigned)(r >> 64);
}
