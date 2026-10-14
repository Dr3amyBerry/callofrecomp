// Portable runtime for recompiled 32-bit x86 modules: guest address space,
// multi-module dispatch, host thunks and a PE section loader.
#include "recomp_rt.h"
#include "module_lifecycle.h"
#include "heap_lifecycle.h"
#include "dispatch_index.h"
#include "pe_loader_bounds.h"
#include "commit_runs.h"
#ifdef __ANDROID__
#include "compass_markers.h"
#endif
#if defined(CODRECOMP_HOT_X87_FASTPATH)
#include "hot_x87_transform.h"
#endif

#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#if defined(__i386__) || defined(__x86_64__)
#include <x86intrin.h>
#endif

#ifdef _WIN32
#include <windows.h>
#else
#include <signal.h>
#include <sys/mman.h>
#include <unistd.h>
#include <time.h>
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
// The full stack is 0x0FD00000..0x10100000. Keep host service pages below it.
#define SCRATCH 0x0FC00000u
#define TIB 0x0FC10000u

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
    if (shim_realtime) {
#if defined(__i386__) || defined(__x86_64__)
        return __rdtsc();
#else
        return host_counter(); // portable virtual 1-GHz counter
#endif
    }
    static uint64_t t;
    return t += 1000;
}

// ---------------------------------------------------------------- memory

static uint8_t committed[1u << 20];  // one flag per 4 KiB page

void guest_commit(uint32_t addr, uint32_t size) {
    if ((uint64_t)addr + size > (1ull << 32)) guest_fatal("commit outside guest memory");
    uint32_t first = addr >> 12, last = (uint32_t)(((uint64_t)addr + size + 4095) >> 12);
    uint32_t cursor = first, p, count;
    while (commit_next_run(committed, &cursor, last, &p, &count)) {
        size_t length = (size_t)count << 12;
#ifdef _WIN32
        if (!VirtualAlloc(MEM + ((uint64_t)p << 12), length, MEM_COMMIT, PAGE_READWRITE))
#else
        if (mprotect(MEM + ((uint64_t)p << 12), length, PROT_READ | PROT_WRITE))
#endif
            guest_fatal("commit failed at %08x", p << 12);
        memset(committed + p, 1, count);
    }
}

int guest_committed(uint32_t addr) { return committed[addr >> 12]; }

static uint32_t heap_top = HEAP_BASE;
typedef struct heap_block {
    uint32_t base, span, size;
    struct heap_block *next;
    uint32_t owner;
} heap_block;
static uint32_t heap_handles[128], next_heap_handle = 0x00710001u;
static int heap_handle_valid(uint32_t handle) {
    if (handle == 0x00710000u) return 1;
    for (unsigned i = 0; i < 128; i++) if (heap_handles[i] == handle && handle) return 1;
    return 0;
}
static heap_block *heap_live[4096], *heap_free;
static unsigned heap_hash(uint32_t address) { return (address >> 4) & 4095; }
static heap_block *heap_find(uint32_t address) {
    for (heap_block *b = heap_live[heap_hash(address)]; b; b = b->next)
        if (b->base + 16 == address) return b;
    return NULL;
}
uint32_t guest_heap_alloc(uint32_t size) {
    uint64_t span64 = 16 + (((uint64_t)(size ? size : 1) + 15) & ~15ull);
    if (span64 > HEAP_SIZE) return 0;
    uint32_t span = (uint32_t)span64;
    heap_block *b = NULL;
    heap_block **link = &heap_free;
    while (*link && (*link)->span < span) link = &(*link)->next;
    if (*link) {
        b = *link;
        if (b->span > span) {
            heap_block *rest = malloc(sizeof *rest);
            if (!rest) return 0;
            *rest = (heap_block){b->base + span, b->span - span, 0, b->next};
            *link = rest;
        } else *link = b->next;
    } else {
        if ((uint64_t)heap_top + span > (uint64_t)HEAP_BASE + HEAP_SIZE) return 0;
        b = malloc(sizeof *b); if (!b) return 0;
        b->base = heap_top; heap_top += span;
    }
    b->span = span; b->size = size; b->owner = 0x00710000u;
    uint32_t p = b->base + 16;
    unsigned hash = heap_hash(p); b->next = heap_live[hash]; heap_live[hash] = b;
    guest_commit(b->base, span); wr(G(b->base), 4, size);
    memset(G(p), 0, size); return p;
}
int guest_heap_free(uint32_t address) {
    heap_block **live = &heap_live[heap_hash(address)];
    while (*live && (*live)->base + 16 != address) live = &(*live)->next;
    if (!*live) return 0;
    heap_block *b = *live; *live = b->next; b->size = 0;
    heap_block **link = &heap_free, *previous = NULL;
    while (*link && (*link)->base < b->base) { previous = *link; link = &(*link)->next; }
    b->next = *link; *link = b;
    if (b->next && b->base + b->span == b->next->base) {
        heap_block *next = b->next; b->span += next->span; b->next = next->next; free(next);
    }
    if (previous && previous->base + previous->span == b->base) {
        previous->span += b->span; previous->next = b->next; free(b);
    }
    return 1;
}
uint32_t guest_heap_size(uint32_t address) {
    heap_block *b = heap_find(address); return b ? b->size : UINT32_MAX;
}
uint32_t guest_heap_realloc(uint32_t address, uint32_t size, uint32_t flags) {
    heap_block *b = heap_find(address); if (!b) return 0;
    if (size <= b->span - 16) {
        if ((flags & 8) && size > b->size) memset(G(address + b->size), 0, size - b->size);
        b->size = size; wr(G(b->base), 4, size); return address;
    }
    if (flags & 0x10) return 0; // HEAP_REALLOC_IN_PLACE_ONLY
    uint32_t p = guest_heap_alloc(size); if (!p) return 0;
    heap_find(p)->owner = b->owner;
    memcpy(G(p), G(address), b->size < size ? b->size : size);
    guest_heap_free(address); return p;
}

uint32_t guest_heap_create(void) {
    for (unsigned i = 0; i < 128; i++) if (!heap_handles[i]) {
        if (next_heap_handle == UINT32_MAX) return 0;
        return heap_handles[i] = next_heap_handle++;
    }
    return 0;
}
int guest_heap_destroy(uint32_t handle) {
    if (!heap_handle_valid(handle) || handle == 0x00710000u) return 0;
    for (unsigned i = 0; i < 4096; i++) {
        heap_block *b = heap_live[i];
        while (b) {
            heap_block *next = b->next;
            if (b->owner == handle) guest_heap_free(b->base + 16);
            b = next;
        }
    }
    for (unsigned i = 0; i < 128; i++) if (heap_handles[i] == handle) heap_handles[i] = 0;
    return 1;
}
uint32_t guest_heap_owned_alloc(uint32_t handle, uint32_t size) {
    if (!heap_handle_valid(handle)) return 0;
    uint32_t p = guest_heap_alloc(size);
    if (p) heap_find(p)->owner = handle;
    return p;
}
static int heap_owns(uint32_t handle, uint32_t address) {
    heap_block *b = heap_find(address);
    return heap_handle_valid(handle) && b && b->owner == handle;
}
int guest_heap_owned_free(uint32_t handle, uint32_t address) {
    return heap_owns(handle, address) ? guest_heap_free(address) : 0;
}
uint32_t guest_heap_owned_size(uint32_t handle, uint32_t address) {
    return heap_owns(handle, address) ? guest_heap_size(address) : UINT32_MAX;
}
uint32_t guest_heap_owned_realloc(uint32_t handle, uint32_t address, uint32_t size, uint32_t flags) {
    return heap_owns(handle, address) ? guest_heap_realloc(address, size, flags) : 0;
}

uint32_t guest_alloc(uint32_t size) {
    uint32_t p = guest_heap_alloc(size);
    if (!p) guest_fatal("guest heap exhausted (%u bytes)", size);
    return p;
}

// Virtual reservations are independent of the CRT heap and module images.
#define VIRTUAL_BASE 0x80000000u
#define VIRTUAL_END  0xF0000000ull
typedef struct virtual_region {
    uint32_t base, size;
    struct virtual_region *next;
} virtual_region;
static virtual_region *virtual_regions;
static void guest_decommit(uint32_t base, uint32_t size) {
    if (!size) return;
#ifdef _WIN32
    if (!VirtualFree(MEM + base, size, MEM_DECOMMIT)) guest_fatal("decommit failed");
#else
    if (madvise(MEM + base, size, MADV_DONTNEED) || mprotect(MEM + base, size, PROT_NONE))
        guest_fatal("decommit failed");
#endif
    memset(committed + (base >> 12), 0, size >> 12);
}
static virtual_region *virtual_find(uint32_t base, uint64_t end) {
    for (virtual_region *r = virtual_regions; r; r = r->next)
        if (base >= r->base && base < (uint64_t)r->base + r->size
                && end <= (uint64_t)r->base + r->size) return r;
    return NULL;
}
uint32_t guest_virtual_alloc(uint32_t address, uint32_t size, uint32_t flags) {
    if (!size || !(flags & 0x3000) || (flags & ~0x103000u)) return 0;
    uint64_t end = (uint64_t)address + size;
    if (end > (1ull << 32)) return 0;
    uint32_t base = address & ~4095u;
    uint64_t rounded_end = (end + 4095) & ~4095ull;
    if (!address || (flags & 0x2000)) {
        if (address) base = address & ~65535u;
        else {
            base = VIRTUAL_BASE;
            for (virtual_region *r = virtual_regions; r; r = r->next) {
                if ((uint64_t)base + ((size + 4095ull) & ~4095ull) <= r->base) break;
                base = (uint32_t)(((uint64_t)r->base + r->size + 65535) & ~65535ull);
            }
            rounded_end = (uint64_t)base + ((size + 4095ull) & ~4095ull);
        }
        if (base < VIRTUAL_BASE || rounded_end > VIRTUAL_END) return 0;
        virtual_region **link = &virtual_regions;
        while (*link && (*link)->base < base) {
            if ((uint64_t)(*link)->base + (*link)->size > base) return 0;
            link = &(*link)->next;
        }
        if (*link && rounded_end > (*link)->base) return 0;
        virtual_region *r = malloc(sizeof *r); if (!r) return 0;
        *r = (virtual_region){base, (uint32_t)(rounded_end - base), *link}; *link = r;
    } else if (!virtual_find(base, rounded_end)) return 0;
    if (flags & 0x1000) guest_commit(base, (uint32_t)(rounded_end - base));
    return base;
}
int guest_virtual_free(uint32_t address, uint32_t size, uint32_t flags) {
    virtual_region *r = virtual_find(address, (uint64_t)address + size);
    if (!r) return 0;
    if (flags == 0x8000) {
        if (size || address != r->base) return 0;
        guest_decommit(r->base, r->size);
        virtual_region **link = &virtual_regions; while (*link != r) link = &(*link)->next;
        *link = r->next; free(r); return 1;
    }
    if (flags != 0x4000) return 0;
    uint32_t base = address & ~4095u;
    uint64_t end = ((uint64_t)address + size + 4095) & ~4095ull;
    if (!size) { if (address != r->base) return 0; end = (uint64_t)r->base + r->size; }
    if (end > (uint64_t)r->base + r->size) return 0;
    guest_decommit(base, (uint32_t)(end - base)); return 1;
}

uint32_t guest_strdup(const char *s) {
    uint32_t n = (uint32_t)strlen(s), p = guest_alloc(n + 2);  // double NUL for env blocks
    memcpy(G(p), s, n);
    return p;
}

static struct { uint32_t pc, esp, seh; } fault_history[64];
static uint32_t fault_history_count;
static int trace_fault;
static void on_fault_report(uint64_t host_addr) {
    printf("CRASH guest_addr=%08llx pc=%08x\n", (unsigned long long)(host_addr - (uint64_t)(uintptr_t)MEM), PC);
    printf("REG eax=%08x ecx=%08x edx=%08x ebx=%08x esp=%08x ebp=%08x esi=%08x edi=%08x\n",
        reg32(0), reg32(4), reg32(8), reg32(12), reg32(16), reg32(20), reg32(24), reg32(28));
    uint32_t count = fault_history_count < 64 ? fault_history_count : 64;
    for (uint32_t i = 0; i < count; i++) {
        uint32_t slot = (fault_history_count - count + i) & 63;
        printf("TRACE pc=%08x esp=%08x seh=%08x\n", fault_history[slot].pc, fault_history[slot].esp, fault_history[slot].seh);
    }
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
    trace_fault = getenv("CODRECOMP_TRACE_FAULT") != NULL;
    fault_history_count = 0;
#ifdef _WIN32
    MEM = VirtualAlloc(NULL, 1ull << 32, MEM_RESERVE, PAGE_NOACCESS);
    AddVectoredExceptionHandler(1, on_fault);
#else
    MEM = mmap(NULL, 1ull << 32, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
    if (MEM == MAP_FAILED) MEM = NULL;
#ifndef __ANDROID__
    // Android's managed runtime/native bridge owns fault signals. Installing a
    // guest-only handler process-wide interferes with Java/native transitions.
    struct sigaction sa = {0};
    sa.sa_sigaction = on_fault;
    sa.sa_flags = SA_SIGINFO;
    sigaction(SIGSEGV, &sa, NULL);
    sigaction(SIGBUS, &sa, NULL);
#endif
#endif
    if (!MEM) guest_fatal("cannot reserve 4 GiB guest space");
    // Ghidra x86 register layout / FINIT state. CRT control-word updates retain
    // exception-mask bits; zero would incorrectly enable every x87 exception.
    wr(R + 0x10a0, 2, 0x037f); // FPUControlWord
    wr(R + 0x10a2, 2, 0);      // FPUStatusWord
    wr(R + 0x10a4, 2, 0xffff); // FPUTagWord: all registers empty
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
static unsigned loaded_references[16];
static int loaded_count;
static struct { const recomp_module *m; const char *path; } available[16];
static int available_count;
static recomp_chunk all_chunks[4096];
static int all_chunk_count;
static dispatch_index code_index;

#if defined(__ANDROID__) && defined(CODRECOMP_CPU_PROFILING)
#include "profile_sampler.h"
/* Local, opt-in CPU diagnostics. Sample calls rather than logging each branch. */
static int cpu_profile = -1;
static uint32_t profile_sequence = UINT32_C(0x9e3779b9);
enum { PROFILE_SLOTS = 4096 + THUNK_MAX };
static uint64_t profile_time[PROFILE_SLOTS], profile_count[PROFILE_SLOTS], profile_report;
static uint64_t profile_clock(int clock) {
    struct timespec t;
    clock_gettime(clock, &t);
    return (uint64_t)t.tv_sec * 1000000000u + t.tv_nsec;
}
static uint64_t profile_begin(void) {
    if (cpu_profile < 0) cpu_profile = getenv("CODRECOMP_CPU_STATS") != NULL;
    return cpu_profile && profile_sampler_next(&profile_sequence)
        ? profile_clock(CLOCK_THREAD_CPUTIME_ID) : 0;
}
static void profile_end(unsigned slot, uint64_t start) {
    if (!start) return;
    profile_time[slot] += profile_clock(CLOCK_THREAD_CPUTIME_ID) - start;
    profile_count[slot]++;
    uint64_t now = profile_clock(CLOCK_MONOTONIC);
    if (!profile_report) profile_report = now;
    if (now - profile_report < 5000000000ull) return;
    for (int rank = 0; rank < 6; rank++) {
        unsigned best = 0;
        for (unsigned i = 1; i < PROFILE_SLOTS; i++)
            if (profile_time[i] > profile_time[best]) best = i;
        if (!profile_time[best]) break;
        if (best >= 4096) {
            thunk_slot *host = &thunks[best - 4096];
            fprintf(stdout, "cpu sample: host %s!%s time_us=%llu calls=%llu\n",
                host->dll, host->name, (unsigned long long)(profile_time[best] / 1000),
                (unsigned long long)profile_count[best]);
        } else {
            fprintf(stdout, "cpu sample: chunk %08x-%08x time_us=%llu calls=%llu\n",
                all_chunks[best].start, all_chunks[best].end,
                (unsigned long long)(profile_time[best] / 1000),
                (unsigned long long)profile_count[best]);
        }
        profile_time[best] = 0;
    }
    memset(profile_time, 0, sizeof profile_time);
    memset(profile_count, 0, sizeof profile_count);
    profile_report = now;
}
#else
#define profile_begin() 0
#define profile_end(slot, start) ((void)0)
#endif

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

unsigned module_references(uint32_t base) {
    for (int i = 0; i < loaded_count; i++)
        if (loaded[i]->image_base == base) return loaded_references[i];
    return 0;
}

int module_unload(uint32_t base) {
    for (int i = 0; i < loaded_count; i++) {
        if (loaded[i]->image_base != base) continue;
        if (--loaded_references[i]) return 1;
        memset(G(base), 0, loaded[i]->image_size);
        memmove(loaded + i, loaded + i + 1, (loaded_count - i - 1) * sizeof *loaded);
        memmove(loaded_references + i, loaded_references + i + 1,
            (loaded_count - i - 1) * sizeof *loaded_references);
        loaded_count--;
        all_chunk_count = 0;
        for (int j = 0; j < loaded_count; j++)
            for (int k = 0; k < loaded[j]->chunk_count; k++)
                all_chunks[all_chunk_count++] = loaded[j]->chunks[k];
        qsort(all_chunks, all_chunk_count, sizeof all_chunks[0], cmp_chunk);
        dispatch_index_build(&code_index, all_chunks, all_chunk_count);
        return 1;
    }
    return 0;
}

int module_load(const recomp_module *m, const char *path) {
    for (int i = 0; i < loaded_count; i++) {
        if (!strcasecmp(loaded[i]->name, m->name)) {
            if (loaded_references[i] == UINT32_MAX) return 0;
            loaded_references[i]++;
            return 1;
        }
    }
    if (loaded_count == 16 || m->chunk_count < 0
            || m->chunk_count > 4096 - all_chunk_count) return 0;
    if (!m->image_size ||
        (uint64_t)m->image_base + m->image_size > UINT64_C(0x100000000)) return 0;
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    if (fseek(f, 0, SEEK_END)) { fclose(f); return 0; }
    long n = ftell(f);
    if (n < 64 || n > 512L * 1024 * 1024 || fseek(f, 0, SEEK_SET)) {
        fclose(f); errno = ENOEXEC; return 0;
    }
    uint8_t *buf = malloc((size_t)n);
    if (!buf) { fclose(f); return 0; }
    int ok = fread(buf, 1, (size_t)n, f) == (size_t)n;
    if (fclose(f)) ok = 0;
    pe_plan plan;
    if (!ok || !pe_prepare(buf, (size_t)n, m->image_size, &plan)) {
        free(buf); errno = ENOEXEC; return 0;
    }
    for (const recomp_import *im = m->imports; im->dll; ++im) {
        uint64_t offset = (uint64_t)im->iat_va - m->image_base;
        if (im->iat_va < m->image_base || offset + 4 > m->image_size) {
            free(buf); errno = ENOEXEC; return 0;
        }
    }
    guest_commit(m->image_base, m->image_size);
    memset(G(m->image_base), 0, m->image_size);
    memcpy(G(m->image_base), buf, plan.headers);
    for (unsigned i = 0; i < plan.count; i++) {
        pe_copy s = plan.sec[i];
        if (s.n) memcpy(G(m->image_base + s.dst), buf + s.src, s.n);
    }
    free(buf);

    loaded_references[loaded_count] = 1;
    loaded[loaded_count++] = m;
    for (int i = 0; i < m->chunk_count; i++) all_chunks[all_chunk_count++] = m->chunks[i];
    qsort(all_chunks, all_chunk_count, sizeof all_chunks[0], cmp_chunk);
    dispatch_index_build(&code_index, all_chunks, all_chunk_count);
    for (const recomp_import *im = m->imports; im->dll; im++) wr(G(im->iat_va), 4, resolve_import(im->dll, im->name));
    return 1;
}

// ---------------------------------------------------------------- execution

#ifdef __ANDROID__
// Enabled only when Android has generated its *matching* private HUD overlay.
// With a 4:3 or unrecognized HUD, keep the original marker positions.
static float compass_marker_horizontal;
static unsigned compass_marker_log_flags;

void guest_configure_compass_markers(int width, int height, int overlay_ready) {
    compass_marker_horizontal = compass_marker_factor(width, height, overlay_ready);
    compass_marker_log_flags = 0;
}

static void guest_project_compass_marker(uint32_t esp, unsigned arg_start,
                                         unsigned log_bit) {
    // One stack frame: return address, optionally syscall opcode, then
    // float x,y,w,h. Called only from original CoD 1.5 pointer functions.
    if (esp > UINT32_MAX - arg_start - 12) return;
    const uint32_t xa = esp + arg_start, wa = xa + 8;
    if (!guest_committed(xa) || !guest_committed(wa) ||
        !guest_committed(0x3012a948u)) return;
    compass_marker_rect mark;
    uint32_t old_x = mem32(xa), old_y = mem32(xa + 4);
    uint32_t old_w = mem32(wa), old_h = mem32(wa + 4);
    uint32_t scale_bits = mem32(0x3012a948u);
    float zoom;
    memcpy(&mark.x, &old_x, sizeof old_x);
    memcpy(&mark.y, &old_y, sizeof old_y);
    memcpy(&mark.width, &old_w, sizeof old_w);
    memcpy(&mark.height, &old_h, sizeof old_h);
    memcpy(&zoom, &scale_bits, sizeof zoom);
    if (!compass_marker_project(&mark, compass_marker_horizontal, zoom))
        return;
    uint32_t new_x, new_y, new_w;
    memcpy(&new_x, &mark.x, sizeof new_x);
    memcpy(&new_y, &mark.y, sizeof new_y);
    memcpy(&new_w, &mark.width, sizeof new_w);
    wr(G(xa), 4, new_x);
    wr(G(xa + 4), 4, new_y);
    wr(G(wa), 4, new_w);
    if (!(compass_marker_log_flags & log_bit)) {
        compass_marker_log_flags |= log_bit;
        fprintf(stdout, "codrecomp: compass marker projected call=0x%08x factor=%.5f zoom=%.3f\n",
                mem32(esp), compass_marker_horizontal, zoom);
    }
}
#endif

void guest_run(void) {
    while (PC != GUEST_EXIT_PC) {
        if (trace_fault) {
            uint32_t seh = mem32(TIB);
            uint32_t slot = fault_history_count++ & 63;
            fault_history[slot].pc = PC; fault_history[slot].esp = reg32(REG_ESP);
            fault_history[slot].seh = seh;
        }
        if (PC >= THUNK_BASE && PC < THUNK_BASE + 16 * THUNK_MAX) {
            thunk_slot *t = &thunks[(PC - THUNK_BASE) / 16];
            uint32_t esp = reg32(REG_ESP), ret = mem32(esp);
#ifdef __ANDROID__
            // Objective-star sprite uses R_DRAWSTRETCHPIC syscall #0x4b
            // directly. Identify the *exact* CoDSP 1.5 cgame caller
            // before touching its ephemeral stack floats.
            if (compass_marker_horizontal > 0.0f &&
                ret == 0x3001cedau && mem32(esp + 4) == 0x4bu &&
                module_loaded_at(0x30000000u))
                guest_project_compass_marker(esp, 8, 4u);
#endif
            uint64_t sample = profile_begin();
            set_reg32(REG_EAX, t->fn(esp));
            profile_end(4096 + (unsigned)(t - thunks), sample);
            set_reg32(REG_ESP, esp + 4 + t->pop);
            PC = ret;
            continue;
        }
#ifdef CODRECOMP_HOT_X87_FASTPATH
        // Verified only for the exact CoDSP 1.5 guest function entry.
        // Any unsafe address or nonfinite value falls back to generated p-code.
        if (PC == 0x005061b0u && module_loaded_at(0x00400000u) &&
            codsp_hot_transform_5061b0(R, MEM, &PC))
            continue;
#endif
#ifdef __ANDROID__
        // CoD 1.5 cgame draws green allies and tank indicators by calling
        // the original rotated-sprite helper at 0x30012260, and a secondary
        // objective pulse via 0x30012200. The saved call-return addresses
        // below are exact original instructions, not function-wide guesses.
        if (compass_marker_horizontal > 0.0f &&
            (PC == 0x30012260u || PC == 0x30012200u) &&
            module_loaded_at(0x30000000u)) {
            uint32_t esp = reg32(REG_ESP), caller = mem32(esp);
            if (PC == 0x30012260u && caller == 0x3000d971u)
                guest_project_compass_marker(esp, 4, 1u); // allies
            else if (PC == 0x30012260u && caller == 0x3000df4fu)
                guest_project_compass_marker(esp, 4, 2u); // tanks
            else if (PC == 0x30012200u && caller == 0x3001d0b7u)
                guest_project_compass_marker(esp, 4, 8u); // objective pulse
        }
#endif
        int found = dispatch_index_find(&code_index, all_chunks, all_chunk_count, PC);
        recomp_miss = 0;
        if (found >= 0) {
            uint64_t sample = profile_begin();
            all_chunks[found].fn();
            profile_end((unsigned)found, sample);
        }
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
