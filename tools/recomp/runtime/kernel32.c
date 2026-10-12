// KERNEL32 shims for recompiled modules: process/CRT services, heap, TLS,
// code pages and module loading. Deterministic where the original is not.
#include <stdio.h>
#include <stdlib.h>
#include <strings.h>

#include "recomp_rt.h"

uint32_t guest_main_base;  // image base returned by GetModuleHandleA(NULL)
const char *guest_command_line = "codrecomp";

static uint32_t last_error, tls[64], tls_next;

static uint32_t ch_at(uint32_t s, uint32_t i, int unit) { return (uint32_t)rd(G(s + i * unit), unit); }

static uint32_t str_len(uint32_t s, int32_t n, int unit) {
    if (n >= 0) return (uint32_t)n;
    uint32_t i = 0;
    while (ch_at(s, i, unit)) i++;
    return i + 1;  // -1 means NUL-terminated, count includes the terminator
}

static uint32_t convert_chars(uint32_t src, int32_t n, int su, uint32_t dst, uint32_t cap, int du) {
    uint32_t len = str_len(src, n, su);
    if (!cap) return len;
    if (cap < len) return 0;
    for (uint32_t i = 0; i < len; i++) {
        uint32_t c = ch_at(src, i, su);
        wr(G(dst + i * du), du, du == 1 && c > 0xFF ? '?' : c);
    }
    return len;
}

static uint32_t string_type(uint32_t src, int32_t n, int unit, uint32_t out) {  // CT_CTYPE1
    uint32_t len = str_len(src, n, unit);
    for (uint32_t i = 0; i < len; i++) {
        uint32_t c = ch_at(src, i, unit), t = 0;
        if (c < 0x80) {
            if (c >= 'A' && c <= 'Z') t |= 0x001 | 0x100;
            if (c >= 'a' && c <= 'z') t |= 0x002 | 0x100;
            if (c >= '0' && c <= '9') t |= 0x004 | 0x080;
            if ((c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')) t |= 0x080;
            if (c == ' ' || (c >= 9 && c <= 13)) t |= 0x008;
            if (c == ' ' || c == '\t') t |= 0x040;
            if (c < 0x20 || c == 0x7F) t |= 0x020;
            if (c > 0x20 && c < 0x7F && !(t & 0x104)) t |= 0x010;
        }
        wr(G(out + 2 * i), 2, t);
    }
    return 1;
}

static uint32_t map_string(uint32_t flags, uint32_t src, int32_t n, int unit, uint32_t dst, uint32_t cap) {
    uint32_t len = str_len(src, n, unit);
    if (!cap) return len;
    if (cap < len) return 0;
    for (uint32_t i = 0; i < len; i++) {
        uint32_t c = ch_at(src, i, unit);
        if ((flags & 0x100) && c >= 'A' && c <= 'Z') c += 32;  // LCMAP_LOWERCASE
        if ((flags & 0x200) && c >= 'a' && c <= 'z') c -= 32;  // LCMAP_UPPERCASE
        wr(G(dst + i * unit), unit, c);
    }
    return len;
}

static uint32_t compare_string(uint32_t flags, uint32_t a, int32_t na, uint32_t b, int32_t nb, int unit) {
    uint32_t la = str_len(a, na, unit), lb = str_len(b, nb, unit);
    for (uint32_t i = 0; i < la && i < lb; i++) {
        uint32_t x = ch_at(a, i, unit), y = ch_at(b, i, unit);
        if (flags & 1) {  // NORM_IGNORECASE
            if (x >= 'A' && x <= 'Z') x += 32;
            if (y >= 'A' && y <= 'Z') y += 32;
        }
        if (x != y) return x < y ? 1 : 3;
    }
    return la == lb ? 2 : (la < lb ? 1 : 3);  // CSTR_LESS_THAN / EQUAL / GREATER_THAN
}

#define K(name) static uint32_t k_##name(uint32_t esp)
#define A(i) ARG(esp, i)

K(GetLastError) { (void)esp; return last_error; }
K(SetLastError) { last_error = A(0); return 0; }
K(GetCurrentThreadId) { (void)esp; return 1; }
K(GetCurrentThread) { (void)esp; return 0xFFFFFFFEu; }
K(GetCurrentProcess) { (void)esp; return 0xFFFFFFFFu; }
K(GetTickCount) { (void)esp; static uint32_t t = 1000; return t += 16; }
K(TlsAlloc) { (void)esp; return tls_next < 64 ? tls_next++ : 0xFFFFFFFFu; }
K(TlsSetValue) { tls[A(0) & 63] = A(1); return 1; }
K(TlsGetValue) { return tls[A(0) & 63]; }
K(ReturnTrue) { (void)esp; return 1; }
K(ReturnZero) { (void)esp; return 0; }
K(GetVersionExA) {
    uint32_t v[5] = {148, 5, 1, 2600, 2};  // Windows XP, VER_PLATFORM_WIN32_NT
    memcpy(G(A(0)), v, sizeof v);
    return 1;
}
K(HeapCreate) { (void)esp; return 0x00710000u; }
K(HeapAlloc) { return guest_alloc(A(2)); }
K(HeapSize) { return mem32(A(2) - 16); }
K(HeapReAlloc) {
    uint32_t old = A(2), n = A(3), p = guest_alloc(n), oldn = mem32(old - 16);
    memcpy(G(p), G(old), oldn < n ? oldn : n);
    return p;
}
K(VirtualAlloc) {
    if (A(0)) { guest_commit(A(0), A(1)); return A(0); }
    return (guest_alloc(A(1) + 4096) + 4095) & ~4095u;
}
K(GetCommandLineA) { (void)esp; static uint32_t s; return s ? s : (s = guest_strdup(guest_command_line)); }
K(GetEnvironmentStrings) { (void)esp; return guest_alloc(8); }
K(GetStartupInfoA) { memset(G(A(0)), 0, 68); wr(G(A(0)), 4, 68); return 0; }
K(GetStdHandle) { (void)esp; return 0xFFFFFFFFu; }
K(SetHandleCount) { return A(0); }
K(GetModuleFileNameA) {
    const char *s = "C:\\codrecomp\\CoDSP.exe";
    uint32_t n = (uint32_t)strlen(s) < A(2) ? (uint32_t)strlen(s) : A(2) - 1;
    memcpy(G(A(1)), s, n);
    wr(G(A(1) + n), 1, 0);
    return n;
}
K(GetModuleHandleA) {
    if (!A(0)) return guest_main_base;
    const recomp_module *m = module_by_name((const char *)G(A(0)));
    return m ? m->image_base : 0;
}
static int host_dll_handle_valid(uint32_t h) { return h >= 0x7F000000u && h < 0x80000000u; }

K(GetProcAddress) {
    if (A(1) > 0xFFFF && host_dll_handle_valid(A(0))) return host_dll_proc(A(0), (const char *)G(A(1)));
    const recomp_module *m = module_loaded_at(A(0));
    return m && A(1) > 0xFFFF ? module_export(m, (const char *)G(A(1))) : 0;
}
K(LoadLibraryA) {
    const char *name = (const char *)G(A(0));
    const recomp_module *m;
    const char *path = module_available_path(name, &m);
    uint32_t host = host_dll_handle(name);
    if (!path && host) return host;
    if (!path) {
        printf("LoadLibraryA(\"%s\") -> not available\n", name);
        return 0;
    }
    if (!module_by_name(m->name)) {
        if (!module_load(m, path)) return 0;
        uint32_t attach[3] = {m->image_base, 1, 0};
        if (!guest_call(m->entry_point, 3, attach)) return 0;
    }
    return m->image_base;
}
K(FreeLibrary) { (void)esp; return 1; }
K(GetACP) { (void)esp; return 1252; }
K(GetOEMCP) { (void)esp; return 437; }
K(GetCPInfo) {  // single-byte code page, default char '?'
    memset(G(A(1)), 0, 20);
    wr(G(A(1)), 4, 1);
    wr(G(A(1) + 4), 1, '?');
    return 1;
}
K(QueryPerformanceCounter) { static uint64_t t = 1000000; wr(G(A(0)), 8, t += 16000); return 1; }
K(QueryPerformanceFrequency) { wr(G(A(0)), 8, 1000000); return 1; }
K(GetSystemTimeAsFileTime) { wr(G(A(0)), 8, 0x01C4000000000000ull); return 0; }
K(GetSystemInfo) {
    memset(G(A(0)), 0, 36);
    wr(G(A(0) + 4), 4, 4096);
    wr(G(A(0) + 28), 4, 65536);
    return 0;
}
K(WideCharToMultiByte) { return convert_chars(A(2), A(3), 2, A(4), A(5), 1); }
K(MultiByteToWideChar) { return convert_chars(A(2), A(3), 1, A(4), A(5), 2); }
K(GetStringTypeA) { return string_type(A(2), A(3), 1, A(4)); }
K(GetStringTypeW) { return string_type(A(1), A(2), 2, A(3)); }
K(LCMapStringA) { return map_string(A(1), A(2), A(3), 1, A(4), A(5)); }
K(LCMapStringW) { return map_string(A(1), A(2), A(3), 2, A(4), A(5)); }
K(CompareStringA) { return compare_string(A(1), A(2), A(3), A(4), A(5), 1); }
K(CompareStringW) { return compare_string(A(1), A(2), A(3), A(4), A(5), 2); }
K(ExitProcess) { printf("ExitProcess(%u)\n", A(0)); fflush(stdout); exit((int)A(0)); }
K(OutputDebugStringA) { printf("ODS: %s", (const char *)G(A(0))); return 0; }

#define S(name, pop) {"KERNEL32.dll", #name, k_##name, pop}
#define ALIAS(name, fn, pop) {"KERNEL32.dll", #name, k_##fn, pop}
const thunk_def kernel32_thunks[] = {
    S(GetLastError, 0), S(SetLastError, 4), S(GetCurrentThreadId, 0), ALIAS(GetCurrentProcessId, GetCurrentThreadId, 0),
    S(GetCurrentThread, 0), S(GetCurrentProcess, 0), S(GetTickCount, 0), S(TlsAlloc, 0), S(TlsSetValue, 8),
    S(TlsGetValue, 4), ALIAS(TlsFree, ReturnTrue, 4), S(GetVersionExA, 4), S(HeapCreate, 12),
    ALIAS(HeapDestroy, ReturnTrue, 4), ALIAS(HeapFree, ReturnTrue, 12), S(HeapAlloc, 12), S(HeapSize, 12),
    S(HeapReAlloc, 16), S(VirtualAlloc, 16), ALIAS(VirtualFree, ReturnTrue, 12), ALIAS(VirtualProtect, ReturnTrue, 16),
    S(GetCommandLineA, 0), S(GetEnvironmentStrings, 0), ALIAS(GetEnvironmentStringsW, GetEnvironmentStrings, 0),
    ALIAS(FreeEnvironmentStringsA, ReturnTrue, 4), ALIAS(FreeEnvironmentStringsW, ReturnTrue, 4),
    S(GetStartupInfoA, 4), S(GetStdHandle, 4), ALIAS(GetFileType, ReturnZero, 4), S(SetHandleCount, 4),
    S(GetModuleFileNameA, 12), S(GetModuleHandleA, 4), S(GetProcAddress, 8), S(LoadLibraryA, 4),
    S(FreeLibrary, 4), S(GetACP, 0), S(GetOEMCP, 0), S(GetCPInfo, 8),
    ALIAS(InitializeCriticalSection, ReturnZero, 4), ALIAS(EnterCriticalSection, ReturnZero, 4),
    ALIAS(LeaveCriticalSection, ReturnZero, 4), ALIAS(DeleteCriticalSection, ReturnZero, 4),
    S(QueryPerformanceCounter, 4), S(QueryPerformanceFrequency, 4), S(GetSystemTimeAsFileTime, 4),
    S(GetSystemInfo, 4), S(WideCharToMultiByte, 32), S(MultiByteToWideChar, 24), S(GetStringTypeA, 20),
    S(GetStringTypeW, 16), S(LCMapStringA, 24), S(LCMapStringW, 24), S(CompareStringA, 24), S(CompareStringW, 24),
    S(ExitProcess, 4), S(OutputDebugStringA, 4),
    {0, 0, 0, 0},
};
