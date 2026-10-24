// Opt-in (CODRECOMP_GL_STATE_FILTER) elision of provably idempotent guest GL
// state calls before they reach GL4ES. OFF by default.
//
// The filter mirrors ONLY the guest-visible value of a few state items and
// drops a call when the identical, valid value was the last one forwarded and
// nothing that could change that state behind our back has happened since.
// It never alters arguments, never reorders calls and never caches anything
// that GL4ES does not already deduplicate itself (identical value => no-op),
// so the observable GL4ES state is unchanged.  The saving is the thunk +
// GL4ES entry/dispatch cost of each dropped call, nothing more.
//
// Conservative rules:
//  * unknown state (start, reset, invalidation) always forwards the call;
//  * invalid/unlisted enums are never cached and invalidate the item;
//  * inside glBegin/glEnd and glNewList/glEndList nothing is filtered or
//    cached (GL4ES records those calls instead of executing them);
//  * glPopAttrib, glPopClientAttrib, glCallList(s), glDeleteTextures invalidate
//    everything; glInterleavedArrays and vertex-attrib array toggles
//    invalidate client-array enables.
#pragma once
#include <stdint.h>
#include <string.h>

enum {
    GL_SF_UNITS = 4,
    GL_SF_CAPS = 6,
    GL_SF_CLIENT_ARRAYS = 3,     // vertex, normal, color
};

typedef enum {
    GL_SF_OP_ENABLE,
    GL_SF_OP_DISABLE,
    GL_SF_OP_CLIENT_ENABLE,
    GL_SF_OP_CLIENT_DISABLE,
    GL_SF_OP_BIND_TEXTURE,       // a=target b=texture
    GL_SF_OP_ACTIVE_TEXTURE,     // a=GL_TEXTURE0+n
    GL_SF_OP_CLIENT_ACTIVE_TEXTURE,
    GL_SF_OP_DEPTH_MASK,
    GL_SF_OP_DEPTH_FUNC,
    GL_SF_OP_BLEND_FUNC,         // a=src b=dst
    GL_SF_OP_CULL_FACE,
} gl_sf_op;

typedef enum {
    GL_SF_EV_RESET,
    GL_SF_EV_INVALIDATE_ALL,
    GL_SF_EV_INVALIDATE_CLIENT,
    GL_SF_EV_BEGIN,
    GL_SF_EV_END,
    GL_SF_EV_LIST_BEGIN,
    GL_SF_EV_LIST_END,
} gl_sf_event;

typedef struct gl_state_filter {
    int8_t   cap[GL_SF_CAPS];                       // -1 unknown, 0, 1
    int8_t   client_array[GL_SF_CLIENT_ARRAYS];
    int8_t   client_texcoord[GL_SF_UNITS];
    int8_t   active;                                // -1 unknown, else unit
    int8_t   client_active;
    uint8_t  bound_known[GL_SF_UNITS];
    uint32_t bound[GL_SF_UNITS];                    // GL_TEXTURE_2D binding
    int16_t  depth_mask;                            // -1 unknown, else raw byte
    int32_t  depth_func;                            // 0 unknown
    int32_t  blend_src, blend_dst;                  // 0 unknown
    int32_t  cull_mode;                             // 0 unknown
    uint8_t  in_begin, in_list;
    uint64_t forwarded, skipped;
} gl_state_filter;

static inline void gl_sf_invalidate_client(gl_state_filter *f) {
    memset(f->client_array, -1, sizeof f->client_array);
    memset(f->client_texcoord, -1, sizeof f->client_texcoord);
}

static inline void gl_sf_invalidate_all(gl_state_filter *f) {
    memset(f->cap, -1, sizeof f->cap);
    gl_sf_invalidate_client(f);
    f->active = f->client_active = -1;
    memset(f->bound_known, 0, sizeof f->bound_known);
    f->depth_mask = -1;
    f->depth_func = f->blend_src = f->blend_dst = f->cull_mode = 0;
}

static inline void gl_sf_event_apply(gl_state_filter *f, gl_sf_event ev) {
    switch (ev) {
    case GL_SF_EV_RESET:
        memset(f, 0, sizeof *f);
        gl_sf_invalidate_all(f);
        return;
    case GL_SF_EV_INVALIDATE_ALL: gl_sf_invalidate_all(f); return;
    case GL_SF_EV_INVALIDATE_CLIENT: gl_sf_invalidate_client(f); return;
    case GL_SF_EV_BEGIN: f->in_begin = 1; gl_sf_invalidate_all(f); return;
    case GL_SF_EV_END: f->in_begin = 0; gl_sf_invalidate_all(f); return;
    case GL_SF_EV_LIST_BEGIN: f->in_list = 1; gl_sf_invalidate_all(f); return;
    case GL_SF_EV_LIST_END: f->in_list = 0; gl_sf_invalidate_all(f); return;
    }
}

// Capabilities with unit-independent, GL4ES-deduplicated state.  GL_ALPHA_TEST
// and the GL_TEXTURE_* caps are deliberately absent (GL4ES re-evaluates them).
static inline int gl_sf_cap_slot(uint32_t cap) {
    switch (cap) {
    case 0x0BE2u: return 0;  // GL_BLEND
    case 0x0B71u: return 1;  // GL_DEPTH_TEST
    case 0x0B44u: return 2;  // GL_CULL_FACE
    case 0x0B90u: return 3;  // GL_STENCIL_TEST
    case 0x8037u: return 4;  // GL_POLYGON_OFFSET_FILL
    case 0x0B60u: return 5;  // GL_FOG
    default: return -1;
    }
}

static inline int gl_sf_set_i8(int8_t *slot, int8_t value) {
    const int same = *slot == value;
    *slot = value;
    return same;
}

static inline int gl_sf_blend_factor_valid(uint32_t v) {
    return v == 0u || v == 1u || (v >= 0x0300u && v <= 0x0308u);
}

// Returns nonzero when the call is a provable no-op and may be dropped.  When
// it returns zero the caller must forward the call: the new value has already
// been recorded as the current one.
static inline int gl_sf_redundant(gl_state_filter *f, gl_sf_op op, uint32_t a, uint32_t b) {
    int same = 0;
    if (f->in_begin || f->in_list) { f->forwarded++; return 0; }
    switch (op) {
    case GL_SF_OP_ENABLE:
    case GL_SF_OP_DISABLE: {
        const int slot = gl_sf_cap_slot(a);
        if (slot >= 0) same = gl_sf_set_i8(&f->cap[slot], op == GL_SF_OP_ENABLE);
        break;
    }
    case GL_SF_OP_CLIENT_ENABLE:
    case GL_SF_OP_CLIENT_DISABLE: {
        const int8_t value = op == GL_SF_OP_CLIENT_ENABLE;
        if (a == 0x8074u) same = gl_sf_set_i8(&f->client_array[0], value);       // vertex
        else if (a == 0x8075u) same = gl_sf_set_i8(&f->client_array[1], value);  // normal
        else if (a == 0x8076u) same = gl_sf_set_i8(&f->client_array[2], value);  // color
        else if (a == 0x8078u && f->client_active >= 0)                           // texcoord
            same = gl_sf_set_i8(&f->client_texcoord[f->client_active], value);
        break;
    }
    case GL_SF_OP_BIND_TEXTURE:
        if (a == 0x0DE1u && f->active >= 0) {
            const int u = f->active;
            same = f->bound_known[u] && f->bound[u] == b;
            f->bound_known[u] = 1;
            f->bound[u] = b;
        } else if (a == 0x0DE1u) {
            // active unit unknown: the binding of an unknown unit changes
            memset(f->bound_known, 0, sizeof f->bound_known);
        } else {
            // non-2D targets are not tracked, and can alias 2D bindings
            memset(f->bound_known, 0, sizeof f->bound_known);
        }
        break;
    case GL_SF_OP_ACTIVE_TEXTURE:
        if (a >= 0x84C0u && a < 0x84C0u + GL_SF_UNITS)
            same = gl_sf_set_i8(&f->active, (int8_t)(a - 0x84C0u));
        else f->active = -1;
        break;
    case GL_SF_OP_CLIENT_ACTIVE_TEXTURE:
        if (a >= 0x84C0u && a < 0x84C0u + GL_SF_UNITS)
            same = gl_sf_set_i8(&f->client_active, (int8_t)(a - 0x84C0u));
        else f->client_active = -1;
        break;
    case GL_SF_OP_DEPTH_MASK: {
        const int16_t raw = (int16_t)(a & 0xFFu);
        same = f->depth_mask == raw;
        f->depth_mask = raw;
        break;
    }
    case GL_SF_OP_DEPTH_FUNC:
        if (a >= 0x0200u && a <= 0x0207u) { same = f->depth_func == (int32_t)a; f->depth_func = (int32_t)a; }
        else f->depth_func = 0;
        break;
    case GL_SF_OP_BLEND_FUNC:
        if (gl_sf_blend_factor_valid(a) && gl_sf_blend_factor_valid(b)) {
            same = f->blend_src == (int32_t)a + 1 && f->blend_dst == (int32_t)b + 1;
            f->blend_src = (int32_t)a + 1;
            f->blend_dst = (int32_t)b + 1;
        } else f->blend_src = f->blend_dst = 0;
        break;
    case GL_SF_OP_CULL_FACE:
        if (a == 0x0404u || a == 0x0405u || a == 0x0408u) {
            same = f->cull_mode == (int32_t)a;
            f->cull_mode = (int32_t)a;
        } else f->cull_mode = 0;
        break;
    }
    if (same) f->skipped++;
    else f->forwarded++;
    return same;
}
