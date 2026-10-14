/*
 * One independent depth/stencil VkImage per swapchain framebuffer.
 * Vulkan render pass performs automatic UNDEFINED -> ATTACHMENT_OPTIMAL
 * transition and clears depth=1.0/stencil=0; no sampling or CPU readback.
 * Never share a single writable depth attachment across in-flight frames.
 */
#define VK_USE_PLATFORM_ANDROID_KHR 1
#include "wsa_vk_depth.h"
#include <stdint.h>
#include <string.h>

VkFormat vk_demo_depth_format(VkPhysicalDevice physical) {
    if (!physical) return VK_FORMAT_UNDEFINED;
    const VkFormat candidates[]={
        VK_FORMAT_D24_UNORM_S8_UINT,
        VK_FORMAT_D32_SFLOAT_S8_UINT,
        VK_FORMAT_D16_UNORM_S8_UINT
    };
    for (uint32_t i=0;i<sizeof(candidates)/sizeof(candidates[0]);i++) {
        VkFormatProperties properties;
        vkGetPhysicalDeviceFormatProperties(physical,candidates[i],&properties);
        if (properties.optimalTilingFeatures&
            VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT)
            return candidates[i];
    }
    return VK_FORMAT_UNDEFINED;
}

void vk_demo_depth_destroy(vk_demo_depth *v) {
    if(!v||!v->device)return;
    if(v->view)vkDestroyImageView(v->device,v->view,NULL);
    if(v->image)vkDestroyImage(v->device,v->image,NULL);
    if(v->memory)vkFreeMemory(v->device,v->memory,NULL);
    memset(v,0,sizeof(*v));
}

VkResult vk_demo_depth_create(vk_demo_depth *v,VkPhysicalDevice physical,
                               VkDevice device,VkFormat format,
                               uint32_t width,uint32_t height) {
    if(!v||!physical||!device||!width||!height||
       format==VK_FORMAT_UNDEFINED)
        return VK_ERROR_INITIALIZATION_FAILED;
    memset(v,0,sizeof(*v));
    v->device=device;
    VkResult r;
    VkImageCreateInfo ii={0};
    ii.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
    ii.imageType=VK_IMAGE_TYPE_2D;
    ii.extent=(VkExtent3D){width,height,1};
    ii.format=format;
    ii.mipLevels=1;
    ii.arrayLayers=1;
    ii.samples=VK_SAMPLE_COUNT_1_BIT;
    ii.tiling=VK_IMAGE_TILING_OPTIMAL;
    ii.usage=VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT;
    ii.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED;
    ii.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
    r=vkCreateImage(device,&ii,NULL,&v->image);
    if(r!=VK_SUCCESS)goto failed;
    VkMemoryRequirements req;
    vkGetImageMemoryRequirements(device,v->image,&req);
    VkPhysicalDeviceMemoryProperties mem;
    vkGetPhysicalDeviceMemoryProperties(physical,&mem);
    uint32_t type_index=UINT32_MAX;
    for(uint32_t i=0;i<mem.memoryTypeCount;i++) {
        if(!(req.memoryTypeBits&(1u<<i)))continue;
        if((mem.memoryTypes[i].propertyFlags & VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)
             ==VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT){
            type_index=i;break;
        }
    }
    if(type_index==UINT32_MAX){r=VK_ERROR_FEATURE_NOT_PRESENT;goto failed;}
    VkMemoryAllocateInfo ai={0};
    ai.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    ai.allocationSize=req.size;
    ai.memoryTypeIndex=type_index;
    r=vkAllocateMemory(device,&ai,NULL,&v->memory);
    if(r!=VK_SUCCESS)goto failed;
    r=vkBindImageMemory(device,v->image,v->memory,0);
    if(r!=VK_SUCCESS)goto failed;
    VkImageViewCreateInfo vi={0};
    vi.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
    vi.image=v->image;
    vi.viewType=VK_IMAGE_VIEW_TYPE_2D;
    vi.format=format;
    vi.subresourceRange.aspectMask=VK_IMAGE_ASPECT_DEPTH_BIT|
                                    VK_IMAGE_ASPECT_STENCIL_BIT;
    vi.subresourceRange.levelCount=1;
    vi.subresourceRange.layerCount=1;
    r=vkCreateImageView(device,&vi,NULL,&v->view);
    if(r!=VK_SUCCESS)goto failed;
    return VK_SUCCESS;
failed:
    vk_demo_depth_destroy(v);
    return r;
}
