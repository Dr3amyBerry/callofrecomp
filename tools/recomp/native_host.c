// 32-bit reference host: loads the ORIGINAL module with LoadLibrary and replays
// the trace.h command sequence. Build with an i686 Windows compiler.
#include <stdarg.h>
#include <stdlib.h>
#include <windows.h>

#include "trace.h"

static const char *native_str(uint32_t a) {
    MEMORY_BASIC_INFORMATION mbi;
    if (!a || !VirtualQuery((void *)(uintptr_t)a, &mbi, sizeof mbi) || mbi.State != MEM_COMMIT ||
        (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)))
        return NULL;
    return (const char *)(uintptr_t)a;
}

static int __cdecl syscall_cb(int id, ...) {
    uint32_t args[TRACE_ARGS];
    va_list ap;
    va_start(ap, id);
    for (int i = 0; i < TRACE_ARGS; i++) args[i] = va_arg(ap, uint32_t);
    va_end(ap);
    return (int)trace_syscall(id, args, native_str);
}

static LONG CALLBACK on_fault(EXCEPTION_POINTERS *e) {
    ULONG_PTR addr = e->ExceptionRecord->NumberParameters > 1 ? e->ExceptionRecord->ExceptionInformation[1] : 0;
    printf("CRASH code=%08lx guest_addr=%08lx pc=%08lx\n", e->ExceptionRecord->ExceptionCode,
           (unsigned long)addr, (unsigned long)e->ContextRecord->Eip);
    fflush(stdout);
    ExitProcess(3);
    return EXCEPTION_CONTINUE_SEARCH;
}

typedef void(__cdecl *dll_entry_fn)(void *);
typedef int(__cdecl *vm_main_fn)(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t,
                                 uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s <original module.dll>\n", argv[0]); return 1; }
    AddVectoredExceptionHandler(1, on_fault);
    HMODULE h = LoadLibraryA(argv[1]);
    if (!h) { printf("LoadLibrary failed %lu\n", GetLastError()); return 2; }
    dll_entry_fn entry = (dll_entry_fn)GetProcAddress(h, "dllEntry");
    vm_main_fn vm = (vm_main_fn)GetProcAddress(h, "vmMain");
    entry((void *)syscall_cb);
    for (int i = 0; i < trace_command_count; i++) {
        const uint32_t *a = trace_commands[i].args;
        trace_vmmain_begin(i);
        trace_vmmain_end((uint32_t)vm(a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8], a[9], a[10], a[11], a[12]));
    }
    return 0;
}
