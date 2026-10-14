// Deterministic MOV-sequence equivalence for the private CoDSP 1.5 copy
// loop. No original code or game assets are required.
#include "codsp_copy32.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

enum { SIZE=0x3000, REG=0x2000 };
static uint8_t golden_mem[SIZE], candidate_mem[SIZE];
static uint8_t golden_regs[REG], candidate_regs[REG];
static unsigned rng_state=0x73bf6121u;
static uint32_t random32(void) {
    uint32_t x=rng_state;
    x^=x<<13; x^=x>>17; x^=x<<5;
    return rng_state=x;
}
static uint32_t get32(const uint8_t *p) {
    uint32_t v; memcpy(&v,p,4);return v;
}
static void set32(uint8_t *p,uint32_t v){memcpy(p,&v,4);}
static void original_eight_movs(uint8_t *r,uint8_t *m) {
    uint32_t src=get32(r+0xc), dst=get32(r+8), off=get32(r+0x1c);
    for(int k=0;k<8;k+=2) {
        uint32_t eax=get32(m+src+off+4*k);
        uint32_t esi=get32(m+src+off+4*k+4);
        set32(r+0,eax);set32(r+0x18,esi);
        set32(m+dst+off+4*k,get32(r+0));
        set32(m+dst+off+4*k+4,get32(r+0x18));
    }
}
int main(void) {
    unsigned success=0, fallbacks=0;
    for(int i=0;i<110000;i++) {
        const uint32_t src=(random32()%0x1800u);
        const uint32_t dst=(i%13==0)?src+1+(random32()%29u):
            (i%17==0)?src:(random32()%0x1800u);
        const uint32_t off=(random32()%80u)*32u;
        if(src+off+32>=SIZE || dst+off+32>=SIZE) continue;
        for(int k=0;k<SIZE;k++) golden_mem[k]=(uint8_t)random32();
        for(int k=0;k<REG;k++) golden_regs[k]=(uint8_t)random32();
        set32(golden_regs+0xc,src);
        set32(golden_regs+8,dst);
        set32(golden_regs+0x1c,off);
        memcpy(candidate_regs,golden_regs,REG);
        memcpy(candidate_mem,golden_mem,SIZE);
        original_eight_movs(golden_regs,golden_mem);
        if(codsp_copy32_step(candidate_regs,candidate_mem))success++;
        else {original_eight_movs(candidate_regs,candidate_mem);fallbacks++;}
        if(memcmp(candidate_regs,golden_regs,REG) ||
           memcmp(candidate_mem,golden_mem,SIZE)) {
            fprintf(stderr,"copy32 mismatch i=%d src=%u dst=%u off=%u\n",i,src,dst,off);
            return 1;
        }
    }
    assert(success>1000 && fallbacks>1000);
    // The fast helper must decline 32-bit address wrap without touching
    // memory or register state.
    set32(candidate_regs+0xc,0xfffffff0u);
    set32(candidate_regs+8,0x100u);
    set32(candidate_regs+0x1c,16u);
    assert(codsp_copy32_step(candidate_regs,candidate_mem)==0);
    puts("codsp copy32 block differential: PASS");
    printf("accepted=%u fallback=%u\n",success,fallbacks);
    return 0;
}
