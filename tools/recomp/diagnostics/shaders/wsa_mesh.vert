#version 450
layout(location=0) in vec2 inPosition;
layout(location=1) in vec3 inColor;
layout(location=2) in vec2 inUV;
layout(push_constant) uniform Camera { mat4 transform; } camera;
layout(location=0) out vec3 color;
layout(location=1) out vec2 uv;
void main() {
    gl_Position = camera.transform * vec4(inPosition, 0.0, 1.0);
    color = inColor;
    uv = inUV;
}
