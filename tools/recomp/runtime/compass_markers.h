// Host-side layout math for the *already patched* 640x480 CoD 1.5 HUD.
// Do not alter the 3D projection or the original game's UI assets.
#ifndef CODRECOMP_COMPASS_MARKERS_H
#define CODRECOMP_COMPASS_MARKERS_H
#include <math.h>

typedef struct {
    float x, y, width, height;
} compass_marker_rect;

// x scale of the real screen versus a 4:3 virtual layout. 0 disables hook.
static inline float compass_marker_factor(int width, int height, int overlay_ready) {
    if (!overlay_ready || width <= 0 || height <= 0) return 0.0f;
    double ratio = (4.0 / 3.0) * (double)height / (double)width;
    return ratio > 0.2 && ratio < 0.9999 ? (float)ratio : 0.0f;
}

// Original hud.menu has Compass at (-25,345) with 160x160 size. The
// optional generated overlay narrows X, preserving the original center.
static inline float compass_marker_center_x(float factor, float hud_size) {
    const float left = -25.0f + (160.0f - 160.0f * factor) * 0.5f;
    return left + 80.0f * factor * hud_size;
}

// Narrow sprite X so it has the same physical scale as Y, then clamp only
// the *outer rim* of the marker's center. The original compass pointers have
// a 43.75 virtual-unit radius, so without accounting for their own half-size
// the icons straddle the circular ring. Inner markers retain their precise
// relative distances; rim markers move inward just enough to fit their full
// texture while preserving direction. No 3D/world-space positions change.
// Caller must identify the original 1.5 guest draw callsite exactly.
static inline int compass_marker_project(compass_marker_rect *r,
                                          float factor, float hud_size) {
    if (!r || !(factor > 0.2f && factor < 0.9999f) ||
        !isfinite(hud_size) || hud_size < 0.25f || hud_size > 2.5f ||
        !isfinite(r->x) || !isfinite(r->y) ||
        !isfinite(r->width) || !isfinite(r->height) ||
        !(r->width > 0.1f && r->width < 128.0f) ||
        !(r->height > 0.1f && r->height < 128.0f))
        return 0;
    const float cx = compass_marker_center_x(factor, hud_size);
    // The original 1.5 pointer callbacks vertically center their geometry
    // and shift it upward by (zoom-1)*160.
    const float cy = 345.0f + 80.0f * hud_size -
                     (hud_size - 1.0f) * 160.0f;
    float dx = r->x + 0.5f * r->width - cx;
    float dy = r->y + 0.5f * r->height - cy;
    const float radius = hypotf(dx, dy);
    const float inner_radius = 43.75f * hud_size -
                               0.5f * r->height - 1.5f;
    if (!(inner_radius > 1.0f)) return 0;
    if (radius > inner_radius) {
        const float bounded = inner_radius / radius;
        dx *= bounded;
        dy *= bounded;
    }
    const float new_w = r->width * factor;
    const float new_x = cx + dx * factor - 0.5f * new_w;
    const float new_y = cy + dy - 0.5f * r->height;
    if (!isfinite(new_x) || !isfinite(new_y) || !isfinite(new_w))
        return 0;
    r->x = new_x;
    r->y = new_y;
    r->width = new_w;
    return 1;
}

// The objective-star drawpath goes straight to syscall 0x4b with physical
// pixel dimensions. Convert back to the game's virtual 640x480 HUD units
// BEFORE applying the same center/radius/aspect correction used for allies.
// Returning to pixels after correction avoids double-scaling and restores
// a circular star medallion (w / h consistent with the physical aspect).
static inline int compass_marker_project_pixels(compass_marker_rect *r,
                                                float factor, float hud_size,
                                                float x_scale, float y_scale) {
    if (!r || !isfinite(x_scale) || !isfinite(y_scale) ||
        x_scale < 0.1f || x_scale > 20.0f ||
        y_scale < 0.1f || y_scale > 20.0f)
        return 0;
    compass_marker_rect virtual_rect = {
        r->x / x_scale, r->y / y_scale,
        r->width / x_scale, r->height / y_scale
    };
    if (!compass_marker_project(&virtual_rect, factor, hud_size)) return 0;
    const compass_marker_rect corrected = {
        virtual_rect.x * x_scale,
        virtual_rect.y * y_scale,
        virtual_rect.width * x_scale,
        virtual_rect.height * y_scale
    };
    if (!isfinite(corrected.x) || !isfinite(corrected.y) ||
        !isfinite(corrected.width) || !isfinite(corrected.height))
        return 0;
    *r = corrected;
    return 1;
}
#endif
