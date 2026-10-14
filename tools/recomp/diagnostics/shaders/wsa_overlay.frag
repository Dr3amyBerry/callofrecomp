#version 450
layout(location=0) in vec3 ignoredColor;
layout(location=1) in vec2 ignoredUV;
layout(location=0) out vec4 outColor;
void main() {
    // Translucent amber overlay, drawn only where stencil == 2.
    // It intentionally uses a different fragment pipeline from the opaque
    // textured quad, exercising SRC_ALPHA / ONE_MINUS_SRC_ALPHA blending.
    outColor = vec4(1.0, 0.23, 0.08, 0.47);
}
