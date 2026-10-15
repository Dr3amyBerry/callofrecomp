// Exact CoDSP 1.5 x87 stack shifts. Shared out-of-line per translation unit.
// Each register slot is 16 bytes, but ONLY the low 10 bytes are architectural;
// copying 16 bytes would corrupt adjacent padding and fail state equivalence.
// Verified generator matches exactly seven ordered p-code COPY operations.
#pragma once
#include <stdint.h>
#include <string.h>
#if defined(_MSC_VER)
#define CODSP_STACK_NOINLINE __declspec(noinline)
#elif defined(__GNUC__) || defined(__clang__)
#define CODSP_STACK_NOINLINE __attribute__((noinline))
#else
#define CODSP_STACK_NOINLINE
#endif

static CODSP_STACK_NOINLINE void codsp_x87_shift_push(uint8_t *r) {
    memcpy(r + 0x1170, r + 0x1160, 10);
    memcpy(r + 0x1160, r + 0x1150, 10);
    memcpy(r + 0x1150, r + 0x1140, 10);
    memcpy(r + 0x1140, r + 0x1130, 10);
    memcpy(r + 0x1130, r + 0x1120, 10);
    memcpy(r + 0x1120, r + 0x1110, 10);
    memcpy(r + 0x1110, r + 0x1100, 10);
}
static CODSP_STACK_NOINLINE void codsp_x87_shift_pop(uint8_t *r) {
    memcpy(r + 0x1100, r + 0x1110, 10);
    memcpy(r + 0x1110, r + 0x1120, 10);
    memcpy(r + 0x1120, r + 0x1130, 10);
    memcpy(r + 0x1130, r + 0x1140, 10);
    memcpy(r + 0x1140, r + 0x1150, 10);
    memcpy(r + 0x1150, r + 0x1160, 10);
    memcpy(r + 0x1160, r + 0x1170, 10);
}
#undef CODSP_STACK_NOINLINE
