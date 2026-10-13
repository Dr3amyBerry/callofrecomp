// State of the *guest* OpenGL bindings, not the GLES buffers used by GL4ES.
// Client-array parameters are guest pointers only when their target is unbound.
#pragma once
#include <stddef.h>
#include <stdint.h>

enum { GL_BRIDGE_ARRAY_BUFFER = 0x8892u, GL_BRIDGE_ELEMENT_ARRAY_BUFFER = 0x8893u };

typedef struct gl_bridge_buffers {
    uint32_t array_buffer;
    uint32_t element_array_buffer;
} gl_bridge_buffers;

static inline void gl_bridge_reset(gl_bridge_buffers *s) {
    s->array_buffer = s->element_array_buffer = 0;
}

static inline void gl_bridge_bind(gl_bridge_buffers *s, uint32_t target, uint32_t name) {
    if (target == GL_BRIDGE_ARRAY_BUFFER) s->array_buffer = name;
    else if (target == GL_BRIDGE_ELEMENT_ARRAY_BUFFER) s->element_array_buffer = name;
}

static inline void *gl_bridge_arg(const gl_bridge_buffers *s, uint32_t target,
                                  uint8_t *guest_base, uint32_t guest_value) {
    const uint32_t binding = target == GL_BRIDGE_ARRAY_BUFFER ? s->array_buffer :
                             target == GL_BRIDGE_ELEMENT_ARRAY_BUFFER ? s->element_array_buffer : 0;
    if (binding) return (void *)(uintptr_t)guest_value; // byte offset, including zero
    return guest_value ? (void *)(guest_base + (uintptr_t)guest_value) : NULL;
}

static inline void gl_bridge_deleted(gl_bridge_buffers *s, uint32_t name) {
    if (!name) return;
    if (s->array_buffer == name) s->array_buffer = 0;
    if (s->element_array_buffer == name) s->element_array_buffer = 0;
}

static inline void gl_bridge_delete_many(gl_bridge_buffers *s, int count,
                                          const uint32_t *names) {
    if (!names || count <= 0 || (!s->array_buffer && !s->element_array_buffer)) return;
    for (int i = 0; i < count; ++i) {
        uint32_t name;
        // Guest buffers may be byte-aligned even when the host requires alignment.
        __builtin_memcpy(&name, (const uint8_t *)names + (size_t)i * sizeof name, sizeof name);
        gl_bridge_deleted(s, name);
        if (!s->array_buffer && !s->element_array_buffer) break;
    }
}
