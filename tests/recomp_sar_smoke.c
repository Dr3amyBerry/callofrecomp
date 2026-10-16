/* Independent bit oracle for 128-bit sign-extended arithmetic right shift.
   No calls to sar(), sx(), host signed shifts or compiler intrinsics in oracle. */
#include "recomp_rt.h"
#ifndef SAR_CASES
#define SAR_CASES 1024
#endif
#define W(N) static u128 wrap_##N(const uint8_t *p, u128 count) { return sar(rd(p, N),count,N); }
W(1) W(2) W(3) W(4) W(5) W(6) W(7) W(8)
W(9) W(10) W(11) W(12) W(13) W(14) W(15) W(16)
int main(void) {
    u128 (*const funcs[])(const uint8_t *,u128) = {
        wrap_1,wrap_2,wrap_3,wrap_4,wrap_5,wrap_6,wrap_7,wrap_8,
        wrap_9,wrap_10,wrap_11,wrap_12,wrap_13,wrap_14,wrap_15,wrap_16
    };
    const u128 bounds[] = {
        0,1,7,8,15,16,31,32,63,64,65,79,80,127,128,129,
        255,256,((u128)1<<32),((u128)1<<64),((u128)1<<127),~(u128)0
    };
    uint64_t rng=UINT64_C(0x93a728b45);
    uint8_t data[19], expected[16], actual[16];
    for(unsigned n=1;n<=16;n++) {
        for(unsigned trial=0;trial<SAR_CASES;trial++) {
            for(unsigned k=0;k<sizeof(data);k++) {
                rng=rng*UINT64_C(6364136223846793005)+1;
                data[k]=(uint8_t)(rng>>33);
            }
            const u128 count = trial < sizeof(bounds)/sizeof(bounds[0])
                ? bounds[trial] : (trial%7==0
                   ? ((u128)rng<<64)|(rng>>1)
                   : (u128)((rng>>23)%300));
            const uint8_t *src=data+1; /* intentionally unaligned */
            const unsigned sign=(src[n-1]>>7)&1u;
            for(unsigned byte=0;byte<16;byte++) {
                unsigned value=0;
                for(unsigned bit=0;bit<8;bit++) {
                    const unsigned bit_index=8*byte+bit;
                    const unsigned source_bit=count>=128
                        ? 128 : (unsigned)count+bit_index;
                    const unsigned one=source_bit>=8*n ? sign
                        : ((src[source_bit/8]>>(source_bit%8))&1u);
                    value |= one<<bit;
                }
                expected[byte]=(uint8_t)value;
            }
            wr(actual,16,funcs[n-1](src,count));
            for(unsigned byte=0;byte<16;byte++)
                if(actual[byte]!=expected[byte])return (int)n;
        }
    }
    return 0;
}
