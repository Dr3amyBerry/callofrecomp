/*
 * Isolated Android Vulkan texture upload: RGBA8 -> host-coherent staging
 * VkBuffer -> device-local optimal-tiled VkImage -> sampled descriptor.
 *
 * No user/game assets. Explicit layout transitions, one-shot submission,
 * fence wait before releasing staging. No GPU measurements implied.
 */
#define VK_USE_PLATFORM_ANDROID_KHR 1
#include "wsa_vk_texture.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static int choose_memory(VkPhysicalDevice physical,uint32_t bits,
                         VkMemoryPropertyFlags required,uint32_t *index) {
    VkPhysicalDeviceMemoryProperties properties;
    vkGetPhysicalDeviceMemoryProperties(physical,&properties);
    for(uint32_t i=0;i<properties.memoryTypeCount;i++) {
        if ((bits&(1u<<i))&&
            (properties.memoryTypes[i].propertyFlags&required)==required) {
            *index=i;
            return 1;
        }
    }
    return 0;
}

static VkResult allocate_for_buffer(VkPhysicalDevice physical,VkDevice device,
                                    VkBuffer buffer,VkMemoryPropertyFlags flags,
                                    VkDeviceMemory *memory) {
    VkMemoryRequirements req;
    vkGetBufferMemoryRequirements(device,buffer,&req);
    uint32_t memory_index=0;
    if(!choose_memory(physical,req.memoryTypeBits,flags,&memory_index))
        return VK_ERROR_FEATURE_NOT_PRESENT;
    VkMemoryAllocateInfo ai={0};
    ai.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    ai.allocationSize=req.size;
    ai.memoryTypeIndex=memory_index;
    return vkAllocateMemory(device,&ai,NULL,memory);
}

static VkResult allocate_for_image(VkPhysicalDevice physical,VkDevice device,
                                   VkImage image,VkMemoryPropertyFlags flags,
                                   VkDeviceMemory *memory) {
    VkMemoryRequirements req;
    vkGetImageMemoryRequirements(device,image,&req);
    uint32_t memory_index=0;
    if(!choose_memory(physical,req.memoryTypeBits,flags,&memory_index))
        return VK_ERROR_FEATURE_NOT_PRESENT;
    VkMemoryAllocateInfo ai={0};
    ai.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    ai.allocationSize=req.size;
    ai.memoryTypeIndex=memory_index;
    return vkAllocateMemory(device,&ai,NULL,memory);
}

static void checker_pixels(uint8_t *bytes) {
    for(uint32_t y=0;y<VK_DEMO_TEX_SIZE;y++){
        for(uint32_t x=0;x<VK_DEMO_TEX_SIZE;x++){
            uint32_t offset=(y*VK_DEMO_TEX_SIZE+x)*4u;
            int light=((x/8u)^(y/8u))&1;
            bytes[offset+0]=(uint8_t)(light?245:33);
            bytes[offset+1]=(uint8_t)(light?232:46);
            bytes[offset+2]=(uint8_t)(light?30:210);
            bytes[offset+3]=255;
        }
    }
}

void vk_demo_texture_destroy(vk_demo_texture *t) {
    if(!t||!t->device)return;
    if(t->descriptor_pool)vkDestroyDescriptorPool(t->device,t->descriptor_pool,NULL);
    if(t->layout)vkDestroyDescriptorSetLayout(t->device,t->layout,NULL);
    if(t->sampler)vkDestroySampler(t->device,t->sampler,NULL);
    if(t->view)vkDestroyImageView(t->device,t->view,NULL);
    if(t->image)vkDestroyImage(t->device,t->image,NULL);
    if(t->memory)vkFreeMemory(t->device,t->memory,NULL);
    memset(t,0,sizeof(*t));
}

VkResult vk_demo_texture_create(vk_demo_texture *t,
                                VkPhysicalDevice physical,VkDevice device,
                                VkQueue queue,uint32_t queue_family) {
    if(!t||!physical||!device||!queue)return VK_ERROR_INITIALIZATION_FAILED;
    memset(t,0,sizeof(*t));
    t->device=device;
    VkResult r=VK_ERROR_INITIALIZATION_FAILED;
    VkBuffer staging=VK_NULL_HANDLE;
    VkDeviceMemory staging_mem=VK_NULL_HANDLE;
    VkCommandPool command_pool=VK_NULL_HANDLE;
    VkCommandBuffer command=VK_NULL_HANDLE;
    VkFence completion=VK_NULL_HANDLE;
    int submitted=0;
    VkFormatProperties format;
    vkGetPhysicalDeviceFormatProperties(physical,VK_FORMAT_R8G8B8A8_UNORM,&format);
    if((format.optimalTilingFeatures&VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT)==0)
        return VK_ERROR_FORMAT_NOT_SUPPORTED;
    const VkDeviceSize size=(VkDeviceSize)VK_DEMO_TEX_SIZE*VK_DEMO_TEX_SIZE*4u;
    VkBufferCreateInfo staging_info={0};
    staging_info.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    staging_info.size=size;staging_info.usage=VK_BUFFER_USAGE_TRANSFER_SRC_BIT;
    staging_info.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
    r=vkCreateBuffer(device,&staging_info,NULL,&staging);
    if(r!=VK_SUCCESS)goto fail;
    r=allocate_for_buffer(physical,device,staging,
            VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
            &staging_mem);
    if(r!=VK_SUCCESS)goto fail;
    r=vkBindBufferMemory(device,staging,staging_mem,0);
    if(r!=VK_SUCCESS)goto fail;
    void* mapped=NULL;
    r=vkMapMemory(device,staging_mem,0,size,0,&mapped);
    if(r!=VK_SUCCESS)goto fail;
    checker_pixels(mapped);
    vkUnmapMemory(device,staging_mem);

    VkImageCreateInfo image={0};
    image.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
    image.imageType=VK_IMAGE_TYPE_2D;
    image.format=VK_FORMAT_R8G8B8A8_UNORM;
    image.extent=(VkExtent3D){VK_DEMO_TEX_SIZE,VK_DEMO_TEX_SIZE,1};
    image.mipLevels=1;image.arrayLayers=1;
    image.samples=VK_SAMPLE_COUNT_1_BIT;
    image.tiling=VK_IMAGE_TILING_OPTIMAL;
    image.usage=VK_IMAGE_USAGE_TRANSFER_DST_BIT|VK_IMAGE_USAGE_SAMPLED_BIT;
    image.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
    image.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED;
    r=vkCreateImage(device,&image,NULL,&t->image);
    if(r!=VK_SUCCESS)goto fail;
    r=allocate_for_image(physical,device,t->image,
            VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,&t->memory);
    if(r!=VK_SUCCESS)goto fail;
    r=vkBindImageMemory(device,t->image,t->memory,0);
    if(r!=VK_SUCCESS)goto fail;

    VkCommandPoolCreateInfo pool_info={0};
    pool_info.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
    pool_info.queueFamilyIndex=queue_family;
    pool_info.flags=VK_COMMAND_POOL_CREATE_TRANSIENT_BIT;
    r=vkCreateCommandPool(device,&pool_info,NULL,&command_pool);
    if(r!=VK_SUCCESS)goto fail;
    VkCommandBufferAllocateInfo alloc={0};
    alloc.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    alloc.commandPool=command_pool;
    alloc.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    alloc.commandBufferCount=1;
    r=vkAllocateCommandBuffers(device,&alloc,&command);
    if(r!=VK_SUCCESS)goto fail;
    VkCommandBufferBeginInfo begin={0};
    begin.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    begin.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    r=vkBeginCommandBuffer(command,&begin);
    if(r!=VK_SUCCESS)goto fail;

    VkImageMemoryBarrier barrier={0};
    barrier.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED;
    barrier.newLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    barrier.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;
    barrier.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;
    barrier.image=t->image;
    barrier.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
    barrier.subresourceRange.levelCount=1;
    barrier.subresourceRange.layerCount=1;
    barrier.srcAccessMask=0;
    barrier.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;
    vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
        VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,NULL,0,NULL,1,&barrier);

    VkBufferImageCopy copy={0};
    copy.bufferOffset=0;
    copy.imageSubresource.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
    copy.imageSubresource.mipLevel=0;
    copy.imageSubresource.baseArrayLayer=0;
    copy.imageSubresource.layerCount=1;
    copy.imageExtent=(VkExtent3D){VK_DEMO_TEX_SIZE,VK_DEMO_TEX_SIZE,1};
    vkCmdCopyBufferToImage(command,staging,t->image,
                           VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,1,&copy);
    barrier.oldLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    barrier.newLayout=VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    barrier.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;
    barrier.dstAccessMask=VK_ACCESS_SHADER_READ_BIT;
    vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TRANSFER_BIT,
        VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,0,0,NULL,0,NULL,1,&barrier);
    r=vkEndCommandBuffer(command);
    if(r!=VK_SUCCESS)goto fail;
    VkFenceCreateInfo fi={0};
    fi.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
    r=vkCreateFence(device,&fi,NULL,&completion);
    if(r!=VK_SUCCESS)goto fail;
    VkSubmitInfo submit={0};
    submit.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO;
    submit.commandBufferCount=1;
    submit.pCommandBuffers=&command;
    r=vkQueueSubmit(queue,1,&submit,completion);
    if(r!=VK_SUCCESS)goto fail;
    submitted=1;
    r=vkWaitForFences(device,1,&completion,VK_TRUE,UINT64_MAX);
    if(r!=VK_SUCCESS)goto fail;
    /* Only free staging after its queue work has completed. */
    vkDestroyFence(device,completion,NULL);
    completion=VK_NULL_HANDLE;
    vkDestroyCommandPool(device,command_pool,NULL);
    command_pool=VK_NULL_HANDLE;
    vkDestroyBuffer(device,staging,NULL);
    staging=VK_NULL_HANDLE;
    vkFreeMemory(device,staging_mem,NULL);
    staging_mem=VK_NULL_HANDLE;

    VkImageViewCreateInfo vi={0};
    vi.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
    vi.image=t->image;vi.viewType=VK_IMAGE_VIEW_TYPE_2D;
    vi.format=VK_FORMAT_R8G8B8A8_UNORM;
    vi.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
    vi.subresourceRange.levelCount=1;vi.subresourceRange.layerCount=1;
    r=vkCreateImageView(device,&vi,NULL,&t->view);
    if(r!=VK_SUCCESS)goto fail;
    VkSamplerCreateInfo sampler={0};
    sampler.sType=VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO;
    sampler.magFilter=VK_FILTER_NEAREST;
    sampler.minFilter=VK_FILTER_NEAREST;
    sampler.mipmapMode=VK_SAMPLER_MIPMAP_MODE_NEAREST;
    sampler.addressModeU=VK_SAMPLER_ADDRESS_MODE_REPEAT;
    sampler.addressModeV=VK_SAMPLER_ADDRESS_MODE_REPEAT;
    sampler.addressModeW=VK_SAMPLER_ADDRESS_MODE_REPEAT;
    sampler.maxLod=0;
    r=vkCreateSampler(device,&sampler,NULL,&t->sampler);
    if(r!=VK_SUCCESS)goto fail;

    VkDescriptorSetLayoutBinding binding={0};
    binding.binding=0;
    binding.descriptorCount=1;
    binding.descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    binding.stageFlags=VK_SHADER_STAGE_FRAGMENT_BIT;
    VkDescriptorSetLayoutCreateInfo li={0};
    li.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
    li.bindingCount=1;li.pBindings=&binding;
    r=vkCreateDescriptorSetLayout(device,&li,NULL,&t->layout);
    if(r!=VK_SUCCESS)goto fail;
    VkDescriptorPoolSize type={VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,1};
    VkDescriptorPoolCreateInfo pi={0};
    pi.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
    pi.maxSets=1;pi.poolSizeCount=1;pi.pPoolSizes=&type;
    r=vkCreateDescriptorPool(device,&pi,NULL,&t->descriptor_pool);
    if(r!=VK_SUCCESS)goto fail;
    VkDescriptorSetAllocateInfo set={0};
    set.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    set.descriptorPool=t->descriptor_pool;
    set.descriptorSetCount=1;set.pSetLayouts=&t->layout;
    r=vkAllocateDescriptorSets(device,&set,&t->descriptor);
    if(r!=VK_SUCCESS)goto fail;
    VkDescriptorImageInfo sampled={t->sampler,t->view,
                                  VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    VkWriteDescriptorSet write={0};
    write.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    write.dstSet=t->descriptor;
    write.dstBinding=0;
    write.descriptorCount=1;
    write.descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    write.pImageInfo=&sampled;
    vkUpdateDescriptorSets(device,1,&write,0,NULL);
    return VK_SUCCESS;

fail:
    if(completion) {
        /* Wait only after a successful submit, never on an unsignaled
         * fence for work that was not queued. */
        if(submitted)vkWaitForFences(device,1,&completion,VK_TRUE,UINT64_MAX);
        vkDestroyFence(device,completion,NULL);
    }
    if(command_pool)vkDestroyCommandPool(device,command_pool,NULL);
    if(staging)vkDestroyBuffer(device,staging,NULL);
    if(staging_mem)vkFreeMemory(device,staging_mem,NULL);
    vk_demo_texture_destroy(t);
    return r;
}
