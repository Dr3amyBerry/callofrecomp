// Runs the recompiled CoD 1.5 SP engine (CoDSP.exe) from its original entry
// point. The three module DLLs are offered to the engine's LoadLibraryA as
// recompiled modules; Win32 services come from the runtime shims.
#include <stdio.h>
#include <stdlib.h>

#include "gl_thunks.h"
#include "audio.h"

extern const recomp_module recomp_module_codsp, recomp_module_uix86, recomp_module_cgamex86, recomp_module_gamex86;

static int menu_pointer(int x, int y, int *dx, int *dy) {
    if (!module_loaded_at(recomp_module_uix86.image_base)) return 0;
    // Verified 1.5 SP UI_MOUSE_EVENT (vmMain command 4): cursor integers at
    // 0x401C0470/74 are clamped to 640x480 by the original 0x4000C660.
    // Read the current UI position so warping, resize and physical mouse input
    // cannot leave a stale touch origin or apply gameplay mouse sensitivity.
    *dx = x * 640 / 65535 - (int)mem32(0x401C0470u);
    *dy = y * 480 / 65535 - (int)mem32(0x401C0474u);
    // Deliver through IN_MouseMove / VM_Call, which owns the syscall VM context.
    // Calling vmMain directly here would bypass that context during hover.
    return 1;
}

static char *join(const char *dir, const char *file) {
    size_t n = strlen(dir) + strlen(file) + 2;
    char *p = malloc(n);
    snprintf(p, n, "%s/%s", dir, file);
    return p;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <original install dir> [home dir] [+engine args...]\n", argv[0]);
        return 1;
    }
    files_game_dir = argv[1];
    files_home_dir = argc > 2 && argv[2][0] != '+' ? argv[2] : "codrecomp_home";
    static char cmd[4096] = "CoDSP.exe";
    for (int i = 2; i < argc; i++)
        if (argv[i][0] == '+' || argv[i][0] == '-' || i > 2) {
            strncat(cmd, " ", sizeof cmd - strlen(cmd) - 1);
            strncat(cmd, argv[i], sizeof cmd - strlen(cmd) - 1);
        }
    guest_command_line = cmd;
    shim_realtime = 1;

    guest_init();
    shims_register(files_thunks);
    shims_register(kernel32_thunks);
    shims_register(misc_thunks);
    shims_register(window_thunks);
    window_menu_pointer = menu_pointer;
    shims_register(gl_thunks);
    shims_register(audio_thunks);
    host_dll_register("opengl32.dll");
    module_register_available(&recomp_module_uix86, join(argv[1], "uix86.dll"));
    module_register_available(&recomp_module_cgamex86, join(argv[1], "cgamex86.dll"));
    module_register_available(&recomp_module_gamex86, join(argv[1], "gamex86.dll"));
    if (!module_load(&recomp_module_codsp, join(argv[1], "CoDSP.exe"))) { perror("CoDSP.exe"); return 2; }
    guest_main_base = recomp_module_codsp.image_base;

    printf("codrecomp: starting CoDSP.exe entry %08x\n", recomp_module_codsp.entry_point);
    fflush(stdout);
    guest_call(recomp_module_codsp.entry_point, 0, NULL);
    printf("codrecomp: engine entry returned\n");
    return 0;
}
