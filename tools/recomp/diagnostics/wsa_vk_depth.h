/* Isolated per-swapchain depth+stencil attachment for Android Vulkan demo. */
#pragma once
#define VK_USE_PLATFORM_ANDROID_KHR 1
#include <vulkan/vulkan.h>
#include <stdint.h>

typedef struct vk_demo_depth {
    VkDevice device;
    VkImage image;
    VkDeviceMemory memory;
    VkImageView view;
} vk_demo_depth;

VkFormat vk_demo_depth_format(VkPhysicalDevice physical);
VkResult vk_demo_depth_create(vk_demo_depth *out, VkPhysicalDevice physical,
                               VkDevice device, VkFormat format,
                               uint32_t width, uint32_t height);
void vk_demo_depth_destroy(vk_demo_depth *value);
