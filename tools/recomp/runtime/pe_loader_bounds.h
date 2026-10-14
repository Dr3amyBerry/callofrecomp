#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>
/* Validate all PE32 copy spans before touching the 32-bit guest address space. */
enum { PE_MAX_SECTIONS = 96 };
typedef struct { uint32_t dst, src, n; } pe_copy;
typedef struct { uint32_t headers; unsigned count; pe_copy sec[PE_MAX_SECTIONS]; } pe_plan;
static inline uint16_t pe16(const uint8_t *p) {
    return (uint16_t)((unsigned)p[0] | (unsigned)p[1] << 8);
}
static inline uint32_t pe32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static inline int pe_span(size_t at, size_t size, size_t bound) {
    return at <= bound && size <= bound - at;
}
static inline int pe_prepare(const uint8_t *f, size_t size, uint32_t image, pe_plan *out) {
    if (!f || !out || size < 64 || image < 64 || f[0] != 'M' || f[1] != 'Z') return 0;
    uint32_t pe = pe32(f + 0x3c);
    if (!pe_span(pe, 24, size) || memcmp(f + pe, "PE\0\0", 4)) return 0;
    const uint8_t *coff = f + pe + 4;
    unsigned count = pe16(coff + 2), osz = pe16(coff + 16);
    if (pe16(coff) != 0x14c || !count || count > PE_MAX_SECTIONS || osz < 64) return 0;
    size_t opt = (size_t)pe + 24;
    if (!pe_span(opt, osz, size)) return 0;
    const uint8_t *oh = f + opt;
    uint32_t headers = pe32(oh + 60);
    size_t sect = opt + osz;
    if (pe16(oh) != 0x10b || pe32(oh + 56) != image ||
        !headers || headers > image || headers > size ||
        !pe_span(sect, count * 40u, size) || sect + count * 40u > headers) return 0;
    pe_plan plan = {0};
    plan.headers = headers; plan.count = count;
    for (unsigned i = 0; i < count; i++) {
        const uint8_t *s = f + sect + 40u * i;
        uint32_t virt = pe32(s + 8), dst = pe32(s + 12);
        uint32_t n = pe32(s + 16), src = pe32(s + 20);
        uint32_t memsize = virt ? virt : n;
        if (dst > image || memsize > image - dst) return 0;
        if (virt && n > virt) n = virt;
        if (n && !pe_span(src, n, size)) return 0;
        plan.sec[i] = (pe_copy){dst,src,n};
    }
    *out = plan;
    return 1;
}
