#include "runtime/x87_native_state.h"
#include <stdio.h>
#include <string.h>
#define CHECK(c) do { if(!(c)) {fprintf(stderr,"native state line %d\n",__LINE__);return 1;} } while(0)
static void put16(uint8_t *p,uint16_t x) {memcpy(p,&x,2);}
static uint16_t get16(const uint8_t *p) {uint16_t x;memcpy(&x,p,2);return x;}
int main(void) {
    uint8_t regs[0x2000],copy[0x2000];
    for(unsigned i=0;i<sizeof regs;i++) regs[i]=(uint8_t)(i*73+19);
    memcpy(copy,regs,sizeof regs);
    x87_native_state state;
    x87_native_state_from_registers(&state,regs,0x23,0x2b);
    CHECK(!memcmp(state.bytes,regs+0x10a0,2));
    CHECK(!memcmp(state.bytes+4,regs+0x10a2,2));
    CHECK(!memcmp(state.bytes+8,regs+0x10a4,2));
    CHECK(!memcmp(state.bytes+18,regs+0x10a6,2));
    CHECK(!memcmp(state.bytes+20,regs+0x10a8,4));
    CHECK(!memcmp(state.bytes+12,regs+0x10ac,4));
    CHECK(get16(state.bytes+16)==0x23 && get16(state.bytes+24)==0x2b);
    for(unsigned i=0;i<8;i++) CHECK(!memcmp(state.bytes+28+10*i,regs+0x1100+16*i,10));
    /* Export must preserve all unrelated register bytes, including slot padding. */
    x87_native_state_to_registers(regs,&state);
    CHECK(!memcmp(regs,copy,sizeof regs));
    /* A round trip is byte-exact for all mapped fields with distinct source data. */
    memset(regs+0x10a0,0,16);
    for(unsigned i=0;i<8;i++) memset(regs+0x1100+16*i,0,10);
    x87_native_state_to_registers(regs,&state);
    CHECK(!memcmp(regs,copy,sizeof regs));
    for(unsigned top=0;top<8;top++) for(unsigned pattern=0;pattern<2;pattern++) {
        memset(&state,0,sizeof state);
        put16(state.bytes,0x037f);put16(state.bytes+4,(uint16_t)((top<<11)|0x35));
        uint16_t tags=0;
        for(unsigned i=0;i<8;i++) {
            unsigned tag=pattern?i%4:3;
            tags |= tag << (2*((top+i)%8));
            uint64_t sig=UINT64_C(0x8000000000000000)+((uint64_t)i<<59);
            uint16_t exponent=0x3fff;
            if(tag==1) {sig=0;exponent=0;}
            if(tag==2) {sig=UINT64_C(0xc000000000000001);exponent=0x7fff;}
            memcpy(state.bytes+28+i*10,&sig,8);put16(state.bytes+36+i*10,exponent);
        }
        put16(state.bytes+8,tags);
        x87_native_state output;
        CHECK(x87_native_state_roundtrip(&state,&output));
        CHECK(get16(output.bytes)==get16(state.bytes));
        CHECK(get16(output.bytes+4)==get16(state.bytes+4));
        CHECK(get16(output.bytes+8)==get16(state.bytes+8));
        CHECK(!memcmp(output.bytes+28,state.bytes+28,80));
        CHECK(x87_native_state_roundtrip(&output,&output));
        CHECK(get16(output.bytes+8)==tags);
        CHECK(!memcmp(output.bytes+28,state.bytes+28,80));
    }
    x87_native_state untouched;memset(&untouched,0xa5,sizeof untouched);
    x87_native_state output=untouched;put16(state.bytes,0x037e);
    CHECK(!x87_native_state_roundtrip(&state,&output));CHECK(!memcmp(&output,&untouched,sizeof output));
    put16(state.bytes,0x017f);
    CHECK(!x87_native_state_roundtrip(&state,&output));CHECK(!memcmp(&output,&untouched,sizeof output));
    put16(state.bytes,0x837f);
    CHECK(!x87_native_state_roundtrip(&state,&output));CHECK(!memcmp(&output,&untouched,sizeof output));
    put16(state.bytes,0x033f);
    CHECK(!x87_native_state_roundtrip(&state,&output));CHECK(!memcmp(&output,&untouched,sizeof output));
    put16(state.bytes,0x037f);
    unsigned char saved[512] __attribute__((aligned(16)));
    unsigned char before[512] __attribute__((aligned(16)))={0};
    unsigned char after[512] __attribute__((aligned(16)))={0};
    unsigned short hostcw=0x0b7f;
    __asm__ volatile("fxsave64 %0" : "=m"(saved) : : "memory");
    __asm__ volatile("fninit; fldcw %0; fld1; fldpi" : : "m"(hostcw) : "st","st(1)");
    __asm__ volatile("fxsave64 %0" : "=m"(before) : : "memory");
    uint64_t host_ip=UINT64_C(0x176543210),host_dp=UINT64_C(0x165432100);
    memcpy(before+8,&host_ip,8);memcpy(before+16,&host_dp,8);
    __asm__ volatile("fxrstor64 %0; fxsave64 %0" : "+m"(before) : : "memory","st","st(1)");
    int accepted=x87_native_state_roundtrip(&state,&output);
    __asm__ volatile("fxsave64 %0" : "=m"(after) : : "memory");
    __asm__ volatile("fxrstor64 %0" : : "m"(saved) : "memory","st","st(1)");
    CHECK(accepted);CHECK(!memcmp(before,after,32));
    for(unsigned i=0;i<8;i++) CHECK(!memcmp(before+32+16*i,after+32+16*i,10));
    /* A pending UNMASKED host exception must not fire during guest import.
       Restore the original host state before any later waiting instruction. */
    unsigned char pending[512] __attribute__((aligned(16)));
    memcpy(pending,saved,sizeof pending);
    put16(pending,0x037e);put16(pending+2,0x8081);pending[4]=0;
    __asm__ volatile("fxrstor64 %0" : : "m"(pending) : "memory","st","st(1)",
        "st(2)","st(3)","st(4)","st(5)","st(6)","st(7)");
    accepted=x87_native_state_roundtrip(&state,&output);
    __asm__ volatile("fxsave64 %0; fxrstor64 %1" : "=m"(after) : "m"(saved) : "memory","st","st(1)",
        "st(2)","st(3)","st(4)","st(5)","st(6)","st(7)");
    CHECK(accepted);CHECK(get16(after)==0x037e);CHECK((get16(after+2)&0x8081)==0x8081);
    puts("native x87 state mapping/TOP/full tags/eight binary80 slots passed");
    return 0;
}
