#include "recomp_rt.h"
#include <float.h>
#include <stdio.h>

static u128 ext(uint16_t exponent, uint64_t significand) {
    return ((u128)exponent << 64) | significand;
}
static uint64_t bits(double d) { uint64_t b; memcpy(&b, &d, 8); return b; }
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "x87 check failed at line %d\n", __LINE__); return 1; } } while (0)
int main(void) {
    /* Literal Intel binary80 encodings: explicit integer bit and bias 16383. */
    CHECK(d2f(1.0, 10) == ext(0x3fff, UINT64_C(0x8000000000000000)));
    CHECK(f2d(ext(0x3fff, UINT64_C(0x8000000000000000)), 10) == 1.0);
    CHECK(d2f(-0.0, 10) == ext(0x8000, 0));
    CHECK(bits(f2d(ext(0x8000, 0), 10)) == UINT64_C(0x8000000000000000));
    CHECK(d2f(INFINITY, 10) == ext(0x7fff, UINT64_C(0x8000000000000000)));
    CHECK(f2d(ext(0xffff, UINT64_C(0x8000000000000000)), 10) == -INFINITY);
    CHECK(isnan(f2d(ext(0x7fff, UINT64_C(0xc000000000000000)), 10)));
    CHECK(isnan(f2d(ext(0x7fff, UINT64_C(0x8000000000000001)), 10)));
    CHECK((uint16_t)(d2f(NAN, 10) >> 64) == 0x7fff);
    CHECK(((uint64_t)d2f(NAN, 10) >> 62) == 3);
    CHECK(bits(f2d(ext(0, 1), 10)) == 0); /* x87 minimum subnormal underflows double. */
    CHECK(bits(f2d(ext(0x8000, UINT64_C(0x7fffffffffffffff)), 10)) == UINT64_C(0x8000000000000000));
    CHECK(f2d(ext(0, UINT64_C(0x8000000000000000)), 10) == 0); /* pseudo-denormal is valid */
    CHECK(isnan(f2d(ext(0x3fff, 1), 10))); /* unnormal */
    CHECK(isnan(f2d(ext(0x7fff, 0), 10))); /* pseudo-infinity */
    CHECK(isnan(f2d(ext(0x7fff, 1), 10))); /* pseudo-NaN */
    CHECK(d2f(DBL_MIN, 10) == ext(0x3c01, UINT64_C(0x8000000000000000)));
    CHECK(d2f(0x1p-1074, 10) == ext(0x3bcd, UINT64_C(0x8000000000000000)));
    CHECK(d2f(DBL_MAX, 10) == ext(0x43fe, UINT64_C(0xfffffffffffff800)));
    uint8_t memory[12]; memset(memory, 0xa5, sizeof memory);
    wr(memory + 1, 10, d2f(1.0, 10));
    const uint8_t one80[10] = {0, 0, 0, 0, 0, 0, 0, 0x80, 0xff, 0x3f};
    CHECK(!memcmp(memory + 1, one80, 10) && memory[0] == 0xa5 && memory[11] == 0xa5);
    CHECK(f2d(rd(memory + 1, 10), 10) == 1.0);
    double values[] = {0, -0.0, 1, -1, 360, 0.1, DBL_MIN, DBL_MAX,
        0x1p-1074, -0x1p-1074, 0x0.fffffffffffffp-1022, INFINITY, -INFINITY};
    for (unsigned i = 0; i < sizeof values / sizeof *values; i++)
        CHECK(bits(f2d(d2f(values[i], 10), 10)) == bits(values[i]));
    /* Every double exponent class and varied mantissas must survive storage. */
    uint64_t state = UINT64_C(0x18ad325713b49267);
    for (unsigned exponent = 0; exponent < 2047; exponent++) {
        for (unsigned i = 0; i < 8; i++) {
            state ^= state << 13; state ^= state >> 7; state ^= state << 17;
            uint64_t input = (state & UINT64_C(0x800fffffffffffff)) | ((uint64_t)exponent << 52);
            double d; memcpy(&d, &input, 8);
            CHECK(bits(f2d(d2f(d, 10), 10)) == input);
        }
    }
    /* Nearest/even, significand carry, double underflow and overflow. */
    CHECK(f2d(ext(0x3fff, UINT64_C(0x8000000000000400)), 10) == 1.0);
    CHECK(f2d(ext(0x3fff, UINT64_C(0x8000000000000c00)), 10) == 0x1.0000000000002p0);
    CHECK(f2d(ext(0x3fff, UINT64_MAX), 10) == 2.0);
    CHECK(f2d(ext(0x3bcc, UINT64_C(0x8000000000000000)), 10) == 0);
    CHECK(f2d(ext(0x3bcc, UINT64_C(0x8000000000000001)), 10) == 0x1p-1074);
    CHECK(f2d(ext(0x43fe, UINT64_MAX), 10) == INFINITY);
    CHECK(d2f(1.0, 4) == 0x3f800000 && d2f(1.0, 8) == UINT64_C(0x3ff0000000000000));
    puts("binary80 encoding, rounding, limits and unsupported inputs passed");
    return 0;
}
