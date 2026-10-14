#include <SDL.h>
#include <jni.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include "../tools/recomp/runtime/widescreen.h"
#define main engine_main
#include "../tools/recomp/hosts/engine_host.c"
#undef main

JNIEXPORT jint JNICALL Java_org_callofrecomp_GameActivity_nativeInput(
    JNIEnv *env, jclass cls, jint kind, jint control, jint x, jint y) {
    (void)env; (void)cls;
    return window_push_input(kind, control, x, y);
}

extern int window_load_state(void);
JNIEXPORT jint JNICALL Java_org_callofrecomp_GameActivity_nativeLoadState(
    JNIEnv *env, jclass cls) {
    (void)env; (void)cls;
    return window_load_state();
}

__attribute__((visibility("default"))) int SDL_main(int argc, char **argv) {
    if (argc < 3) return 1;
    mkdir(argv[2], 0700);
    char log[4096];
    snprintf(log, sizeof log, "%s/codrecomp.log", argv[2]);
    int fd = open(log, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fd >= 0) { dup2(fd, STDOUT_FILENO); dup2(fd, STDERR_FILENO); close(fd); }
    setvbuf(stdout, NULL, _IOLBF, 0);
    /* Opt-in local diagnostics; absent in normal play to avoid log I/O. */
    char frame_stats[4096];
    snprintf(frame_stats, sizeof frame_stats, "%s/frame_stats", argv[2]);
    if (access(frame_stats, F_OK) == 0) setenv("CODRECOMP_FRAME_STATS", "1", 1);
    else unsetenv("CODRECOMP_FRAME_STATS");
    snprintf(frame_stats, sizeof frame_stats, "%s/cpu_stats", argv[2]);
    if (access(frame_stats, F_OK) == 0) setenv("CODRECOMP_CPU_STATS", "1", 1);
    else unsetenv("CODRECOMP_CPU_STATS");
    snprintf(frame_stats, sizeof frame_stats, "%s/gl_stats", argv[2]);
    if (access(frame_stats, F_OK) == 0) setenv("CODRECOMP_GL_STATS", "1", 1);
    else unsetenv("CODRECOMP_GL_STATS");
    snprintf(frame_stats, sizeof frame_stats, "%s/gl_time", argv[2]);
    if (access(frame_stats, F_OK) == 0) setenv("CODRECOMP_GL_TIME", "1", 1);
    else unsetenv("CODRECOMP_GL_TIME");
    setenv("LIBGL_ES", "2", 1);
    setenv("LIBGL_GL", "21", 1);
    setenv("LIBGL_NOBANNER", "1", 1);
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS)) { fprintf(stderr, "SDL: %s\n", SDL_GetError()); return 2; }
    SDL_DisplayMode dm = {0};
    SDL_GetCurrentDisplayMode(0, &dm);
    /* The activity is landscape; a device can initially report portrait mode. */
    int display_width = dm.w, display_height = dm.h;
    /* Java supplies the actual fixed-size EGL buffer, not the physical display.
     * Merely lowering engine cvars would otherwise render into a corner. */
    for (int i = 1; i + 2 < argc; i++) {
        if (strcmp(argv[i], "+set")) continue;
        int value = atoi(argv[i + 2]);
        if (value <= 0 || value > 16384) continue;
        if (!strcmp(argv[i + 1], "r_customwidth")) display_width = value;
        if (!strcmp(argv[i + 1], "r_customheight")) display_height = value;
    }
    if (display_width > 0 && display_height > display_width) {
        int swap = display_width; display_width = display_height; display_height = swap;
    }
    widescreen_config display = widescreen_for_display(display_width, display_height);
    // GameActivity has already prepared the HUD overlay. Match the same
    // viewport; when the HUD was unrecognized or the aspect is 4:3, do
    // NOT modify any guest-drawn friend/tank/objective marker geometry.
    char hud_overlay[4096];
    int hud_path_length = snprintf(hud_overlay, sizeof hud_overlay,
        "%s/main/zzzz_codrecomp_hud_fix.pk3", argv[2]);
    int hud_overlay_ready = hud_path_length > 0 &&
        (size_t)hud_path_length < sizeof hud_overlay &&
        access(hud_overlay, R_OK) == 0;
    extern void guest_configure_compass_markers(int width, int height, int overlay_ready);
    guest_configure_compass_markers(display.width, display.height, hud_overlay_ready);
    printf("codrecomp: compass marker transform %s (%dx%d, overlay=%d)\n",
        hud_overlay_ready && display.aspect > (4.0 / 3.0) + 0.0001
            ? "enabled" : "inactive",
        display.width, display.height, hud_overlay_ready);
    char width[16], height[16], aspect[32], fov[32];
    snprintf(width, sizeof width, "%d", display.width);
    snprintf(height, sizeof height, "%d", display.height);
    snprintf(aspect, sizeof aspect, "%.8f", display.aspect);
    snprintf(fov, sizeof fov, "%.6f", display.fov);
    char *extra[] = {"+set", "r_mode", "-1", "+set", "r_customwidth", width,
                    "+set", "r_customheight", height, "+set", "r_customaspect", aspect,
                    "+set", "cg_fov", fov, "+set", "r_fullscreen", "0"};
    const int extra_count = (int)(sizeof extra / sizeof *extra);
    char **args = calloc((size_t)argc + extra_count + 1, sizeof *args);
    if (!args) return 3;
    memcpy(args, argv, (size_t)argc * sizeof *args);
    memcpy(args + argc, extra, sizeof extra);
    fprintf(stdout, "codrecomp: widescreen %dx%d aspect=%s horizontal FOV=%s\n",
        display.width, display.height, aspect, fov);
    int result = engine_main(argc + extra_count, args);
    free(args);
    return result;
}
