/* Typed, diagnostic-only OpenGL 1.x -> Vulkan state preparation.
 *
 * No Vulkan or third-party OpenGL headers are needed. Never claim that an
 * incomplete capture is renderable; unknown/unsupported states are sticky.
 * Included in a generated bridge only when CODRECOMP_GL_VK_STATE_CAPTURE.
 */
#pragma once
#include <stdint.h>
#include <stddef.h>

#define GLVK_MAX_TEXTURE_UNITS 4u
#define GLVK_MAX_MATRIX_STACK 32u

/* Subset of the Khronos OpenGL 1.x enumerants used by CoDSP. */
enum {
    GLVK_FALSE=0, GLVK_TRUE=1,
    GLVK_ZERO=0, GLVK_ONE=1,
    GLVK_DEPTH_TEST=0x0b71, GLVK_BLEND=0x0be2, GLVK_STENCIL_TEST=0x0b90,
    GLVK_CULL_FACE=0x0b44, GLVK_ALPHA_TEST=0x0bc0,
    GLVK_TEXTURE_2D=0x0de1, GLVK_LIGHTING=0x0b50,
    GLVK_FOG=0x0b60, GLVK_SCISSOR_TEST=0x0c11,
    GLVK_NEVER=0x0200, GLVK_LESS=0x0201, GLVK_EQUAL=0x0202,
    GLVK_LEQUAL=0x0203, GLVK_GREATER=0x0204, GLVK_NOTEQUAL=0x0205,
    GLVK_GEQUAL=0x0206, GLVK_ALWAYS=0x0207,
    GLVK_KEEP=0x1e00, GLVK_REPLACE=0x1e01, GLVK_INCR=0x1e02,
    GLVK_DECR=0x1e03, GLVK_INVERT=0x150a,
    GLVK_INCR_WRAP=0x8507, GLVK_DECR_WRAP=0x8508,
    GLVK_SRC_COLOR=0x0300, GLVK_ONE_MINUS_SRC_COLOR=0x0301,
    GLVK_SRC_ALPHA=0x0302, GLVK_ONE_MINUS_SRC_ALPHA=0x0303,
    GLVK_DST_ALPHA=0x0304, GLVK_ONE_MINUS_DST_ALPHA=0x0305,
    GLVK_DST_COLOR=0x0306, GLVK_ONE_MINUS_DST_COLOR=0x0307,
    GLVK_SRC_ALPHA_SATURATE=0x0308,
    GLVK_FRONT=0x0404, GLVK_BACK=0x0405, GLVK_FRONT_AND_BACK=0x0408,
    GLVK_CW=0x0900, GLVK_CCW=0x0901,
    GLVK_MODELVIEW=0x1700, GLVK_PROJECTION=0x1701, GLVK_TEXTURE=0x1702,
    GLVK_TEXTURE0=0x84c0,
    GLVK_TEXTURE_ENV=0x2300, GLVK_TEXTURE_ENV_MODE=0x2200,
    GLVK_MODULATE=0x2100
};

typedef enum {
    GLVK_OP_ENABLE, GLVK_OP_DISABLE,
    GLVK_OP_DEPTH_FUNC, GLVK_OP_DEPTH_MASK,
    GLVK_OP_BLEND_FUNC, GLVK_OP_STENCIL_FUNC, GLVK_OP_STENCIL_OP,
    GLVK_OP_STENCIL_MASK, GLVK_OP_CULL_FACE, GLVK_OP_FRONT_FACE,
    GLVK_OP_ALPHA_FUNC,
    GLVK_OP_TEX_ENV_I, GLVK_OP_TEX_ENV_F,
    GLVK_OP_TEX_ENV_IV, GLVK_OP_TEX_ENV_FV,
    GLVK_OP_ACTIVE_TEXTURE, GLVK_OP_BIND_TEXTURE,
    GLVK_OP_MATRIX_MODE, GLVK_OP_LOAD_IDENTITY,
    GLVK_OP_LOAD_MATRIX_F, GLVK_OP_MULT_MATRIX_F,
    GLVK_OP_LOAD_MATRIX_D, GLVK_OP_MULT_MATRIX_D,
    GLVK_OP_PUSH_MATRIX, GLVK_OP_POP_MATRIX,
    GLVK_OP_TRANSLATE, GLVK_OP_ROTATE, GLVK_OP_SCALE,
    GLVK_OP_ORTHO, GLVK_OP_FRUSTUM,
    GLVK_OP_UNSUPPORTED_STATE
} gl_vk_opcode;

typedef struct {
    float current[16]; /* OpenGL column-major, no implicit transpose */
    float stack[GLVK_MAX_MATRIX_STACK][16];
    uint32_t stack_len;
} gl_vk_matrix;

typedef struct {
    uint32_t bound_2d;
    uint32_t env_mode; /* Strict subset: MODULATE/REPLACE only */
    uint8_t enabled_2d;
    gl_vk_matrix texture_matrix;
} gl_vk_texture_unit;

enum {
    GLVK_LEGACY_TEXTURE_STATE=0,
    GLVK_LEGACY_TEXTURE_UPLOAD=1,
    GLVK_LEGACY_MATRIX_TRANSFORM=2,
    GLVK_LEGACY_VERTEX_INPUT=3,
    GLVK_LEGACY_LIGHTING_FOG=4,
    GLVK_LEGACY_BUFFER=5,
    GLVK_LEGACY_OTHER=6,
    GLVK_LEGACY_CATEGORY_COUNT=7
};
typedef struct {
    uint8_t enabled_depth, write_depth, enabled_blend, enabled_stencil;
    uint8_t enabled_cull, enabled_alpha, enabled_scissor;
    uint32_t depth_func, blend_src, blend_dst;
    uint32_t stencil_func, stencil_ref, stencil_compare_mask, stencil_write_mask;
    uint32_t stencil_fail, stencil_zfail, stencil_zpass;
    uint32_t cull_face, front_face, alpha_func;
    float alpha_ref;
    uint32_t active_texture, matrix_mode;
    gl_vk_matrix modelview, projection;
    gl_vk_texture_unit texture[GLVK_MAX_TEXTURE_UNITS];
    uint64_t supported_calls, unsupported_calls, matrix_pushes, matrix_pops;
    uint64_t legacy_categories[GLVK_LEGACY_CATEGORY_COUNT]; /* Family histogram for next capture. */
    uint32_t unsupported_flags; /* Sticky: never silently drop GL features. */
} gl_vk_state;

enum {
    GLVK_UNSUPPORTED_CAP=1u,
    GLVK_UNSUPPORTED_ENUM=2u,
    GLVK_UNSUPPORTED_MATRIX=4u,
    GLVK_UNSUPPORTED_TEXTURE=8u,
    GLVK_UNSUPPORTED_LEGACY=16u,
    GLVK_UNSUPPORTED_PTR=32u
};

void gl_vk_state_reset(gl_vk_state *s);
int gl_vk_state_apply(gl_vk_state *s, gl_vk_opcode op,
                      uint32_t a, uint32_t b, uint32_t c, const void *pointer);
/* Push product PROJECTION * MODELVIEW for vertex shader (column-major).
 * Diagnostic geometry only; assumes input is already an OpenGL clip-space
 * compatible vertex. Doesn't by itself translate GL vertex arrays. */
int gl_vk_state_mvp(const gl_vk_state *s, float output[16]);
int gl_vk_state_pipeline_ready(const gl_vk_state *s);
uint32_t gl_vk_state_matrix_digest(const gl_vk_state *s);
