// Bound the I/O and CPU overhead when copying an immutable install file into
// the writable overlay on first open. Works for binary data and empty files.
#pragma once
#include <stdio.h>
#include <stdint.h>

static inline int file_copy_stream(FILE *input, FILE *output) {
    if (!input || !output) return 0;
    unsigned char block[16 * 1024];
    size_t length;
    while ((length = fread(block, 1, sizeof block, input)) != 0) {
        if (fwrite(block, 1, length, output) != length) return 0;
    }
    return !ferror(input) && fflush(output) == 0;
}
