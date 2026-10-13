#pragma once
#include <stdint.h>

/* Periodic sampling can repeatedly select the same call in a guest loop.
   Deterministic varying intervals avoid locking onto its call-count period.
   Used only in opt-in profiling; normal APKs compile the entire path out. */
static inline int profile_sampler_next(uint32_t *state) {
    uint32_t value = *state ? *state : UINT32_C(0x9e3779b9);
    value ^= value << 13;
    value ^= value >> 17;
    value ^= value << 5;
    *state = value;
    return (value & 255u) == 0;
}
