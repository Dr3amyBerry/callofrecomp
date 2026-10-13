#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "gl_lookup.h"

int main(void) {
    const thunk_def table[] = {
        {"opengl32.dll", "glActiveTexture", NULL, 4},
        {"opengl32.dll", "glBindBufferARB", NULL, 8},
        {"opengl32.dll", "glColorPointer", NULL, 16},
        {"opengl32.dll", "glDrawElements", NULL, 16},
        {"opengl32.dll", "glGetString", NULL, 4},
        {"opengl32.dll", "glVertexPointer", NULL, 16},
    };
    const size_t n = sizeof table / sizeof table[0];
    for (size_t i = 0; i < n; ++i) {
        const thunk_def *p = gl_find_sorted_thunk(table, n, table[i].name);
        if (p != &table[i]) return 1;
    }
    if (gl_find_sorted_thunk(table, n, "glA") ||
        gl_find_sorted_thunk(table, n, "glBind") ||
        gl_find_sorted_thunk(table, n, "glDrawElement") ||
        gl_find_sorted_thunk(table, n, "glZZZ") ||
        gl_find_sorted_thunk(table, 0, "glActiveTexture")) return 2;
    puts("sorted GL thunk lookup passed");
    return 0;
}
