#ifndef CODRECOMP_VM_ABI_H
#define CODRECOMP_VM_ABI_H

#include <stdint.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Legacy CoD 1 PC native-VM traffic is 32-bit. Keep that wire/reconstruction
 * representation explicit even when the future host is 64-bit ARM.
 */
typedef uint32_t cod_vm_word32_t;

/*
 * vmMain in the observed native modules is called with command + a fixed bank
 * of argument slots. Twelve slots cover the recovered UI signature and the
 * engine VM_Call forwarding path we have mapped so far.
 */
enum { COD_VM_MAX_ARGS = 12 };

typedef struct cod_vm_call32_s {
    cod_vm_word32_t command;
    cod_vm_word32_t args[COD_VM_MAX_ARGS];
} cod_vm_call32_t;

/*
 * Pointer/integer transport inside the eventual native host must use host
 * pointer width. Never cast an Android pointer down to cod_vm_word32_t unless
 * it is intentionally being encoded for legacy-compatible state.
 */
typedef uintptr_t cod_host_word_t;
typedef intptr_t cod_host_sword_t;

static inline cod_vm_word32_t cod_vm_float_to_word(float value) {
    cod_vm_word32_t word;
    memcpy(&word, &value, sizeof(word));
    return word;
}

static inline float cod_vm_word_to_float(cod_vm_word32_t word) {
    float value;
    memcpy(&value, &word, sizeof(value));
    return value;
}

#ifdef __cplusplus
}
#endif

#endif /* CODRECOMP_VM_ABI_H */
