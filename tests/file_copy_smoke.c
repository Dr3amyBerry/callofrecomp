#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "file_copy.h"

int main(void) {
    FILE *src = tmpfile(), *dst = tmpfile();
    if (!src || !dst) return 1;
    unsigned char expected[16387], got[16387];
    for (int i = 0; i < (int)sizeof expected; ++i)
        expected[i] = (unsigned char)((i * 53u + 79u) & 255u);
    if (fwrite(expected, 1, sizeof expected, src) != sizeof expected) return 2;
    if (fseek(src, 0, SEEK_SET)) return 3;
    if (!file_copy_stream(src, dst)) return 4;
    if (fflush(dst) || fseek(dst, 0, SEEK_SET)) return 5;
    if (fread(got, 1, sizeof got, dst) != sizeof got) return 6;
    if (memcmp(expected, got, sizeof expected)) return 7;
    if (fgetc(dst) != EOF) return 8;
    fclose(src); fclose(dst);
    src = tmpfile(); dst = tmpfile();
    if (!src || !dst || !file_copy_stream(src, dst)) return 9;
    if (fseek(dst, 0, SEEK_END) || ftell(dst) != 0) return 10;
    if (file_copy_stream(NULL, dst) || file_copy_stream(src, NULL)) return 11;
    fclose(src); fclose(dst);
    puts("buffered file copy passed");
    return 0;
}
