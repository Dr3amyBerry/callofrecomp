/* Differential checks against OpenGL fixed-function matrix equations.
 * Independent numeric expectations, including 8-byte x86 double slot ABI
 * addressed in separate generator tests. No game data/renderer involved. */
#include "gl_vk_state.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static int close_f(float a,float b){return fabsf(a-b)<0.0002f;}
static void eq(float a,float b){assert(close_f(a,b));}
static void op(gl_vk_state *s,gl_vk_opcode opcode,const double v[6]){
    assert(gl_vk_state_apply(s,opcode,0,0,0,v));
}
static void mode(gl_vk_state *s,uint32_t gl_mode){
    assert(gl_vk_state_apply(s,GLVK_OP_MATRIX_MODE,gl_mode,0,0,NULL));
}
static void reset_matrix(gl_vk_state *s){
    assert(gl_vk_state_apply(s,GLVK_OP_LOAD_IDENTITY,0,0,0,NULL));
}

static void translate_scale_order(void){
    gl_vk_state s;gl_vk_state_reset(&s);
    const double translation[6]={5,-3,7},scale[6]={2,4,6};
    op(&s,GLVK_OP_TRANSLATE,translation);
    op(&s,GLVK_OP_SCALE,scale);
    /* T*S, not S*T: translation column remains unchanged. */
    eq(s.modelview.current[0],2);
    eq(s.modelview.current[5],4);
    eq(s.modelview.current[10],6);
    eq(s.modelview.current[12],5);
    eq(s.modelview.current[13],-3);
    eq(s.modelview.current[14],7);
    reset_matrix(&s);
    op(&s,GLVK_OP_SCALE,scale);
    op(&s,GLVK_OP_TRANSLATE,translation);
    /* S*T, translation is scaled. */
    eq(s.modelview.current[12],10);
    eq(s.modelview.current[13],-12);
    eq(s.modelview.current[14],42);
}

static void rotation_normalized_axis(void){
    gl_vk_state s;gl_vk_state_reset(&s);
    const double r[6]={90,0,0,5};
    op(&s,GLVK_OP_ROTATE,r);
    /* 90 degrees around normalized +Z, right-handed OpenGL. */
    eq(s.modelview.current[0],0);
    eq(s.modelview.current[1],1);
    eq(s.modelview.current[4],-1);
    eq(s.modelview.current[5],0);
    eq(s.modelview.current[10],1);
    reset_matrix(&s);
    const double around_x[6]={180,9,0,0};
    op(&s,GLVK_OP_ROTATE,around_x);
    eq(s.modelview.current[5],-1);
    eq(s.modelview.current[10],-1);
}

static void projection_equations(void){
    gl_vk_state s;gl_vk_state_reset(&s);
    mode(&s,GLVK_PROJECTION);
    const double ortho[6]={-2,2,-1,3,-4,6};
    op(&s,GLVK_OP_ORTHO,ortho);
    const float *a=s.projection.current;
    eq(a[0],0.5f);
    eq(a[5],0.5f);
    eq(a[10],-0.2f);
    eq(a[12],0);
    eq(a[13],-0.5f);
    eq(a[14],-0.2f);
    reset_matrix(&s);
    const double frustum[6]={-1,1,-1,1,1,11};
    op(&s,GLVK_OP_FRUSTUM,frustum);
    a=s.projection.current;
    eq(a[0],1);
    eq(a[5],1);
    eq(a[10],-1.2f);
    eq(a[11],-1);
    eq(a[14],-2.2f);
    eq(a[15],0);
    mode(&s,GLVK_MODELVIEW);
    const double translate[6]={0,0,-3};
    op(&s,GLVK_OP_TRANSLATE,translate);
    float mvp[16];
    assert(gl_vk_state_mvp(&s,mvp));
    eq(mvp[0],1);
    eq(mvp[14],1.4f); /* -1.2*(-3) + -2.2 */
    eq(mvp[15],3);
}

static void texture_projection_independent_and_stacks(void){
    gl_vk_state s;gl_vk_state_reset(&s);
    mode(&s,GLVK_PROJECTION);
    const double proj[6]={-2,2,-2,2,-1,1};
    op(&s,GLVK_OP_ORTHO,proj);
    mode(&s,GLVK_TEXTURE);
    const double uv[6]={.125,.25,0};
    op(&s,GLVK_OP_TRANSLATE,uv);
    assert(gl_vk_state_apply(&s,GLVK_OP_PUSH_MATRIX,0,0,0,NULL));
    const double uv_scale[6]={2,2,1};
    op(&s,GLVK_OP_SCALE,uv_scale);
    eq(s.texture[0].texture_matrix.current[0],2);
    assert(gl_vk_state_apply(&s,GLVK_OP_POP_MATRIX,0,0,0,NULL));
    eq(s.texture[0].texture_matrix.current[0],1);
    eq(s.texture[0].texture_matrix.current[12],.125f);
    assert(gl_vk_state_apply(&s,GLVK_OP_ACTIVE_TEXTURE,GLVK_TEXTURE0+1,0,0,NULL));
    op(&s,GLVK_OP_TRANSLATE,uv);
    eq(s.texture[1].texture_matrix.current[12],.125f);
    /* Neither texture matrix affects projection/modelview MVP. */
    float mvp[16];
    assert(gl_vk_state_mvp(&s,mvp));
    eq(mvp[0],0.5f);
    eq(mvp[12],0);
}

static void invalid_inputs_fail_closed_no_mutation(void){
    gl_vk_state s;gl_vk_state_reset(&s);
    const double zero_axis[6]={60,0,0,0};
    const double invalid_frustum[6]={-1,1,-1,1,-1,11};
    const double invalid_ortho[6]={1,1,-1,1,-2,2};
    const double invalid_nan[6]={NAN,0,0};
    const double giant[6]={1e308,0,0};
    const gl_vk_opcode operations[]={
        GLVK_OP_ROTATE,GLVK_OP_FRUSTUM,GLVK_OP_ORTHO,
        GLVK_OP_TRANSLATE,GLVK_OP_TRANSLATE
    };
    const double *inputs[]={zero_axis,invalid_frustum,invalid_ortho,invalid_nan,giant};
    for(unsigned k=0;k<sizeof(operations)/sizeof(operations[0]);k++){
        gl_vk_state_reset(&s);
        float before[16];
        memcpy(before,s.modelview.current,sizeof(before));
        assert(!gl_vk_state_apply(&s,operations[k],0,0,0,inputs[k]));
        assert(s.unsupported_flags&GLVK_UNSUPPORTED_MATRIX);
        assert(memcmp(before,s.modelview.current,sizeof(before))==0);
        assert(!gl_vk_state_pipeline_ready(&s));
        float result[16];
        assert(!gl_vk_state_mvp(&s,result));
    }
    gl_vk_state_reset(&s);
    assert(!gl_vk_state_apply(&s,GLVK_OP_TRANSLATE,0,0,0,NULL));
    assert(s.unsupported_flags&GLVK_UNSUPPORTED_PTR);
}
int main(void){
    translate_scale_order();
    rotation_normalized_axis();
    projection_equations();
    texture_projection_independent_and_stacks();
    invalid_inputs_fail_closed_no_mutation();
    puts("GL matrix differential: translation, scale, normalized rotation, "
         "ortho/frustum, texture stack, fail-closed PASS");
    return 0;
}
