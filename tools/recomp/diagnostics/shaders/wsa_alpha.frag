#version 450
layout(location=0) in vec3 primaryColor;
layout(location=1) in vec2 uv;
layout(set=0,binding=0) uniform sampler2D tex;
/* Matches the vertex shader's 64-byte transform; the following four floats
 * are host-provided render state, NOT textures from Call of Duty. */
layout(push_constant) uniform Camera {
    mat4 transform;
    vec4 texEnvAlpha;
} settings;
layout(location=0) out vec4 outColor;
void main() {
    vec4 texel = texture(tex,uv);
    /* MODULATE (8448): primary * texel. REPLACE (7681): texel. */
    vec4 result = settings.texEnvAlpha.x < 0.5
        ? texel * vec4(primaryColor,1.0)
        : texel;
    if(settings.texEnvAlpha.w > 0.5) {
        float a=result.a;
        float ref=settings.texEnvAlpha.y;
        int func=int(settings.texEnvAlpha.z+0.5);
        bool pass;
        if(func==512)pass=false;             /* GL_NEVER */
        else if(func==513)pass=a<ref;        /* GL_LESS */
        else if(func==514)pass=a==ref;       /* GL_EQUAL */
        else if(func==515)pass=a<=ref;       /* GL_LEQUAL */
        else if(func==516)pass=a>ref;        /* GL_GREATER */
        else if(func==517)pass=a!=ref;       /* GL_NOTEQUAL */
        else if(func==518)pass=a>=ref;       /* GL_GEQUAL */
        else pass=true;                     /* GL_ALWAYS after validation */
        if(!pass)discard;
    }
    outColor=result;
}
