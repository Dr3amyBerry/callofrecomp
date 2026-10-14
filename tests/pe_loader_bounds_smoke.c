#include "pe_loader_bounds.h"
#include <stdio.h>
#include <string.h>
#define CK(x) do{if(!(x)){fprintf(stderr,"PE check failed at %d\n",__LINE__);return 1;}}while(0)
static void wr16(uint8_t *p,uint32_t v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void wr32(uint8_t *p,uint32_t v){for(int i=0;i<4;i++)p[i]=(uint8_t)(v>>(i*8));}
static void make(uint8_t *p){
 memset(p,0,1024);p[0]='M';p[1]='Z';wr32(p+0x3c,0x80);
 memcpy(p+0x80,"PE\0\0",4);wr16(p+0x84,0x14c);wr16(p+0x86,2);
 wr16(p+0x94,0xe0);wr16(p+0x98,0x10b);wr32(p+0x98+56,0x4000);
 wr32(p+0x98+60,0x200);
 wr32(p+0x178+8,0x1000);wr32(p+0x178+12,0x1000);
 wr32(p+0x178+16,0x100);wr32(p+0x178+20,0x200);
 wr32(p+0x1a0+8,0x1000);wr32(p+0x1a0+12,0x2000);
 wr32(p+0x1a0+16,0x100);wr32(p+0x1a0+20,0x300);
}
int main(void){
 uint8_t f[1024];pe_plan plan;make(f);
 CK(pe_prepare(f,sizeof f,0x4000,&plan));CK(plan.count==2&&plan.headers==0x200);
 CK(plan.sec[1].dst==0x2000&&plan.sec[1].src==0x300);
 CK(!pe_prepare(f,60,0x4000,&plan));CK(!pe_prepare(f,0x90,0x4000,&plan));
 f[0]=0;CK(!pe_prepare(f,sizeof f,0x4000,&plan));make(f);
 f[0x80]=0;CK(!pe_prepare(f,sizeof f,0x4000,&plan));make(f);
 wr32(f+0x3c,0xfffffff0);CK(!pe_prepare(f,sizeof f,0x4000,&plan));make(f);
 wr16(f+0x84,0x8664);CK(!pe_prepare(f,sizeof f,0x4000,&plan));make(f);
 wr16(f+0x86,97);CK(!pe_prepare(f,sizeof f,0x4000,&plan));make(f);
 wr16(f+0x94,60);CK(!pe_prepare(f,sizeof f,0x4000,&plan));make(f);
 wr16(f+0x98,0x20b);CK(!pe_prepare(f,sizeof f,0x4000,&plan));make(f);
 wr32(f+0x98+56,0x5000);CK(!pe_prepare(f,sizeof f,0x4000,&plan));make(f);
 wr32(f+0x98+60,0x190);CK(!pe_prepare(f,sizeof f,0x4000,&plan));make(f);
 wr32(f+0x178+12,0x3f00);CK(!pe_prepare(f,sizeof f,0x4000,&plan));make(f);
 wr32(f+0x178+20,0xfffffffe);CK(!pe_prepare(f,sizeof f,0x4000,&plan));make(f);
 wr32(f+0x178+20,0x3c0);wr32(f+0x178+16,0x100);
 CK(!pe_prepare(f,sizeof f,0x4000,&plan));make(f);
 wr32(f+0x178+8,0x40);wr32(f+0x178+16,0x200);
 CK(pe_prepare(f,sizeof f,0x4000,&plan)&&plan.sec[0].n==0x40);
 puts("PE32 bounds and malformed section fixtures passed");return 0;
}
