#define CODRECOMP_X87_NORMAL_F2D 1
#include "recomp_rt.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>

static uint32_t state = 0x89abcdefu;
static uint32_t rng(void) {
    uint32_t x = state;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    return state = x;
}
static int cases = 0, fast = 0;
static int verify(unsigned se, uint64_t sig) {
    u128 bits = ((u128)se << 64) | sig;
    // (f2d) disables the function-like opt-in macro and calls original.
    double reference = (f2d)(bits, 10);
    double candidate = f2d(bits, 10);
    uint64_t a, b;
    memcpy(&a, &reference, 8);
    memcpy(&b, &candidate, 8);
    if (a != b) {
        fprintf(stderr, "binary80 mismatch se=%04x sig=%016llx expected=%016llx got=%016llx\n",
                se, (unsigned long long)sig,
                (unsigned long long)a, (unsigned long long)b);
        return 0;
    }
    cases++;
    if ((unsigned)((se & 0x7fff) - 15361u) <= 2045u &&
        (sig & UINT64_C(0x80000000000007ff)) ==
             UINT64_C(0x8000000000000000))
        fast++;
    return 1;
}
int main(void) {
    static const uint64_t special[] = {
        0, 1, 0x7ff, 0xffff, UINT64_C(0x4000000000000000),
        UINT64_C(0x7fffffffffffffff), UINT64_C(0x8000000000000000),
        UINT64_C(0x8000000000000001), UINT64_C(0xbfffffffffffffff),
        UINT64_C(0xffffffffffffffff)
    };
    // All exponent/sign pairs, J=0 encodings and edge significands.
    for (unsigned se=0; se<65536u; ++se)
        for (unsigned j=0; j<sizeof(special)/sizeof(special[0]); ++j)
            if (!verify(se, special[j])) return 1;
    // Exactly representable binary64-derived binary80, including boundaries.
    for (unsigned i=0; i<250000u; ++i) {
        unsigned exp = 15361u + (rng() % 2046u);
        unsigned se = exp | ((rng() & 1u) << 15);
        uint64_t sig = UINT64_C(0x8000000000000000) |
                       ((((uint64_t)rng() << 32) | rng()) &
                       UINT64_C(0x7ffffffffffff800));
        if (!verify(se, sig)) return 1;
    }
    // Inexact significands, underflow, overflow, pseudo-denormal, NaN.
    for (unsigned i=0; i<300000u; ++i) {
        unsigned se=rng() & 0xffffu;
        uint64_t sig=((uint64_t)rng()<<32)|rng();
        if (!verify(se,sig)) return 1;
    }
    for (unsigned i=0; i<10000u; ++i) {
        u128 v=((u128)rng()<<32)|rng();
        double a=(f2d)(v,8), b=f2d(v,8);
        uint64_t ba,bb; memcpy(&ba,&a,8);memcpy(&bb,&b,8);
        if(ba!=bb){fprintf(stderr,"binary64 mismatch\n");return 1;}
        a=(f2d)(v,4);b=f2d(v,4);
        memcpy(&ba,&a,8);memcpy(&bb,&b,8);
        if(ba!=bb){fprintf(stderr,"binary32 mismatch\n");return 1;}
    }
    printf("x87 normal f2d: %d bit-identical cases, %d fast eligible, 20000 binary32/64 checks\n",
           cases,fast);
    return fast > 200000 ? 0 : 1;
}
