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
    // Rebuild after DLL unload/reload must erase old page entries and indices.
    dispatch_index_build(&index_table,chunks+2,1);
    if(dispatch_index_find(&index_table,chunks+2,1,0x1000)!=-1 ||
       dispatch_index_find(&index_table,chunks+2,1,0x4000)!=0)return 2;
    dispatch_index_build(&index_table,0,0);
    if(dispatch_index_find(&index_table,0,0,0x4000)!=-1)return 3;
    puts("Dispatch index: boundaries, shared pages, holes, unload rebuild OK");
    return 0;
}
