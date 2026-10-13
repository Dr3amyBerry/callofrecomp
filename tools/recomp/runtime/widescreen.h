#ifndef CODRECOMP_WIDESCREEN_H
#define CODRECOMP_WIDESCREEN_H
#include <math.h>

typedef struct { int width, height; double aspect, fov; } widescreen_config;

/* Preserve the vertical view of the original 80-degree 4:3 camera. Wider
 * displays gain horizontal view instead of stretching or cropping the world. */
static inline widescreen_config widescreen_for_display(int width, int height) {
    if (width <= 0 || height <= 0) { width = 1280; height = 720; }
    widescreen_config config = {width, height, (double)width / height, 80};
    const double radians = 3.14159265358979323846 / 180.0;
    config.fov = 2 * atan(tan(40 * radians) * config.aspect / (4.0 / 3.0)) / radians;
    if (config.fov < 1) config.fov = 1;
    if (config.fov > 160) config.fov = 160;
    return config;
}
#endif
