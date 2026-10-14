/* Strict mapping of a supported typed OpenGL state subset to Vulkan.
 * Used only by the standalone diagnostic Vulkan scene so far.
 * A real CoDSP Vulkan renderer DOES NOT exist.
 */
#pragma once
#define VK_USE_PLATFORM_ANDROID_KHR 1
#include <vulkan/vulkan.h>
#include "../runtime/gl_vk_state.h"

typedef struct vk_gl_pipeline_state {
    VkPipelineDepthStencilStateCreateInfo depth;
    VkPipelineColorBlendAttachmentState color;
    VkPipelineRasterizationStateCreateInfo raster;
} vk_gl_pipeline_state;

/* Return 0 on unknown/unimplemented fixed-function states; no guesses. */
int vk_gl_translate_pipeline(const gl_vk_state *gl, vk_gl_pipeline_state *vk);
