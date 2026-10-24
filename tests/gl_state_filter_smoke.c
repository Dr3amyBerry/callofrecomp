// Synthetic differential test for gl_state_filter.h. No game data, no GL.
// A reference "GL4ES" state machine receives either every call or only the
// calls the filter forwards; its full state must be identical after every call.
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "gl_state_filter.h"

typedef struct model {
    int cap[GL_SF_CAPS];
    int client[GL_SF_CLIENT_ARRAYS];
    int texcoord[GL_SF_UNITS];
    int active, client_active;
    uint32_t bound[GL_SF_UNITS];
    int depth_mask;
    uint32_t depth_func, src, dst, cull;
} model;

static const uint32_t caps[] = {0x0BE2, 0x0B71, 0x0B44, 0x0B90, 0x8037, 0x0B60, 0x0BC0, 0x0DE1, 0xDEAD};
static const uint32_t carr[] = {0x8074, 0x8075, 0x8076, 0x8078, 0x8077};
static const uint32_t cull_modes[] = {0x0404, 0x0405, 0x0408, 0x0000};

static uint32_t rng = 12345u;
static uint32_t next_u32(void) { rng = rng * 1664525u + 1013904223u; return rng >> 8; }

static void apply(model *m, gl_sf_op op, uint32_t a, uint32_t b) {
    switch (op) {
    case GL_SF_OP_ENABLE:
    case GL_SF_OP_DISABLE: {
        int slot = gl_sf_cap_slot(a);
        if (slot >= 0) m->cap[slot] = op == GL_SF_OP_ENABLE;
        break;
    }
    case GL_SF_OP_CLIENT_ENABLE:
    case GL_SF_OP_CLIENT_DISABLE: {
        int v = op == GL_SF_OP_CLIENT_ENABLE;
        if (a == 0x8074) m->client[0] = v;
        else if (a == 0x8075) m->client[1] = v;
        else if (a == 0x8076) m->client[2] = v;
        else if (a == 0x8078 && m->client_active >= 0 && m->client_active < GL_SF_UNITS) m->texcoord[m->client_active] = v;
        break;
    }
    case GL_SF_OP_BIND_TEXTURE:
        if (a == 0x0DE1 && m->active >= 0 && m->active < GL_SF_UNITS) m->bound[m->active] = b;
        break;
    case GL_SF_OP_ACTIVE_TEXTURE:
        if (a >= 0x84C0 && a < 0x84C0 + GL_SF_UNITS) m->active = (int)(a - 0x84C0);
        break;
    case GL_SF_OP_CLIENT_ACTIVE_TEXTURE:
        if (a >= 0x84C0 && a < 0x84C0 + GL_SF_UNITS) m->client_active = (int)(a - 0x84C0);
        break;
    case GL_SF_OP_DEPTH_MASK: m->depth_mask = (int)(a & 0xFF); break;
    case GL_SF_OP_DEPTH_FUNC: if (a >= 0x200 && a <= 0x207) m->depth_func = a; break;
    case GL_SF_OP_BLEND_FUNC:
        if (gl_sf_blend_factor_valid(a) && gl_sf_blend_factor_valid(b)) { m->src = a; m->dst = b; }
        break;
    case GL_SF_OP_CULL_FACE:
        if (a == 0x0404 || a == 0x0405 || a == 0x0408) m->cull = a;
        break;
    }
}

// Events that the real driver executes: calls that mutate state invisibly.
static void mutate(model *m) {
    for (int i = 0; i < GL_SF_CAPS; ++i) m->cap[i] = (int)(next_u32() & 1);
    for (int i = 0; i < GL_SF_CLIENT_ARRAYS; ++i) m->client[i] = (int)(next_u32() & 1);
    for (int i = 0; i < GL_SF_UNITS; ++i) { m->texcoord[i] = (int)(next_u32() & 1); m->bound[i] = next_u32() % 5; }
    m->active = (int)(next_u32() % GL_SF_UNITS);
    m->client_active = (int)(next_u32() % GL_SF_UNITS);
    m->depth_mask = (int)(next_u32() & 1);
    m->depth_func = 0x200 + (next_u32() & 7);
    m->src = next_u32() & 1; m->dst = next_u32() & 1;
    m->cull = cull_modes[next_u32() % 3];
}

static int same(const model *a, const model *b) { return memcmp(a, b, sizeof *a) == 0; }

static int expect(int cond, const char *what) {
    if (!cond) fprintf(stderr, "FAIL: %s\n", what);
    return !cond;
}

static int directed_tests(void) {
    int bad = 0;
    gl_state_filter f;
    gl_sf_event_apply(&f, GL_SF_EV_RESET);
    // Unknown state always forwards, then identical repeat drops.
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_ENABLE, 0x0BE2, 0), "first enable forwards");
    bad += expect(gl_sf_redundant(&f, GL_SF_OP_ENABLE, 0x0BE2, 0), "second enable drops");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_DISABLE, 0x0BE2, 0), "disable forwards");
    // Texture and alpha-test caps are never filtered (GL4ES re-evaluates them).
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_ENABLE, 0x0DE1, 0), "tex2d not cached 1");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_ENABLE, 0x0DE1, 0), "tex2d not cached 2");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_ENABLE, 0x0BC0, 0), "alpha test not cached 1");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_ENABLE, 0x0BC0, 0), "alpha test not cached 2");
    // Binding is per active unit.
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_BIND_TEXTURE, 0x0DE1, 7), "bind with unknown unit forwards");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_ACTIVE_TEXTURE, 0x84C0, 0), "active 0 forwards");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_BIND_TEXTURE, 0x0DE1, 7), "bind unit0");
    bad += expect(gl_sf_redundant(&f, GL_SF_OP_BIND_TEXTURE, 0x0DE1, 7), "rebind unit0 drops");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_ACTIVE_TEXTURE, 0x84C1, 0), "active 1");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_BIND_TEXTURE, 0x0DE1, 7), "same id other unit forwards");
    bad += expect(gl_sf_redundant(&f, GL_SF_OP_ACTIVE_TEXTURE, 0x84C1, 0), "same active drops");
    // Cube-map or other targets are forwarded and reset tracking.
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_BIND_TEXTURE, 0x8513, 3), "cube forwards");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_BIND_TEXTURE, 0x0DE1, 7), "bind after cube forwards");
    // Invalidation after list execution / deletion.
    gl_sf_event_apply(&f, GL_SF_EV_INVALIDATE_ALL);
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_ENABLE, 0x0BE2, 0), "enable after invalidate forwards");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_BIND_TEXTURE, 0x0DE1, 7), "bind after invalidate forwards");
    // Begin/End and list compilation bypass the filter entirely.
    gl_sf_event_apply(&f, GL_SF_EV_BEGIN);
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_ENABLE, 0x0BE2, 0), "in begin 1");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_ENABLE, 0x0BE2, 0), "in begin 2");
    gl_sf_event_apply(&f, GL_SF_EV_END);
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_ENABLE, 0x0BE2, 0), "after end forwards");
    gl_sf_event_apply(&f, GL_SF_EV_LIST_BEGIN);
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_CULL_FACE, 0x0405, 0), "in list 1");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_CULL_FACE, 0x0405, 0), "in list 2");
    gl_sf_event_apply(&f, GL_SF_EV_LIST_END);
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_CULL_FACE, 0x0405, 0), "after list forwards");
    bad += expect(gl_sf_redundant(&f, GL_SF_OP_CULL_FACE, 0x0405, 0), "cull repeat drops");
    // Invalid enums never become cached.
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_CULL_FACE, 0x0000, 0), "invalid cull forwards");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_CULL_FACE, 0x0000, 0), "invalid cull forwards again");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_CULL_FACE, 0x0405, 0), "cull after invalid forwards");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_BLEND_FUNC, 0x0302, 0x0303), "blend");
    bad += expect(gl_sf_redundant(&f, GL_SF_OP_BLEND_FUNC, 0x0302, 0x0303), "blend repeat drops");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_BLEND_FUNC, 0x0302, 0x0304), "blend changed dst");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_BLEND_FUNC, 0xFFFF, 0), "invalid blend forwards");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_BLEND_FUNC, 0x0302, 0x0304), "blend after invalid forwards");
    // GLboolean arrives in a 32-bit stack slot: only the low byte counts.
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_DEPTH_MASK, 0x00000001, 0), "mask 1");
    bad += expect(gl_sf_redundant(&f, GL_SF_OP_DEPTH_MASK, 0xABCDEF01, 0), "mask 1 high garbage drops");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_DEPTH_MASK, 0, 0), "mask 0");
    // Client arrays: texcoord needs a known client unit and tracks per unit.
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_CLIENT_ENABLE, 0x8078, 0), "texcoord with unknown unit");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_CLIENT_ENABLE, 0x8078, 0), "texcoord with unknown unit again");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_CLIENT_ACTIVE_TEXTURE, 0x84C1, 0), "client active 1");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_CLIENT_ENABLE, 0x8078, 0), "texcoord unit1 on");
    bad += expect(gl_sf_redundant(&f, GL_SF_OP_CLIENT_ENABLE, 0x8078, 0), "texcoord unit1 repeat drops");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_CLIENT_ACTIVE_TEXTURE, 0x84C0, 0), "client active 0");
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_CLIENT_ENABLE, 0x8078, 0), "texcoord unit0 unknown forwards");
    gl_sf_event_apply(&f, GL_SF_EV_INVALIDATE_CLIENT);
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_CLIENT_ENABLE, 0x8078, 0), "texcoord after client invalidate forwards");
    // Reset forgets everything, including list/begin flags.
    gl_sf_event_apply(&f, GL_SF_EV_BEGIN);
    gl_sf_event_apply(&f, GL_SF_EV_RESET);
    bad += expect(!gl_sf_redundant(&f, GL_SF_OP_ENABLE, 0x0B71, 0), "reset forwards");
    bad += expect(gl_sf_redundant(&f, GL_SF_OP_ENABLE, 0x0B71, 0), "reset clears begin flag");
    return bad;
}

static int differential_test(void) {
    model ref, filtered;
    gl_state_filter f;
    memset(&ref, 0, sizeof ref);
    memset(&filtered, 0, sizeof filtered);
    gl_sf_event_apply(&f, GL_SF_EV_RESET);
    int in_begin = 0, in_list = 0;
    uint64_t dropped = 0;
    for (int step = 0; step < 400000; ++step) {
        const uint32_t pick = next_u32() % 100;
        if (pick < 2) {
            // Opaque state-mutating call (glCallList/glPopAttrib/glDeleteTextures).
            if (!in_begin && !in_list) { mutate(&ref); filtered = ref; }
            gl_sf_event_apply(&f, GL_SF_EV_INVALIDATE_ALL);
        } else if (pick < 3) {
            // Begin/End: while open, state calls are recorded (not applied) by GL4ES;
            // model that by applying them to neither state.
            in_begin = !in_begin;
            gl_sf_event_apply(&f, in_begin ? GL_SF_EV_BEGIN : GL_SF_EV_END);
        } else if (pick < 4) {
            in_list = !in_list;
            gl_sf_event_apply(&f, in_list ? GL_SF_EV_LIST_BEGIN : GL_SF_EV_LIST_END);
        } else if (pick < 5) {
            // glInterleavedArrays-like: changes client enables, filter told.
            for (int i = 0; i < GL_SF_CLIENT_ARRAYS; ++i) ref.client[i] = (int)(next_u32() & 1);
            for (int i = 0; i < GL_SF_UNITS; ++i) ref.texcoord[i] = (int)(next_u32() & 1);
            filtered = ref;
            gl_sf_event_apply(&f, GL_SF_EV_INVALIDATE_CLIENT);
        } else {
            gl_sf_op op = (gl_sf_op)(next_u32() % 11);
            uint32_t a = 0, b = 0;
            switch (op) {
            case GL_SF_OP_ENABLE: case GL_SF_OP_DISABLE: a = caps[next_u32() % 9]; break;
            case GL_SF_OP_CLIENT_ENABLE: case GL_SF_OP_CLIENT_DISABLE: a = carr[next_u32() % 5]; break;
            case GL_SF_OP_BIND_TEXTURE: a = (next_u32() % 8) ? 0x0DE1 : 0x8513; b = next_u32() % 5; break;
            case GL_SF_OP_ACTIVE_TEXTURE: case GL_SF_OP_CLIENT_ACTIVE_TEXTURE: a = 0x84C0 + next_u32() % 6; break;
            case GL_SF_OP_DEPTH_MASK: a = (next_u32() & 1) | ((next_u32() % 3) ? 0 : 0x100); break;
            case GL_SF_OP_DEPTH_FUNC: a = 0x1FF + next_u32() % 10; break;
            case GL_SF_OP_BLEND_FUNC: a = next_u32() % 12; b = next_u32() % 12; if (a >= 2) a += 0x2FE; if (b >= 2) b += 0x2FE; break;
            case GL_SF_OP_CULL_FACE: a = cull_modes[next_u32() % 4]; break;
            }
            const int drop = gl_sf_redundant(&f, op, a, b);
            if (!in_begin && !in_list) {
                apply(&ref, op, a, b);
                if (!drop) apply(&filtered, op, a, b);
                else dropped++;
            } else if (drop) {
                fprintf(stderr, "FAIL: dropped call inside Begin/List at step %d\n", step);
                return 1;
            }
            if (!same(&ref, &filtered)) {
                fprintf(stderr, "FAIL: state diverged at step %d op=%d a=%x b=%x drop=%d\n", step, op, a, b, drop);
                return 1;
            }
        }
    }
    if (dropped < 1000) { fprintf(stderr, "FAIL: filter never dropped (%llu)\n", (unsigned long long)dropped); return 1; }
    printf("differential: dropped=%llu forwarded=%llu\n",
           (unsigned long long)f.skipped, (unsigned long long)f.forwarded);
    return 0;
}

int main(void) {
    int bad = directed_tests();
    if (bad) return 1;
    return differential_test();
}
