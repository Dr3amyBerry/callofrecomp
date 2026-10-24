#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
uint64_t ref_f2d10(uint64_t, unsigned);
uint64_t fast_f2d10(uint64_t, unsigned);
void ref_d2f10(uint64_t, uint64_t *, unsigned *);
void fast_d2f10(uint64_t, uint64_t *, unsigned *);
static uint64_t s = 0x9e3779b97f4a7c15ull;
static uint64_t rnd(void) { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }
static unsigned long long n_f2d, n_d2f, n_fast_f2d, n_fast_d2f;
static int chk_d2f(uint64_t b) {
    uint64_t l1, l2; unsigned s1, s2;
    ref_d2f10(b, &l1, &s1); fast_d2f10(b, &l2, &s2);
    n_d2f++;
    unsigned e = (b >> 52) & 0x7ff; if (e && e != 0x7ff) n_fast_d2f++;
    if (l1 != l2 || s1 != s2) { printf("d2f10 MISMATCH %016llx\n", (unsigned long long)b); return 1; }
    return 0;
}
static int chk_f2d(uint64_t sig, unsigned se) {
    uint64_t a = ref_f2d10(sig, se), b = fast_f2d10(sig, se);
    n_f2d++;
    if ((unsigned)((se & 0x7fff) - 15361u) <= 2045u && (sig & 0x80000000000007ffull) == 0x8000000000000000ull) n_fast_f2d++;
    if (a != b) { printf("f2d10 MISMATCH se=%04x sig=%016llx\n", se, (unsigned long long)sig); return 1; }
    return 0;
}
int main(int argc, char **argv) {
    long rounds = argc > 1 ? atol(argv[1]) : 4000000;
    int bad = 0;
    /* d2f: every sign/exponent against structured + random fractions */
    for (unsigned sg = 0; sg < 2; sg++) for (unsigned e = 0; e < 2048; e++) {
        uint64_t base = ((uint64_t)sg << 63) | ((uint64_t)e << 52);
        bad |= chk_d2f(base);
        for (int k = 0; k < 52; k++) { bad |= chk_d2f(base | (1ull << k)); bad |= chk_d2f(base | ((1ull << k) - 1)); }
        bad |= chk_d2f(base | 0x000fffffffffffffull);
        for (int k = 0; k < 64; k++) bad |= chk_d2f(base | (rnd() & 0x000fffffffffffffull));
    }
    for (long i = 0; i < rounds; i++) bad |= chk_d2f(rnd());
    /* f2d: every se (65536) x structured significands */
    for (unsigned se = 0; se < 65536; se++) {
        uint64_t sigs[] = {0, 1, 0x7ff, 0x800, 0x8000000000000000ull, 0x8000000000000001ull,
            0x80000000000007ffull, 0x8000000000000800ull, 0x8000000000000400ull, 0x80000000000003ffull,
            0x8000000000000401ull, 0xffffffffffffffffull, 0xfffffffffffff800ull, 0xfffffffffffffc00ull,
            0x7fffffffffffffffull, 0x4000000000000000ull, 0xc000000000000000ull, 0xbfffffffffffffffull};
        for (unsigned i = 0; i < sizeof sigs / sizeof *sigs; i++) bad |= chk_f2d(sigs[i], se);
        for (int k = 0; k < 16; k++) bad |= chk_f2d(rnd(), se);
        for (int k = 0; k < 16; k++) bad |= chk_f2d(0x8000000000000000ull | (rnd() & 0x7ffffffffffff800ull), se);
        for (int k = 0; k < 16; k++) bad |= chk_f2d(rnd() & 0xfffffffffffff800ull, se);
    }
    for (long i = 0; i < rounds; i++) { uint64_t r = rnd(); bad |= chk_f2d(rnd() | (r & 1 ? 0x8000000000000000ull : 0), (unsigned)(r >> 40) & 0xffff); }
    printf("%s d2f=%llu (fast-class %llu) f2d=%llu (fast-class %llu)\n", bad ? "FAIL" : "PASS",
           n_d2f, n_fast_d2f, n_f2d, n_fast_f2d);
    return bad;
}
