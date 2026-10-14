#version 450
layout(location=0) in vec3 color;
layout(location=1) in vec2 uv;
layout(location=0) out vec4 outColor;
void main() {
    // Procedural checkerboard, deliberately no textures from Call of Duty.
    float checker = mod(floor(uv.x * 12.0) + floor(uv.y * 12.0), 2.0);
    outColor = vec4(color * mix(0.35, 1.0, checker), 1.0);
}
