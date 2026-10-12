// Helpers shared by the generated gl_thunks.c and window.c.
#pragma once
#include "recomp_rt.h"

#if defined(_WIN32) && !defined(_WIN64)
#define GLAPI_CALL __stdcall
#else
#define GLAPI_CALL
#endif

static inline void *GP(uint32_t a) { return a ? (void *)G(a) : (void *)0; }
static inline float F32(uint32_t b) { float f; memcpy(&f, &b, 4); return f; }
static inline double F64(uint32_t esp, int slot) { uint64_t b = (uint64_t)rd(G(esp + 4 + 4 * slot), 8); double d; memcpy(&d, &b, 8); return d; }

void gl_missing(const char *name);
static inline void gl_guest_pointer(uint32_t output, const void *host) {
    uintptr_t address = (uintptr_t)host, base = (uintptr_t)MEM;
    if (host && (address < base || (uint64_t)(address - base) >= (1ull << 32)))
        guest_fatal("OpenGL returned a pointer outside guest memory");
    wr(G(output), 4, host ? (uint32_t)(address - base) : 0);
}
uint32_t gl_guest_string(unsigned int name, const void *host);
void gl_load(void *(*getproc)(const char *));
extern const thunk_def gl_thunks[];
// UI-thread input: 0 absolute menu pointer, 1 scancode, 2 mouse button,
// 3 relative look, 4 menu activation after a frame (control 1 cancels).
// Absolute coordinates use 0..65535; key/button x is held.
int window_push_input(int kind, int control, int x, int y);
