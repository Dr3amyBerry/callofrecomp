// Shared, deterministic syscall trace used by native_host.c (32-bit, real DLL)
// and recomp_host.c (recompiled module) so that both runs can be diffed.
#pragma once
#include <stdint.h>
#include <stdio.h>

#define TRACE_ARGS 4

typedef struct { uint32_t args[13]; } trace_command;

// vmMain command sequence: {command, args...}. Semantics are not asserted here;
// both hosts simply replay the same calls.
static const trace_command trace_commands[] = {
    {{0}},
    {{1, 0, 0}},
    {{5, 100}},
    {{6}},
    {{2}},
};
static const int trace_command_count = sizeof trace_commands / sizeof trace_commands[0];

static void trace_vmmain_begin(int i) {
    printf("VMMAIN %u\n", trace_commands[i].args[0]);
    fflush(stdout);
}

static void trace_vmmain_end(uint32_t ret) {
    printf("RET %08x\n", ret);
    fflush(stdout);
}

// Logs printable NUL-terminated strings, raw values otherwise.
static uint32_t trace_syscall(int32_t id, const uint32_t *args, const char *(*str)(uint32_t)) {
    printf("SYS %d", id);
    for (int i = 0; i < TRACE_ARGS; i++) {
        const char *s = str(args[i]);
        int n = 0, ok = s != NULL;
        while (ok && n < 64 && s[n]) {
            if (s[n] < 0x20 || s[n] > 0x7e) ok = 0;
            n++;
        }
        if (ok && n >= 2 && n < 64) printf(" \"%s\"", s);
        else printf(" %08x", args[i]);
    }
    printf("\n");
    fflush(stdout);
    return 0;
}
