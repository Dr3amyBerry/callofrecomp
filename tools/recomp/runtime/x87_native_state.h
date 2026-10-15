// Experimental state boundary for a future native x87 region backend.
// Not included by recomp_rt.h and not enabled in the Android application.
#pragma once
#include <stdint.h>
#include <string.h>

// Intel 32-bit-operand FNSAVE/FRSTOR format: full 16-bit physical tag word,
// logical ST0..ST7 as eight 10-byte values. Unlike FXSAVE, tags are not abridged.
typedef struct { uint8_t bytes[108]; } x87_native_state;

// Proven against the project's generated FRSTOR field loads. Selectors do not
// have mapped R fields here: callers MUST supply the actual guest selectors.
// This serialization does not prove that the current lowering maintains the
// represented state correctly. Inputs must be valid internal buffers.
static inline void x87_native_state_from_registers(x87_native_state *output,
        const uint8_t *regs,uint16_t code_selector,uint16_t data_selector) {
    x87_native_state s={{0}};
    memcpy(s.bytes,regs+0x10a0,2);
    memcpy(s.bytes+4,regs+0x10a2,2);
    memcpy(s.bytes+8,regs+0x10a4,2);
    memcpy(s.bytes+18,regs+0x10a6,2);
    memcpy(s.bytes+20,regs+0x10a8,4);
    memcpy(s.bytes+12,regs+0x10ac,4);
    memcpy(s.bytes+16,&code_selector,2);
    memcpy(s.bytes+24,&data_selector,2);
    for(unsigned i=0;i<8;i++) memcpy(s.bytes+28+10*i,regs+0x1100+16*i,10);
    *output=s;
}

// Write exactly the mapped bytes; retain unrelated registers and slot padding.
// The complete state remains available to the caller for selectors/metadata.
// Local staging supports overlap between the state and register buffers.
static inline void x87_native_state_to_registers(uint8_t *regs,
        const x87_native_state *input) {
    const x87_native_state s=*input;
    memcpy(regs+0x10a0,s.bytes,2);
    memcpy(regs+0x10a2,s.bytes+4,2);
    memcpy(regs+0x10a4,s.bytes+8,2);
    memcpy(regs+0x10a6,s.bytes+18,2);
    memcpy(regs+0x10a8,s.bytes+20,4);
    memcpy(regs+0x10ac,s.bytes+12,4);
    for(unsigned i=0;i<8;i++) memcpy(regs+0x1100+16*i,s.bytes+28+10*i,10);
}

// Diagnostic native import/export only. No guest instruction is executed.
// Reserved bytes are hardware-defined; do not compare entire images blindly.
// This does NOT normalize native FIP/FDP/FOP to guest addresses/opcodes after
// arithmetic, handle memory faults, or implement unmasked guest exceptions.
static inline int x87_native_state_roundtrip(const x87_native_state *input,
        x87_native_state *output) {
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
    uint16_t cw;memcpy(&cw,input->bytes,2);
    if((cw&0x7f)!=0x7f || ((cw>>8)&3)==1 || (cw&0xe080)) return 0;
    const x87_native_state in=*input;
    x87_native_state result;
    uint8_t host[512] __attribute__((aligned(16)));
    // FNINIT is nonwaiting: clear any pending host exception AFTER saving it,
    // before FRSTOR (which can otherwise raise that host exception).
    __asm__ volatile("fxsave64 %[host]\n\tfninit\n\tfrstor %[in]\n\tfnsave %[out]\n\tfxrstor64 %[host]"
        : [host] "=m"(host),[out] "=m"(result)
        : [in] "m"(in)
        : "memory","st","st(1)","st(2)","st(3)",
          "st(4)","st(5)","st(6)","st(7)");
    *output=result;
    return 1;
#else
    (void)input;(void)output;return 0;
#endif
}
