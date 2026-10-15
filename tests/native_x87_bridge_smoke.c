#include "runtime/native_x87_bridge.h"
#include <stdio.h>
#include <string.h>
#define CHECK(c) do {if(!(c)){fprintf(stderr,"native bridge line %d\n",__LINE__);return 1;}}while(0)
int main(void) {
    const native_x87_instruction instructions[]={{0x1000,0x401000,0x100},{0x1004,0x401003,0x118}};
    native_x87_context context={0};context.instructions=instructions;context.count=2;
    context.memory_base=UINT64_C(0x100000000);context.code_selector=0x23;context.data_selector=0x2b;
    uint32_t seed_ip=0x400000,seed_dp=0x7000;
    memcpy(context.initial.bytes+12,&seed_ip,4);memcpy(context.initial.bytes+20,&seed_dp,4);
    uint8_t image[512]={0};uint16_t cw=0x37f,sw=0x3800;
    memcpy(image,&cw,2);memcpy(image+2,&sw,2);image[4]=0x80;
    uint64_t sig=UINT64_C(0x8000000000000000),ip=0x1000,dp=UINT64_C(0x100000008);
    uint16_t exponent=0x3fff;memcpy(image+32,&sig,8);memcpy(image+40,&exponent,2);
    memcpy(image+8,&ip,8);memcpy(image+16,&dp,8);
    x87_native_state state;memset(&state,0xa5,sizeof state);uint32_t pc=0xdead;
    CHECK(native_x87_decode_fault(&context,0x1004,image,&state,&pc));CHECK(pc==0x401003);
    uint32_t v;memcpy(&v,state.bytes+12,4);CHECK(v==0x401000);
    memcpy(&v,state.bytes+20,4);CHECK(v==8);
    uint16_t h;memcpy(&h,state.bytes+18,2);CHECK(h==0x100);
    memcpy(&h,state.bytes+8,2);CHECK(h==0x3fff);
    x87_native_state unchanged=state;uint32_t oldpc=pc;
    CHECK(!native_x87_decode_fault(&context,0x9999,image,&state,&pc));
    CHECK(!memcmp(&state,&unchanged,sizeof state)&&pc==oldpc);
    ip=0x8888;memcpy(image+8,&ip,8);
    CHECK(!native_x87_decode_fault(&context,0x1004,image,&state,&pc));
    CHECK(!memcmp(&state,&unchanged,sizeof state)&&pc==oldpc);
    ip=seed_ip;dp=seed_dp;memcpy(image+8,&ip,8);memcpy(image+16,&dp,8);
    CHECK(native_x87_decode_fault(&context,0x1004,image,&state,&pc));
    CHECK(!memcmp(state.bytes+12,&seed_ip,4)&&!memcmp(state.bytes+20,&seed_dp,4));
    dp=0x9999;memcpy(image+16,&dp,8);unchanged=state;oldpc=pc;
    CHECK(!native_x87_decode_fault(&context,0x1004,image,&state,&pc));
    CHECK(!memcmp(&state,&unchanged,sizeof state)&&pc==oldpc);
    uint8_t regs[0x2000]={0},memory[32]={0};uint32_t target=0x12345678;
    memcpy(memory+16,&target,4);
    native_x87_finish_return(regs,memory,&state,16,0x401010,&pc);
    memcpy(&v,regs+0x10,4);CHECK(v==20&&pc==target);
    memcpy(&v,regs+0x284,4);CHECK(v==target);
    puts("native x87 fault relocation/rejection/virtual return passed");return 0;
}
