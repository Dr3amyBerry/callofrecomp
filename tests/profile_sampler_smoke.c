#include "profile_sampler.h"
#include <stdio.h>

int main(void) {
    uint32_t state = UINT32_C(0x9e3779b9);
    unsigned phases[257] = {0}, count = 0;
    for (unsigned i = 0; i < 257 * 4096; i++) {
        if (profile_sampler_next(&state)) { phases[i % 257]++; count++; }
        if (!state) return 1;
    }
    for (unsigned phase = 0; phase < 257; phase++) {
        if (!phases[phase]) { fprintf(stderr, "Unsampled repeating phase %u\n", phase); return 2; }
    }
    if (count < 3500 || count > 4700) return 3;
    state = 0;
    (void)profile_sampler_next(&state);
    if (!state) return 4;
    printf("%u samples cover all 257 repeating call phases\n", count);
    return 0;
}
