/*
 * Android Vulkan availability smoke test; no rendering or project assets.
 * Built with Android NDK and run explicitly in WSA (x86_64).
 * Tests only instance and device enumeration, NOT swapchain/present/performance.
 */
#include <vulkan/vulkan.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned major(uint32_t v){return VK_VERSION_MAJOR(v);}
static unsigned minor(uint32_t v){return VK_VERSION_MINOR(v);}
static unsigned patch(uint32_t v){return VK_VERSION_PATCH(v);}

int main(void) {
    uint32_t api=VK_API_VERSION_1_0;
    VkResult r=vkEnumerateInstanceVersion(&api);
    printf("vkEnumerateInstanceVersion=%d, loader=%u.%u.%u\n",(int)r,
           major(api),minor(api),patch(api));
    if (r!=VK_SUCCESS) return 2;
    VkApplicationInfo app={0};
    app.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app.pApplicationName="callofrecomp-vulkan-wsa-smoke";
    app.apiVersion=VK_API_VERSION_1_0;
    VkInstanceCreateInfo ci={0};
    ci.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    ci.pApplicationInfo=&app;
    VkInstance instance=VK_NULL_HANDLE;
    r=vkCreateInstance(&ci,NULL,&instance);
    printf("vkCreateInstance=%d\n",(int)r);
    if (r!=VK_SUCCESS) return 3;
    uint32_t count=0;
    r=vkEnumeratePhysicalDevices(instance,&count,NULL);
    printf("vkEnumeratePhysicalDevices=%d, device_count=%u\n",(int)r,count);
    if (r!=VK_SUCCESS) {vkDestroyInstance(instance,NULL);return 4;}
    if (count==0) {vkDestroyInstance(instance,NULL);return 5;}
    VkPhysicalDevice* devices=(VkPhysicalDevice*)calloc(count,sizeof(*devices));
    if (!devices) {vkDestroyInstance(instance,NULL);return 6;}
    r=vkEnumeratePhysicalDevices(instance,&count,devices);
    if (r!=VK_SUCCESS) {free(devices);vkDestroyInstance(instance,NULL);return 7;}
    for(uint32_t i=0;i<count;i++) {
        VkPhysicalDeviceProperties p;
        vkGetPhysicalDeviceProperties(devices[i],&p);
        printf("device_%u: name=%s, api=%u.%u.%u, vendor=%04x, device=%04x, type=%u\n",
               i,p.deviceName,major(p.apiVersion),minor(p.apiVersion),patch(p.apiVersion),
               p.vendorID,p.deviceID,p.deviceType);
        uint32_t nf=0;
        vkGetPhysicalDeviceQueueFamilyProperties(devices[i],&nf,NULL);
        VkQueueFamilyProperties* fam=(VkQueueFamilyProperties*)calloc(nf,sizeof(*fam));
        if(fam) {
            vkGetPhysicalDeviceQueueFamilyProperties(devices[i],&nf,fam);
            for(uint32_t j=0;j<nf;j++)
                printf("queue_%u_%u: flags=%u, count=%u\n",i,j,fam[j].queueFlags,fam[j].queueCount);
            free(fam);
        }
        uint32_t ec=0;
        r=vkEnumerateDeviceExtensionProperties(devices[i],NULL,&ec,NULL);
        if (r==VK_SUCCESS&&ec) {
            VkExtensionProperties* ex=(VkExtensionProperties*)calloc(ec,sizeof(*ex));
            if(ex) {
                r=vkEnumerateDeviceExtensionProperties(devices[i],NULL,&ec,ex);
                int swapchain=0;
                if(r==VK_SUCCESS)for(uint32_t e=0;e<ec;e++)
                    if (!strcmp(ex[e].extensionName,VK_KHR_SWAPCHAIN_EXTENSION_NAME))
                        swapchain=1;
                printf("device_%u_extensions=%u VK_KHR_swapchain=%d\n",i,ec,swapchain);
                free(ex);
            }
        }
    }
    free(devices);
    vkDestroyInstance(instance,NULL);
    return 0;
}
