#include "compass_markers.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>

static int near(float a, float b) { return fabsf(a-b) < 0.00015f; }
int main(void) {
    const float f = compass_marker_factor(1280, 576, 1);
    assert(near(f, 0.6f));
    assert(near(compass_marker_center_x(f, 1.0f), 55.0f));
    assert(compass_marker_factor(640, 480, 1) == 0.0f);
    assert(compass_marker_factor(1280, 576, 0) == 0.0f);
    assert(compass_marker_factor(0, 576, 1) == 0.0f);
    assert(compass_marker_factor(1920, 1080, 1) > 0.74f);
    compass_marker_rect left={55.0f-43.75f-5.0f,420.0f,10.0f,10.0f};
    compass_marker_rect right={55.0f+43.75f-5.0f,420.0f,10.0f,10.0f};
    assert(compass_marker_project(&left,f,1.0f));
    assert(compass_marker_project(&right,f,1.0f));
    // Rim is 43.75 units from center, minus 5-unit half sprite and
    // 1.5-unit safety margin so green icons never protrude outside.
    assert(near(left.x+left.width*.5f,55.0f-37.25f*f));
    assert(near(right.x+right.width*.5f,55.0f+37.25f*f));
    assert(near(left.width,6.0f));
    assert(near(left.y,420.0f));
    assert(near(left.height,10.0f));
    // Marker rotation should not change the *radial* placement; only X.
    compass_marker_rect top={55.0f-5.0f,425.0f-43.75f-5.0f,10,10};
    assert(compass_marker_project(&top,f,1.0f));
    assert(near(top.x+top.width*.5f,55.0f));
    assert(near(top.y + top.height*.5f,425.0f-37.25f));
    assert(hypotf((top.x + top.width*.5f-55.0f)/f,
                  top.y + top.height*.5f - 425.0f) <= 37.251f);
    // Markers inside the ring must not be moved radially, only X aspect.
    compass_marker_rect inner={55.0f+10.0f-5.0f,425.0f+14.0f-5.0f,10,10};
    assert(compass_marker_project(&inner,f,1.0f));
    assert(near(inner.y,425.0f+14.0f-5.0f));
    assert(near(inner.x+inner.width*.5f,55.0f+10.0f*f));
    // Big objective icon gets the smaller permitted ring for its dimensions.
    compass_marker_rect objective={55.0f+43.75f-16.0f,425.0f-16.0f,32,32};
    assert(compass_marker_project(&objective,f,1.0f));
    assert(near(objective.x+objective.width*.5f,55.0f+26.25f*f));
    assert(near(objective.y,425.0f-16.0f));
    // Center and zoom options preserve valid positioning.
    compass_marker_rect zoom={45,410,16,16};
    assert(compass_marker_project(&zoom,f,1.2f));
    assert(near(zoom.width,9.6f));
    assert(near(compass_marker_center_x(f,1.2f),64.6f));
    compass_marker_rect zero={45,410,16,16};
    assert(!compass_marker_project(&zero,0,1.0f));
    assert(near(zero.x,45.0f));
    zero.width = NAN;
    assert(!compass_marker_project(&zero,f,1.0f));
    compass_marker_rect bad={45,410,10,10};
    assert(!compass_marker_project(&bad,f,INFINITY));
    // Both X and Y of a 4:3 screen remain untouched because the hook is off.
    puts("compass marker aspect and guard smoke: PASS");
    return 0;
}
