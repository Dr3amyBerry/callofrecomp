#pragma once
#include <stdatomic.h>
#include <string.h>
typedef struct { atomic_int phase; int pending; char line[512]; unsigned used; } loading_status;
static inline void loading_status_init(loading_status *s){
    memset(s,0,sizeof *s);atomic_init(&s->phase,1);
}
static inline int loading_status_get(loading_status *s){return atomic_load_explicit(&s->phase,memory_order_relaxed);}
static inline void loading_status_line(loading_status *s){
    int phase=0;
    if(strstr(s->line,"FS_Startup"))phase=2;
    else if(strstr(s->line,"Initializing OpenGL"))phase=3;
    else if(strstr(s->line,"Server Initialization")||strstr(s->line,"Loading "))phase=5;
    else if(strstr(s->line,"Parsing menu file")&&loading_status_get(s)!=5)phase=4;
    if(phase){s->pending=0;atomic_store_explicit(&s->phase,phase,memory_order_relaxed);}
    if(strstr(s->line,"Common Initialization Complete")||strstr(s->line,"CL_InitCGame:")){
        s->pending=1;atomic_store_explicit(&s->phase,6,memory_order_relaxed);
    }
}
static inline void loading_status_feed(loading_status *s,const char *text){
    for(;*text;text++){
        if(*text=='\n'){s->line[s->used]=0;loading_status_line(s);s->used=0;}
        else if(s->used<sizeof s->line-1)s->line[s->used++]=*text;
    }
}
static inline void loading_status_frame(loading_status *s){
    if(s->pending){s->pending=0;atomic_store_explicit(&s->phase,0,memory_order_relaxed);}
}
