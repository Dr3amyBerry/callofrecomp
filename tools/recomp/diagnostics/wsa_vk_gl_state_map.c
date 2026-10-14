#define VK_USE_PLATFORM_ANDROID_KHR 1
#include "wsa_vk_gl_state_map.h"
#include <string.h>

static int map_compare(uint32_t gl,VkCompareOp *vk) {
    switch(gl) {
        case GLVK_NEVER:*vk=VK_COMPARE_OP_NEVER;return 1;
        case GLVK_LESS:*vk=VK_COMPARE_OP_LESS;return 1;
        case GLVK_EQUAL:*vk=VK_COMPARE_OP_EQUAL;return 1;
        case GLVK_LEQUAL:*vk=VK_COMPARE_OP_LESS_OR_EQUAL;return 1;
        case GLVK_GREATER:*vk=VK_COMPARE_OP_GREATER;return 1;
        case GLVK_NOTEQUAL:*vk=VK_COMPARE_OP_NOT_EQUAL;return 1;
        case GLVK_GEQUAL:*vk=VK_COMPARE_OP_GREATER_OR_EQUAL;return 1;
        case GLVK_ALWAYS:*vk=VK_COMPARE_OP_ALWAYS;return 1;
    }
    return 0;
}
static int map_stencil(uint32_t gl,VkStencilOp *vk) {
    switch(gl){
        case GLVK_ZERO:*vk=VK_STENCIL_OP_ZERO;return 1;
        case GLVK_KEEP:*vk=VK_STENCIL_OP_KEEP;return 1;
        case GLVK_REPLACE:*vk=VK_STENCIL_OP_REPLACE;return 1;
        case GLVK_INCR:*vk=VK_STENCIL_OP_INCREMENT_AND_CLAMP;return 1;
        case GLVK_DECR:*vk=VK_STENCIL_OP_DECREMENT_AND_CLAMP;return 1;
        case GLVK_INVERT:*vk=VK_STENCIL_OP_INVERT;return 1;
        case GLVK_INCR_WRAP:*vk=VK_STENCIL_OP_INCREMENT_AND_WRAP;return 1;
        case GLVK_DECR_WRAP:*vk=VK_STENCIL_OP_DECREMENT_AND_WRAP;return 1;
    }
    return 0;
}
static int map_blend(uint32_t gl,int is_alpha,VkBlendFactor *vk) {
    switch(gl){
        case GLVK_ZERO:*vk=VK_BLEND_FACTOR_ZERO;return 1;
        case GLVK_ONE:*vk=VK_BLEND_FACTOR_ONE;return 1;
        case GLVK_SRC_COLOR:*vk=is_alpha?VK_BLEND_FACTOR_SRC_ALPHA:VK_BLEND_FACTOR_SRC_COLOR;return 1;
        case GLVK_ONE_MINUS_SRC_COLOR:
            *vk=is_alpha?VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA:VK_BLEND_FACTOR_ONE_MINUS_SRC_COLOR;return 1;
        case GLVK_DST_COLOR:*vk=is_alpha?VK_BLEND_FACTOR_DST_ALPHA:VK_BLEND_FACTOR_DST_COLOR;return 1;
        case GLVK_ONE_MINUS_DST_COLOR:
            *vk=is_alpha?VK_BLEND_FACTOR_ONE_MINUS_DST_ALPHA:VK_BLEND_FACTOR_ONE_MINUS_DST_COLOR;return 1;
        case GLVK_SRC_ALPHA:*vk=VK_BLEND_FACTOR_SRC_ALPHA;return 1;
        case GLVK_ONE_MINUS_SRC_ALPHA:*vk=VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA;return 1;
        case GLVK_DST_ALPHA:*vk=VK_BLEND_FACTOR_DST_ALPHA;return 1;
        case GLVK_ONE_MINUS_DST_ALPHA:*vk=VK_BLEND_FACTOR_ONE_MINUS_DST_ALPHA;return 1;
        case GLVK_SRC_ALPHA_SATURATE:
            if(is_alpha){*vk=VK_BLEND_FACTOR_ONE;return 1;}
            *vk=VK_BLEND_FACTOR_SRC_ALPHA_SATURATE;return 1;
    }
    return 0;
}
int vk_gl_translate_pipeline(const gl_vk_state *gl,vk_gl_pipeline_state *vk) {
    if(!gl||!vk||!gl_vk_state_pipeline_ready(gl))return 0;
    memset(vk,0,sizeof(*vk));
    vk->depth.sType=VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO;
    vk->depth.depthTestEnable=(VkBool32)gl->enabled_depth;
    vk->depth.depthWriteEnable=(VkBool32)gl->write_depth;
    if(!map_compare(gl->depth_func,&vk->depth.depthCompareOp))return 0;
    vk->depth.stencilTestEnable=(VkBool32)gl->enabled_stencil;
    VkStencilOpState stencil={0};
    if(!map_compare(gl->stencil_func,&stencil.compareOp)||
       !map_stencil(gl->stencil_fail,&stencil.failOp)||
       !map_stencil(gl->stencil_zfail,&stencil.depthFailOp)||
       !map_stencil(gl->stencil_zpass,&stencil.passOp))return 0;
    stencil.compareMask=gl->stencil_compare_mask;
    stencil.writeMask=gl->stencil_write_mask;
    stencil.reference=gl->stencil_ref;
    vk->depth.front=vk->depth.back=stencil;
    vk->color.blendEnable=(VkBool32)gl->enabled_blend;
    vk->color.colorWriteMask=VK_COLOR_COMPONENT_R_BIT|VK_COLOR_COMPONENT_G_BIT|
                              VK_COLOR_COMPONENT_B_BIT|VK_COLOR_COMPONENT_A_BIT;
    if(!map_blend(gl->blend_src,0,&vk->color.srcColorBlendFactor)||
       !map_blend(gl->blend_dst,0,&vk->color.dstColorBlendFactor)||
       !map_blend(gl->blend_src,1,&vk->color.srcAlphaBlendFactor)||
       !map_blend(gl->blend_dst,1,&vk->color.dstAlphaBlendFactor))return 0;
    vk->color.colorBlendOp=VK_BLEND_OP_ADD;
    vk->color.alphaBlendOp=VK_BLEND_OP_ADD;
    vk->raster.sType=VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO;
    vk->raster.polygonMode=VK_POLYGON_MODE_FILL;
    vk->raster.cullMode=gl->enabled_cull?
          (gl->cull_face==GLVK_FRONT?VK_CULL_MODE_FRONT_BIT:
           gl->cull_face==GLVK_BACK?VK_CULL_MODE_BACK_BIT:
           gl->cull_face==GLVK_FRONT_AND_BACK?VK_CULL_MODE_FRONT_AND_BACK:
           VK_CULL_MODE_FLAG_BITS_MAX_ENUM):VK_CULL_MODE_NONE;
    if(vk->raster.cullMode==VK_CULL_MODE_FLAG_BITS_MAX_ENUM)return 0;
    vk->raster.frontFace=gl->front_face==GLVK_CCW?
        VK_FRONT_FACE_COUNTER_CLOCKWISE:VK_FRONT_FACE_CLOCKWISE;
    vk->raster.lineWidth=1.0f;
    return 1;
}
