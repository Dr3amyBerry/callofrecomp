// Exercise the Win32 file boundary through real guest thunks, without game data.
#include <stdio.h>
#include "recomp_rt.h"

static uint32_t call(const char *name, int n, uint32_t *args) {
    uint32_t fn = shim_lookup("KERNEL32.dll", name);
    if (!fn) guest_fatal("missing test thunk %s", name);
    return guest_call(fn, n, args);
}

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    files_game_dir = argv[1];
    files_home_dir = argv[2];
    guest_init();
    shims_register(files_thunks);
    shims_register(kernel32_thunks);
    uint32_t args[7] = {guest_strdup("C:\\cod\\fixture.pk3"), 0x80000000u, 1, 0, 3, 0, 0};
    uint32_t h = call("CreateFileA", 7, args);
    if (h == 0xFFFFFFFFu) return 3;
    args[0] = h;
    if (call("GetFileType", 1, args) != 1) {
        fprintf(stderr, "regular files must report FILE_TYPE_DISK to the guest CRT\n");
        return 4;
    }
    uint32_t buf = guest_alloc(8), count = guest_alloc(4);
    uint32_t read_args[5] = {h, buf, 4, count, 0};
    if (!call("ReadFile", 5, read_args) || mem32(count) != 4 || memcmp(G(buf), "PK\003\004", 4)) return 5;
    if (!call("CloseHandle", 1, args)) return 6;
    if (call("GetFileType", 1, args) != 0) return 7;
    // The original CRT checks GetLastError after a failed rename, then the
    // engine deletes the old autosave and retries. Never hide that failure.
    uint32_t move_args[2] = {guest_strdup("C:\\cod\\temp.svg"), guest_strdup("C:\\cod\\autosave.svg")};
    uint32_t no_error[1] = {0};
    call("SetLastError", 1, no_error);
    if (call("MoveFileA", 2, move_args)) return 8;
    if (call("GetLastError", 0, NULL) != 183) return 9; // ERROR_ALREADY_EXISTS
    args[0] = move_args[1]; args[1] = 0x80000000u;
    h = call("CreateFileA", 7, args);
    if (h == 0xFFFFFFFFu) return 14;
    read_args[0] = h; read_args[2] = 3;
    if (!call("ReadFile", 5, read_args) || mem32(count) != 3 || memcmp(G(buf), "old", 3)) return 15;
    args[0] = h;
    if (!call("CloseHandle", 1, args)) return 16;
    if (!call("DeleteFileA", 1, &move_args[1])) return 10;
    if (!call("MoveFileA", 2, move_args)) return 11;
    if (call("MoveFileA", 2, move_args)) return 12; // source was consumed
    if (call("GetLastError", 0, NULL) != 2) return 13; // ERROR_FILE_NOT_FOUND
    puts("recompiled file boundary passed");
    return 0;
}
