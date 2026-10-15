// Experimental binary80 arithmetic primitive. NOT connected to pcode2c or APK.
// This is not an x87 instruction emulator: guest stack/tag/TOP, sticky-status
// merging, FIP/FDP, memory faults and unmasked exceptions belong to the caller's
// future architectural backend. No existing fidelity gate is relaxed here.
#pragma once
#include <stdint.h>
#include <string.h>

typedef struct { uint8_t bytes[10]; } x87_native_value;
typedef struct {
    x87_native_value value;
    // Fresh arithmetic exception bits 0..5 and C1 immediately after arithmetic,
    // BEFORE storing the result. This is deliberately not a guest status word.
    uint16_t operation_status;
} x87_native_result;
enum { X87_NATIVE_ADD, X87_NATIVE_SUB, X87_NATIVE_MUL, X87_NATIVE_DIV };

// Valid internal buffers only; no guest RAM is accessed. Aliased inputs/output
// are supported. Rejected controls/opcodes leave output and host FPU untouched.
// Every exception must be masked: returning an unmasked exception precisely at
// its guest PC requires an architectural integration that does not exist yet.
static inline int x87_native_binary(unsigned op, uint16_t cw,
        const x87_native_value *lhs, const x87_native_value *rhs,
        x87_native_result *output) {
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
    if (op > X87_NATIVE_DIV || (cw & 0x7f) != 0x7f ||
        ((cw >> 8) & 3) == 1 || (cw & 0xe080)) return 0;
    const x87_native_value a=*lhs, b=*rhs;
    x87_native_result result;
    uint16_t status;
    uint8_t host[512] __attribute__((aligned(16)));
    // One indivisible compiler block: spills of live compiler x87 values must
    // occur BEFORE the save. No compiler SSE operation may be interleaved with
    // the save/restore pair, which restores XMM registers as well as x87.
#define X87_NATIVE_CALCULATE(instruction) \
    __asm__ volatile("fxsave64 %[host]\n\tfninit\n\tfldcw %[cw]\n\tfldt %[b]\n\tfldt %[a]\n\t" \
        instruction " %%st(1), %%st\n\tfnstsw %[sw]\n\tfstpt %[result]\n\tfstp %%st(0)\n\tfxrstor64 %[host]" \
        : [host] "=m"(host), [result] "=m"(result.value), [sw] "=m"(status) \
        : [cw] "m"(cw), [a] "m"(a), [b] "m"(b) \
        : "memory", "st", "st(1)", "st(2)", "st(3)", \
          "st(4)", "st(5)", "st(6)", "st(7)")
    switch(op) {
        case X87_NATIVE_ADD: X87_NATIVE_CALCULATE("fadd"); break;
        case X87_NATIVE_SUB: X87_NATIVE_CALCULATE("fsub"); break;
        case X87_NATIVE_MUL: X87_NATIVE_CALCULATE("fmul"); break;
        case X87_NATIVE_DIV: X87_NATIVE_CALCULATE("fdiv"); break;
    }
#undef X87_NATIVE_CALCULATE
    result.operation_status=status & 0x023f;
    *output=result;
    return 1;
#else
    (void)op; (void)cw; (void)lhs; (void)rhs; (void)output;
    return 0;
#endif
}
