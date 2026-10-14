/* Synthetic PE32 sections and host C chunks; no original engine data. */
#include "recomp_rt.h"
#include <stdio.h>
#include <stdlib.h>

#define BASE 0x24000000u
#define BSS (BASE + 0x2100u)
static unsigned attaches, detaches;
static uint32_t attach_bss, detach_bss;
static int bad_arguments;

static void module_code(void) {
    uint32_t esp = reg32(REG_ESP);
    if (PC == BASE + 0x1000) {
        uint32_t reason = ARG(esp, 1);
        if (ARG(esp, 0) != BASE || ARG(esp, 2) != 0 || reason > 1) bad_arguments = 1;
        if (reason == 1) { attaches++; attach_bss = mem32(BSS); }
        else { detaches++; detach_bss = mem32(BSS); }
        set_reg32(REG_EAX, 1);
        set_reg32(REG_ESP, esp + 16);
    } else {
        set_reg32(REG_EAX, 0x12345678);
        set_reg32(REG_ESP, esp + 4);
    }
    PC = mem32(esp);
}

static const recomp_chunk chunks[] = {
    {BASE + 0x1000, BASE + 0x1001, module_code},
    {BASE + 0x1100, BASE + 0x1101, module_code}
};
static const recomp_import imports[] = {{0}};
static const recomp_export exports[] = {{"fixture_export", BASE + 0x1100}, {0}};
static const recomp_module fixture = {"lifecycle.dll", BASE, 0x4000,
    BASE + 0x1000, chunks, 2, imports, exports};

static int write_fixture(const char *path) {
    uint8_t pe[0x400] = {0};
    memcpy(pe, "MZ", 2); wr(pe + 0x3c, 4, 0x80);
    memcpy(pe + 0x80, "PE\0\0", 4);
    wr(pe + 0x84, 2, 0x14c); wr(pe + 0x86, 2, 2);
    wr(pe + 0x94, 2, 0xe0); wr(pe + 0x96, 2, 0x2102);
    uint8_t *optional = pe + 0x98;
    wr(optional, 2, 0x10b); wr(optional + 16, 4, 0x1000);
    wr(optional + 28, 4, BASE); wr(optional + 32, 4, 0x1000);
    wr(optional + 36, 4, 0x200); wr(optional + 56, 4, 0x4000);
    wr(optional + 60, 4, 0x200); wr(optional + 68, 2, 3);
    wr(optional + 92, 4, 16);
    uint8_t *section = pe + 0x178;
    memcpy(section, ".text", 5); wr(section + 8, 4, 0x1000);
    wr(section + 12, 4, 0x1000); wr(section + 16, 4, 0x100);
    wr(section + 20, 4, 0x200); wr(section + 36, 4, 0x60000020);
    section += 40;
    memcpy(section, ".data", 5); wr(section + 8, 4, 0x1000);
    wr(section + 12, 4, 0x2000); wr(section + 16, 4, 0x100);
    wr(section + 20, 4, 0x300); wr(section + 36, 4, 0xc0000040);
    memset(pe + 0x200, 0x90, 0x100); memset(pe + 0x300, 0x5a, 0x100);
    FILE *stream = fopen(path, "wb"); if (!stream) return 0;
    int ok = fwrite(pe, 1, sizeof pe, stream) == sizeof pe;
    return fclose(stream) == 0 && ok;
}

static uint32_t call(const char *name, int n, const uint32_t *args) {
    uint32_t fn = shim_lookup("kernel32.dll", name);
    if (!fn) guest_fatal("missing lifecycle thunk %s", name);
    return guest_call(fn, n, args);
}
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "module lifecycle check failed at line %d\n", __LINE__); return 1; } } while (0)

int main(int argc, char **argv) {
    if (argc < 2 || !write_fixture(argv[1])) return 2;
    guest_init(); shims_register(kernel32_thunks);
    module_register_available(&fixture, argv[1]);
    uint32_t name = guest_strdup("lifecycle.dll"), symbol = guest_strdup("fixture_export");
    uint32_t a[2] = {name, 0};
    // A bad PE must not commit/modify guest memory or mark a module loaded.
    FILE *corrupt = fopen(argv[1], "rb+");
    CHECK(corrupt && fputc('X', corrupt) != EOF && fclose(corrupt) == 0);
    CHECK(call("LoadLibraryA", 1, a) == 0);
    CHECK(!module_loaded_at(BASE) && !guest_committed(BASE + 0x2000));
    CHECK(write_fixture(argv[1]));
    corrupt = fopen(argv[1], "rb+");
    CHECK(corrupt && fseek(corrupt, 0x178 + 12, SEEK_SET) == 0);
    uint8_t bad_va[4] = {0, 0x3f, 0, 0};
    CHECK(fwrite(bad_va, 1, 4, corrupt) == 4 && fclose(corrupt) == 0);
    CHECK(call("LoadLibraryA", 1, a) == 0);
    CHECK(!module_loaded_at(BASE) && !guest_committed(BASE + 0x2000));
    CHECK(write_fixture(argv[1]));
    CHECK(call("LoadLibraryA", 1, a) == BASE);
    CHECK(attaches == 1 && !detaches && !attach_bss && !bad_arguments);
    CHECK(mem32(BASE + 0x2000) == 0x5a5a5a5a && mem32(BASE + 0x3500) == 0);
    if (argc > 2 && !strcmp(argv[2], "stale-call")) {
        a[0] = BASE; CHECK(call("FreeLibrary", 1, a));
        guest_call(BASE + 0x1100, 0, NULL);
        fprintf(stderr, "unloaded chunk still dispatched\n"); return 3;
    }
    CHECK(call("LoadLibraryA", 1, a) == BASE && attaches == 1);
    CHECK(call("GetModuleHandleA", 1, a) == BASE); /* must not retain */
    a[0] = BASE; a[1] = symbol;
    CHECK(call("GetProcAddress", 2, a) == BASE + 0x1100);
    CHECK(guest_call(BASE + 0x1100, 0, NULL) == 0x12345678);
    wr(G(BSS), 4, 0xdeadbeef); wr(G(BASE + 0x3500), 4, 0x11223344);
    CHECK(call("FreeLibrary", 1, a));
    CHECK(module_loaded_at(BASE) == &fixture && !detaches);
    CHECK(call("FreeLibrary", 1, a));
    CHECK(detaches == 1 && detach_bss == 0xdeadbeef && !bad_arguments);
    CHECK(!module_loaded_at(BASE) && !module_by_name("lifecycle.dll"));
    CHECK(!call("GetProcAddress", 2, a));
    CHECK(!call("FreeLibrary", 1, a));
    a[0] = name; CHECK(!call("GetModuleHandleA", 1, a));
    for (unsigned i = 0; i < 25; i++) {
        a[0] = name; CHECK(call("LoadLibraryA", 1, a) == BASE);
        CHECK(attaches == i + 2 && attach_bss == 0 && mem32(BASE + 0x3500) == 0);
        CHECK(mem32(BASE + 0x2000) == 0x5a5a5a5a);
        CHECK(guest_call(BASE + 0x1100, 0, NULL) == 0x12345678);
        wr(G(BSS), 4, i + 1); wr(G(BASE + 0x3500), 4, i + 1);
        a[0] = BASE; CHECK(call("FreeLibrary", 1, a));
        CHECK(detaches == i + 2 && detach_bss == i + 1 && !module_loaded_at(BASE));
    }
    CHECK(!bad_arguments);
    puts("DLL reference counts, attach/detach, export removal and BSS reload passed");
    return 0;
}
