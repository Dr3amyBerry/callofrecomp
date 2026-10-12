// Shims for Win32 services the engine probes but does not need to work:
// DirectDraw (video-memory query), shell, MIDI, joystick.
#include <stdio.h>

#include "recomp_rt.h"

#define K(name) static uint32_t k_##name(uint32_t esp)
#define A(i) ARG(esp, i)

K(Fail) { (void)esp; return 0x80004005u; }  // E_FAIL
K(Zero) { (void)esp; return 0; }
K(MessageBoxA) {
    printf("MessageBox [%s]: %s\n", A(2) ? (const char *)G(A(2)) : "", A(1) ? (const char *)G(A(1)) : "");
    fflush(stdout);
    return 1;  // IDOK
}

#define AL(dll, name, fn, pop) {dll, #name, k_##fn, pop}
const thunk_def misc_thunks[] = {
    AL("DDRAW.dll", DirectDrawCreateEx, Fail, 16),
    AL("DDRAW.dll", DirectDrawEnumerateExA, Zero, 12),
    AL("SHELL32.dll", ShellExecuteA, Zero, 24),
    AL("USER32.dll", MessageBoxA, MessageBoxA, 16),
    {0, 0, 0, 0},
};
