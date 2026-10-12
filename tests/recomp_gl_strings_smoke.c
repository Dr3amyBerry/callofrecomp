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
    SDL_Quit();
    puts("guest GL strings and queued input passed");
    return 0;
}
