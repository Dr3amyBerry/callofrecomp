#include <stdio.h>
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
    puts("guest GL strings passed");
    return 0;
}
