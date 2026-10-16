/* Bit-independent oracle for the opt-in narrow SHL helper. No game assets. */
#include "recomp_rt.h"
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static uint32_t rng_state = UINT32_C(0x32791af0);
static uint32_t rng(void) {
    rng_state = rng_state * UINT32_C(1664525) + UINT32_C(1013904223);
    return rng_state;
}
static u128 input(void) {
    return ((u128)rng() << 96) | ((u128)rng() << 64) |
           ((u128)rng() << 32) | rng();
}
static u128 expected_bits(u128 a, u128 b, unsigned n) {
    const unsigned bits = n * 8u;
    if (b >= bits) return 0;
    const unsigned shift = (unsigned)b;
    u128 result = 0;
    for (unsigned i = shift; i < bits; ++i)
        if ((a >> (i - shift)) & 1u) result |= (u128)1 << i;
    return result;
}
int main(void) {
    static const unsigned fixed[] = {
        0, 1, 2, 7, 8, 15, 16, 31, 32, 63, 64, 65,
        79, 80, 119, 120, 127, 128, 129, 255,
    };
    for (unsigned n = 1; n <= 16; ++n) {
        for (unsigned trial = 0; trial < 768; ++trial) {
            u128 a = input();
            u128 count = trial < sizeof fixed / sizeof fixed[0]
                ? fixed[trial] : (trial & 3) ? rng() % 132u : input();
            if (trial == 127) count = ((u128)1 << 64) | 7u;
            if (trial == 256) count = ((u128)1 << 127) | 3u;
            if (trial == 257) a = (u128)-1;
            const u128 original = mask(shl(a, count), n);
            const u128 optimized = mask(codsp_arm64_narrow_shl(a, count, n), n);
            const u128 reference = expected_bits(a, count, n);
            if (original != reference || optimized != reference) {
                fprintf(stderr, "SHL mismatch width=%u trial=%u\n", n, trial);
                return 1;
            }
            uint8_t reg_a[16], reg_b[16];
            memset(reg_a, 0x9b, sizeof reg_a);
            memcpy(reg_b, reg_a, sizeof reg_b);
            wr(reg_a, n, original);
            wr(reg_b, n, optimized);
            if (memcmp(reg_a, reg_b, sizeof reg_a)) {
                fprintf(stderr, "SHL write changed other register bytes: %u %u\n",
                        n, trial);
                return 2;
            }
        }
    }
    puts("narrow-left-shift: 12288 bitwise oracle cases PASS");
    return 0;
}
