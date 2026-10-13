#ifndef CODRECOMP_HEAP_LIFECYCLE_H
#define CODRECOMP_HEAP_LIFECYCLE_H
#include <stdint.h>
uint32_t guest_heap_create(void);
int guest_heap_destroy(uint32_t handle);
uint32_t guest_heap_owned_alloc(uint32_t handle, uint32_t size);
int guest_heap_owned_free(uint32_t handle, uint32_t address);
uint32_t guest_heap_owned_size(uint32_t handle, uint32_t address);
uint32_t guest_heap_owned_realloc(uint32_t handle, uint32_t address, uint32_t size, uint32_t flags);
#endif
