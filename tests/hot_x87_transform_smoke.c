// Synthetic acceptance and fallback checks. Original game assets not needed.
#include "hot_x87_transform.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

static void put_float(uint8_t *m, uint32_t addr, float f) {
    memcpy(m + addr, &f, sizeof f);
}
static float get_float(uint8_t *m, uint32_t addr) {
    float f;
    memcpy(&f, m + addr, sizeof f);
    return f;
}
int main(void) {
    uint8_t *mem = (uint8_t *)calloc(1, 0x8000);
    uint8_t regs[0x2000] = {0};
    assert(mem != NULL);
    uint32_t pc = 0x005061b0;
    codsp_hot_wr32(regs, 0x1000);
    codsp_hot_wr32(regs + 4, 0x3000);
    codsp_hot_wr32(regs + 8, 0x2000);
    codsp_hot_wr32(regs + 0x10, 0x6000);
    codsp_hot_wr32(regs + 0x18, 0x5000);
    codsp_hot_wr32(regs + 0x1c, 0x4000);
    codsp_hot_wr32(mem + 0x6000, 0x00400099);
    for (int i = 0; i < 10; i++) regs[0x1150 + i] = (uint8_t)(i + 17);
    // Column-major affine identity with a translation (1, 2, 3).
    for (int i = 0; i < 16; i++) put_float(mem, 0x1000 + 4 * i, 0.0f);
    for (int i = 0; i < 4; i++) put_float(mem, 0x1000 + 4 * (i * 5), 1.0f);
    for (int i = 0; i < 3; i++) {
        put_float(mem, 0x1000 + (12 + i) * 4, (float)(i + 1));
        put_float(mem, 0x2000 + i * 4, (float)(i + 4));
        put_float(mem, 0x3000 + i * 4, (float)(i + 7));
    }
    assert(codsp_hot_transform_5061b0(regs, mem, &pc) == 1);
    assert(pc == 0x00400099);
    assert(codsp_hot_rd32(regs + 0x10) == 0x6004);
    assert(codsp_hot_rd32(regs + 0x284) == 0x00400099);
    assert(codsp_hot_rd32(regs + 0x10ac) == 0x00506242);
    for (int i = 0; i < 10; i++) {
        assert(regs[0x1160 + i] == i + 17);
        assert(regs[0x1170 + i] == i + 17);
    }
    for (int i = 0; i < 3; i++) {
        assert(get_float(mem, 0x4000 + i * 4) == (float)(2 * i + 5));
        assert(get_float(mem, 0x5000 + i * 4) == (float)(i + 7));
    }
    uint8_t saved[0x2000], saved_mem[0x8000];
    memcpy(saved, regs, sizeof regs);
    memcpy(saved_mem, mem, 0x8000);
    uint32_t before = pc;
    codsp_hot_wr32(regs + 0x1c, 0x1000); // output aliases source.
    memcpy(saved, regs, sizeof regs);
    assert(!codsp_hot_transform_5061b0(regs, mem, &pc));
    assert(!memcmp(saved, regs, sizeof regs));
    assert(!memcmp(saved_mem, mem, 0x8000));
    assert(pc == before);
    codsp_hot_wr32(regs + 0x1c, 0x4000);
    put_float(mem, 0x1000, INFINITY);
    memcpy(saved, regs, sizeof regs);
    assert(!codsp_hot_transform_5061b0(regs, mem, &pc));
    assert(!memcmp(saved, regs, sizeof regs));
    assert(pc == before);
    free(mem);
    puts("hot x87 transform smoke: pass");
    return 0;
}
