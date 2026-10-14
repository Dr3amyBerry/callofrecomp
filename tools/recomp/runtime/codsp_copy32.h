// CoDSP.exe 1.5 p-code: replace ONLY the eight MOV-load/store pairs
// L_42b100..L_42b13a, leaving original decrement, EFLAGS, loop/return
// instructions at L_42b13e onward unchanged. Opt-in generated C experiment.
//
// The original block copies 8 little-endian dwords from (EBX+EDI) to
// (EDX+EDI), preserving the last two loads in EAX and ESI. Source/destination
// spans must not overlap *within this 32-byte block*; otherwise the original
// read/write ordering can differ from a C memcpy. Fallback is exact p-code.
#ifndef CODRECOMP_CODSP_COPY32_H
#define CODRECOMP_CODSP_COPY32_H
#include <stdint.h>
#include <string.h>

static inline int codsp_copy32_step(uint8_t *regs, uint8_t *guest_mem) {
    uint32_t src, dst, off;
    memcpy(&src, regs + 0x0c, sizeof src);  // EBX
    memcpy(&dst, regs + 0x08, sizeof dst);  // EDX
    memcpy(&off, regs + 0x1c, sizeof off);  // EDI, loop position
    const uint64_t s = (uint64_t)src + off;
    const uint64_t d = (uint64_t)dst + off;
    // Generated x86 address calculations wrap to 32 bits. Preserve the
    // original path on wrap and near the 4-GiB limit.
    if (s + 32 > UINT64_C(0x100000000) ||
        d + 32 > UINT64_C(0x100000000) ||
        (s < d + 32 && d < s + 32))
        return 0;

    uint32_t eax, esi;
    // Match the original final MOV pair and preserve full register state.
    memcpy(&eax, guest_mem + s + 24, sizeof eax);
    memcpy(&esi, guest_mem + s + 28, sizeof esi);
    memcpy(guest_mem + d, guest_mem + s, 32);
    memcpy(regs + 0, &eax, sizeof eax);
    memcpy(regs + 0x18, &esi, sizeof esi);
    // EFLAGS and the stack are left exactly as the original eight MOVs.
    // Caller jumps to L_42b13e, which executes original loop flags.
    return 1;
}
#endif
