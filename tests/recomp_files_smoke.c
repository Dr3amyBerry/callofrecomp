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
    uint32_t seek[4] = {h, 1, 0, 0};
    if (call("SetFilePointer",4,seek)!=1)return 20;
    read_args[2]=7;
    if (!call("ReadFile",5,read_args)||mem32(count)!=3||memcmp(G(buf),"K\003\004",3))return 21;
    seek[1]=2;seek[3]=2;
    if(call("SetFilePointer",4,seek)!=6)return 22;
    if(!call("ReadFile",5,read_args)||mem32(count)!=0)return 23;
    seek[1]=(uint32_t)-1;seek[3]=0;
    if(call("SetFilePointer",4,seek)!=UINT32_MAX)return 24;
    seek[1]=0;
    if(call("SetFilePointer",4,seek)!=0)return 25;
    read_args[2]=4;
    if(!call("ReadFile",5,read_args)||mem32(count)!=4||memcmp(G(buf),"PK\003\004",4))return 26;
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
    // Copy-on-write OPEN_EXISTING must reproduce the entire binary original
    // when the overlay does not yet contain the file.
    uint32_t original_copy = guest_strdup("C:\\cod\\copy_fixture.bin");
    uint32_t copy_args[7] = {original_copy, 0xC0000000u, 1, 0, 3, 0, 0};
    uint32_t copy_h = call("CreateFileA", 7, copy_args);
    if (copy_h == UINT32_MAX) return 28;
    uint32_t copy_buf = guest_alloc(4096), copy_count = guest_alloc(4);
    uint32_t copy_read[5] = {copy_h, copy_buf, 4096, copy_count, 0};
    for (uint32_t pos = 0; pos < 16 * 1024 + 147; ) {
        uint32_t size = (16 * 1024 + 147) - pos;
        if (size > 4096) size = 4096;
        copy_read[2] = size;
        if (!call("ReadFile", 5, copy_read) || mem32(copy_count) != size) return 29;
        for (uint32_t i = 0; i < size; i++)
            if (((uint8_t *)G(copy_buf))[i] != (uint8_t)(((pos + i) * 53 + 71) & 255)) return 30;
        pos += size;
    }
    if (!call("CloseHandle", 1, &copy_h)) return 31;
    // Real engine clocks must advance with elapsed time, not once per call.
    // Otherwise CPU calibration selects the no-prediction low-spec profile.
    shim_realtime = 1;
    uint32_t clock_arg[1] = {guest_alloc(8)};
    call("QueryPerformanceFrequency", 1, clock_arg);
    uint64_t frequency = (uint64_t)rd(G(clock_arg[0]), 8);
    call("QueryPerformanceCounter", 1, clock_arg);
    uint64_t before = (uint64_t)rd(G(clock_arg[0]), 8);
    uint64_t ticks_before = (uint64_t)rdtsc_val();
    uint32_t millis_before = call("GetTickCount", 0, NULL);
    uint32_t delay[1] = {30}; call("Sleep", 1, delay);
    call("QueryPerformanceCounter", 1, clock_arg);
    uint64_t elapsed = (uint64_t)rd(G(clock_arg[0]), 8) - before;
    if (!frequency || elapsed * 1000 / frequency < 25) return 17;
    if ((uint64_t)rdtsc_val() - ticks_before < 25000000) return 18;
    if ((uint32_t)(call("GetTickCount", 0, NULL) - millis_before) < 25) return 19;
    shim_realtime = 0;
    call("QueryPerformanceCounter", 1, clock_arg);
    before = (uint64_t)rd(G(clock_arg[0]), 8);
    call("QueryPerformanceCounter", 1, clock_arg);
    if ((uint64_t)rd(G(clock_arg[0]), 8) - before != 16000) return 20;
    ticks_before = (uint64_t)rdtsc_val();
    if ((uint64_t)rdtsc_val() - ticks_before != 1000) return 21;
    puts("recompiled file boundary passed");
    return 0;
}
