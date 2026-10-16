
#include "recomp_rt.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
uint8_t *MEM,R[0x2000],U[0x400000];
uint32_t PC;int recomp_miss;
void baseline_chunk_0(void);void candidate_chunk_0(void);
static uint32_t seed=0x42ace925u;
static uint32_t rng(void){seed=seed*1664525u+1013904223u;return seed;}
static const uint32_t interesting[]={
 0u,0x80000000u,0x00000001u,0x807fffffu,0x00800000u,
 0x7f7fffffu,0xff7fffffu,0x7f800000u,0xff800000u,0x7fc00000u,
 0x7f800001u,0xffc00000u,0x3f800000u,0xbf800000u,0x000fffffu,
 0x80800000u,0x3f000000u,0x80000001u
};
int main(void) {
 static uint8_t mem[0x4000],initial[0x4000],mem_a[0x4000];
 static uint8_t initial_r[0x2000],r_a[0x2000];
 static uint8_t initial_u[0x400000],u_a[0x400000];
 MEM=mem;
 const uint32_t pcs[]={0x4d82d4u,0x4d82dbu,0x4d82f1u,0x4d845bu,0x4d8471u,
                         0x4d94f4u,0x4d94fbu,0x4d9505u,0x4d950au,0x4d9511u};
 for(unsigned trial=0;trial<80;trial++) {
  for(unsigned i=0;i<sizeof initial_r;i++)initial_r[i]=(uint8_t)(rng()>>24);
  for(unsigned i=0;i<sizeof initial;i++)initial[i]=(uint8_t)(rng()>>24);
  memset(initial_u,0xaa,sizeof initial_u);
  const uint32_t word=trial<sizeof interesting/sizeof interesting[0]
      ? interesting[trial]:rng();
  for(unsigned k=0;k<6;k++)memcpy(initial+0x1ff8+k*4,&word,4);
  wr(initial_r+0,4,0);wr(initial_r+4,4,0x2000);wr(initial_r+8,4,0x2000);
  for(unsigned p=0;p<sizeof pcs/sizeof pcs[0];p++) {
   uint32_t pc_a=0;
   for(int candidate=0;candidate<2;candidate++) {
    memcpy(R,initial_r,sizeof R);memcpy(MEM,initial,sizeof mem);
    memcpy(U,initial_u,sizeof U);PC=pcs[p];recomp_miss=0;

    if(candidate)candidate_chunk_0();else baseline_chunk_0();
    if(recomp_miss){fprintf(stderr,"recomp miss %x\n",pcs[p]);return 5;}
    if(!candidate){
     pc_a=PC;memcpy(r_a,R,sizeof R);memcpy(mem_a,MEM,sizeof mem);
     memcpy(u_a,U,sizeof U);
    }else if(PC!=pc_a||memcmp(r_a,R,sizeof R)||memcmp(mem_a,MEM,sizeof mem)||
              memcmp(u_a,U,sizeof U)) {
     fprintf(stderr,"AB diverged pc %x trial %u\n",pcs[p],trial);return 10;
    }
   }
  }
 }
 return 0;
}
