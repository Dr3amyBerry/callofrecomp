// Frozen pre-fast-path conversion reference for differential tests.
static inline double reference_f2d(u128 v, int n) {
    if (n == 4) { uint32_t b = (uint32_t)v; float f; memcpy(&f, &b, 4); return f; }
    uint64_t b = (uint64_t)v;
    if (n == 10) {
        uint64_t significand = b;
        unsigned se = (unsigned)(v >> 64) & 0xffff;
        unsigned exponent = se & 0x7fff;
        uint64_t sign = (uint64_t)(se & 0x8000) << 48;
        if (exponent && !(significand >> 63)) {
            // Intel unsupported encodings (unnormals/pseudo-infinity/NaN):
            // fail closed to real indefinite rather than interpreting as finite.
            b = UINT64_C(0xfff8000000000000);
        } else if (exponent == 0x7fff) {
            uint64_t fraction = significand & UINT64_C(0x7fffffffffffffff);
            b = sign | UINT64_C(0x7ff0000000000000);
            if (fraction) b |= (fraction >> 11) | UINT64_C(0x0008000000000000);
        } else {
            // E=0,J=1 pseudo-denormals have the same value as E=1,J=1.
            int e = (int)(exponent ? exponent : 1) - 16383 + 1023;
            if (e >= 2047) b = sign | UINT64_C(0x7ff0000000000000);
            else if (e <= 0) {
                b = sign | x87_round_shift(significand, (unsigned)(12 - e));
            } else {
                uint64_t rounded = x87_round_shift(significand, 11);
                // Adding the rounded fraction also handles carry to next exponent.
                b = sign | (((uint64_t)(e - 1) << 52) + rounded);
            }
        }
    }
    double d; memcpy(&d, &b, 8); return d;
}
