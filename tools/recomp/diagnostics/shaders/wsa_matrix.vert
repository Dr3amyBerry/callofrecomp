#version 450
// OpenGL's modelview*projection data is column-major, like GLSL mat4.
// Explicitly convert OpenGL's clip-space conventions to Vulkan's:
 // invert Y for the positive-height Android viewport, and shift z from
 // [-w,+w] to [0,+w] without changing the perspective divide.
layout(location=0) in vec2 inPosition;
layout(location=1) in vec3 inColor;
layout(location=2) in vec2 inUV;
layout(push_constant) uniform Camera { mat4 glProjectionModelview; } camera;
layout(location=0) out vec3 color;
layout(location=1) out vec2 uv;
void main() {
    vec4 clip = camera.glProjectionModelview * vec4(inPosition,0.0,1.0);
    clip.y = -clip.y;
    clip.z = (clip.z + clip.w) * 0.5;
    gl_Position = clip;
    color = inColor;
    uv = inUV;
}
