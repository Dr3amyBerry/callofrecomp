#include <stdio.h>
#include <SDL.h>
#include "gl_thunks.h"

static void GLAPI_CALL fake_get_pointer(int name, void **out) {
    (void)name;
    *out = G(0x60001000u);
}

static const void *last_elements, *last_range, *last_vertex, *last_texcoord;
static unsigned bind_calls;

static void GLAPI_CALL fake_bind_buffer(int target, int name) {
    (void)target; (void)name;
    bind_calls++;
}
static void GLAPI_CALL fake_draw_elements(int mode, int count, int type, void *indices) {
    (void)mode; (void)count; (void)type;
    last_elements = indices;
}
static void GLAPI_CALL fake_draw_range(int mode, int first, int last, int count, int type, void *indices) {
    (void)mode; (void)first; (void)last; (void)count; (void)type;
    last_range = indices;
}
static void GLAPI_CALL fake_vertex_pointer(int size, int type, int stride, void *pointer) {
    (void)size; (void)type; (void)stride;
    last_vertex = pointer;
}
static void GLAPI_CALL fake_texcoord_pointer(int size, int type, int stride, void *pointer) {
    (void)size; (void)type; (void)stride;
    last_texcoord = pointer;
}
static void GLAPI_CALL fake_delete_buffers(int count, void *names) { (void)count; (void)names; }
static void *getproc(const char *name) {
    if (!strcmp(name, "glGetPointerv")) return (void *)fake_get_pointer;
    if (!strcmp(name, "glBindBufferARB")) return (void *)fake_bind_buffer;
    if (!strcmp(name, "glDrawElements")) return (void *)fake_draw_elements;
    if (!strcmp(name, "glDrawRangeElements")) return (void *)fake_draw_range;
    if (!strcmp(name, "glVertexPointer")) return (void *)fake_vertex_pointer;
    if (!strcmp(name, "glTexCoordPointer")) return (void *)fake_texcoord_pointer;
    if (!strcmp(name, "glDeleteBuffersARB")) return (void *)fake_delete_buffers;
    return NULL;
}

static int menu_delta(int x, int y, int *dx, int *dy) {
    (void)x; (void)y;
    *dx = 10; *dy = 20;
    return 1;
}

int main(void) {
    guest_init();
    char extensions[32768];
    strcpy(extensions, "GL_EXT_texture_compression_s3tc GL_ARB_multitexture ");
    while (strlen(extensions) + 32 < sizeof extensions) strcat(extensions, "GL_UNSUPPORTED_example ");
    uint32_t p = gl_guest_string(0x1F03, extensions);
    const char *s = (const char *)G(p);
    if (strlen(s) > 4095 || !strstr(s, "GL_EXT_texture_compression_s3tc") || strstr(s, "GL_UNSUPPORTED_example")) {
        fputs("guest extensions must preserve supported S3TC and bound unsupported capabilities\n", stderr);
        return 1;
    }
    p = gl_guest_string(0x1F02, "4.6.0 Test Driver");
    if (strcmp((const char *)G(p), "4.6.0 Test Driver")) return 2;
    gl_load(getproc);
    shims_register(gl_thunks);
    uint32_t output = guest_alloc(8);
    wr(G(output + 4), 4, 0x12345678);
    uint32_t args[2] = {0, output};
    guest_call(shim_lookup("opengl32.dll", "glGetPointerv"), 2, args);
    if (mem32(output) != 0x60001000u || mem32(output + 4) != 0x12345678) {
        fputs("GL pointer outputs must use guest addresses without overwriting adjacent bytes\n", stderr);
        return 3;
    }
    // The same GL parameter is guest RAM when no buffer is bound and a BYTE
    // OFFSET when the corresponding VBO/IBO is bound. Zero must remain NULL.
    uint32_t indices = guest_alloc(32), vertices = guest_alloc(32);
    uint32_t draw[4] = {4, 3, 0x1403, indices};
    guest_call(shim_lookup("opengl32.dll", "glDrawElements"), 4, draw);
    if (last_elements != G(indices)) return 29;
    uint32_t vertex[4] = {3, 0x1406, 12, vertices};
    guest_call(shim_lookup("opengl32.dll", "glVertexPointer"), 4, vertex);
    if (last_vertex != G(vertices)) return 30;
    uint32_t element_binding[2] = {0x8893, 27}; // GL_ELEMENT_ARRAY_BUFFER
    guest_call(shim_lookup("opengl32.dll", "glBindBufferARB"), 2, element_binding);
    if (bind_calls != 1) return 31;
    draw[3] = 16;
    guest_call(shim_lookup("opengl32.dll", "glDrawElements"), 4, draw);
    if (last_elements != (void *)(uintptr_t)16) return 32;
    uint32_t ranged[6] = {4, 0, 3, 3, 0x1403, 24};
    guest_call(shim_lookup("opengl32.dll", "glDrawRangeElements"), 6, ranged);
    if (last_range != (void *)(uintptr_t)24) return 33;
    vertex[3] = vertices;
    guest_call(shim_lookup("opengl32.dll", "glVertexPointer"), 4, vertex);
    if (last_vertex != G(vertices)) return 34; // ELEMENT buffer must not change ARRAY
    uint32_t array_binding[2] = {0x8892, 41}; // GL_ARRAY_BUFFER
    guest_call(shim_lookup("opengl32.dll", "glBindBufferARB"), 2, array_binding);
    vertex[3] = 20;
    guest_call(shim_lookup("opengl32.dll", "glVertexPointer"), 4, vertex);
    if (last_vertex != (void *)(uintptr_t)20) return 35;
    uint32_t texcoord[4] = {2, 0x1406, 8, 32};
    guest_call(shim_lookup("opengl32.dll", "glTexCoordPointer"), 4, texcoord);
    if (last_texcoord != (void *)(uintptr_t)32) return 36;
    draw[3] = indices;
    guest_call(shim_lookup("opengl32.dll", "glDrawElements"), 4, draw);
    if (last_elements != (void *)(uintptr_t)indices) return 37;
    element_binding[1] = 0;
    guest_call(shim_lookup("opengl32.dll", "glBindBufferARB"), 2, element_binding);
    guest_call(shim_lookup("opengl32.dll", "glDrawElements"), 4, draw);
    if (last_elements != G(indices)) return 38;
    uint32_t buf = guest_alloc(4), n = 1;
    wr(G(buf), 4, 41);
    uint32_t deleting[2] = {n, buf};
    guest_call(shim_lookup("opengl32.dll", "glDeleteBuffersARB"), 2, deleting);
    vertex[3] = vertices;
    guest_call(shim_lookup("opengl32.dll", "glVertexPointer"), 4, vertex);
    if (last_vertex != G(vertices)) return 39;
    array_binding[1] = 11;
    guest_call(shim_lookup("opengl32.dll", "glBindBufferARB"), 2, array_binding);
    gl_load(getproc); // recreation clears stale bound IDs, not just function pointers
    guest_call(shim_lookup("opengl32.dll", "glVertexPointer"), 4, vertex);
    if (last_vertex != G(vertices)) return 40;
    // A click can begin and end before the game polls; retain both transitions.
    if (SDL_Init(SDL_INIT_EVENTS)) return 4;
    shims_register(window_thunks);
    // The GL resolver must return the exact existing thunk for early, middle,
    // late and unknown names after moving to a sorted lookup.
    uint32_t resolve = shim_lookup("opengl32.dll", "wglGetProcAddress");
    const char *valid[] = {"glActiveTexture", "glDrawElements", "glVertexPointer"};
    for (int i = 0; i < 3; ++i) {
        uint32_t name = guest_strdup(valid[i]), params[1] = {name};
        uint32_t proc = guest_call(resolve, 1, params);
        if (!proc || proc != shim_lookup("opengl32.dll", valid[i])) return 41;
    }
    uint32_t missing = guest_strdup("glNotAnOpenGLFunction"), unknown[1] = {missing};
    if (guest_call(resolve, 1, unknown) != 0) return 42;
    SDL_Event event = {0};
    event.type = SDL_MOUSEBUTTONDOWN; event.button.button = SDL_BUTTON_LEFT;
    if (SDL_PushEvent(&event) != 1) return 5;
    event.type = SDL_MOUSEBUTTONUP;
    if (SDL_PushEvent(&event) != 1) return 6;
    uint32_t message = guest_alloc(28);
    uint32_t peek[5] = {message, 0, 0, 0, 1};
    uint32_t fn = shim_lookup("USER32.dll", "PeekMessageA");
    if (!guest_call(fn, 5, peek) || mem32(message+4) != 0x201 || mem32(message+8) != 1) return 7;
    if (!guest_call(fn, 5, peek) || mem32(message+4) != 0x202 || mem32(message+8) != 0) return 8;
    event.type = SDL_MOUSEBUTTONDOWN; event.button.button = SDL_BUTTON_LEFT;
    SDL_PushEvent(&event);
    event.button.button = SDL_BUTTON_RIGHT; SDL_PushEvent(&event);
    event.type = SDL_MOUSEBUTTONUP; event.button.button = SDL_BUTTON_LEFT; SDL_PushEvent(&event);
    event.type = SDL_MOUSEMOTION; event.motion.xrel = 3; event.motion.yrel = 4; SDL_PushEvent(&event);
    event.type = SDL_MOUSEBUTTONUP; event.button.button = SDL_BUTTON_RIGHT; SDL_PushEvent(&event);
    const uint32_t messages[] = {0x201, 0x204, 0x202, 0x200, 0x205};
    const uint32_t states[] = {1, 3, 2, 2, 0};
    for (int i = 0; i < 5; i++)
        if (!guest_call(fn, 5, peek) || mem32(message+4) != messages[i] || mem32(message+8) != states[i]) return 9;
    if (!window_push_input(0, 1, 32768, 32768) || !window_push_input(0, 2, 32768, 32768)) return 10;
    const uint32_t touch_messages[] = {0x200, 0x201, 0x200, 0x202};
    for (int i = 0; i < 4; i++)
        if (!guest_call(fn, 5, peek) || mem32(message+4) != touch_messages[i]
                || mem32(message+12) != ((239u << 16) | 319u)) return 11;
    if (!window_push_input(1, SDL_SCANCODE_W, 1, 0)
            || !window_push_input(1, SDL_SCANCODE_W, 0, 0)) return 12;
    if (!guest_call(fn, 5, peek) || mem32(message+4) != 0x100 || mem32(message+8) != 'W') return 13;
    if (!guest_call(fn, 5, peek) || mem32(message+4) != 0x101 || mem32(message+8) != 'W') return 14;
    if (window_push_input(0, 0, -1, 0) || window_push_input(1, SDL_NUM_SCANCODES, 1, 0)
            || window_push_input(5, 0, 0, 0)) return 15;
    // A slow frame must not discard the release at the end of an input burst.
    for (int i = 0; i < 400; i++)
        if (!window_push_input(1, SDL_SCANCODE_W, !(i & 1), 0)) return 16;
    for (int i = 0; i < 400; i++)
        if (!guest_call(fn, 5, peek) || mem32(message+4) != (i & 1 ? 0x101u : 0x100u)) return 17;
    // The original engine warps to its center each frame. An unchanged absolute
    // touch must yield zero delta, rather than move the UI cursor repeatedly.
    uint32_t center[2] = {320, 240};
    guest_call(shim_lookup("USER32.dll", "SetCursorPos"), 2, center);
    if (!window_push_input(0, 0, 32768, 32768)) return 18;
    guest_call(fn, 5, peek);
    uint32_t point = guest_alloc(8);
    guest_call(shim_lookup("USER32.dll", "GetCursorPos"), 1, &point);
    if (mem32(point) != 320 || mem32(point+4) != 240) return 19;
    // Menu activation waits until movement has been processed by a frame.
    if (!window_push_input(4, 0, 32768, 32768)) return 20;
    if (!guest_call(fn, 5, peek) || mem32(message+4) != 0x200) return 21;
    if (guest_call(fn, 5, peek)) return 22;
    uint32_t hdc = 0;
    guest_call(shim_lookup("GDI32.dll", "SwapBuffers"), 1, &hdc);
    if (!guest_call(fn, 5, peek) || mem32(message+4) != 0x201) return 23;
    if (!guest_call(fn, 5, peek) || mem32(message+4) != 0x202) return 24;
    if (!window_push_input(4, 0, 32768, 32768) || !window_push_input(4, 1, 0, 0)) return 25;
    if (!guest_call(fn, 5, peek) || mem32(message+4) != 0x200) return 26;
    guest_call(shim_lookup("GDI32.dll", "SwapBuffers"), 1, &hdc);
    if (guest_call(fn, 5, peek)) return 27;
    // Down/up can arrive before one engine frame. Absolute UI movement must
    // replace the pending delta, rather than apply the same target twice.
    window_menu_pointer = menu_delta;
    guest_call(shim_lookup("USER32.dll", "SetCursorPos"), 2, center);
    window_push_input(0, 0, 32768, 32768);
    window_push_input(0, 0, 32768, 32768);
    guest_call(fn, 5, peek); guest_call(fn, 5, peek);
    guest_call(shim_lookup("USER32.dll", "GetCursorPos"), 1, &point);
    if (mem32(point) != 330 || mem32(point+4) != 260) {
        fputs("Batched absolute touches must not accumulate UI movement\n", stderr);
        return 28;
    }
    window_menu_pointer = NULL;
    SDL_Quit();
    puts("guest GL strings and queued input passed");
    return 0;
}
