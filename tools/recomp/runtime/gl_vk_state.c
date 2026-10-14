#include "gl_vk_state.h"
#include <string.h>
#include <math.h>

static void identity(float m[16]) {
    memset(m,0,sizeof(float)*16);
    for(unsigned i=0;i<4;i++)m[5*i]=1.0f;
}
static void matrix_mul(float out[16],const float a[16],const float b[16]) {
    float temp[16];
    for(unsigned column=0;column<4;column++)
        for(unsigned row=0;row<4;row++){
            float value=0;
            for(unsigned k=0;k<4;k++)
                value+=a[4*k+row]*b[4*column+k];
            temp[4*column+row]=value;
        }
    memcpy(out,temp,sizeof(temp));
}
static int compare_is_valid(uint32_t f) {
    return f>=GLVK_NEVER&&f<=GLVK_ALWAYS;
}
static int stencil_op_is_valid(uint32_t f) {
    return f==GLVK_ZERO||f==GLVK_KEEP||f==GLVK_REPLACE||
        f==GLVK_INCR||f==GLVK_DECR||f==GLVK_INVERT||
        f==GLVK_INCR_WRAP||f==GLVK_DECR_WRAP;
}
static int blend_is_valid(uint32_t f,int dst) {
    if(f==GLVK_ZERO||f==GLVK_ONE||f==GLVK_SRC_ALPHA||
       f==GLVK_ONE_MINUS_SRC_ALPHA||f==GLVK_DST_ALPHA||
       f==GLVK_ONE_MINUS_DST_ALPHA||f==GLVK_DST_COLOR||
       f==GLVK_ONE_MINUS_DST_COLOR)return 1;
    if(!dst&&(f==GLVK_SRC_COLOR||f==GLVK_ONE_MINUS_SRC_COLOR||
              f==GLVK_SRC_ALPHA_SATURATE))return 1;
    if(dst&&(f==GLVK_SRC_COLOR||f==GLVK_ONE_MINUS_SRC_COLOR))return 1;
    return 0;
}
static int invalid(gl_vk_state *s,uint32_t flag) {
    s->unsupported_flags|=flag;
    s->unsupported_calls++;
    return 0;
}
static gl_vk_matrix *current_matrix(gl_vk_state *s) {
    if(s->matrix_mode==GLVK_MODELVIEW)return &s->modelview;
    if(s->matrix_mode==GLVK_PROJECTION)return &s->projection;
    if(s->matrix_mode==GLVK_TEXTURE&&s->active_texture<GLVK_MAX_TEXTURE_UNITS)
        return &s->texture[s->active_texture].texture_matrix;
    return NULL;
}
void gl_vk_state_reset(gl_vk_state *s) {
    if(!s)return;
    memset(s,0,sizeof(*s));
    s->write_depth=1;
    s->depth_func=GLVK_LESS;
    s->blend_src=GLVK_ONE;
    s->blend_dst=GLVK_ZERO;
    s->stencil_func=GLVK_ALWAYS;
    s->stencil_compare_mask=UINT32_MAX;
    s->stencil_write_mask=UINT32_MAX;
    s->stencil_fail=GLVK_KEEP;
    s->stencil_zfail=GLVK_KEEP;
    s->stencil_zpass=GLVK_KEEP;
    s->cull_face=GLVK_BACK;
    s->front_face=GLVK_CCW;
    s->alpha_func=GLVK_ALWAYS;
    s->matrix_mode=GLVK_MODELVIEW;
    identity(s->modelview.current);
    identity(s->projection.current);
    for(unsigned i=0;i<GLVK_MAX_TEXTURE_UNITS;i++)
        identity(s->texture[i].texture_matrix.current);
}
static int apply_cap(gl_vk_state *s,uint32_t cap,uint8_t enabled) {
    switch(cap) {
        case GLVK_DEPTH_TEST:s->enabled_depth=enabled;return 1;
        case GLVK_BLEND:s->enabled_blend=enabled;return 1;
        case GLVK_STENCIL_TEST:s->enabled_stencil=enabled;return 1;
        case GLVK_CULL_FACE:s->enabled_cull=enabled;return 1;
        case GLVK_ALPHA_TEST:s->enabled_alpha=enabled;return 1;
        case GLVK_SCISSOR_TEST:s->enabled_scissor=enabled;return 1;
        case GLVK_TEXTURE_2D:
            if(s->active_texture>=GLVK_MAX_TEXTURE_UNITS)
                return invalid(s,GLVK_UNSUPPORTED_TEXTURE);
            s->texture[s->active_texture].enabled_2d=enabled;
            return 1;
        default:return invalid(s,GLVK_UNSUPPORTED_CAP);
    }
}
static int use_matrix(gl_vk_state *s,const float *incoming,int multiply) {
    gl_vk_matrix *m=current_matrix(s);
    if(!incoming)return invalid(s,GLVK_UNSUPPORTED_PTR);
    if(!m)return invalid(s,GLVK_UNSUPPORTED_MATRIX);
    float input[16];
    /* Guest pointers can be unaligned; memcpy avoids undefined behaviour. */
    memcpy(input,incoming,sizeof(input));
    for(int i=0;i<16;i++)if(!isfinite(input[i]))
        return invalid(s,GLVK_UNSUPPORTED_MATRIX);
    if(multiply)matrix_mul(m->current,m->current,input);
    else memcpy(m->current,input,sizeof(input));
    return 1;
}
int gl_vk_state_apply(gl_vk_state *s,gl_vk_opcode op,
                      uint32_t a,uint32_t b,uint32_t c,const void *pointer) {
    if(!s)return 0;
    int result=1;
    switch(op){
        case GLVK_OP_ENABLE:result=apply_cap(s,a,1);break;
        case GLVK_OP_DISABLE:result=apply_cap(s,a,0);break;
        case GLVK_OP_DEPTH_FUNC:
            if(!compare_is_valid(a))result=invalid(s,GLVK_UNSUPPORTED_ENUM);
            else s->depth_func=a;
            break;
        case GLVK_OP_DEPTH_MASK:s->write_depth=(uint8_t)(a!=0);break;
        case GLVK_OP_BLEND_FUNC:
            if(!blend_is_valid(a,0)||!blend_is_valid(b,1))
                result=invalid(s,GLVK_UNSUPPORTED_ENUM);
            else {s->blend_src=a;s->blend_dst=b;}
            break;
        case GLVK_OP_STENCIL_FUNC:
            if(!compare_is_valid(a))result=invalid(s,GLVK_UNSUPPORTED_ENUM);
            else {
                s->stencil_func=a;s->stencil_ref=b;
                s->stencil_compare_mask=c;
            }
            break;
        case GLVK_OP_STENCIL_OP:
            if(!stencil_op_is_valid(a)||!stencil_op_is_valid(b)||
               !stencil_op_is_valid(c))
                result=invalid(s,GLVK_UNSUPPORTED_ENUM);
            else {s->stencil_fail=a;s->stencil_zfail=b;s->stencil_zpass=c;}
            break;
        case GLVK_OP_STENCIL_MASK:s->stencil_write_mask=a;break;
        case GLVK_OP_CULL_FACE:
            if(a!=GLVK_FRONT&&a!=GLVK_BACK&&a!=GLVK_FRONT_AND_BACK)
                result=invalid(s,GLVK_UNSUPPORTED_ENUM);
            else s->cull_face=a;
            break;
        case GLVK_OP_FRONT_FACE:
            if(a!=GLVK_CW&&a!=GLVK_CCW)
                result=invalid(s,GLVK_UNSUPPORTED_ENUM);
            else s->front_face=a;
            break;
        case GLVK_OP_ALPHA_FUNC:{
            float value;
            if(pointer)memcpy(&value,pointer,sizeof(value));
            else memcpy(&value,&b,sizeof(value)); /* ABI float bits from guest */
            if(!compare_is_valid(a)||!isfinite(value))
                result=invalid(s,GLVK_UNSUPPORTED_ENUM);
            else {
                s->alpha_func=a;
                /* OpenGL alpha reference is clamped to [0,1]. */
                s->alpha_ref=value<0.f?0.f:(value>1.f?1.f:value);
            }
            break;
        }
        case GLVK_OP_ACTIVE_TEXTURE:
            if(a<GLVK_TEXTURE0||a>=GLVK_TEXTURE0+GLVK_MAX_TEXTURE_UNITS)
                result=invalid(s,GLVK_UNSUPPORTED_TEXTURE);
            else s->active_texture=a-GLVK_TEXTURE0;
            break;
        case GLVK_OP_BIND_TEXTURE:
            if(a!=GLVK_TEXTURE_2D||s->active_texture>=GLVK_MAX_TEXTURE_UNITS)
                result=invalid(s,GLVK_UNSUPPORTED_TEXTURE);
            else s->texture[s->active_texture].bound_2d=b;
            break;
        case GLVK_OP_MATRIX_MODE:
            if(a!=GLVK_MODELVIEW&&a!=GLVK_PROJECTION&&a!=GLVK_TEXTURE)
                result=invalid(s,GLVK_UNSUPPORTED_MATRIX);
            else s->matrix_mode=a;
            break;
        case GLVK_OP_LOAD_IDENTITY: {
            gl_vk_matrix *m=current_matrix(s);
            if(!m)result=invalid(s,GLVK_UNSUPPORTED_MATRIX);
            else identity(m->current);
            break;
        }
        case GLVK_OP_LOAD_MATRIX_F:case GLVK_OP_MULT_MATRIX_F:
            result=use_matrix(s,(const float *)pointer,
                              op==GLVK_OP_MULT_MATRIX_F);
            break;
        case GLVK_OP_LOAD_MATRIX_D:case GLVK_OP_MULT_MATRIX_D:{
            if(!pointer){result=invalid(s,GLVK_UNSUPPORTED_PTR);break;}
            const double *src=(const double *)pointer;
            float conv[16];
            for(int i=0;i<16;i++){
                double value;
                memcpy(&value,(const uint8_t *)src+sizeof(double)*(size_t)i,sizeof(value));
                conv[i]=(float)value;
            }
            result=use_matrix(s,conv,op==GLVK_OP_MULT_MATRIX_D);
            break;
        }
        case GLVK_OP_PUSH_MATRIX: {
            gl_vk_matrix *m=current_matrix(s);
            if(!m||m->stack_len==GLVK_MAX_MATRIX_STACK) {
                result=invalid(s,GLVK_UNSUPPORTED_MATRIX);
            }else {
                memcpy(m->stack[m->stack_len++],m->current,sizeof(m->current));
                s->matrix_pushes++;
            }
            break;
        }
        case GLVK_OP_POP_MATRIX:{
            gl_vk_matrix *m=current_matrix(s);
            if(!m||!m->stack_len)result=invalid(s,GLVK_UNSUPPORTED_MATRIX);
            else {
                memcpy(m->current,m->stack[--m->stack_len],sizeof(m->current));
                s->matrix_pops++;
            }
            break;
        }
        case GLVK_OP_UNSUPPORTED_STATE:
            if(a<GLVK_LEGACY_CATEGORY_COUNT)s->legacy_categories[a]++;
            result=invalid(s,GLVK_UNSUPPORTED_LEGACY);break;
        default:result=invalid(s,GLVK_UNSUPPORTED_ENUM);break;
    }
    if(result)s->supported_calls++;
    return result;
}
int gl_vk_state_pipeline_ready(const gl_vk_state *s) {
    if(!s||s->unsupported_flags)return 0;
    /* Fixed-function alpha test needs shader-side discard, which is not
     * implemented in the WSA prototype. Multiple texture combiners are not
     * translated either, even if their state can be observed. */
    if(s->enabled_alpha||s->enabled_scissor)return 0;
    unsigned textured=0;
    for(unsigned i=0;i<GLVK_MAX_TEXTURE_UNITS;i++)
        textured+=s->texture[i].enabled_2d?1u:0u;
    return textured<=1;
}
uint32_t gl_vk_state_matrix_digest(const gl_vk_state *s) {
    if(!s)return 0;
    /* An FNV1a fingerprint for diagnostics only; not used for correctness. */
    uint32_t hash=2166136261u;
    const float *matrices[]={s->modelview.current,s->projection.current};
    for(size_t j=0;j<2;j++){
        const uint8_t *data=(const uint8_t *)matrices[j];
        for(size_t i=0;i<sizeof(float)*16;i++){
            hash^=data[i];
            hash*=16777619u;
        }
    }
    return hash;
}
