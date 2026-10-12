// Portable runtime for recompiled 32-bit x86 modules: guest address space,
// multi-module dispatch, host thunks and a PE section loader.
#include "recomp_rt.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <strings.h>

#ifdef _WIN32
#include <windows.h>
#else
#include <signal.h>
#include <sys/mman.h>
#include <unistd.h>
#endif

uint8_t *MEM;
uint8_t R[0x2000];
uint8_t U[0x400000];
uint32_t PC;
int recomp_miss;

#define THUNK_BASE 0xFFF00000u
#define THUNK_MAX 4096
#define HEAP_BASE 0x60000000u
#define HEAP_SIZE 0x10000000u
#define STACK_TOP 0x10100000u
#define STACK_SIZE 0x00400000u
#define SCRATCH 0x0FF00000u
#define TIB 0x0FF10000u

void guest_fatal(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    printf("FATAL pc=%08x: ", PC);
    vprintf(fmt, ap);
    printf("\n");
    va_end(ap);
    fflush(stdout);
    exit(5);
}

void unsupported(const char *what) { guest_fatal("unsupported %s", what); }

u128 cpuid_ptr(void) { return SCRATCH; }  // zeroed: report no CPU features

u128 rdtsc_val(void) {
    static uint64_t t;
    return t += 1000;
}

// ---------------------------------------------------------------- memory

static uint8_t committed[1u << 20];  // one flag per 4 KiB page

void guest_commit(uint32_t addr, uint32_t size) {
    uint32_t first = addr >> 12, last = (uint32_t)(((uint64_t)addr + size + 4095) >> 12);
    for (uint32_t p = first; p < last; p++) {
        if (committed[p]) continue;
#ifdef _WIN32
        if (!VirtualAlloc(MEM + ((uint64_t)p << 12), 4096, MEM_COMMIT, PAGE_READWRITE))
#else
        if (mprotect(MEM + ((uint64_t)p << 12), 4096, PROT_READ | PROT_WRITE))
#endif
            guest_fatal("commit failed at %08x", p << 12);
        committed[p] = 1;
    }
}

int guest_committed(uint32_t addr) { return committed[addr >> 12]; }

static uint32_t heap_top = HEAP_BASE;

uint32_t guest_alloc(uint32_t size) {
    uint32_t p = heap_top + 16;
    uint64_t top = ((uint64_t)p + size + 15) & ~15ull;
    if (top > HEAP_BASE + HEAP_SIZE) guest_fatal("guest heap exhausted (%u bytes)", size);
    heap_top = (uint32_t)top;
    guest_commit(p - 16, size + 16);
    wr(G(p - 16), 4, size);
    memset(G(p), 0, size);
    return p;
}

uint32_t guest_strdup(const char *s) {
    uint32_t n = (uint32_t)strlen(s), p = guest_alloc(n + 2);  // double NUL for env blocks
    memcpy(G(p), s, n);
    return p;
}

static void on_fault_report(uint64_t host_addr) {
    printf("CRASH guest_addr=%08llx pc=%08x\n", (unsigned long long)(host_addr - (uint64_t)(uintptr_t)MEM), PC);
    fflush(stdout);
}

#ifdef _WIN32
static LONG CALLBACK on_fault(EXCEPTION_POINTERS *e) {
    if (e->ExceptionRecord->ExceptionCode != EXCEPTION_ACCESS_VIOLATION) return EXCEPTION_CONTINUE_SEARCH;
    on_fault_report(e->ExceptionRecord->ExceptionInformation[1]);
    ExitProcess(3);
    return EXCEPTION_CONTINUE_SEARCH;
}
#else
static void on_fault(int sig, siginfo_t *info, void *ctx) {
    (void)sig;
    (void)ctx;
    on_fault_report((uint64_t)(uintptr_t)info->si_addr);
    _exit(3);
}
#endif

void guest_init(void) {
#ifdef _WIN32
    MEM = VirtualAlloc(NULL, 1ull << 32, MEM_RESERVE, PAGE_NOACCESS);
    AddVectoredExceptionHandler(1, on_fault);
#else
    MEM = mmap(NULL, 1ull << 32, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
    if (MEM == MAP_FAILED) MEM = NULL;
    struct sigaction sa = {0};
    sa.sa_sigaction = on_fault;
    sa.sa_flags = SA_SIGINFO;
    sigaction(SIGSEGV, &sa, NULL);
    sigaction(SIGBUS, &sa, NULL);
#endif
    if (!MEM) guest_fatal("cannot reserve 4 GiB guest space");
    guest_commit(STACK_TOP - STACK_SIZE, STACK_SIZE);
    guest_commit(SCRATCH, 0x1000);
    // Minimal thread information block for fs:[...]: empty SEH chain, stack bounds, self pointer.
    guest_commit(TIB, 0x1000);
    wr(G(TIB + 0x00), 4, 0xFFFFFFFFu);
    wr(G(TIB + 0x04), 4, STACK_TOP);
    wr(G(TIB + 0x08), 4, STACK_TOP - STACK_SIZE);
    wr(G(TIB + 0x18), 4, TIB);
    set_reg32(REG_FS_OFFSET, TIB);
    set_reg32(REG_ESP, STACK_TOP - 64);
}

// ---------------------------------------------------------------- thunks

typedef struct { const char *dll, *name; thunk_fn fn; int pop; } thunk_slot;
static thunk_slot thunks[THUNK_MAX];
static int thunk_count;
static const thunk_def *shim_tables[64];
static int shim_table_count;

void shims_register(const thunk_def *table) { shim_tables[shim_table_count++] = table; }

uint32_t thunk_address(const char *dll, const char *name, thunk_fn fn, int pop) {
    for (int i = 0; i < thunk_count; i++)
        if (thunks[i].fn == fn && !strcasecmp(thunks[i].dll, dll) && !strcmp(thunks[i].name, name))
            return THUNK_BASE + 16 * i;
    if (thunk_count == THUNK_MAX) guest_fatal("too many thunks");
    thunks[thunk_count] = (thunk_slot){dll, name, fn, pop};
    return THUNK_BASE + 16 * thunk_count++;
}

static uint32_t missing_import(uint32_t esp) {
    thunk_slot *t = &thunks[(PC - THUNK_BASE) / 16];
    guest_fatal("import %s!%s not implemented (ret=%08x)", t->dll, t->name, mem32(esp));
    return 0;
}

uint32_t shim_lookup(const char *dll, const char *name) {
    for (int t = 0; t < shim_table_count; t++)
        for (const thunk_def *d = shim_tables[t]; d->name; d++)
            if (!strcasecmp(d->dll, dll) && !strcmp(d->name, name)) return thunk_address(d->dll, d->name, d->fn, d->pop);
    return 0;
}

// Host-provided DLLs (e.g. opengl32.dll) loadable through LoadLibraryA.
static const char *host_dlls[16];
static int host_dll_count;
#define HOST_DLL_BASE 0x7F000000u

void host_dll_register(const char *name) { host_dlls[host_dll_count++] = name; }

static void dll_basename(const char *in, char *out, size_t cap) {
    const char *b = in;
    for (const char *p = in; *p; p++)
        if (*p == '\\' || *p == '/') b = p + 1;
    snprintf(out, cap, "%s%s", b, strchr(b, '.') ? "" : ".dll");
}

uint32_t host_dll_handle(const char *name) {
    char base[128];
    dll_basename(name, base, sizeof base);
    for (int i = 0; i < host_dll_count; i++)
        if (!strcasecmp(host_dlls[i], base)) return HOST_DLL_BASE + 0x10000u * (uint32_t)i;
    return 0;
}

uint32_t host_dll_proc(uint32_t handle, const char *name) {
    uint32_t i = (handle - HOST_DLL_BASE) / 0x10000u;
    if (handle < HOST_DLL_BASE || i >= (uint32_t)host_dll_count) return 0;
    return shim_lookup(host_dlls[i], name);
}

static uint32_t resolve_import(const char *dll, const char *name) {
    uint32_t t = shim_lookup(dll, name);
    if (t) return t;
    const recomp_module *m = module_by_name(dll);
    if (m) {
        uint32_t va = module_export(m, name);
        if (va) return va;
    }
    return thunk_address(dll, name, missing_import, 0);
}

// ---------------------------------------------------------------- modules

static const recomp_module *loaded[16];
static int loaded_count;
static struct { const recomp_module *m; const char *path; } available[16];
static int available_count;
static recomp_chunk all_chunks[4096];
static int all_chunk_count;

const recomp_module *module_by_name(const char *name) {
    for (int i = 0; i < loaded_count; i++)
        if (!strcasecmp(loaded[i]->name, name)) return loaded[i];
    return NULL;
}

const recomp_module *module_loaded_at(uint32_t base) {
    for (int i = 0; i < loaded_count; i++)
        if (loaded[i]->image_base == base) return loaded[i];
    return NULL;
}

uint32_t module_export(const recomp_module *m, const char *name) {
    for (const recomp_export *e = m->exports; e->name; e++)
        if (!strcmp(e->name, name)) return e->va;
    return 0;
}

void module_register_available(const recomp_module *m, const char *path) {
    available[available_count].m = m;
    available[available_count++].path = path;
}

const char *module_available_path(const char *name, const recomp_module **out) {
    for (int i = 0; i < available_count; i++) {
        const char *base = strrchr(name, '\\');
        base = base ? base + 1 : name;
        const char *base2 = strrchr(base, '/');
        base = base2 ? base2 + 1 : base;
        if (!strcasecmp(available[i].m->name, base)) {
            *out = available[i].m;
            return available[i].path;
        }
    }
    return NULL;
}

static int cmp_chunk(const void *a, const void *b) {
    uint32_t x = ((const recomp_chunk *)a)->start, y = ((const recomp_chunk *)b)->start;
    return x < y ? -1 : x > y;
}

int module_load(const recomp_module *m, const char *path) {
    if (module_by_name(m->name)) return 1;
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *buf = malloc((size_t)n);
    if (!buf || fread(buf, 1, (size_t)n, f) != (size_t)n) guest_fatal("cannot read %s", path);
    fclose(f);

    guest_commit(m->image_base, m->image_size);
    uint32_t pe;
    memcpy(&pe, buf + 0x3c, 4);
    uint16_t nsec = (uint16_t)rd(buf + pe + 6, 2), optsz = (uint16_t)rd(buf + pe + 20, 2);
    uint32_t hdrs = (uint32_t)rd(buf + pe + 24 + 60, 4);
    memcpy(G(m->image_base), buf, hdrs);
    for (int i = 0; i < nsec; i++) {
        uint8_t *s = buf + pe + 24 + optsz + 40 * i;
        uint32_t va = (uint32_t)rd(s + 12, 4), rawsz = (uint32_t)rd(s + 16, 4), raw = (uint32_t)rd(s + 20, 4);
        uint32_t vsz = (uint32_t)rd(s + 8, 4);
        if (rawsz > vsz && vsz) rawsz = vsz;
        if (raw + rawsz <= (uint32_t)n) memcpy(G(m->image_base + va), buf + raw, rawsz);
    }
    free(buf);

    loaded[loaded_count++] = m;
    for (int i = 0; i < m->chunk_count; i++) all_chunks[all_chunk_count++] = m->chunks[i];
    qsort(all_chunks, all_chunk_count, sizeof all_chunks[0], cmp_chunk);
    for (const recomp_import *im = m->imports; im->dll; im++) wr(G(im->iat_va), 4, resolve_import(im->dll, im->name));
    return 1;
}

// ---------------------------------------------------------------- execution

void guest_run(void) {
    while (PC != GUEST_EXIT_PC) {
        if (PC >= THUNK_BASE && PC < THUNK_BASE + 16 * THUNK_MAX) {
            thunk_slot *t = &thunks[(PC - THUNK_BASE) / 16];
            uint32_t esp = reg32(REG_ESP), ret = mem32(esp);
            set_reg32(REG_EAX, t->fn(esp));
            set_reg32(REG_ESP, esp + 4 + t->pop);
            PC = ret;
            continue;
        }
        int lo = 0, hi = all_chunk_count - 1, found = -1;
        while (lo <= hi) {
            int mid = (lo + hi) / 2;
            if (PC < all_chunks[mid].start) hi = mid - 1;
            else if (PC >= all_chunks[mid].end) lo = mid + 1;
            else { found = mid; break; }
        }
        recomp_miss = 0;
        if (found >= 0) all_chunks[found].fn();
        if (found < 0 || (recomp_miss && PC >= all_chunks[found].start && PC < all_chunks[found].end))
            guest_fatal("no recompiled code at this address");
    }
}

uint32_t guest_call(uint32_t fn, int n, const uint32_t *args) {
    uint32_t saved_esp = reg32(REG_ESP), saved_pc = PC, esp = saved_esp;
    for (int i = n - 1; i >= 0; i--) { esp -= 4; wr(G(esp), 4, args[i]); }
    esp -= 4;
    wr(G(esp), 4, GUEST_EXIT_PC);
    set_reg32(REG_ESP, esp);
    PC = fn;
    guest_run();
    set_reg32(REG_ESP, saved_esp);
    PC = saved_pc;
    return reg32(REG_EAX);
}
