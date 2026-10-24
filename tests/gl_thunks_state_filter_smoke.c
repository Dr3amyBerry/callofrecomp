// End-to-end check of the GENERATED gl_thunks.c: the same source is built with
// and without CODRECOMP_GL_STATE_FILTER against counting fake GL entry points.
// Synthetic guest stack only; no game data and no real GL.
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include "gl_lookup.h"
#include "gl_thunks.c"

uint8_t *MEM;
uint8_t R[4096], U[4096];
uint32_t PC;
int recomp_miss;
void guest_fatal(const char *fmt, ...) { (void)fmt; fputs("guest_fatal\n", stderr); exit(99); }
void gl_missing(const char *name) { fprintf(stderr, "missing %s\n", name); exit(98); }
uint32_t gl_guest_string(unsigned int name, const void *host) { (void)name; (void)host; return 0; }

static int calls[8];
enum { C_ENABLE, C_DISABLE, C_BIND, C_ACTIVE, C_DELETE, C_BEGIN, C_END, C_DEPTHMASK };
static void f_enable(int a) { (void)a; calls[C_ENABLE]++; }
static void f_disable(int a) { (void)a; calls[C_DISABLE]++; }
static void f_bind(int a, int b) { (void)a; (void)b; calls[C_BIND]++; }
static void f_active(int a) { (void)a; calls[C_ACTIVE]++; }
static void f_delete(int n, const unsigned *p) { (void)n; (void)p; calls[C_DELETE]++; }
static void f_begin(int m) { (void)m; calls[C_BEGIN]++; }
static void f_end(void) { calls[C_END]++; }
static void f_depthmask(int m) { (void)m; calls[C_DEPTHMASK]++; }

static void *getproc(const char *n) {
    if (!strcmp(n, "glEnable")) return (void *)f_enable;
    if (!strcmp(n, "glDisable")) return (void *)f_disable;
    if (!strcmp(n, "glBindTexture")) return (void *)f_bind;
    if (!strcmp(n, "glActiveTextureARB")) return (void *)f_active;
    if (!strcmp(n, "glDeleteTextures")) return (void *)f_delete;
    if (!strcmp(n, "glBegin")) return (void *)f_begin;
    if (!strcmp(n, "glEnd")) return (void *)f_end;
    if (!strcmp(n, "glDepthMask")) return (void *)f_depthmask;
    return NULL;
}

static size_t count;
static void call(const char *name, uint32_t a0, uint32_t a1) {
    const thunk_def *d = gl_find_sorted_thunk(gl_thunks, count, name);
    if (!d) { fprintf(stderr, "no thunk %s\n", name); exit(97); }
    const uint32_t esp = 0x1000;
    memcpy(G(esp + 4), &a0, 4);
    memcpy(G(esp + 8), &a1, 4);
    d->fn(esp);
}

#define CHECK(cond) do { if (!(cond)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #cond); return 1; } } while (0)

int main(void) {
    MEM = calloc(1, 0x4000);
    CHECK(MEM);
    while (gl_thunks[count].name) count++;
#ifdef CODRECOMP_GL_STATE_FILTER
    const int filtered = 1;
#else
    const int filtered = 0;
#endif
    gl_load(getproc);

    call("glEnable", 0x0BE2, 0);
    call("glEnable", 0x0BE2, 0);
    call("glEnable", 0x0BE2, 0);
    CHECK(calls[C_ENABLE] == (filtered ? 1 : 3));
    call("glDisable", 0x0BE2, 0);
    CHECK(calls[C_DISABLE] == 1);
    call("glEnable", 0x0BE2, 0);
    CHECK(calls[C_ENABLE] == (filtered ? 2 : 4));

    call("glActiveTextureARB", 0x84C0, 0);
    call("glActiveTextureARB", 0x84C0, 0);
    CHECK(calls[C_ACTIVE] == (filtered ? 1 : 2));
    call("glBindTexture", 0x0DE1, 5);
    call("glBindTexture", 0x0DE1, 5);
    CHECK(calls[C_BIND] == (filtered ? 1 : 2));
    call("glDeleteTextures", 1, 0);
    CHECK(calls[C_DELETE] == 1);                       // events are always forwarded
    call("glBindTexture", 0x0DE1, 5);
    CHECK(calls[C_BIND] == (filtered ? 2 : 3));        // invalidated by the delete

    call("glDepthMask", 0xFFFFFF01u, 0);
    call("glDepthMask", 1, 0);
    CHECK(calls[C_DEPTHMASK] == (filtered ? 1 : 2));

    call("glBegin", 7, 0);
    call("glEnable", 0x0BE2, 0);
    call("glEnable", 0x0BE2, 0);
    call("glEnd", 0, 0);
    CHECK(calls[C_BEGIN] == 1 && calls[C_END] == 1);
    CHECK(calls[C_ENABLE] == (filtered ? 4 : 6));      // both forwarded inside Begin/End

    // Context re-creation resets the filter.
    call("glEnable", 0x0BE2, 0);
    gl_load(getproc);
    const int before = calls[C_ENABLE];
    call("glEnable", 0x0BE2, 0);
    CHECK(calls[C_ENABLE] == before + 1);

    printf("gl_thunks state filter %s: OK\n", filtered ? "ON" : "OFF");
    return 0;
}
