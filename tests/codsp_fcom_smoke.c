#define CODRECOMP_X87_FCOM_FASTPATH 1
#include "codsp_fcom.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { R_SIZE=0x1180, M_SIZE=8192 };
static uint8_t ref_regs[R_SIZE], candidate_regs[R_SIZE], memory[M_SIZE], before_mem[M_SIZE];
static uint32_t seed = 0x5432ab89u;
static uint32_t rng(void) {
    uint32_t x=seed;
    x ^= x<<13; x ^= x>>17; x ^= x<<5; return seed=x;
}

// Oracle deliberately executes the ORIGINAL p-code logic in separate
// operations: float32 -> binary80 -> double, flag scratch and x87 pop.
static void reference(uint8_t *r, const uint8_t *mem, uint32_t pc, uint32_t address) {
    wr(r+0x10ac,4,(u128)pc);
    const u128 converted = d2f(f2d(rd(mem+address,4),4),10);
    wr(r+0x1091,1,0);
    const u128 unordered = (u128)(isnan(f2d(rd(r+0x1100,10),10)) ||
                                  isnan(f2d(converted,10)));
    wr(r+0x1092,1,unordered & 1);
    const u128 less = (u128)(f2d(rd(r+0x1100,10),10) < f2d(converted,10));
    wr(r+0x1090,1,mask((rd(r+0x1092,1)|less),1));
    const u128 equal=(u128)(f2d(rd(r+0x1100,10),10) == f2d(converted,10));
    wr(r+0x1093,1,mask((rd(r+0x1092,1)|equal),1));
    const u128 c0=rd(r+0x1090,1),c1=rd(r+0x1091,1);
    const u128 c2=rd(r+0x1092,1),c3=rd(r+0x1093,1);
    wr(r+0x10a2,2,mask((c0<<8)|(c1<<9)|(c2<<10)|(c3<<14),2));
    for(unsigned i=0;i<7;i++)
        wr(r+0x1100+16*i,10,rd(r+0x1110+16*i,10));
}
static int check(uint32_t se, uint64_t sig, uint32_t rhs_bits, int case_no) {
    const uint32_t address = (rng()% (M_SIZE-16)) & ~3u;
    const uint32_t pc=0x00400000u+(rng()&0xffffffu);
    for(unsigned j=0;j<R_SIZE;j++)ref_regs[j]=(uint8_t)rng();
    for(unsigned j=0;j<M_SIZE;j++)memory[j]=(uint8_t)rng();
    wr(ref_regs+0x1100,10,((u128)se<<64)|sig);
    wr(memory+address,4,rhs_bits);
    memcpy(candidate_regs,ref_regs,R_SIZE);
    memcpy(before_mem,memory,M_SIZE);
    reference(ref_regs,memory,pc,address);
    if(codsp_fcom_pop_float32(candidate_regs,memory,pc,address)!=1 ||
       memcmp(ref_regs,candidate_regs,R_SIZE) || memcmp(memory,before_mem,M_SIZE)) {
        fprintf(stderr,"FCOM mismatch #%d se=%04x sig=%016llx float=%08x\n",
          case_no,se,(unsigned long long)sig,rhs_bits);
        return 0;
    }
    return 1;
}
int main(void) {
    static const uint16_t se_values[]={
        0,1,2,15360,15361,16383,16384,17406,0x7ffe,0x7fff,
        0x8000,0x8001,0xbfff,0xffff
    };
    static const uint64_t sig_values[]={
        0,1,UINT64_C(0x7ff),UINT64_C(0x7fffffffffffffff),
        UINT64_C(0x4000000000000000),UINT64_C(0x8000000000000000),
        UINT64_C(0x8000000000000001),UINT64_C(0xc000000000000000),
        UINT64_C(0xffffffffffffffff)
    };
    static const uint32_t floats[]={
        0,0x80000000u,0x3f800000u,0xbf800000u,0x7f800000u,
        0xff800000u,0x7fc12345u,0xffc00001u,0x7fa10000u,
        0x00000001u,0x80000001u,0x7f7fffffu,0xff7fffffu
    };
    int cases=0;
    for(unsigned e=0;e<sizeof se_values/sizeof se_values[0];e++)
      for(unsigned j=0;j<sizeof sig_values/sizeof sig_values[0];j++)
        for(unsigned k=0;k<sizeof floats/sizeof floats[0];k++) {
            if(!check(se_values[e],sig_values[j],floats[k],++cases))return 1;
        }
    for(int i=0;i<150000;i++){
        uint32_t se=rng()&0xffffu;
        uint64_t sig=((uint64_t)rng()<<32)|rng();
        uint32_t rhs=rng();
        if(!check(se,sig,rhs,++cases))return 1;
    }
    printf("x87 full compare/pop: %d complete register+memory differential cases passed\n",cases);
    return 0;
}
