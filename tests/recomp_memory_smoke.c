#include <stdio.h>
#include "recomp_rt.h"
static uint32_t call(const char *name, int n, uint32_t *args) {
    uint32_t fn = shim_lookup("KERNEL32.dll", name);
    if (!fn) guest_fatal("missing memory thunk %s", name);
    return guest_call(fn, n, args);
}
int main(void) {
    guest_init(); shims_register(kernel32_thunks);
    uint32_t tib = reg32(REG_FS_OFFSET), low = mem32(tib + 8), high = mem32(tib + 4);
    uint32_t cpu = (uint32_t)cpuid_ptr();
    if ((uint64_t)tib + 4096 > low && tib < high) return 26;
    if ((uint64_t)cpu + 4096 > low && cpu < high) return 27;
    // Large original game frames may use any byte of the declared stack.
    memset(G(low), 0xa5, high - low);
    if (mem32(tib) != UINT32_MAX || mem32(tib+4) != high || mem32(tib+8) != low
            || mem32(tib+24) != tib || mem32(cpu)) return 28;
    if (rd(R + 0x10a0, 2) != 0x037f || rd(R + 0x10a2, 2) != 0
            || rd(R + 0x10a4, 2) != 0xffff) return 25;
    uint32_t a[4] = {0x710000, 8, 64, 0};
    uint32_t p = call("HeapAlloc", 3, a);
    memset(G(p), 0x5a, 64);
    a[2] = p;
    if (!call("HeapFree", 3, a)) return 1;
    a[2] = 64;
    uint32_t q = call("HeapAlloc", 3, a);
    if (q != p || mem32(q)) return 2;
    memset(G(q), 0x5a, 64);
    a[2] = q; a[3] = 1024;
    p = call("HeapReAlloc", 4, a);
    if (!p || mem32(p) != 0x5a5a5a5a || mem32(p + 64)) return 3;
    a[2] = p;
    if (call("HeapSize", 3, a) != 1024) return 4;
    if (!call("HeapFree", 3, a) || call("HeapFree", 3, a)) return 5;
    // Total allocated exceeds the arena: release must actually reclaim space.
    for (int i = 0; i < 20; i++) {
        a[2] = 16u << 20;
        p = call("HeapAlloc", 3, a); if (!p) return 6;
        a[2] = p; if (!call("HeapFree", 3, a)) return 7;
    }
    uint32_t va[4] = {0, 8192, 0x2000, 4};
    p = call("VirtualAlloc", 4, va);
    if (!p || (p & 65535) || guest_committed(p)) return 8;
    va[0] = p; va[1] = 4096; va[2] = 0x1000;
    if (call("VirtualAlloc", 4, va) != p || !guest_committed(p) || guest_committed(p+4096)) return 9;
    wr(G(p), 4, 0x12345678);
    uint32_t vf[3] = {p, 4096, 0x4000};
    if (!call("VirtualFree", 3, vf) || guest_committed(p)) return 10;
    if (call("VirtualAlloc", 4, va) != p || mem32(p)) return 11;
    vf[1] = 1; vf[2] = 0x8000;
    if (call("VirtualFree", 3, vf)) return 12;
    vf[1] = 0;
    if (!call("VirtualFree", 3, vf) || guest_committed(p)) return 13;
    va[0] = 0; va[1] = 8192; va[2] = 0x3000;
    q = call("VirtualAlloc", 4, va);
    if (q != p || mem32(q) || mem32(q+4096)) return 14;
    vf[0] = q;
    if (!call("VirtualFree", 3, vf)) return 15;
    va[1] = 65536;
    p = call("VirtualAlloc", 4, va);
    q = call("VirtualAlloc", 4, va);
    if (q != p + 65536) return 16;
    vf[0] = q;
    if (!call("VirtualFree", 3, vf)) return 17;
    vf[0] = p;
    if (!call("VirtualFree", 3, vf)) return 18;
    a[2] = 100; p = call("HeapAlloc", 3, a);
    a[2] = 100; q = call("HeapAlloc", 3, a);
    a[2] = p; if (!call("HeapFree", 3, a)) return 19;
    a[2] = q; if (!call("HeapFree", 3, a)) return 20;
    a[2] = 200; q = call("HeapAlloc", 3, a);
    if (q != p) return 21; // adjacent freed spans coalesce
    wr(G(q), 4, 0x12345678);
    a[1] = 0x10; a[2] = q; a[3] = 4096;
    if (call("HeapReAlloc", 4, a) || mem32(q) != 0x12345678) return 22;
    a[1] = 8; a[2] = UINT32_MAX;
    if (call("HeapAlloc", 3, a)) return 23;
    va[0] = 0xfffff000; va[1] = 8192;
    if (call("VirtualAlloc", 4, va)) return 24;
    uint32_t create[3] = {0, 0, 0};
    uint32_t h1 = call("HeapCreate", 3, create), h2 = call("HeapCreate", 3, create);
    if (!h1 || !h2 || h1 == h2) return 29;
    a[0] = h1; a[1] = 8; a[2] = 16u << 20;
    p = call("HeapAlloc", 3, a); if (!p) return 30;
    a[0] = h2; a[2] = p;
    if (call("HeapFree", 3, a) || call("HeapSize", 3, a) != UINT32_MAX) return 31;
    a[0] = h1;
    if (!call("HeapDestroy", 1, a) || call("HeapDestroy", 1, a)) return 32;
    if (call("HeapSize", 3, a) != UINT32_MAX) return 33;
    a[0] = h2; a[2] = 16u << 20;
    q = call("HeapAlloc", 3, a); if (q != p) return 34;
    if (!call("HeapDestroy", 1, a)) return 35;
    for (int i = 0; i < 20; i++) {
        a[0] = call("HeapCreate", 3, create); a[2] = 16u << 20;
        if (!a[0] || !call("HeapAlloc", 3, a) || !call("HeapDestroy", 1, a)) return 36;
    }
    uint32_t slots[64];
    for (unsigned i = 0; i < 64; i++) {
        slots[i] = call("TlsAlloc", 0, NULL); if (slots[i] != i) return 37;
    }
    if (call("TlsAlloc", 0, NULL) != UINT32_MAX) return 38;
    a[0] = 5; a[1] = 123;
    if (!call("TlsSetValue", 2, a) || call("TlsGetValue", 1, a) != 123) return 39;
    if (!call("TlsFree", 1, a) || call("TlsFree", 1, a)) return 40;
    if (call("TlsAlloc", 0, NULL) != 5 || call("TlsGetValue", 1, a)) return 41;
    for (unsigned i = 0; i < 64; i++) { a[0] = slots[i]; if (!call("TlsFree", 1, a)) return 42; }
    for (unsigned i = 0; i < 100; i++) {
        a[0] = call("TlsAlloc", 0, NULL);
        if (a[0] == UINT32_MAX || !call("TlsFree", 1, a)) return 43;
    }
    a[0] = UINT32_MAX; if (call("TlsSetValue", 2, a) || call("TlsFree", 1, a)) return 44;
    puts("recompiled memory lifecycle passed"); return 0;
}
