// Host for a module recompiled by pcode2c.py: maps the original PE sections
// into a 4 GiB guest space, runs the generated code and logs engine syscalls
// in the same trace format as native_host.c so both can be diffed.
#include "recomp_rt.h"

#include <stdio.h>
#include <stdlib.h>
#include <windows.h>

#include "trace.h"

uint8_t *MEM;
uint8_t R[0x2000];
uint8_t U[0x320000];
uint32_t PC;
int recomp_miss;

enum { REG_EAX = 0x0, REG_ESP = 0x10, REG_FS_OFFSET = 0x110 };
#define EXIT_PC 0xFFFFFFF0u
#define SYSCALL_PC 0xFFFF0000u
#define IMPORT_PC 0xFFFE0000u
#define STACK_TOP 0x10100000u
#define SCRATCH 0x0FF00000u
#define TIB 0x0FF10000u

static uint32_t r32(uint32_t off) { return (uint32_t)rd(R + off, 4); }
static void w32(uint32_t off, uint32_t v) { wr(R + off, 4, v); }
static uint32_t m32(uint32_t a) { return (uint32_t)rd(G(a), 4); }

static void commit(uint32_t addr, uint32_t size) {
    if (!VirtualAlloc(MEM + addr, size, MEM_COMMIT, PAGE_READWRITE)) {
        fprintf(stderr, "commit failed %08x\n", addr);
        exit(2);
    }
}

void unsupported(const char *what) {
    printf("UNSUPPORTED %s at %08x\n", what, PC);
    exit(4);
}

u128 cpuid_ptr(void) { return SCRATCH; }

u128 rdtsc_val(void) {
    static uint64_t t;
    return t += 1000;
}  // zeroed: report no CPU features

static int guest_readable(uint32_t a) {
    MEMORY_BASIC_INFORMATION mbi;
    return VirtualQuery(MEM + a, &mbi, sizeof mbi) && mbi.State == MEM_COMMIT;
}

static const char *guest_str(uint32_t a) {
    return a && guest_readable(a) ? (const char *)(MEM + a) : NULL;
}

static LONG CALLBACK on_fault(EXCEPTION_POINTERS *e) {
    ULONG_PTR addr = e->ExceptionRecord->NumberParameters > 1 ? e->ExceptionRecord->ExceptionInformation[1] : 0;
    printf("CRASH code=%08lx guest_addr=%08llx pc=%08x\n", e->ExceptionRecord->ExceptionCode,
           (unsigned long long)(addr - (ULONG_PTR)MEM), PC);
    fflush(stdout);
    ExitProcess(3);
    return EXCEPTION_CONTINUE_SEARCH;
}

// Guest heap: bump allocator with a 16-byte size header, never reused.
#define HEAP_BASE 0x60000000u
#define HEAP_SIZE 0x08000000u
static uint32_t heap_top = HEAP_BASE;

static uint32_t guest_alloc(uint32_t size) {
    uint32_t p = heap_top + 16;
    heap_top = (p + size + 15) & ~15u;
    if (heap_top > HEAP_BASE + HEAP_SIZE) unsupported("guest heap exhausted");
    wr(G(p - 16), 4, size);
    memset(G(p), 0, size);
    return p;
}

static uint32_t guest_cstr(const char *s) {
    uint32_t p = guest_alloc((uint32_t)strlen(s) + 2);  // double NUL for env blocks
    memcpy(G(p), s, strlen(s));
    return p;
}

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

// stdcall KERNEL32 shims used by the statically linked MSVC CRT.
// Return value; *nargs = argument words the callee pops.
static uint32_t import_call(const char *name, uint32_t esp, int *nargs) {
#define IS(n, k) (!strcmp(name, n) && (*nargs = (k), 1))
#define A(i) m32(esp + 4 + 4 * (i))
    static uint32_t tls[64], tls_next, last_error;
    *nargs = 0;
    if (IS("GetLastError", 0)) return last_error;
    if (IS("SetLastError", 1)) { last_error = A(0); return 0; }
    if (IS("GetCurrentThreadId", 0) || IS("GetCurrentProcessId", 0)) return 1;
    if (IS("GetCurrentThread", 0)) return 0xFFFFFFFEu;
    if (IS("GetCurrentProcess", 0)) return 0xFFFFFFFFu;
    if (IS("GetTickCount", 0)) return 1000;
    if (IS("TlsAlloc", 0)) return tls_next < 64 ? tls_next++ : 0xFFFFFFFFu;
    if (IS("TlsSetValue", 2)) { tls[A(0) & 63] = A(1); return 1; }
    if (IS("TlsGetValue", 1)) return tls[A(0) & 63];
    if (IS("TlsFree", 1)) return 1;
    if (IS("GetVersionExA", 1)) {
        uint32_t v[5] = {148, 5, 1, 2600, 2};  // size, Windows XP, VER_PLATFORM_WIN32_NT
        memcpy(G(A(0)), v, sizeof v);
        return 1;
    }
    if (IS("HeapCreate", 3)) return 0x00710000u;
    if (IS("HeapDestroy", 1) || IS("HeapFree", 3)) return 1;
    if (IS("HeapAlloc", 3)) return guest_alloc(A(2));
    if (IS("HeapSize", 3)) return m32(A(2) - 16);
    if (IS("HeapReAlloc", 4)) {
        uint32_t old = A(2), n = A(3), p = guest_alloc(n), oldn = m32(old - 16);
        memcpy(G(p), G(old), oldn < n ? oldn : n);
        return p;
    }
    if (IS("VirtualAlloc", 4)) return A(0) ? A(0) : guest_alloc(A(1) + 4096) + 4095 & ~4095u;
    if (IS("VirtualFree", 3) || IS("VirtualProtect", 4)) return 1;
    if (IS("GetCommandLineA", 0)) { static uint32_t s; return s ? s : (s = guest_cstr("codrecomp")); }
    if (IS("GetEnvironmentStrings", 0) || IS("GetEnvironmentStringsW", 0)) return guest_alloc(8);
    if (IS("FreeEnvironmentStringsA", 1) || IS("FreeEnvironmentStringsW", 1)) return 1;
    if (IS("GetStartupInfoA", 1)) { memset(G(A(0)), 0, 68); wr(G(A(0)), 4, 68); return 0; }
    if (IS("GetStdHandle", 1)) return 0xFFFFFFFFu;
    if (IS("GetFileType", 1)) return 0;
    if (IS("SetHandleCount", 1)) return A(0);
    if (IS("GetModuleFileNameA", 3)) {
        const char *s = "C:\\codrecomp\\module.dll";
        uint32_t n = (uint32_t)strlen(s) < A(2) ? (uint32_t)strlen(s) : A(2) - 1;
        memcpy(G(A(1)), s, n);
        wr(G(A(1) + n), 1, 0);
        return n;
    }
    if (IS("GetModuleHandleA", 1)) return A(0) ? 0 : recomp_image_base;
    if (IS("GetProcAddress", 2)) return 0;
    if (IS("GetACP", 0)) return 1252;
    if (IS("GetOEMCP", 0)) return 437;
    if (IS("GetCPInfo", 2)) {  // single-byte code page, default char '?'
        memset(G(A(1)), 0, 20);
        wr(G(A(1)), 4, 1);
        wr(G(A(1) + 4), 1, '?');
        return 1;
    }
    if (IS("InitializeCriticalSection", 1) || IS("EnterCriticalSection", 1) ||
        IS("LeaveCriticalSection", 1) || IS("DeleteCriticalSection", 1))
        return 0;
    if (IS("QueryPerformanceCounter", 1)) { wr(G(A(0)), 8, 1000000); return 1; }
    if (IS("GetSystemTimeAsFileTime", 1)) { wr(G(A(0)), 8, 0x01C4000000000000ull); return 0; }
    if (IS("GetSystemInfo", 1)) { memset(G(A(0)), 0, 36); wr(G(A(0) + 4), 4, 4096); wr(G(A(0) + 28), 4, 65536); return 0; }
    // Code-page shims: Latin-1 / single-byte only, which is all the CRT setup needs.
    if (IS("WideCharToMultiByte", 8)) return convert_chars(A(2), A(3), 2, A(4), A(5), 1);
    if (IS("MultiByteToWideChar", 6)) return convert_chars(A(2), A(3), 1, A(4), A(5), 2);
    if (IS("GetStringTypeA", 5)) return string_type(A(2), A(3), 1, A(4));
    if (IS("GetStringTypeW", 4)) return string_type(A(1), A(2), 2, A(3));
    if (IS("LCMapStringA", 6)) return map_string(A(1), A(2), A(3), 1, A(4), A(5));
    if (IS("LCMapStringW", 6)) return map_string(A(1), A(2), A(3), 2, A(4), A(5));
    if (IS("CompareStringA", 6)) return compare_string(A(1), A(2), A(3), A(4), A(5), 1);
    if (IS("CompareStringW", 6)) return compare_string(A(1), A(2), A(3), A(4), A(5), 2);
    printf("IMPORT %s not implemented at ret=%08x\n", name, m32(esp));
    exit(5);
#undef IS
#undef A
}

static void run(void) {
    while (PC != EXIT_PC) {
        if (PC == SYSCALL_PC) {
            uint32_t esp = r32(REG_ESP), args[TRACE_ARGS];
            for (int i = 0; i < TRACE_ARGS; i++) args[i] = m32(esp + 8 + 4 * i);
            w32(REG_EAX, trace_syscall((int32_t)m32(esp + 4), args, guest_str));
            PC = m32(esp);
            w32(REG_ESP, esp + 4);
            continue;
        }
        if (PC >= IMPORT_PC && PC < IMPORT_PC + 0x10000) {
            uint32_t esp = r32(REG_ESP);
            int nargs;
            w32(REG_EAX, import_call(recomp_imports[(PC - IMPORT_PC) / 16].name, esp, &nargs));
            PC = m32(esp);
            w32(REG_ESP, esp + 4 + 4 * nargs);
            continue;
        }
        int lo = 0, hi = recomp_chunk_count - 1, found = -1;
        while (lo <= hi) {
            int mid = (lo + hi) / 2;
            if (PC < recomp_chunks[mid].start) hi = mid - 1;
            else if (PC >= recomp_chunks[mid].end) lo = mid + 1;
            else { found = mid; break; }
        }
        recomp_miss = 0;
        if (found >= 0) recomp_chunks[found].fn();
        if (found < 0 || (recomp_miss && PC >= recomp_chunks[found].start && PC < recomp_chunks[found].end)) {
            printf("NO CODE at pc=%08x\n", PC);
            exit(6);
        }
    }
}

static uint32_t call_guest(uint32_t fn, int n, const uint32_t *args) {
    uint32_t saved = r32(REG_ESP), esp = saved;
    for (int i = n - 1; i >= 0; i--) { esp -= 4; wr(G(esp), 4, args[i]); }
    esp -= 4;
    wr(G(esp), 4, EXIT_PC);
    w32(REG_ESP, esp);
    PC = fn;
    run();
    w32(REG_ESP, saved);
    return r32(REG_EAX);
}

static uint32_t entry_point;

static void load_image(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); exit(2); }
    static uint8_t buf[1 << 22];
    size_t n = fread(buf, 1, sizeof buf, f);
    fclose(f);
    commit(recomp_image_base, recomp_image_size);
    uint32_t pe = *(uint32_t *)(buf + 0x3c);
    uint16_t nsec = *(uint16_t *)(buf + pe + 6), optsz = *(uint16_t *)(buf + pe + 20);
    uint32_t hdrs = *(uint32_t *)(buf + pe + 24 + 60);
    entry_point = recomp_image_base + *(uint32_t *)(buf + pe + 24 + 16);
    memcpy(G(recomp_image_base), buf, hdrs);
    for (int i = 0; i < nsec; i++) {
        uint8_t *s = buf + pe + 24 + optsz + 40 * i;
        uint32_t va = *(uint32_t *)(s + 12), rawsz = *(uint32_t *)(s + 16), raw = *(uint32_t *)(s + 20);
        if (raw + rawsz <= n) memcpy(G(recomp_image_base + va), buf + raw, rawsz);
    }
    for (int i = 0; i < recomp_import_count; i++) wr(G(recomp_imports[i].iat_va), 4, IMPORT_PC + 16 * i);
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s <original module.dll>\n", argv[0]); return 1; }
    MEM = VirtualAlloc(NULL, 1ull << 32, MEM_RESERVE, PAGE_NOACCESS);
    AddVectoredExceptionHandler(1, on_fault);
    load_image(argv[1]);
    commit(STACK_TOP - 0x100000, 0x100000);
    commit(SCRATCH, 0x1000);
    // Minimal thread information block for fs:[...]: empty SEH chain, stack bounds, self pointer.
    commit(TIB, 0x1000);
    wr(G(TIB + 0x00), 4, 0xFFFFFFFFu);
    wr(G(TIB + 0x04), 4, STACK_TOP);
    wr(G(TIB + 0x08), 4, STACK_TOP - 0x100000);
    wr(G(TIB + 0x18), 4, TIB);
    w32(REG_FS_OFFSET, TIB);
    w32(REG_ESP, STACK_TOP - 64);

    commit(HEAP_BASE, HEAP_SIZE);

    // Run the module's CRT DllMain(DLL_PROCESS_ATTACH) like LoadLibrary does.
    uint32_t attach[3] = {recomp_image_base, 1, 0};
    if (!call_guest(entry_point, 3, attach)) { printf("DllMain failed\n"); return 7; }

    uint32_t cb = SYSCALL_PC;
    call_guest(recomp_export_dllEntry, 1, &cb);
    for (int i = 0; i < trace_command_count; i++) {
        uint32_t args[13] = {0};
        memcpy(args, trace_commands[i].args, sizeof trace_commands[i].args);
        trace_vmmain_begin(i);
        trace_vmmain_end(call_guest(recomp_export_vmMain, 13, args));
    }
    return 0;
}
