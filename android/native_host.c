#include <SDL.h>
#include <jni.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#define main engine_main
#include "../tools/recomp/hosts/engine_host.c"
#undef main

JNIEXPORT jint JNICALL Java_org_callofrecomp_GameActivity_nativeInput(
    JNIEnv *env, jclass cls, jint kind, jint control, jint x, jint y) {
    (void)env; (void)cls;
    return window_push_input(kind, control, x, y);
}

__attribute__((visibility("default"))) int SDL_main(int argc, char **argv) {
    if (argc < 3) return 1;
    mkdir(argv[2], 0700);
    char log[4096];
    snprintf(log, sizeof log, "%s/codrecomp.log", argv[2]);
    int fd = open(log, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fd >= 0) { dup2(fd, STDOUT_FILENO); dup2(fd, STDERR_FILENO); close(fd); }
    setvbuf(stdout, NULL, _IOLBF, 0);
    setenv("LIBGL_ES", "2", 1);
    setenv("LIBGL_GL", "21", 1);
    setenv("LIBGL_NOBANNER", "1", 1);
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS)) { fprintf(stderr, "SDL: %s\n", SDL_GetError()); return 2; }
    SDL_DisplayMode dm = {0};
    SDL_GetCurrentDisplayMode(0, &dm);
    char width[16], height[16];
    snprintf(width, sizeof width, "%d", dm.w > 0 ? dm.w : 1280);
    snprintf(height, sizeof height, "%d", dm.h > 0 ? dm.h : 720);
    char *extra[] = {"+set", "r_mode", "-1", "+set", "r_customwidth", width,
                    "+set", "r_customheight", height, "+set", "r_fullscreen", "0"};
    char **args = calloc((size_t)argc + 13, sizeof *args);
    if (!args) return 3;
    memcpy(args, argv, (size_t)argc * sizeof *args);
    memcpy(args + argc, extra, sizeof extra);
    int result = engine_main(argc + 12, args);
    free(args);
    return result;
}
