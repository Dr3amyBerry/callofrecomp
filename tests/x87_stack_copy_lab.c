/* Isolated x87 80-bit stack-pop lowering experiment: NO guest code.
 * Each logical slot holds 10 payload bytes in a 16-byte register stride.
 * Retain the unused six bytes per slot byte-for-byte.
 * Test both reference rd/wr and an equivalent direct memcpy sequence.
 * This is an equivalence lab, not an approved Android optimization.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef unsigned __int128 u128;
static inline u128 rd(const uint8_t *p, int n) {
    u128 v = 0;
    memcpy(&v, p, (size_t)n);
    return v;
}
static inline void wr(uint8_t *p, int n, u128 v) {
    memcpy(p, &v, (size_t)n);
}

#if defined(_MSC_VER)
#define KEEP __declspec(noinline)
#else
#define KEEP __attribute__((noinline))
#endif

KEEP void x87_pop_ref(uint8_t *r) {
    wr(r+0x1100,10,rd(r+0x1110,10));
    wr(r+0x1110,10,rd(r+0x1120,10));
    wr(r+0x1120,10,rd(r+0x1130,10));
    wr(r+0x1130,10,rd(r+0x1140,10));
    wr(r+0x1140,10,rd(r+0x1150,10));
    wr(r+0x1150,10,rd(r+0x1160,10));
    wr(r+0x1160,10,rd(r+0x1170,10));
}
KEEP void x87_pop_memcpy(uint8_t *r) {
    memcpy(r+0x1100,r+0x1110,10);
    memcpy(r+0x1110,r+0x1120,10);
    memcpy(r+0x1120,r+0x1130,10);
    memcpy(r+0x1130,r+0x1140,10);
    memcpy(r+0x1140,r+0x1150,10);
    memcpy(r+0x1150,r+0x1160,10);
    memcpy(r+0x1160,r+0x1170,10);
}
#ifndef CODRECOMP_LAB_ASM_ONLY
static uint32_t rng=0x74a5ce99u;
static uint32_t random_word(void){
    rng^=rng<<13;
    rng^=rng>>17;
    rng^=rng<<5;
    return rng;
}
int main(void) {
    uint8_t expected[0x1200], actual[0x1200];
    for(int trial=0;trial<20000;trial++) {
        for(size_t k=0;k<sizeof(expected);k++) {
            expected[k]=(uint8_t)(trial == 0 ? 0 :
                         trial == 1 ? 255 :
                         trial == 2 ? (k&255) : random_word());
        }
        memcpy(actual,expected,sizeof(expected));
        x87_pop_ref(expected);
        x87_pop_memcpy(actual);
        if(memcmp(expected,actual,sizeof(expected))) {
            fprintf(stderr,"x87 stack pop mismatch in trial %d\n",trial);
            return 1;
        }
    }
    puts("20000 synthetic x87 80-bit stack-copy cases matched byte for byte");
    return 0;
}
#endif
