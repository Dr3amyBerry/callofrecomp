/* Independent byte oracle for logical right shift, including overshifts.
   No game data, no x86 instruction-count masking (that belongs to decoding). */
#include "recomp_rt.h"

#define WRAPPER(N) static u128 shift_##N(const uint8_t *a, u128 count) { return shr(rd(a,N),count); }
WRAPPER(1) WRAPPER(2) WRAPPER(3) WRAPPER(4)
WRAPPER(5) WRAPPER(6) WRAPPER(7) WRAPPER(8)
WRAPPER(9) WRAPPER(10) WRAPPER(11) WRAPPER(12)
WRAPPER(13) WRAPPER(14) WRAPPER(15) WRAPPER(16)

int main(void) {
    u128 (*functions[])(const uint8_t *,u128) = {
        shift_1,shift_2,shift_3,shift_4,shift_5,shift_6,shift_7,shift_8,
        shift_9,shift_10,shift_11,shift_12,shift_13,shift_14,shift_15,shift_16};
    const u128 counts[] = {0,1,7,8,15,16,31,32,63,64,65,79,80,127,128,129,
        255,256,((u128)1<<32),((u128)1<<64),~(u128)0};
    uint64_t random=UINT64_C(0x5a17cafe);
    uint8_t data[18],expected[16],actual[16];
    for (int n=1;n<=16;n++) {
        for (unsigned trial=0;trial<512;trial++) {
            for (unsigned byte=0;byte<18;byte++) {
                random=random*UINT64_C(6364136223846793005)+1;
                data[byte]=(uint8_t)(random>>32);
            }
            u128 count=trial<sizeof counts/sizeof *counts ? counts[trial] :
                (u128)((random>>32)&255);
            for (unsigned byte=0;byte<16;byte++) {
                unsigned value=0;
                if (count<128) {
                    unsigned source=byte+(unsigned)count/8, bits=(unsigned)count%8;
                    if (source<(unsigned)n) value=data[1+source]>>bits;
                    if (bits && source+1<(unsigned)n)
                        value|=(unsigned)data[2+source]<<(8-bits);
                }
                expected[byte]=(uint8_t)value;
            }
            /* Unaligned source, full 128-bit result and zero extension. */
            wr(actual,16,functions[n-1](data+1,count));
            for(unsigned byte=0;byte<16;byte++)
                if(actual[byte]!=expected[byte])return n;
        }
    }
    return 0;
}
