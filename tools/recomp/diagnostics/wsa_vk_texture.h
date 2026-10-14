/* Self-contained sampled VkImage milestone (standalone Vulkan APK only). */
#pragma once
#define VK_USE_PLATFORM_ANDROID_KHR 1
#include <vulkan/vulkan.h>
#include <stdint.h>

#define VK_DEMO_TEX_SIZE 64u
typedef struct vk_demo_texture {
    VkDevice device;
    VkImage image;
    VkDeviceMemory memory;
    VkImageView view;
    VkSampler sampler;
    VkDescriptorSetLayout layout;
    VkDescriptorPool descriptor_pool;
    VkDescriptorSet descriptor;
} vk_demo_texture;

VkResult vk_demo_texture_create(vk_demo_texture *texture,
                                VkPhysicalDevice physical, VkDevice device,
                                VkQueue queue, uint32_t queue_family,
                                int alpha_scene);
void vk_demo_texture_destroy(vk_demo_texture *texture);
