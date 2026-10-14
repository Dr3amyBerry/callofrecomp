#pragma once
#include <stdint.h>
#include <string.h>
/* 2 MiB of BSS, not a copy of game memory. Rebuilt only when modules change. */
/* A dispatch_index is zero-initialized (BSS in guest.c). Each rebuild
   increments generation; hints from earlier module layouts then fail closed. */
typedef struct {
    uint16_t page[1u<<20];
    uint64_t generation;
} dispatch_index;
typedef struct {
    uint64_t generation;
    int last_chunk; /* -1 means not cached */
} dispatch_recent;
static inline void dispatch_index_build(dispatch_index *index,const recomp_chunk *chunks,int count){
    uint64_t next_generation=index->generation+1;
    /* Clearing page[] must not clear the generation, used by dispatch hints. */
    memset(index->page,0,sizeof index->page);
    index->generation=next_generation;
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
    /* Adjacent chunks commonly share a 4-KiB index page. The index keeps
       the last chunk on the page: test its immediate predecessor before
       falling back to a binary search. Pages with more than two chunks,
       including holes, still use the exact-range fallback. */
    if(candidate>0&&candidate<count&&pc>=chunks[candidate-1].start
       &&pc<chunks[candidate-1].end)return candidate-1;
    /* Chunks can share a 4-KiB page. Check exact boundaries on those pages. */
    int lo=0,hi=count-1;
    while(lo<=hi){int mid=(lo+hi)/2;
        if(pc<chunks[mid].start)hi=mid-1;
        else if(pc>=chunks[mid].end)lo=mid+1;
        else return mid;
    }
    return -1;
}

/* Optional per-guest_run() fast path. No dynamic allocation and no change to
   normal dispatch_index_find(). Recheck both PC boundaries on every hit.
   A module load/unload rebuild invalidates the cached index by generation.
   The hint is local to guest_run, so recursion/reentrancy never shares it. */
static inline int dispatch_index_find_recent(
    const dispatch_index *index, const recomp_chunk *chunks, int count,
    uint32_t pc, dispatch_recent *recent) {
    if (recent->last_chunk >= 0 &&
            recent->generation == index->generation &&
            recent->last_chunk < count) {
        const recomp_chunk *chunk = &chunks[recent->last_chunk];
        if (pc >= chunk->start && pc < chunk->end)
            return recent->last_chunk;
    }
    int found = dispatch_index_find(index, chunks, count, pc);
    recent->last_chunk = found;
    recent->generation = index->generation;
    return found;
}
