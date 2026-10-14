/*
 * Minimal, read-only Vulkan feature/extension census for feasibility of
 * Mesa Zink (OpenGL-on-Vulkan). No game assets, vendor driver overrides,
 * privileged services, VK devices or queues are created.
 *
 * Checks a conservative feature subset of pinned Mesa Zink 26.2.4 GL2.1.
 * Promoted-to-core extensions are accepted at their corresponding Vulkan API
 * level, instead of being wrongly flagged missing from the extension list.
 * A "ready" from this simple probe is NOT a full Vulkan Profile check:
 * VkFormatProperties, limits and full extension feature chains still need
 * the official zink_check_requirements tool for a definitive result.
 */
#define VK_USE_PLATFORM_ANDROID_KHR 1
#include <vulkan/vulkan.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Exact GL2.1 baseline extension names from Mesa 26.2.4
 * src/gallium/drivers/zink/VP_ZINK_requirements.json.
 * Zero core_version means not promoted to Vulkan core.
 * Core promotions avoid false negatives for unadvertised extension names.
 */
static const struct { const char *name; uint32_t core_version; } required_extensions[]={
    {"VK_KHR_maintenance1",VK_API_VERSION_1_1},
    {"VK_KHR_maintenance5",VK_API_VERSION_1_4},
    {"VK_KHR_create_renderpass2",VK_API_VERSION_1_2},
    {"VK_KHR_timeline_semaphore",VK_API_VERSION_1_2},
    {"VK_EXT_custom_border_color",0},
    {"VK_EXT_line_rasterization",0},
    {"VK_KHR_swapchain_mutable_format",0},
    {"VK_KHR_incremental_present",0},
    {"VK_EXT_border_color_swizzle",0},
    {"VK_KHR_descriptor_update_template",VK_API_VERSION_1_1},
    {"VK_KHR_dynamic_rendering",VK_API_VERSION_1_3}
};

static int has_extension(const VkExtensionProperties *ext,uint32_t count,
                         const char *name) {
    for(uint32_t i=0;i<count;i++){
        if(strcmp(ext[i].extensionName,name)==0)return 1;
    }
    return 0;
}
static int inspect_gpu(VkInstance instance,VkPhysicalDevice gpu,uint32_t index){
    VkPhysicalDeviceProperties props;
    VkPhysicalDeviceFeatures feat;
    vkGetPhysicalDeviceProperties(gpu,&props);
    vkGetPhysicalDeviceFeatures(gpu,&feat);
    printf("ZINK_GPU index=%u name=%s api=%u.%u.%u vendor=0x%04x device=0x%04x\n",
        index,props.deviceName,VK_VERSION_MAJOR(props.apiVersion),
        VK_VERSION_MINOR(props.apiVersion),VK_VERSION_PATCH(props.apiVersion),
        props.vendorID,props.deviceID);
    uint32_t n=0;
    VkResult r=vkEnumerateDeviceExtensionProperties(gpu,NULL,&n,NULL);
    if(r!=VK_SUCCESS){
        printf("ZINK_ERROR enumeration=%d\n",(int)r);
        return 2;
    }
    VkExtensionProperties *ext=calloc(n?n:1u,sizeof(*ext));
    if(!ext)return 3;
    r=vkEnumerateDeviceExtensionProperties(gpu,NULL,&n,ext);
    if(r!=VK_SUCCESS){free(ext);return 2;}
    uint32_t missing=0;
#define FEATURE(name) do { int supported=(feat.name!=VK_FALSE); \
    printf("ZINK_FEATURE name=%s supported=%d\n",#name,supported); \
    if(!supported)missing++; \
} while(0)
    FEATURE(robustBufferAccess);
    FEATURE(logicOp);
    FEATURE(fillModeNonSolid);
    FEATURE(alphaToOne);
    FEATURE(shaderClipDistance);
#undef FEATURE
    for(size_t i=0;i<sizeof(required_extensions)/sizeof(required_extensions[0]);i++){
        const char *name=required_extensions[i].name;
        int advertised=has_extension(ext,n,name);
        int via_core=(required_extensions[i].core_version!=0 &&
                props.apiVersion>=required_extensions[i].core_version);
        int supported=advertised||via_core;
        printf("ZINK_EXTENSION name=%s supported=%d advertised=%d core_promoted=%d\n",
               name,supported,advertised,via_core);
        if(!supported)missing++;
    }
    int scalar=(props.apiVersion>=VK_API_VERSION_1_2)||
        has_extension(ext,n,"VK_EXT_scalar_block_layout");
    printf("ZINK_EXTENSION name=scalar_block_layout_available supported=%d\n",scalar);
    if(!scalar)missing++;
    int dri_external=has_extension(ext,n,"VK_KHR_external_memory");
    printf("ZINK_OPTIONAL name=external_memory_for_DRI supported=%d\n",dri_external);
    VkPhysicalDeviceCustomBorderColorFeaturesEXT border={0};
    border.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_CUSTOM_BORDER_COLOR_FEATURES_EXT;
    VkPhysicalDeviceVulkan12Features f12={0};
    f12.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES;
    VkPhysicalDeviceBorderColorSwizzleFeaturesEXT swizzle={0};
    swizzle.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_BORDER_COLOR_SWIZZLE_FEATURES_EXT;
    VkPhysicalDeviceLineRasterizationFeaturesEXT lines={0};
    lines.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_LINE_RASTERIZATION_FEATURES_EXT;
    VkPhysicalDeviceMaintenance5FeaturesKHR maint={0};
    maint.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MAINTENANCE_5_FEATURES_KHR;
    VkPhysicalDeviceDynamicRenderingFeaturesKHR dynamic={0};
    dynamic.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DYNAMIC_RENDERING_FEATURES_KHR;
    border.pNext=&f12;
    f12.pNext=&swizzle;
    swizzle.pNext=&lines;
    lines.pNext=&maint;
    maint.pNext=&dynamic;
    VkPhysicalDeviceFeatures2 f2={0};
    f2.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2;
    f2.pNext=&border;
    /*
     * Vulkan 1.1 promotes Features2, but old Android loaders may require
     * KHR. If unavailable, explicitly mark these as not measured.
     */
    PFN_vkGetPhysicalDeviceFeatures2 get_features2=
         (PFN_vkGetPhysicalDeviceFeatures2)vkGetInstanceProcAddr(
             instance,"vkGetPhysicalDeviceFeatures2");
    if(get_features2){
        get_features2(gpu,&f2);
        printf("ZINK_FEATURE_EXT name=customBorderColorWithoutFormat supported=%d\n",
               border.customBorderColorWithoutFormat?1:0);
        printf("ZINK_FEATURE_EXT name=scalarBlockLayout supported=%d\n",
               f12.scalarBlockLayout?1:0);
        printf("ZINK_FEATURE_EXT name=drawIndirectCount supported=%d\n",
               f12.drawIndirectCount?1:0);
        printf("ZINK_FEATURE_EXT name=timelineSemaphore supported=%d\n",
               f12.timelineSemaphore?1:0);
        printf("ZINK_FEATURE_EXT name=borderColorSwizzleFromImage supported=%d\n",
               swizzle.borderColorSwizzleFromImage?1:0);
        printf("ZINK_FEATURE_EXT name=rectangularLines supported=%d\n",
               lines.rectangularLines?1:0);
        printf("ZINK_FEATURE_EXT name=bresenhamLines supported=%d\n",
               lines.bresenhamLines?1:0);
        printf("ZINK_FEATURE_EXT name=maintenance5 supported=%d\n",
               maint.maintenance5?1:0);
        printf("ZINK_FEATURE_EXT name=dynamicRendering supported=%d\n",
               dynamic.dynamicRendering?1:0);
    }else{
        puts("ZINK_FEATURE_EXT name=customBorderColorWithoutFormat supported=unknown");
        puts("ZINK_FEATURE_EXT name=scalarBlockLayout supported=unknown");
    }
    printf("ZINK_SUMMARY gpu=%u conservative_missing=%u full_profile_checked=0\n",
        index,missing);
    free(ext);
    return 0;
}
int main(void){
    VkApplicationInfo ai={0};
    ai.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO;
    ai.pApplicationName="Zink compatibility census";
    ai.apiVersion=VK_API_VERSION_1_1;
    VkInstanceCreateInfo create={0};
    create.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    create.pApplicationInfo=&ai;
    VkInstance instance=VK_NULL_HANDLE;
    VkResult r=vkCreateInstance(&create,NULL,&instance);
    if(r!=VK_SUCCESS){
        printf("ZINK_ERROR vkCreateInstance=%d\n",(int)r);
        return 2;
    }
    uint32_t n=0;
    r=vkEnumeratePhysicalDevices(instance,&n,NULL);
    if(r!=VK_SUCCESS||n==0){
        printf("ZINK_ERROR enumerate_gpus=%d count=%u\n",(int)r,n);
        vkDestroyInstance(instance,NULL);
        return 2;
    }
    VkPhysicalDevice *gpus=calloc(n,sizeof(*gpus));
    if(!gpus){vkDestroyInstance(instance,NULL);return 3;}
    r=vkEnumeratePhysicalDevices(instance,&n,gpus);
    if(r!=VK_SUCCESS){free(gpus);vkDestroyInstance(instance,NULL);return 2;}
    printf("ZINK_PROBE gpus=%u\n",n);
    for(uint32_t i=0;i<n;i++)inspect_gpu(instance,gpus[i],i);
    free(gpus);
    vkDestroyInstance(instance,NULL);
    return 0;
}
