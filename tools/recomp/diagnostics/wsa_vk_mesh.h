/* Standalone Android Vulkan indexed geometry milestone. No game assets. */
#pragma once
#define VK_USE_PLATFORM_ANDROID_KHR 1
#include <vulkan/vulkan.h>
#include "wsa_vk_texture.h"
#include <android/asset_manager.h>
#include <stddef.h>
#include <stdint.h>

typedef struct vk_demo_mesh {
    VkDevice device;
    VkPipelineLayout layout;
    VkPipeline pipeline;
    VkPipeline overlay_pipeline;
    VkBuffer vertices_indices;
    VkDeviceMemory memory;
    uint32_t index_count;
    int textured;
    int depth_scene;
    int alpha_scene;
    vk_demo_texture texture;
} vk_demo_mesh;

VkResult vk_demo_mesh_create(vk_demo_mesh *out, VkPhysicalDevice physical,
                            VkDevice device, VkRenderPass renderpass,
                            uint32_t width, uint32_t height,
                            AAssetManager *assets,
                            VkQueue queue, uint32_t queue_family,
                            int textured, int depth_scene, int alpha_scene);
void vk_demo_mesh_draw(const vk_demo_mesh *mesh, VkCommandBuffer cb);
void vk_demo_mesh_destroy(vk_demo_mesh *mesh);
void vk_demo_mesh_draw_depth(const vk_demo_mesh *mesh, VkCommandBuffer cb);
void vk_demo_mesh_draw_alpha(const vk_demo_mesh *mesh, VkCommandBuffer cb);
void vk_demo_mesh_draw_matrix(const vk_demo_mesh *mesh, VkCommandBuffer cb);
