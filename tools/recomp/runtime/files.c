// KERNEL32 file-system and system-information shims for the recompiled engine.
// Guest sees the game at C:\cod. Reads resolve to CODRECOMP_HOME (writable
// overlay) first, then the original install; writes always go to the overlay,
// so the user's install is never modified.
#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <time.h>

#include "recomp_rt.h"

#ifdef _WIN32
#include <direct.h>
#define mkdir_host(p) _mkdir(p)
#else
#define mkdir_host(p) mkdir(p, 0755)
#endif

#define GUEST_CWD "C:\\cod"
#define INVALID 0xFFFFFFFFu

const char *files_game_dir = ".";
const char *files_home_dir = "codrecomp_home";
int shim_realtime;  // 0: deterministic clocks (trace tests), 1: wall clock (engine)

uint32_t host_millis(void) {
    struct timespec ts;
    timespec_get(&ts, TIME_UTC);
    return (uint32_t)(ts.tv_sec * 1000ull + ts.tv_nsec / 1000000);
}

// Guest path -> path relative to the game root ("main/pak0.pk3"); NULL if outside.
static int guest_rel(const char *in, char *out, size_t cap) {
    const char *p = in;
    if (!strncasecmp(p, GUEST_CWD, strlen(GUEST_CWD))) {
        p += strlen(GUEST_CWD);
    } else if (p[0] && p[1] == ':') {
        return 0;  // another drive: not part of the game
    }
    while (*p == '\\' || *p == '/') p++;
    size_t n = 0;
    for (; *p && n + 1 < cap; p++) out[n++] = *p == '\\' ? '/' : *p;
    out[n] = 0;
    return 1;
}

static void host_path(const char *root, const char *rel, char *out, size_t cap) {
    snprintf(out, cap, "%s/%s", root, rel);
}

static int exists(const char *path, struct stat *st) { return stat(path, st) == 0; }

// Resolve for reading: overlay first, then the install.
static int resolve_read(const char *guest, char *out, size_t cap, struct stat *st) {
    char rel[1024];
    if (!guest_rel(guest, rel, sizeof rel)) return 0;
    host_path(files_home_dir, rel, out, cap);
    if (exists(out, st)) return 1;
    host_path(files_game_dir, rel, out, cap);
    return exists(out, st);
}

static void mkdirs_for(const char *path) {
    char tmp[1024];
    snprintf(tmp, sizeof tmp, "%s", path);
    for (char *s = tmp + 1; *s; s++)
        if (*s == '/') { *s = 0; mkdir_host(tmp); *s = '/'; }
}

// ---------------------------------------------------------------- handles

typedef struct { FILE *f; DIR *dir; char pattern[260]; char dirpath[1024]; char rel_dir[1024]; int pass; } handle;
static handle handles[256];

static uint32_t new_handle(void) {
    for (uint32_t i = 1; i < 256; i++)
        if (!handles[i].f && !handles[i].dir) return i;
    guest_fatal("out of file handles");
    return 0;
}
static handle *get(uint32_t h) { return h > 0 && h < 256 ? &handles[h] : NULL; }
#define HBASE 0x1000u  // guest-visible handle = HBASE + index

#define K(name) static uint32_t k_##name(uint32_t esp)
#define A(i) ARG(esp, i)
#define S(i) ((const char *)G(A(i)))

K(CreateFileA) {
    uint32_t access = A(1), disp = A(4);
    char path[1100], rel[1024];
    struct stat st;
    const char *mode;
    if (!(access & 0x40000000u)) {  // read only
        if (!resolve_read(S(0), path, sizeof path, &st) || S_ISDIR(st.st_mode)) return INVALID;
        mode = "rb";
    } else {
        if (!guest_rel(S(0), rel, sizeof rel)) return INVALID;
        host_path(files_home_dir, rel, path, sizeof path);
        mkdirs_for(path);
        int have = exists(path, &st);
        if (!have && (disp == 3 || disp == 5)) {  // OPEN_EXISTING / TRUNCATE_EXISTING: copy from install
            char src[1100];
            if (!resolve_read(S(0), src, sizeof src, &st)) return INVALID;
            FILE *a = fopen(src, "rb"), *b = fopen(path, "wb");
            int c;
            while (a && b && (c = fgetc(a)) != EOF) fputc(c, b);
            if (a) fclose(a);
            if (b) fclose(b);
            have = 1;
        }
        if (disp == 1 && have) return INVALID;  // CREATE_NEW
        mode = (disp == 2 || disp == 5 || !have) ? "w+b" : "r+b";
    }
    FILE *f = fopen(path, mode);
    if (!f) return INVALID;
    uint32_t h = new_handle();
    handles[h].f = f;
    return HBASE + h;
}

K(ReadFile) {
    handle *h = get(A(0) - HBASE);
    if (!h || !h->f) return 0;
    size_t n = fread(G(A(1)), 1, A(2), h->f);
    if (A(3)) wr(G(A(3)), 4, (uint32_t)n);
    return 1;
}

K(WriteFile) {
    uint32_t hv = A(0);
    if (hv == INVALID - 10 || hv == INVALID - 11) {  // stdout / stderr pseudo handles
        fwrite(G(A(1)), 1, A(2), stdout);
        if (A(3)) wr(G(A(3)), 4, A(2));
        return 1;
    }
    handle *h = get(hv - HBASE);
    if (!h || !h->f) return 0;
    size_t n = fwrite(G(A(1)), 1, A(2), h->f);
    if (A(3)) wr(G(A(3)), 4, (uint32_t)n);
    return 1;
}

K(SetFilePointer) {
    handle *h = get(A(0) - HBASE);
    if (!h || !h->f) return INVALID;
    static const int whence[3] = {SEEK_SET, SEEK_CUR, SEEK_END};
    if (fseek(h->f, (long)(int32_t)A(1), whence[A(3) % 3])) return INVALID;
    if (A(2)) wr(G(A(2)), 4, 0);
    return (uint32_t)ftell(h->f);
}

K(CloseHandle) {
    handle *h = get(A(0) - HBASE);
    if (h && h->f) { fclose(h->f); h->f = NULL; }
    return 1;
}

K(GetFileType) {
    handle *h = get(A(0) - HBASE);
    return h && h->f ? 1 : 0;  // FILE_TYPE_DISK / FILE_TYPE_UNKNOWN
}

K(FlushFileBuffers) {
    handle *h = get(A(0) - HBASE);
    if (h && h->f) fflush(h->f);
    return 1;
}

static int wildcard(const char *pat, const char *s) {
    if (!*pat) return !*s;
    if (*pat == '*') return wildcard(pat + 1, s) || (*s && wildcard(pat, s + 1));
    if (!*s) return 0;
    char a = *pat, b = *s;
    if (a >= 'A' && a <= 'Z') a += 32;
    if (b >= 'A' && b <= 'Z') b += 32;
    return (a == '?' || a == b) && wildcard(pat + 1, s + 1);
}

// Fill WIN32_FIND_DATAA with the next match; the overlay (pass 0) and the
// install (pass 1) are both listed.
static int find_next(handle *h, uint32_t out) {
    for (;;) {
        struct dirent *e = h->dir ? readdir(h->dir) : NULL;
        if (!e) {
            if (h->dir) closedir(h->dir);
            h->dir = NULL;
            if (h->pass++ >= 1) return 0;
            host_path(files_game_dir, h->rel_dir, h->dirpath, sizeof h->dirpath);
            h->dir = opendir(h->dirpath);
            if (!h->dir) return 0;
            continue;
        }
        if (!wildcard(h->pattern, e->d_name)) continue;
        char full[1400];
        struct stat st;
        snprintf(full, sizeof full, "%s/%s", h->dirpath, e->d_name);
        if (!exists(full, &st)) continue;
        memset(G(out), 0, 320);
        wr(G(out), 4, S_ISDIR(st.st_mode) ? 0x10 : 0x80);
        wr(G(out + 32), 4, (uint32_t)st.st_size);
        snprintf((char *)G(out + 44), 260, "%s", e->d_name);
        return 1;
    }
}

K(FindFirstFileA) {
    char rel[1024];
    if (!guest_rel(S(0), rel, sizeof rel)) return INVALID;
    char *slash = strrchr(rel, '/');
    uint32_t hi = new_handle();
    handle *h = &handles[hi];
    memset(h, 0, sizeof *h);
    snprintf(h->pattern, sizeof h->pattern, "%s", slash ? slash + 1 : rel);
    if (slash) *slash = 0; else rel[0] = 0;
    snprintf(h->rel_dir, sizeof h->rel_dir, "%s", rel);
    host_path(files_home_dir, rel, h->dirpath, sizeof h->dirpath);
    h->dir = opendir(h->dirpath);
    if (!h->dir) {
        h->pass = 1;
        host_path(files_game_dir, rel, h->dirpath, sizeof h->dirpath);
        h->dir = opendir(h->dirpath);
    }
    if (!h->dir || !find_next(h, A(1))) {
        if (h->dir) closedir(h->dir);
        h->dir = NULL;
        return INVALID;
    }
    return HBASE + hi;
}

K(FindNextFileA) {
    handle *h = get(A(0) - HBASE);
    return h && h->dir && find_next(h, A(1));
}

K(FindClose) {
    handle *h = get(A(0) - HBASE);
    if (h && h->dir) closedir(h->dir);
    if (h) h->dir = NULL;
    return 1;
}

K(GetFileAttributesA) {
    char path[1100];
    struct stat st;
    if (!resolve_read(S(0), path, sizeof path, &st)) return INVALID;
    return S_ISDIR(st.st_mode) ? 0x10 : 0x80;
}

K(CreateDirectoryA) {
    char rel[1024], path[1100];
    if (!guest_rel(S(0), rel, sizeof rel)) return 0;
    host_path(files_home_dir, rel, path, sizeof path);
    mkdirs_for(path);
    return mkdir_host(path) == 0 || errno == EEXIST;
}

K(DeleteFileA) {
    char rel[1024], path[1100];
    if (!guest_rel(S(0), rel, sizeof rel)) return 0;
    host_path(files_home_dir, rel, path, sizeof path);
    return remove(path) == 0;
}

K(MoveFileA) {
    char r1[1024], r2[1024], p1[1100], p2[1100];
    if (!guest_rel(S(0), r1, sizeof r1) || !guest_rel(S(1), r2, sizeof r2)) return 0;
    host_path(files_home_dir, r1, p1, sizeof p1);
    host_path(files_home_dir, r2, p2, sizeof p2);
    mkdirs_for(p2);
    return rename(p1, p2) == 0;
}

static uint32_t put_str(uint32_t dst, uint32_t cap, const char *s) {
    uint32_t n = (uint32_t)strlen(s);
    if (cap <= n) return n + 1;
    memcpy(G(dst), s, n + 1);
    return n;
}

K(GetCurrentDirectoryA) { return put_str(A(1), A(0), GUEST_CWD); }
K(GetTempPathA) { return put_str(A(1), A(0), GUEST_CWD "\\temp\\"); }
K(GetSystemDirectoryA) { return put_str(A(0), A(1), "C:\\WINDOWS\\system32"); }
K(GetFullPathNameA) {
    char buf[1100];
    const char *p = S(0);
    if (p[0] && p[1] == ':') snprintf(buf, sizeof buf, "%s", p);
    else snprintf(buf, sizeof buf, GUEST_CWD "\\%s", p);
    uint32_t n = put_str(A(2), A(1), buf);
    if (A(3) && n < A(1)) {
        char *last = strrchr((char *)G(A(2)), '\\');
        wr(G(A(3)), 4, last ? A(2) + (uint32_t)(last + 1 - (char *)G(A(2))) : A(2));
    }
    return n;
}
K(GetDriveTypeA) { (void)esp; return 3; }  // DRIVE_FIXED
K(GlobalMemoryStatus) {
    uint32_t v[8] = {32, 10, 512u << 20, 400u << 20, 1024u << 20, 900u << 20, 2047u << 20, 1800u << 20};
    memcpy(G(A(0)), v, sizeof v);
    return 0;
}
K(Sleep) {
#ifdef _WIN32
    extern __declspec(dllimport) void __stdcall Sleep(unsigned long);
    if (shim_realtime) Sleep(A(0));
#else
    if (shim_realtime) { struct timespec ts = {A(0) / 1000, (A(0) % 1000) * 1000000L}; nanosleep(&ts, NULL); }
#endif
    return 0;
}
K(IsBadPtr) { return !guest_committed(A(0)); }
K(MulDiv) { return A(2) ? (uint32_t)(int32_t)((int64_t)(int32_t)A(0) * (int32_t)A(1) / (int32_t)A(2)) : INVALID; }
K(ReturnZero) { (void)esp; return 0; }
K(ReturnTrue) { (void)esp; return 1; }
K(ReturnInvalid) { (void)esp; return INVALID; }
K(FileTimeToLocalFileTime) { wr(G(A(1)), 8, rd(G(A(0)), 8)); return 1; }
K(FileTimeToSystemTime) {
    uint16_t st[8] = {2004, 3, 2, 2, 12, 0, 0, 0};
    memcpy(G(A(1)), st, sizeof st);
    return 1;
}
K(GetTimeZoneInformation) { memset(G(A(0)), 0, 172); return 0; }
K(timeGetTime) {
    (void)esp;
    static uint32_t t;
    return shim_realtime ? host_millis() : (t += 16);
}
K(GetUserNameA) {
    uint32_t cap = mem32(A(1)), n = put_str(A(0), cap, "player");
    wr(G(A(1)), 4, n + 1);
    return n < cap;
}
K(RaiseException) {
    guest_fatal("RaiseException(%08x, flags=%08x, count=%u, args=%08x, ret=%08x)",
        A(0), A(1), A(2), A(3), mem32(esp));
    return 0;
}
K(FatalAppExitA) { guest_fatal("FatalAppExit: %s", S(1)); return 0; }

#define F(dll, name, pop) {dll, #name, k_##name, pop}
#define AL(dll, name, fn, pop) {dll, #name, k_##fn, pop}
const thunk_def files_thunks[] = {
    F("KERNEL32.dll", GetFileType, 4),
    F("KERNEL32.dll", CreateFileA, 28), F("KERNEL32.dll", ReadFile, 20), F("KERNEL32.dll", WriteFile, 20),
    F("KERNEL32.dll", SetFilePointer, 16), F("KERNEL32.dll", CloseHandle, 4), F("KERNEL32.dll", FlushFileBuffers, 4),
    AL("KERNEL32.dll", SetEndOfFile, ReturnTrue, 4), F("KERNEL32.dll", FindFirstFileA, 8),
    F("KERNEL32.dll", FindNextFileA, 8), F("KERNEL32.dll", FindClose, 4), F("KERNEL32.dll", GetFileAttributesA, 4),
    AL("KERNEL32.dll", SetFileAttributesA, ReturnTrue, 8), F("KERNEL32.dll", CreateDirectoryA, 8),
    F("KERNEL32.dll", DeleteFileA, 4), F("KERNEL32.dll", MoveFileA, 8), F("KERNEL32.dll", GetCurrentDirectoryA, 8),
    F("KERNEL32.dll", GetTempPathA, 8), F("KERNEL32.dll", GetSystemDirectoryA, 8),
    F("KERNEL32.dll", GetFullPathNameA, 16), F("KERNEL32.dll", GetDriveTypeA, 4),
    F("KERNEL32.dll", GlobalMemoryStatus, 4), F("KERNEL32.dll", Sleep, 4), AL("KERNEL32.dll", IsBadReadPtr, IsBadPtr, 8),
    AL("KERNEL32.dll", IsBadWritePtr, IsBadPtr, 8), AL("KERNEL32.dll", IsBadCodePtr, IsBadPtr, 4),
    F("KERNEL32.dll", MulDiv, 12), AL("KERNEL32.dll", SetErrorMode, ReturnZero, 4),
    AL("KERNEL32.dll", SetThreadExecutionState, ReturnZero, 4),
    AL("KERNEL32.dll", SetUnhandledExceptionFilter, ReturnZero, 4),
    AL("KERNEL32.dll", SetConsoleCtrlHandler, ReturnTrue, 8), AL("KERNEL32.dll", FormatMessageA, ReturnZero, 28),
    F("KERNEL32.dll", FileTimeToLocalFileTime, 8), F("KERNEL32.dll", FileTimeToSystemTime, 8),
    F("KERNEL32.dll", GetTimeZoneInformation, 4), AL("KERNEL32.dll", CreateToolhelp32Snapshot, ReturnInvalid, 8),
    AL("KERNEL32.dll", SetEnvironmentVariableA, ReturnTrue, 8), AL("KERNEL32.dll", SetEnvironmentVariableW, ReturnTrue, 8),
    AL("KERNEL32.dll", SetStdHandle, ReturnTrue, 8), F("KERNEL32.dll", RaiseException, 16),
    F("KERNEL32.dll", FatalAppExitA, 8), AL("KERNEL32.dll", IsValidCodePage, ReturnTrue, 4),
    AL("KERNEL32.dll", GetUserDefaultLCID, ReturnZero, 0), F("WINMM.dll", timeGetTime, 0),
    AL("WINMM.dll", timeBeginPeriod, ReturnZero, 4), AL("WINMM.dll", timeEndPeriod, ReturnZero, 4),
    AL("WINMM.dll", joyGetNumDevs, ReturnZero, 0), AL("WINMM.dll", midiInGetNumDevs, ReturnZero, 0),
    F("ADVAPI32.dll", GetUserNameA, 8),
    {0, 0, 0, 0},
};
