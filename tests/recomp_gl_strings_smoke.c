#include <stdio.h>
#include <SDL.h>
#include "gl_thunks.h"

static void GLAPI_CALL fake_get_pointer(int name, void **out) {
    (void)name;
    *out = G(0x60001000u);
}

static void *getproc(const char *name) {
    return !strcmp(name, "glGetPointerv") ? (void *)fake_get_pointer : NULL;
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
    // A click can begin and end before the game polls; retain both transitions.
    if (SDL_Init(SDL_INIT_EVENTS)) return 4;
    shims_register(window_thunks);
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
