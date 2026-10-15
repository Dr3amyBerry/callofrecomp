/* Offline mathematical audit of an *unshipped* alternate canonical-binary80
   packing formula. The production f2d() and CoDSP converter are unchanged.
   No game files, ADB, networking or renderer dependencies. */
#define CODRECOMP_X87_NORMAL_F2D 1
#include "recomp_rt.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>

static uint32_t state = 0x11af1d37u;
static uint32_t next_u32(void) {
    state = 1664525u * state + 1013904223u;
    return state;
}
static uint64_t bits(double d) {
    uint64_t b;
    memcpy(&b,&d,sizeof b);
    return b;
}
static double packed_candidate(u128 v,int n) {
    if (n==10) {
        const uint64_t sig=(uint64_t)v;
        const unsigned se=(unsigned)(v>>64)&0xffffu;
        const unsigned exponent=se & 0x7fffu;
        if ((unsigned)(exponent-15361u)<=2045u &&
            (sig&UINT64_C(0x80000000000007ff))==
                      UINT64_C(0x8000000000000000)) {
            const uint64_t b=((uint64_t)(se&0x8000u)<<48) |
                (((uint64_t)(exponent-15361u)<<52)+(sig>>11));
            double d;
            memcpy(&d,&b,sizeof d);
            return d;
        }
    }
    return (f2d)(v,n);
}
static int64_t cases=0,fast=0;
static int check(unsigned se,uint64_t sig) {
    u128 v=((u128)se<<64)|sig;
    const uint64_t a=bits((f2d)(v,10));
    const uint64_t b=bits(packed_candidate(v,10));
    if (a!=b) {
        fprintf(stderr,"packed binary80 differs: se=%04x sig=%016llx "
                "ref=%016llx actual=%016llx\n",se,(unsigned long long)sig,
                (unsigned long long)a,(unsigned long long)b);
        return 0;
    }
    cases++;
    if ((unsigned)((se&0x7fffu)-15361u)<=2045u &&
        (sig&UINT64_C(0x80000000000007ff))==
              UINT64_C(0x8000000000000000))fast++;
    return 1;
}
int main(void) {
    static const uint64_t edges[] = {
        0,1,0x7ff,0xffff,UINT64_C(0x4000000000000000),
        UINT64_C(0x7fffffffffffffff),UINT64_C(0x8000000000000000),
        UINT64_C(0x8000000000000001),UINT64_C(0xbfffffffffffffff),
        UINT64_C(0xffffffffffffffff)
    };
    for (unsigned se=0;se<65536u;se++)
        for (unsigned i=0;i<sizeof edges/sizeof edges[0];i++)
            if (!check(se,edges[i]))return 2;
    for (unsigned i=0;i<250000u;i++) {
        unsigned se=15361u+next_u32()%2046u;
        se|=(next_u32()&1u)<<15;
        uint64_t sig=UINT64_C(0x8000000000000000) |
           ((((uint64_t)next_u32()<<32)|next_u32()) &
              UINT64_C(0x7ffffffffffff800));
        if (!check(se,sig))return 3;
    }
    for (unsigned i=0;i<300000u;i++) {
        unsigned se=next_u32()&0xffffu;
        uint64_t sig=((uint64_t)next_u32()<<32)|next_u32();
        if (!check(se,sig))return 4;
    }
    for (unsigned i=0;i<10000u;i++) {
        u128 v=((u128)next_u32()<<64)|next_u32();
        if(bits((f2d)(v,8))!=bits(packed_candidate(v,8)) ||
           bits((f2d)(v,4))!=bits(packed_candidate(v,4))) {
            fprintf(stderr,"non-binary80 mode mismatch\n");return 5;
        }
    }
    printf("unshipped binary80 packed-add arithmetic: %lld exact bit "
           "comparisons, %lld fast cases, 20000 binary32/binary64 checks\n",
           (long long)cases,(long long)fast);
    return fast>200000 ? 0 : 6;
}
