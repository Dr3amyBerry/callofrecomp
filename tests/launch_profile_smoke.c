#include "launch_profile.h"
int main(void) {
#ifdef CODRECOMP_WSA_RELEASE_DEFAULTS
    if(LAUNCH_DEFAULT_NATIVE_X87!=1 || LAUNCH_DEFAULT_FRAME_LIMIT!=120) return 1;
#else
    if(LAUNCH_DEFAULT_NATIVE_X87!=0 || LAUNCH_DEFAULT_FRAME_LIMIT!=60) return 2;
#endif
    for(int fallback=0;fallback<=1;fallback++) {
        if(launch_native_x87_setting(fallback,NULL,0)!=fallback ||
           launch_native_x87_setting(fallback,"1",1)!=1 ||
           launch_native_x87_setting(fallback,"0",1)!=0 ||
           launch_native_x87_setting(fallback,"1\n",2)!=fallback ||
           launch_native_x87_setting(fallback,"x",1)!=fallback) return 3;
    }
    return 0;
}
