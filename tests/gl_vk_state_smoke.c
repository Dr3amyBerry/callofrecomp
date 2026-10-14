#include "gl_vk_state.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void op(gl_vk_state *s,gl_vk_opcode code,uint32_t a,uint32_t b,uint32_t c,
               const void *ptr) {
    assert(gl_vk_state_apply(s,code,a,b,c,ptr));
}
static int near(float a,float b) {return fabsf(a-b)<0.0001f;}
static void assert_identity(const float m[16]){
    for(int i=0;i<16;i++)assert(near(m[i],i%5==0?1.0f:0.0f));
}
static void test_defaults_and_depth_stencil_blend(void) {
    gl_vk_state s;
    gl_vk_state_reset(&s);
    assert(!s.enabled_depth&&!s.enabled_blend&&!s.enabled_stencil);
    assert(s.write_depth&&s.depth_func==GLVK_LESS);
    assert(s.blend_src==GLVK_ONE&&s.blend_dst==GLVK_ZERO);
    assert(s.cull_face==GLVK_BACK&&s.front_face==GLVK_CCW);
    assert_identity(s.modelview.current);
    assert_identity(s.projection.current);
    assert(gl_vk_state_pipeline_ready(&s));
    op(&s,GLVK_OP_ENABLE,GLVK_DEPTH_TEST,0,0,NULL);
    op(&s,GLVK_OP_DEPTH_FUNC,GLVK_LEQUAL,0,0,NULL);
    op(&s,GLVK_OP_DEPTH_MASK,0,0,0,NULL);
    op(&s,GLVK_OP_ENABLE,GLVK_BLEND,0,0,NULL);
    op(&s,GLVK_OP_BLEND_FUNC,GLVK_SRC_ALPHA,GLVK_ONE_MINUS_SRC_ALPHA,0,NULL);
    op(&s,GLVK_OP_ENABLE,GLVK_STENCIL_TEST,0,0,NULL);
    op(&s,GLVK_OP_STENCIL_FUNC,GLVK_EQUAL,2,0xff,NULL);
    op(&s,GLVK_OP_STENCIL_OP,GLVK_KEEP,GLVK_KEEP,GLVK_REPLACE,NULL);
    op(&s,GLVK_OP_STENCIL_MASK,0xf0,0,0,NULL);
    op(&s,GLVK_OP_ENABLE,GLVK_CULL_FACE,0,0,NULL);
    op(&s,GLVK_OP_CULL_FACE,GLVK_FRONT,0,0,NULL);
    op(&s,GLVK_OP_FRONT_FACE,GLVK_CW,0,0,NULL);
    assert(s.enabled_depth&&!s.write_depth&&s.depth_func==GLVK_LEQUAL);
    assert(s.enabled_blend&&s.blend_src==GLVK_SRC_ALPHA);
    assert(s.blend_dst==GLVK_ONE_MINUS_SRC_ALPHA);
    assert(s.stencil_func==GLVK_EQUAL&&s.stencil_ref==2);
    assert(s.stencil_compare_mask==0xff&&s.stencil_write_mask==0xf0);
    assert(s.stencil_zpass==GLVK_REPLACE);
    assert(s.cull_face==GLVK_FRONT&&s.front_face==GLVK_CW);
    assert(gl_vk_state_pipeline_ready(&s));
    op(&s,GLVK_OP_DISABLE,GLVK_BLEND,0,0,NULL);
    assert(!s.enabled_blend);
}
static void test_column_major_matrices_and_stacks(void){
    gl_vk_state s;
    gl_vk_state_reset(&s);
    const float scale[16]={2,0,0,0,0,3,0,0,0,0,4,0,0,0,0,1};
    const float translate[16]={1,0,0,0,0,1,0,0,0,0,1,0,5,7,11,1};
    op(&s,GLVK_OP_LOAD_MATRIX_F,0,0,0,scale);
    op(&s,GLVK_OP_MULT_MATRIX_F,0,0,0,translate);
    /* M=S*T, column major; translations scaled by previous transform. */
    assert(near(s.modelview.current[12],10));
    assert(near(s.modelview.current[13],21));
    assert(near(s.modelview.current[14],44));
    op(&s,GLVK_OP_PUSH_MATRIX,0,0,0,NULL);
    op(&s,GLVK_OP_LOAD_IDENTITY,0,0,0,NULL);
    assert_identity(s.modelview.current);
    op(&s,GLVK_OP_POP_MATRIX,0,0,0,NULL);
    assert(near(s.modelview.current[12],10));
    assert(s.matrix_pushes==1&&s.matrix_pops==1);
    op(&s,GLVK_OP_MATRIX_MODE,GLVK_PROJECTION,0,0,NULL);
    double p[16]={0};
    p[0]=0.5;p[5]=0.25;p[10]=0.8;p[15]=1;
    op(&s,GLVK_OP_LOAD_MATRIX_D,0,0,0,p);
    assert(near(s.projection.current[0],0.5f));
    assert(near(s.projection.current[5],0.25f));
    assert(near(s.modelview.current[12],10));
    assert(gl_vk_state_matrix_digest(&s)!=0);
}
static void test_texture_units_are_separate(void){
    gl_vk_state s;
    gl_vk_state_reset(&s);
    op(&s,GLVK_OP_ACTIVE_TEXTURE,GLVK_TEXTURE0,0,0,NULL);
    op(&s,GLVK_OP_ENABLE,GLVK_TEXTURE_2D,0,0,NULL);
    op(&s,GLVK_OP_BIND_TEXTURE,GLVK_TEXTURE_2D,123,0,NULL);
    op(&s,GLVK_OP_ACTIVE_TEXTURE,GLVK_TEXTURE0+1,0,0,NULL);
    op(&s,GLVK_OP_BIND_TEXTURE,GLVK_TEXTURE_2D,456,0,NULL);
    assert(s.texture[0].bound_2d==123&&s.texture[1].bound_2d==456);
    assert(s.texture[0].enabled_2d&&!s.texture[1].enabled_2d);
    op(&s,GLVK_OP_MATRIX_MODE,GLVK_TEXTURE,0,0,NULL);
    float shifted[16]={1,0,0,0,0,1,0,0,0,0,1,0,0.25f,0.5f,0,1};
    op(&s,GLVK_OP_LOAD_MATRIX_F,0,0,0,shifted);
    assert(near(s.texture[1].texture_matrix.current[12],0.25));
    assert_identity(s.texture[0].texture_matrix.current);
    assert(gl_vk_state_pipeline_ready(&s));
    op(&s,GLVK_OP_ENABLE,GLVK_TEXTURE_2D,0,0,NULL);
    /* Multiple fixed-function combiners require additional shader support. */
    assert(!gl_vk_state_pipeline_ready(&s));
}
static void test_fail_closed(void){
    gl_vk_state s;
    gl_vk_state_reset(&s);
    assert(!gl_vk_state_apply(&s,GLVK_OP_ENABLE,0xdead,0,0,NULL));
    assert(s.unsupported_flags&GLVK_UNSUPPORTED_CAP);
    assert(!gl_vk_state_pipeline_ready(&s));
    gl_vk_state_reset(&s);
    assert(!gl_vk_state_apply(&s,GLVK_OP_DEPTH_FUNC,0xdead,0,0,NULL));
    assert(s.depth_func==GLVK_LESS);
    gl_vk_state_reset(&s);
    assert(!gl_vk_state_apply(&s,GLVK_OP_LOAD_MATRIX_F,0,0,0,NULL));
    assert(s.unsupported_flags&GLVK_UNSUPPORTED_PTR);
    gl_vk_state_reset(&s);
    assert(!gl_vk_state_apply(&s,GLVK_OP_POP_MATRIX,0,0,0,NULL));
    assert(s.unsupported_flags&GLVK_UNSUPPORTED_MATRIX);
    gl_vk_state_reset(&s);
    for(uint32_t i=0;i<GLVK_MAX_MATRIX_STACK;i++)
        op(&s,GLVK_OP_PUSH_MATRIX,0,0,0,NULL);
    assert(!gl_vk_state_apply(&s,GLVK_OP_PUSH_MATRIX,0,0,0,NULL));
    gl_vk_state_reset(&s);
    float alpha=.25f;
    uint32_t alpha_bits;
    memcpy(&alpha_bits,&alpha,sizeof(alpha_bits));
    /* Production thunk passes raw guest float bits in operand b. */
    op(&s,GLVK_OP_ALPHA_FUNC,GLVK_GREATER,alpha_bits,0,NULL);
    assert(near(s.alpha_ref,.25f)&&s.alpha_func==GLVK_GREATER);
    op(&s,GLVK_OP_ENABLE,GLVK_ALPHA_TEST,0,0,NULL);
    assert(!gl_vk_state_pipeline_ready(&s));
    op(&s,GLVK_OP_DISABLE,GLVK_ALPHA_TEST,0,0,NULL);
    assert(gl_vk_state_pipeline_ready(&s));
    gl_vk_state_reset(&s);
    assert(!gl_vk_state_apply(&s,GLVK_OP_UNSUPPORTED_STATE,0,0,0,NULL));
    assert(s.unsupported_flags&GLVK_UNSUPPORTED_LEGACY);
    assert(s.legacy_categories[GLVK_LEGACY_TEXTURE_STATE]==1);
    gl_vk_state_reset(&s);
    assert(!gl_vk_state_apply(&s,GLVK_OP_UNSUPPORTED_STATE,
                              GLVK_LEGACY_MATRIX_TRANSFORM,0,0,NULL));
    assert(s.legacy_categories[GLVK_LEGACY_MATRIX_TRANSFORM]==1);
    assert(s.legacy_categories[GLVK_LEGACY_TEXTURE_STATE]==0);
    gl_vk_state_reset(&s);
    assert(!gl_vk_state_apply(&s,GLVK_OP_ACTIVE_TEXTURE,GLVK_TEXTURE0+6,0,0,NULL));
    assert(s.unsupported_flags&GLVK_UNSUPPORTED_TEXTURE);
}
int main(void) {
    test_defaults_and_depth_stencil_blend();
    test_column_major_matrices_and_stacks();
    test_texture_units_are_separate();
    test_fail_closed();
    puts("GL state observer smoke: depth/stencil/blend/matrix/texture unit/fail-closed PASS");
    return 0;
}
