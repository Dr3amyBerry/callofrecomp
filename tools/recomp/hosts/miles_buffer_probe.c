// Optional native x86 contract probe; pass the user's original mss32.dll path.
// Build with i686-w64-mingw32-clang. Samples contain silence, not game assets.
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint32_t (__stdcall *f0)(void);
typedef uint32_t (__stdcall *f1)(uint32_t);
typedef uint32_t (__stdcall *f3)(uint32_t,uint32_t,uint32_t);
typedef uint32_t (__stdcall *f4)(uint32_t,uint32_t,uint32_t,uint32_t);
int main(int argc,char **argv) {
 if(argc!=2)return 1;
 HMODULE lib=LoadLibraryA(argv[1]); if(!lib){printf("load %lu\n",GetLastError());return 2;}
#define FN(type,name,pop) type name=(type)GetProcAddress(lib,"_AIL_" #name "@" #pop); if(!name)return 3
 FN(f0,startup,0); FN(f0,shutdown,0); FN(f4,open_digital_driver,16);
 FN(f1,allocate_sample_handle,4); FN(f1,init_sample,4); FN(f3,set_sample_type,12);
 FN(f1,sample_buffer_ready,4); FN(f1,sample_position,4); FN(f1,sample_status,4);
 FN(f4,load_sample_buffer,16); FN(f3,minimum_sample_buffer_size,12);
 startup(); uint32_t d=open_digital_driver(22050,16,1,0);
 printf("driver %08x\n",d); if(!d)return 4;
 uint32_t s=allocate_sample_handle(d); if(!s){shutdown();return 5;}
 init_sample(s); set_sample_type(s,1,0);
 unsigned char *pcm=calloc(1,44100);
 if(!pcm){shutdown();return 6;}
 printf("minimum %u ready %d status %u pos %d\n",minimum_sample_buffer_size(d,22050,1),(int)sample_buffer_ready(s),sample_status(s),(int)sample_position(s));
 load_sample_buffer(s,0,(uint32_t)(uintptr_t)pcm,22050);
 printf("load0 ready %d status %u pos %d\n",(int)sample_buffer_ready(s),sample_status(s),(int)sample_position(s));
 load_sample_buffer(s,1,(uint32_t)(uintptr_t)pcm+22050,22050);
 printf("load1 ready %d status %u pos %d\n",(int)sample_buffer_ready(s),sample_status(s),(int)sample_position(s));
 for(int i=0;i<6;i++){Sleep(200);printf("t%d ready %d status %u pos %d\n",(i+1)*200,(int)sample_buffer_ready(s),sample_status(s),(int)sample_position(s));fflush(stdout);}
 shutdown();free(pcm);return 0;
}
