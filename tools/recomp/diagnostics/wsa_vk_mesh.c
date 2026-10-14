/*
 * Isolated Vulkan indexed-mesh + shader pipeline. This does NOT translate
 * legacy OpenGL fixed-function state and is not a game renderer.
 */
#define VK_USE_PLATFORM_ANDROID_KHR 1
#include "wsa_vk_mesh.h"
#include <android/asset_manager.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct vertex_demo {
    float pos[2], rgb[3], uv[2];
} vertex_demo;

static const vertex_demo quad[] = {
    {{-0.78f,-0.76f},{0.95f,0.35f,0.18f},{0,0}},
    {{ 0.78f,-0.76f},{0.25f,0.95f,0.28f},{1,0}},
    {{ 0.78f, 0.76f},{0.20f,0.45f,1.00f},{1,1}},
    {{-0.78f, 0.76f},{1.00f,0.90f,0.22f},{0,1}}
};
static const uint16_t indices[] = {0,1,2,2,3,0};
enum { VERTEX_COUNT = sizeof(quad)/sizeof(quad[0]),
       INDEX_COUNT = sizeof(indices)/sizeof(indices[0]) };

static VkResult load_shader(VkDevice device,AAssetManager *assets,
                            const char *path,VkShaderModule *out) {
    *out=VK_NULL_HANDLE;
    if(!assets)return VK_ERROR_INITIALIZATION_FAILED;
    AAsset *asset=AAssetManager_open(assets,path,AASSET_MODE_BUFFER);
    if(!asset)return VK_ERROR_INITIALIZATION_FAILED;
    off64_t length=AAsset_getLength64(asset);
    if(length<20||length>1024*1024||(length%4)!=0) {
        AAsset_close(asset);return VK_ERROR_INITIALIZATION_FAILED;
    }
    void *bytes=malloc((size_t)length);
    if(!bytes){AAsset_close(asset);return VK_ERROR_OUT_OF_HOST_MEMORY;}
    size_t got=0;
    while(got<(size_t)length){
        int read=AAsset_read(asset,(uint8_t*)bytes+got,(size_t)length-got);
        if(read<=0)break;
        got+=(size_t)read;
    }
    AAsset_close(asset);
    VkResult result=VK_ERROR_INITIALIZATION_FAILED;
    if(got==(size_t)length&&((uint32_t*)bytes)[0]==0x07230203u){
        VkShaderModuleCreateInfo info={0};
        info.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;
        info.codeSize=(size_t)length;
        info.pCode=(const uint32_t*)bytes;
        result=vkCreateShaderModule(device,&info,NULL,out);
    }
    free(bytes);
    return result;
}

void vk_demo_mesh_destroy(vk_demo_mesh *m) {
    if(!m||!m->device)return;
    if(m->pipeline)vkDestroyPipeline(m->device,m->pipeline,NULL);
    if(m->layout)vkDestroyPipelineLayout(m->device,m->layout,NULL);
    if(m->vertices_indices)vkDestroyBuffer(m->device,m->vertices_indices,NULL);
    if(m->memory)vkFreeMemory(m->device,m->memory,NULL);
    vk_demo_texture_destroy(&m->texture);
    memset(m,0,sizeof(*m));
}

VkResult vk_demo_mesh_create(vk_demo_mesh *m,VkPhysicalDevice physical,
                            VkDevice device,VkRenderPass renderpass,
                            uint32_t width,uint32_t height,
                            AAssetManager *assets,
                            VkQueue queue,uint32_t queue_family,
                            int textured) {
    if(!m||!physical||!device||!renderpass||!width||!height)
        return VK_ERROR_INITIALIZATION_FAILED;
    memset(m,0,sizeof(*m));
    m->device=device;
    m->index_count=INDEX_COUNT;
    m->textured=!!textured;
    VkResult r=VK_ERROR_INITIALIZATION_FAILED;
    VkShaderModule vert=VK_NULL_HANDLE,frag=VK_NULL_HANDLE;
    r=load_shader(device,assets,"wsa_mesh.vert.spv",&vert);
    if(r!=VK_SUCCESS)goto fail;
    r=load_shader(device,assets,m->textured ?
                  "wsa_texture.frag.spv" : "wsa_mesh.frag.spv",&frag);
    if(r!=VK_SUCCESS)goto fail;

    if(m->textured) {
        r=vk_demo_texture_create(&m->texture,physical,device,queue,queue_family);
        if(r!=VK_SUCCESS)goto fail;
    }

    VkPushConstantRange transform={0};
    transform.stageFlags=VK_SHADER_STAGE_VERTEX_BIT;
    transform.offset=0;
    transform.size=sizeof(float)*16;
    VkPipelineLayoutCreateInfo layout={0};
    layout.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
    layout.pushConstantRangeCount=1;
    layout.pPushConstantRanges=&transform;
    if(m->textured) {
        layout.setLayoutCount=1;
        layout.pSetLayouts=&m->texture.layout;
    }
    r=vkCreatePipelineLayout(device,&layout,NULL,&m->layout);
    if(r!=VK_SUCCESS)goto fail;

    VkPipelineShaderStageCreateInfo stages[2]={{0},{0}};
    stages[0].sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[0].stage=VK_SHADER_STAGE_VERTEX_BIT;
    stages[0].module=vert;
    stages[0].pName="main";
    stages[1].sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[1].stage=VK_SHADER_STAGE_FRAGMENT_BIT;
    stages[1].module=frag;
    stages[1].pName="main";

    VkVertexInputBindingDescription binding={0};
    binding.binding=0;binding.stride=sizeof(vertex_demo);
    binding.inputRate=VK_VERTEX_INPUT_RATE_VERTEX;
    VkVertexInputAttributeDescription attr[3]={{0}};
    attr[0].location=0;attr[0].binding=0;
    attr[0].format=VK_FORMAT_R32G32_SFLOAT;
    attr[0].offset=offsetof(vertex_demo,pos);
    attr[1].location=1;attr[1].binding=0;
    attr[1].format=VK_FORMAT_R32G32B32_SFLOAT;
    attr[1].offset=offsetof(vertex_demo,rgb);
    attr[2].location=2;attr[2].binding=0;
    attr[2].format=VK_FORMAT_R32G32_SFLOAT;
    attr[2].offset=offsetof(vertex_demo,uv);
    VkPipelineVertexInputStateCreateInfo vi={0};
    vi.sType=VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO;
    vi.vertexBindingDescriptionCount=1;vi.pVertexBindingDescriptions=&binding;
    vi.vertexAttributeDescriptionCount=3;vi.pVertexAttributeDescriptions=attr;
    VkPipelineInputAssemblyStateCreateInfo assembly={0};
    assembly.sType=VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO;
    assembly.topology=VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
    VkViewport viewport={0};
    viewport.x=0;viewport.y=0;
    viewport.width=(float)width;viewport.height=(float)height;
    viewport.minDepth=0;viewport.maxDepth=1;
    VkRect2D scissors={0};
    scissors.extent=(VkExtent2D){width,height};
    VkPipelineViewportStateCreateInfo vp={0};
    vp.sType=VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO;
    vp.viewportCount=1;vp.pViewports=&viewport;
    vp.scissorCount=1;vp.pScissors=&scissors;
    VkPipelineRasterizationStateCreateInfo raster={0};
    raster.sType=VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO;
    raster.polygonMode=VK_POLYGON_MODE_FILL;
    raster.cullMode=VK_CULL_MODE_NONE;
    raster.frontFace=VK_FRONT_FACE_COUNTER_CLOCKWISE;
    raster.lineWidth=1.0f;
    VkPipelineMultisampleStateCreateInfo multi={0};
    multi.sType=VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO;
    multi.rasterizationSamples=VK_SAMPLE_COUNT_1_BIT;
    VkPipelineColorBlendAttachmentState attachment={0};
    attachment.colorWriteMask=VK_COLOR_COMPONENT_R_BIT|VK_COLOR_COMPONENT_G_BIT|
                              VK_COLOR_COMPONENT_B_BIT|VK_COLOR_COMPONENT_A_BIT;
    VkPipelineColorBlendStateCreateInfo blend={0};
    blend.sType=VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO;
    blend.attachmentCount=1;blend.pAttachments=&attachment;
    VkGraphicsPipelineCreateInfo ci={0};
    ci.sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO;
    ci.stageCount=2;ci.pStages=stages;
    ci.pVertexInputState=&vi;ci.pInputAssemblyState=&assembly;
    ci.pViewportState=&vp;ci.pRasterizationState=&raster;
    ci.pMultisampleState=&multi;ci.pColorBlendState=&blend;
    ci.layout=m->layout;ci.renderPass=renderpass;ci.subpass=0;
    r=vkCreateGraphicsPipelines(device,VK_NULL_HANDLE,1,&ci,NULL,&m->pipeline);
    if(r!=VK_SUCCESS)goto fail;

    const VkDeviceSize vertex_bytes=sizeof(quad);
    const VkDeviceSize index_bytes=sizeof(indices);
    const VkDeviceSize index_offset=(vertex_bytes+3u)&~(VkDeviceSize)3u;
    VkBufferCreateInfo bi={0};
    bi.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    bi.size=index_offset+index_bytes;
    bi.usage=VK_BUFFER_USAGE_VERTEX_BUFFER_BIT|VK_BUFFER_USAGE_INDEX_BUFFER_BIT;
    bi.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
    r=vkCreateBuffer(device,&bi,NULL,&m->vertices_indices);
    if(r!=VK_SUCCESS)goto fail;
    VkMemoryRequirements req;
    vkGetBufferMemoryRequirements(device,m->vertices_indices,&req);
    VkPhysicalDeviceMemoryProperties props;
    vkGetPhysicalDeviceMemoryProperties(physical,&props);
    uint32_t slot=UINT32_MAX;
    for(uint32_t i=0;i<props.memoryTypeCount;i++) {
        if(!(req.memoryTypeBits & (1u<<i)))continue;
        if((props.memoryTypes[i].propertyFlags &
            (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))==
            (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)){
                slot=i;break;
            }
    }
    if(slot==UINT32_MAX){r=VK_ERROR_FEATURE_NOT_PRESENT;goto fail;}
    VkMemoryAllocateInfo alloc={0};
    alloc.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    alloc.allocationSize=req.size;
    alloc.memoryTypeIndex=slot;
    r=vkAllocateMemory(device,&alloc,NULL,&m->memory);
    if(r!=VK_SUCCESS)goto fail;
    r=vkBindBufferMemory(device,m->vertices_indices,m->memory,0);
    if(r!=VK_SUCCESS)goto fail;
    void* mapped=NULL;
    r=vkMapMemory(device,m->memory,0,req.size,0,&mapped);
    if(r!=VK_SUCCESS)goto fail;
    memcpy(mapped,quad,sizeof(quad));
    memcpy((uint8_t*)mapped+index_offset,indices,sizeof(indices));
    vkUnmapMemory(device,m->memory);
    r=VK_SUCCESS;
fail:
    if(vert)vkDestroyShaderModule(device,vert,NULL);
    if(frag)vkDestroyShaderModule(device,frag,NULL);
    if(r!=VK_SUCCESS)vk_demo_mesh_destroy(m);
    return r;
}

void vk_demo_mesh_draw(const vk_demo_mesh *m,VkCommandBuffer cb) {
    if(!m||!m->pipeline)return;
    const float identity[16]={
        1,0,0,0,
        0,1,0,0,
        0,0,1,0,
        0,0,0,1
    };
    VkDeviceSize offset=0;
    const VkDeviceSize index_offset=(sizeof(quad)+3u)&~(VkDeviceSize)3u;
    vkCmdBindPipeline(cb,VK_PIPELINE_BIND_POINT_GRAPHICS,m->pipeline);
    if(m->textured)vkCmdBindDescriptorSets(cb,VK_PIPELINE_BIND_POINT_GRAPHICS,
                         m->layout,0,1,&m->texture.descriptor,0,NULL);
    vkCmdBindVertexBuffers(cb,0,1,&m->vertices_indices,&offset);
    vkCmdBindIndexBuffer(cb,m->vertices_indices,index_offset,VK_INDEX_TYPE_UINT16);
    vkCmdPushConstants(cb,m->layout,VK_SHADER_STAGE_VERTEX_BIT,0,sizeof(identity),identity);
    vkCmdDrawIndexed(cb,m->index_count,1,0,0,0);
}
