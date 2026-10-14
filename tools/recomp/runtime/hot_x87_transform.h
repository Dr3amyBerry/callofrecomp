// Opt-in, version-specific CoDSP 1.5 transform at guest PC 0x005061B0.
// Converts the six original scalar x87 vector/matrix results with the same
// ordered double arithmetic already used by recomp_rt.h. This is NOT a
// generic x87 emulator and must never run for a different guest entry point.
// Regression evidence: private full-R/RAM differential against generated
// p-code on a real ARM64 device. Fallback handles aliases and nonfinite data.
#pragma once
#include <math.h>
#include <stdint.h>
#include <string.h>

static inline uint32_t codsp_hot_rd32(const uint8_t *p) {
    uint32_t v;
    memcpy(&v, p, sizeof v);
    return v;
}
static inline void codsp_hot_wr32(uint8_t *p, uint32_t v) {
    memcpy(p, &v, sizeof v);
}
static inline float codsp_hot_rdf32(const uint8_t *p) {
    float v;
    memcpy(&v, p, sizeof v);
    return v;
}
static inline void codsp_hot_wrf32(uint8_t *p, float v) {
    memcpy(p, &v, sizeof v);
}
static inline int codsp_hot_overlap(uint32_t a, unsigned an, uint32_t b, unsigned bn) {
    return (uint64_t)a < (uint64_t)b + bn &&
           (uint64_t)b < (uint64_t)a + an;
}

// Returns zero without modifying ANY state unless the fast path is safe.
// When nonzero, writes PC, ESP, scratch return register and the two stale
// x87 stack slots exactly as the current static p-code translation does.
// Call only for CoDSP.exe 1.5 PC 0x005061B0, after verifying the module.
static inline int codsp_hot_transform_5061b0(uint8_t *regs,
                                               uint8_t *guest_mem,
                                               uint32_t *next_pc) {
#if defined(__clang__)
#pragma clang fp contract(off)
#endif
    const uint32_t matrix = codsp_hot_rd32(regs + 0x00);
    const uint32_t dir = codsp_hot_rd32(regs + 0x04);
    const uint32_t pos = codsp_hot_rd32(regs + 0x08);
    const uint32_t esp = codsp_hot_rd32(regs + 0x10);
    const uint32_t out_dir = codsp_hot_rd32(regs + 0x18);
    const uint32_t out_pos = codsp_hot_rd32(regs + 0x1c);
    const uint32_t addr[] = {matrix, pos, dir, out_pos, out_dir, esp};
    const unsigned width[] = {64, 12, 12, 12, 12, 4};
    for (unsigned i = 0; i < 6; i++)
        if ((addr[i] & 3) || (uint64_t)addr[i] + width[i] > (UINT64_C(1) << 32))
            return 0;
    for (unsigned i = 3; i <= 4; i++)
        for (unsigned j = 0; j < 6; j++)
            if (i != j && codsp_hot_overlap(addr[i], width[i], addr[j], width[j]))
                return 0;

    float m[16], p[3], d[3];
    for (unsigned i = 0; i < 16; i++) {
        m[i] = codsp_hot_rdf32(guest_mem + matrix + 4 * i);
        if (!isfinite(m[i])) return 0;
    }
    for (unsigned i = 0; i < 3; i++) {
        p[i] = codsp_hot_rdf32(guest_mem + pos + 4 * i);
        d[i] = codsp_hot_rdf32(guest_mem + dir + 4 * i);
        if (!isfinite(p[i]) || !isfinite(d[i])) return 0;
    }

    // Preserve the exact sequence of binary64 operations for the existing
    // Ghidra p-code f2d/d2f lowering; no FMA, reassociation or fast-math.
    double t = (double)p[1] * m[4];
    t += (double)p[0] * m[0];
    t += (double)m[8] * p[2];
    t += m[12];
    codsp_hot_wrf32(guest_mem + out_pos, (float)t);

    t = (double)p[1] * m[5];
    t += (double)m[9] * p[2];
    t += (double)m[1] * p[0];
    t += m[13];
    codsp_hot_wrf32(guest_mem + out_pos + 4, (float)t);

    t = (double)p[1] * m[6];
    t += (double)m[10] * p[2];
    t += (double)m[2] * p[0];
    t += m[14];
    codsp_hot_wrf32(guest_mem + out_pos + 8, (float)t);

    t = (double)m[8] * d[2];
    t += (double)d[0] * m[0];
    t += (double)m[4] * d[1];
    codsp_hot_wrf32(guest_mem + out_dir, (float)t);

    t = (double)m[9] * d[2];
    t += (double)m[1] * d[0];
    t += (double)m[5] * d[1];
    codsp_hot_wrf32(guest_mem + out_dir + 4, (float)t);

    t = (double)m[2] * d[0];
    t += (double)m[10] * d[2];
    t += (double)m[6] * d[1];
    codsp_hot_wrf32(guest_mem + out_dir + 8, (float)t);

    // The generated x87 push/pop sequence leaves ST0..ST5 intact and
    // duplicates the previous ST5 into both ST6 and ST7. Ret is 32-bit.
    memcpy(regs + 0x1160, regs + 0x1150, 10);
    memcpy(regs + 0x1170, regs + 0x1150, 10);
    codsp_hot_wr32(regs + 0x10ac, 0x00506242u);
    uint32_t return_pc = codsp_hot_rd32(guest_mem + esp);
    codsp_hot_wr32(regs + 0x284, return_pc);
    codsp_hot_wr32(regs + 0x10, esp + 4);
    *next_pc = return_pc;
    return 1;
}
