#pragma once
#include <stdint.h>
#include <string.h>
/* 2 MiB of BSS, not a copy of game memory. Rebuilt only when modules change. */
typedef struct { uint16_t page[1u<<20]; } dispatch_index;
static inline void dispatch_index_build(dispatch_index *index,const recomp_chunk *chunks,int count){
    memset(index,0,sizeof *index);
    for(int i=0;i<count;i++){
        if(chunks[i].end<=chunks[i].start)continue;
        uint32_t end=(chunks[i].end-1)>>12;
        for(uint32_t p=chunks[i].start>>12;p<=end;p++)index->page[p]=(uint16_t)(i+1);
    }
}
static inline int dispatch_index_find(const dispatch_index *index,const recomp_chunk *chunks,int count,uint32_t pc){
    unsigned cached=index->page[pc>>12];
    if(!cached)return -1;
    int candidate=(int)cached-1;
    if(candidate<count&&pc>=chunks[candidate].start&&pc<chunks[candidate].end)return candidate;
    /* Chunks can share a 4-KiB page. Check exact boundaries on those pages. */
    int lo=0,hi=count-1;
    while(lo<=hi){int mid=(lo+hi)/2;
        if(pc<chunks[mid].start)hi=mid-1;
        else if(pc>=chunks[mid].end)lo=mid+1;
        else return mid;
    }
    return -1;
}
