#include "runtime/x87_native_math.h"
#include <stdio.h>
#include <string.h>
#include <float.h>
#define CHECK(c) do { if (!(c)) { fprintf(stderr,"native x87 line %d\n",__LINE__); return 1; } } while(0)
static x87_native_value value(uint16_t se, uint64_t sig) {
    x87_native_value v; memcpy(v.bytes,&sig,8); memcpy(v.bytes+8,&se,2); return v;
}
static int equal(x87_native_value a,x87_native_value b) {return !memcmp(a.bytes,b.bytes,10);}
#if LDBL_MANT_DIG > 53
static volatile long double live_input=0x1p53L;
#else
static volatile long double live_input=0x1p20L;
#endif
static __attribute__((noinline)) long double live_compiler_values(
        const x87_native_value *one,const x87_native_value *tiny) {
    long double a=live_input+1.0L, b=live_input-1.0L;
    x87_native_result r;
    if(!x87_native_binary(X87_NATIVE_ADD,0x037f,one,tiny,&r)) return -1;
    return a-b;
}
int main(void) {
    const x87_native_value one=value(0x3fff,UINT64_C(0x8000000000000000));
    const x87_native_value two=value(0x4000,UINT64_C(0x8000000000000000));
    const x87_native_value three=value(0x4000,UINT64_C(0xc000000000000000));
    const x87_native_value tiny=value(0x3fc0,UINT64_C(0x8000000000000000)); /* 2^-63 */
    x87_native_result r;
    CHECK(x87_native_binary(X87_NATIVE_ADD,0x037f,&one,&two,&r)); CHECK(equal(r.value,three));
    CHECK(x87_native_binary(X87_NATIVE_SUB,0x037f,&three,&two,&r)); CHECK(equal(r.value,one));
    CHECK(x87_native_binary(X87_NATIVE_MUL,0x037f,&two,&three,&r)); CHECK(equal(r.value,value(0x4001,UINT64_C(0xc000000000000000))));
    CHECK(x87_native_binary(X87_NATIVE_DIV,0x037f,&two,&two,&r)); CHECK(equal(r.value,one));
    for(unsigned pc=0;pc<4;pc++) if(pc!=1) for(unsigned rc=0;rc<4;rc++) {
        uint16_t cw=0x7f|(pc<<8)|(rc<<10);
        CHECK(x87_native_binary(X87_NATIVE_ADD,cw,&one,&tiny,&r));
        unsigned shift=pc==0?40:pc==2?11:0;
        uint64_t delta=pc==3?1:rc==2?(UINT64_C(1)<<shift):0;
        CHECK(equal(r.value,value(0x3fff,UINT64_C(0x8000000000000000)+delta)));
        CHECK(!!(r.operation_status&0x20)==(pc!=3));
        CHECK(!!(r.operation_status&0x200)==(pc!=3 && rc==2));
    }
    /* Masked divide-by-zero and invalid must be reported, not trap the host. */
    x87_native_value zero=value(0,0);
    CHECK(x87_native_binary(X87_NATIVE_DIV,0x037f,&one,&zero,&r));
    CHECK(equal(r.value,value(0x7fff,UINT64_C(0x8000000000000000)))); CHECK(r.operation_status&4);
    CHECK(x87_native_binary(X87_NATIVE_DIV,0x037f,&zero,&zero,&r)); CHECK(r.operation_status&1);
    /* Intermediate precision must exceed binary64, not merely store 10 bytes. */
    x87_native_value big=value(0x4034,UINT64_C(0x8000000000000000)); /* 2^53 */
    CHECK(x87_native_binary(X87_NATIVE_ADD,0x037f,&big,&one,&r));
    x87_native_value intermediate=r.value;
    CHECK(x87_native_binary(X87_NATIVE_SUB,0x037f,&intermediate,&big,&r)); CHECK(equal(r.value,one));
    /* Extended range, true subnormal, signed zero and unsupported encoding. */
    x87_native_value minimum=value(1,UINT64_C(0x8000000000000000));
    CHECK(x87_native_binary(X87_NATIVE_DIV,0x037f,&minimum,&two,&r));
    CHECK(equal(r.value,value(0,UINT64_C(0x4000000000000000))));
    x87_native_value subnormal=r.value;
    CHECK(x87_native_binary(X87_NATIVE_MUL,0x037f,&subnormal,&two,&r));
    CHECK(equal(r.value,minimum)); CHECK(r.operation_status&2);
    x87_native_value negative_zero=value(0x8000,0);
    CHECK(x87_native_binary(X87_NATIVE_MUL,0x037f,&negative_zero,&one,&r)); CHECK(equal(r.value,negative_zero));
    x87_native_value unsupported=value(0x3fff,1);
    CHECK(x87_native_binary(X87_NATIVE_ADD,0x037f,&unsupported,&one,&r)); CHECK(r.operation_status&1);
    x87_native_value snan=value(0x7fff,UINT64_C(0x8000000000000001));
    CHECK(x87_native_binary(X87_NATIVE_ADD,0x037f,&snan,&one,&r)); CHECK(r.operation_status&1);
    uint64_t payload; memcpy(&payload,r.value.bytes,8); CHECK(payload>>62==3);
    /* Inputs may alias output. */
    r.value=three;
    CHECK(x87_native_binary(X87_NATIVE_SUB,0x037f,&r.value,&two,&r)); CHECK(equal(r.value,one));
    x87_native_result sentinel; memset(&sentinel,0xa5,sizeof sentinel); r=sentinel;
    CHECK(!x87_native_binary(X87_NATIVE_ADD,0x037e,&one,&two,&r)); CHECK(!memcmp(&r,&sentinel,sizeof r));
    CHECK(!x87_native_binary(X87_NATIVE_ADD,0x017f,&one,&two,&r)); CHECK(!memcmp(&r,&sentinel,sizeof r));
    CHECK(!x87_native_binary(99,0x037f,&one,&two,&r)); CHECK(!memcmp(&r,&sentinel,sizeof r));
    CHECK(!x87_native_binary(X87_NATIVE_ADD,0x837f,&one,&two,&r)); CHECK(!memcmp(&r,&sentinel,sizeof r));
    CHECK(!x87_native_binary(X87_NATIVE_ADD,0x033f,&one,&two,&r)); CHECK(!memcmp(&r,&sentinel,sizeof r));
    CHECK(live_compiler_values(&one,&tiny)==2.0L);
    /* Preserve host x87 stack, control/status, pointers and MXCSR. */
    unsigned char before[512] __attribute__((aligned(16)))={0};
    unsigned char after[512] __attribute__((aligned(16)))={0};
    unsigned char original[512] __attribute__((aligned(16)));
    unsigned short hostcw=0x0b7f;
    __asm__ volatile("fxsave64 %0" : "=m"(original) : : "memory");
    __asm__ volatile("fninit; fldcw %0; fld1; fldpi" : : "m"(hostcw) : "st","st(1)");
    __asm__ volatile("fxsave64 %0" : "=m"(before) : : "memory");
    uint64_t host_ip=UINT64_C(0x176543210),host_dp=UINT64_C(0x165432100);
    memcpy(before+8,&host_ip,8);memcpy(before+16,&host_dp,8);
    __asm__ volatile("fxrstor64 %0; fxsave64 %0" : "+m"(before) : : "memory","st","st(1)");
    int accepted=x87_native_binary(X87_NATIVE_ADD,0x037f,&one,&tiny,&r);
    __asm__ volatile("fxsave64 %0" : "=m"(after) : : "memory");
    __asm__ volatile("fxrstor64 %0" : : "m"(original) : "memory","st","st(1)");
    CHECK(accepted); CHECK(!memcmp(before,after,32));
    for(unsigned i=0;i<8;i++) CHECK(!memcmp(before+32+16*i,after+32+16*i,10));
    unsigned char pending[512] __attribute__((aligned(16)));
    memcpy(pending,original,sizeof pending);
    unsigned short pendingcw=0x037e,pendingsw=0x8081;
    memcpy(pending,&pendingcw,2);memcpy(pending+2,&pendingsw,2);pending[4]=0;
    __asm__ volatile("fxrstor64 %0" : : "m"(pending) : "memory","st","st(1)",
        "st(2)","st(3)","st(4)","st(5)","st(6)","st(7)");
    accepted=x87_native_binary(X87_NATIVE_ADD,0x037f,&one,&tiny,&r);
    __asm__ volatile("fxsave64 %0; fxrstor64 %1" : "=m"(after) : "m"(original) : "memory","st","st(1)",
        "st(2)","st(3)","st(4)","st(5)","st(6)","st(7)");
    unsigned short restoredcw,restoredsw;memcpy(&restoredcw,after,2);memcpy(&restoredsw,after+2,2);
    CHECK(accepted);CHECK(restoredcw==pendingcw);CHECK((restoredsw&0x8081)==0x8081);
    puts("native binary80 arithmetic/control/status/host restoration passed");
    return 0;
}
