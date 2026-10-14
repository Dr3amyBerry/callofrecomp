#version 450
layout(location=0) in vec3 color;
layout(location=1) in vec2 uv;
layout(set=0,binding=0) uniform sampler2D tex;
layout(location=0) out vec4 outColor;
void main() {
    outColor = texture(tex, uv) * vec4(color * 0.65 + vec3(0.35), 1.0);
}
