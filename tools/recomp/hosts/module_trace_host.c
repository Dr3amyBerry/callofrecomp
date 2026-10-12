// Runs one recompiled module like LoadLibrary + engine would (DllMain,
// dllEntry, vmMain sequence from trace.h) and logs engine syscalls in the
// same format as native_host.c. Build with -DRECOMP_MODULE=recomp_module_<name>.
#include <stdio.h>

#include "recomp_rt.h"
#include "trace.h"

extern const recomp_module RECOMP_MODULE;

static const char *guest_str(uint32_t a) { return a && guest_committed(a) ? (const char *)G(a) : NULL; }

static uint32_t syscall_thunk(uint32_t esp) {  // cdecl: int syscall(int id, ...)
    uint32_t args[TRACE_ARGS];
    for (int i = 0; i < TRACE_ARGS; i++) args[i] = ARG(esp, 1 + i);
    return trace_syscall((int32_t)ARG(esp, 0), args, guest_str);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <original %s>\n", argv[0], RECOMP_MODULE.name);
        return 1;
    }
    guest_init();
    shims_register(kernel32_thunks);
    if (!module_load(&RECOMP_MODULE, argv[1])) { perror(argv[1]); return 2; }
    guest_main_base = RECOMP_MODULE.image_base;

    uint32_t attach[3] = {RECOMP_MODULE.image_base, 1, 0};  // DllMain(DLL_PROCESS_ATTACH)
    if (!guest_call(RECOMP_MODULE.entry_point, 3, attach)) { printf("DllMain failed\n"); return 7; }

    uint32_t cb = thunk_address("host", "syscall", syscall_thunk, 0);
    guest_call(module_export(&RECOMP_MODULE, "dllEntry"), 1, &cb);
    for (int i = 0; i < trace_command_count; i++) {
        trace_vmmain_begin(i);
        trace_vmmain_end(guest_call(module_export(&RECOMP_MODULE, "vmMain"), 13, trace_commands[i].args));
    }
    return 0;
}
