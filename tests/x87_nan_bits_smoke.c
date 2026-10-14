#include "x87_nan_bits.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
static uint32_t state=0x7b1234adu;
static uint32_t rng(void) {uint32_t x=state; x ^= x<<13; x ^= x>>17; x ^= x<<5; return state=x;}
static int verify(unsigned se, uint64_t sig) {
    u128 bits=((u128)se << 64)|sig;
    int expected=isnan(f2d(bits,10)) ? 1 : 0;
    int candidate=codsp_x87_isnan_bits(bits) ? 1 : 0;
    if (expected != candidate) {
        fprintf(stderr,"Mismatch binary80 se=%04x sig=%016llx exp=%d got=%d\n",
                se,(unsigned long long)sig,expected,candidate);
        return 0;
    }
    return 1;
}
int main(void) {
    static const uint64_t sigs[] = {
        0, 1, 0x7ff, 0xffff, UINT64_C(0x4000000000000000),
        UINT64_C(0x7fffffffffffffff), UINT64_C(0x8000000000000000),
        UINT64_C(0x8000000000000001), UINT64_C(0xbfffffffffffffff),
        UINT64_C(0xffffffffffffffff),
    };
    unsigned long long tested=0;
    // Exhaustive exponent + sign classification across canonical,
    // pseudo-denormal, pseudo-infinity and unsupported J patterns.
    for(unsigned sign=0;sign<=0x8000;sign+=0x8000)
      for(unsigned e=0;e<0x8000;e++)
        for(unsigned j=0;j<sizeof sigs/sizeof sigs[0];j++) {
            if(!verify(e|sign,sigs[j]))return 1;
            tested++;
        }
    for(unsigned i=0;i<300000;i++) {
        unsigned se=rng()&0xffffu;
        uint64_t sig=((uint64_t)rng()<<32)|rng();
        if(!verify(se,sig)) return 1;
        tested++;
    }
    printf("binary80 direct NaN classification matches recomp f2d/isnan: %llu cases\n",tested);
    return 0;
}
