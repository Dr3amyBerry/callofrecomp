#include "recomp_rt.h"
#include "dispatch_index.h"
#include <stdio.h>
static dispatch_index index_table;
int main(void) {
    recomp_chunk chunks[] = {{0x1000,0x1800,0},{0x1800,0x2800,0},{0x4000,0x5000,0}};
    dispatch_index_build(&index_table,chunks,3);
    uint32_t pcs[] = {0,0x1000,0x17ff,0x1800,0x27ff,0x2800,0x3800,0x4000,0x4fff,0x5000,0xffffffff};
    int expected[] = {-1,0,0,1,1,-1,-1,2,2,-1,-1};
    for(unsigned i=0;i<sizeof pcs/sizeof *pcs;i++)
        if(dispatch_index_find(&index_table,chunks,3,pcs[i])!=expected[i])return 1;
    // Reference scan over many small sorted chunks, with page collisions and
    // gaps: the cached final chunk may be multiple entries after the target.
    recomp_chunk dense[170];
    uint32_t cursor=0x6100u;
    for(int i=0;i<170;i++){
        cursor+=(i%7==0)?13u:0u;
        uint32_t length=(uint32_t)(21+i%79);
        dense[i]=(recomp_chunk){cursor,cursor+length,0};
        cursor+=length;
    }
    dispatch_index_build(&index_table,dense,170);
    for(uint32_t pc=0x60f0u;pc<cursor+80u;pc++){
        int reference=-1;
        for(int k=0;k<170;k++)
            if(pc>=dense[k].start && pc<dense[k].end){reference=k;break;}
        if(dispatch_index_find(&index_table,dense,170,pc)!=reference){
            fprintf(stderr,"Mismatch in colliding page at %08x expected %d\n",pc,reference);
            return 4;
        }
    }
    // A high address must not alias entries near zero, including gaps.
    recomp_chunk high[]={{0x00000010u,0x00000080u,0},
                         {0xffffe800u,0xfffff000u,0},
                         {0xfffff020u,0xffffffffu,0}};
    dispatch_index_build(&index_table,high,3);
    uint32_t high_pc[]={0u,0x10u,0x7fu,0x80u,0xffffe800u,0xffffefffu,
                        0xfffff000u,0xfffff020u,0xfffffffeu,0xffffffffu};
    int high_expect[]={-1,0,0,-1,1,1,-1,2,2,-1};
    for(unsigned i=0;i<sizeof high_pc/sizeof *high_pc;i++)
        if(dispatch_index_find(&index_table,high,3,high_pc[i])!=high_expect[i])return 5;
    // Rebuild after DLL unload/reload must erase old page entries and indices.
    dispatch_index_build(&index_table,chunks+2,1);
    if(dispatch_index_find(&index_table,chunks+2,1,0x1000)!=-1 ||
       dispatch_index_find(&index_table,chunks+2,1,0x4000)!=0)return 2;
    dispatch_index_build(&index_table,0,0);
    if(dispatch_index_find(&index_table,0,0,0x4000)!=-1)return 3;
    puts("Dispatch index: boundaries, shared pages, holes, unload rebuild OK");
    return 0;
}
