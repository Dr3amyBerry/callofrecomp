#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "commit_runs.h"

static void check(int ok) { if (!ok) exit(1); }
int main(void) {
    uint8_t pages[16384] = {0};
    uint32_t cursor = 0, first, count;
    check(commit_next_run(pages, &cursor, 16384, &first, &count));
    check(first == 0 && count == 16384 && cursor == 16384);
    check(!commit_next_run(pages, &cursor, 16384, &first, &count));
    memset(pages, 1, sizeof pages);
    cursor = 0;
    check(!commit_next_run(pages, &cursor, 16384, &first, &count));
    pages[2] = pages[3] = pages[7] = pages[9] = 0;
    cursor = 1;
    check(commit_next_run(pages, &cursor, 9, &first, &count));
    check(first == 2 && count == 2 && cursor == 4);
    memset(pages + first, 1, count); // record successful OS commitment
    check(commit_next_run(pages, &cursor, 9, &first, &count));
    check(first == 7 && count == 1);
    memset(pages + first, 1, count);
    check(!commit_next_run(pages, &cursor, 9, &first, &count));
    check(pages[9] == 0); // exclusive end must not extend into the next region
    cursor = 1;
    check(!commit_next_run(pages, &cursor, 9, &first, &count));
    cursor = 9;
    check(!commit_next_run(pages, &cursor, 9, &first, &count));
    cursor = 8;
    check(commit_next_run(pages, &cursor, 10, &first, &count));
    check(first == 9 && count == 1 && cursor == 10);
    puts("contiguous commitment, holes and exclusive boundaries passed");
    return 0;
}
