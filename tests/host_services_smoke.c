#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "codrecomp/host_services.h"

typedef struct fixture_s {
    int calls;
    const void *last_buffer;
    int32_t last_exec_when;
} fixture_t;

static int32_t fake_open(void *context, const char *path,
                         cod_host_fs_handle_t *out, int32_t mode) {
    fixture_t *f = (fixture_t *)context;
    assert(strcmp(path, "maps/test.cfg") == 0);
    assert(mode == 7); /* Arbitrary host-side test mode, not a CoD enum. */
    ++f->calls;
    *out = 123;
    return 0;
}

static ptrdiff_t fake_read(void *context, void *buffer, size_t count,
                           cod_host_fs_handle_t handle) {
    fixture_t *f = (fixture_t *)context;
    assert(handle == 123 && count >= 2);
    f->last_buffer = buffer;
    ++f->calls;
    ((char *)buffer)[0] = 'O';
    ((char *)buffer)[1] = 'K';
    return 2;
}

static ptrdiff_t fake_write(void *context, const void *buffer, size_t count,
                            cod_host_fs_handle_t handle) {
    fixture_t *f = (fixture_t *)context;
    assert(handle == 123 && count == 2);
    assert(memcmp(buffer, "OK", 2) == 0);
    f->last_buffer = buffer;
    ++f->calls;
    return 2;
}

static void fake_close(void *context, cod_host_fs_handle_t handle) {
    fixture_t *f = (fixture_t *)context;
    assert(handle == 123);
    ++f->calls;
}

static int32_t fake_rename(void *context, const char *old_name,
                           const char *new_name) {
    fixture_t *f = (fixture_t *)context;
    assert(strcmp(old_name, "maps/a") == 0);
    assert(strcmp(new_name, "maps/b") == 0);
    ++f->calls;
    return 0;
}

static int32_t fake_getfilelist(void *context, const char *directory,
                                const char *extension, char *buffer,
                                size_t capacity) {
    fixture_t *f = (fixture_t *)context;
    assert(strcmp(directory, "main") == 0);
    assert(strcmp(extension, ".cfg") == 0);
    assert(capacity >= 1);
    buffer[0] = '\0'; /* Mock only: real list format is not yet implemented. */
    ++f->calls;
    return 0;
}

static void fake_exec(void *context, int32_t when, const char *text) {
    fixture_t *f = (fixture_t *)context;
    assert(strcmp(text, "echo test") == 0);
    f->last_exec_when = when;
    ++f->calls;
}

int main(void) {
    fixture_t f = {0};
    cod_host_services_t host = {
        .context = &f,
        .fs_open = fake_open,
        .fs_read = fake_read,
        .fs_write = fake_write,
        .fs_close = fake_close,
        .fs_rename = fake_rename,
        .fs_getfilelist = fake_getfilelist,
        .execute_console_text = fake_exec,
    };

    cod_host_fs_handle_t h = 0;
    char buffer[16] = {0};
    char list[8] = {0};
    assert(sizeof(cod_host_fs_handle_t) == 4);
    assert(sizeof(uintptr_t) >= sizeof(void *));
    assert(host.fs_open(host.context, "maps/test.cfg", &h, 7) == 0);
    assert(h == 123);
    assert(host.fs_read(host.context, buffer, sizeof(buffer), h) == 2);
    assert(host.fs_write(host.context, buffer, 2, h) == 2);
    assert(f.last_buffer == buffer); /* Host pointers were never truncated. */
    assert(host.fs_rename(host.context, "maps/a", "maps/b") == 0);
    assert(host.fs_getfilelist(host.context, "main", ".cfg", list, sizeof(list)) == 0);
    host.execute_console_text(host.context, 17, "echo test");
    assert(f.last_exec_when == 17);
    host.fs_close(host.context, h);
    assert(f.calls == 7);
    return 0;
}
