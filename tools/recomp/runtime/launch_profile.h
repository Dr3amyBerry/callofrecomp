#pragma once
#include <stddef.h>
#ifdef CODRECOMP_WSA_RELEASE_DEFAULTS
enum { LAUNCH_DEFAULT_NATIVE_X87=1, LAUNCH_DEFAULT_FRAME_LIMIT=120 };
#else
enum { LAUNCH_DEFAULT_NATIVE_X87=0, LAUNCH_DEFAULT_FRAME_LIMIT=60 };
#endif
static inline int launch_native_x87_setting(int fallback,const char *text,size_t length) {
    if(text && length==1) {
        if(text[0]=='1') return 1;
        if(text[0]=='0') return 0;
    }
    return fallback;
}
