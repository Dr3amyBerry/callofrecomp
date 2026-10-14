/*
 * Standalone WSA Vulkan swapchain/presentation experiment.
 *
 * This is deliberately NOT a CallofRecomp renderer. It clears an Android
 * swapchain to a solid color without textures, shaders, scene geometry or
 * fixed-function GL translation. Never compare its FPS directly with the game.
 *
 * Build for x86_64 Android with Vulkan/NativeActivity APIs, package into
 * a separate Android app, and keep its private APK out of the project.
 */
#define VK_USE_PLATFORM_ANDROID_KHR 1
#include <vulkan/vulkan.h>
#include <android/native_activity.h>
#include <android/native_window.h>
#include <android/log.h>
#include <pthread.h>
#include <stdatomic.h>
#include <time.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TAG "RigorVkSurface"
#define INFO(...) __android_log_print(ANDROID_LOG_INFO,TAG,__VA_ARGS__)
#define ERROR(...) __android_log_print(ANDROID_LOG_ERROR,TAG,__VA_ARGS__)
#ifndef VK_BENCH_PREFER_IMMEDIATE
#define VK_BENCH_PREFER_IMMEDIATE 0
#endif
#define RIGOR_TEST_SECONDS 17.0
#define RIGOR_WARMUP_SECONDS 2.0
#define MAX_IN_FLIGHT 2

typedef struct {
    ANativeActivity *activity;
    ANativeWindow *window;
    pthread_t thread;
    atomic_int stop;
    int started;
} VkBenchState;

typedef struct {
    VkInstance instance;
    VkSurfaceKHR surface;
    VkPhysicalDevice physical;
    VkDevice device;
    VkQueue queue;
    uint32_t qfamily;
    VkSwapchainKHR swapchain;
    VkRenderPass renderpass;
    VkCommandPool pool;
    VkImage *images;
    VkImageView *views;
    VkFramebuffer *fb;
    VkCommandBuffer *cmds;
    VkFence *image_fences;
    VkFence fences[MAX_IN_FLIGHT];
    VkSemaphore acquired[MAX_IN_FLIGHT];
    VkSemaphore *completed;
    uint32_t count;
    uint32_t width, height;
    VkPresentModeKHR mode;
} VkBenchVk;

static double wall_seconds(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC,&t);
    return (double)t.tv_sec+(double)t.tv_nsec*1.0e-9;
}
static double cpu_seconds(void) {
    struct timespec t;
    clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t);
    return (double)t.tv_sec+(double)t.tv_nsec*1.0e-9;
}
#define REQUIRE(expression, message) do { \
    VkResult rigor_status=(expression); \
    if (rigor_status!=VK_SUCCESS) { \
        ERROR("%s failed: %d",message,(int)rigor_status); goto finish; \
    } \
} while(0)
#define CHECK(expression,message) do { \
    if (!(expression)) {ERROR("%s",message);goto finish;} \
} while(0)

static uint32_t clamp_u32(uint32_t value,uint32_t lo,uint32_t hi) {
    return value<lo?lo:(value>hi?hi:value);
}

static void destroy_vulkan(VkBenchVk *v) {
    if (v->device) vkDeviceWaitIdle(v->device);
    if (v->device) {
        if(v->completed) for(uint32_t i=0;i<v->count;i++)
            if(v->completed[i])vkDestroySemaphore(v->device,v->completed[i],NULL);
        for(int i=0;i<MAX_IN_FLIGHT;i++) {
            if(v->acquired[i])vkDestroySemaphore(v->device,v->acquired[i],NULL);
            if(v->fences[i])vkDestroyFence(v->device,v->fences[i],NULL);
        }
        if(v->fb)for(uint32_t i=0;i<v->count;i++)
            if(v->fb[i])vkDestroyFramebuffer(v->device,v->fb[i],NULL);
        if(v->pool)vkDestroyCommandPool(v->device,v->pool,NULL);
        if(v->views)for(uint32_t i=0;i<v->count;i++)
            if(v->views[i])vkDestroyImageView(v->device,v->views[i],NULL);
        if(v->renderpass)vkDestroyRenderPass(v->device,v->renderpass,NULL);
        if(v->swapchain)vkDestroySwapchainKHR(v->device,v->swapchain,NULL);
        vkDestroyDevice(v->device,NULL);
    }
    if(v->surface&&v->instance)vkDestroySurfaceKHR(v->instance,v->surface,NULL);
    if(v->instance)vkDestroyInstance(v->instance,NULL);
    free(v->images);free(v->views);free(v->fb);free(v->cmds);
    free(v->completed);free(v->image_fences);
}

static void *run_vulkan(void *arg) {
    VkBenchState *ctx=(VkBenchState*)arg;
    VkBenchVk v={0};
    VkApplicationInfo app={0};
    app.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app.pApplicationName="RigorCore Vulkan WSA surface proof";
    app.apiVersion=VK_API_VERSION_1_0;
    const char* iext[]={
        VK_KHR_SURFACE_EXTENSION_NAME,VK_KHR_ANDROID_SURFACE_EXTENSION_NAME
    };
    VkInstanceCreateInfo ici={0};
    ici.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    ici.pApplicationInfo=&app;
    ici.enabledExtensionCount=2;
    ici.ppEnabledExtensionNames=iext;
    REQUIRE(vkCreateInstance(&ici,NULL,&v.instance),"vkCreateInstance");
    VkAndroidSurfaceCreateInfoKHR sci={0};
    sci.sType=VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR;
    sci.window=ctx->window;
    REQUIRE(vkCreateAndroidSurfaceKHR(v.instance,&sci,NULL,&v.surface),
            "vkCreateAndroidSurfaceKHR");
    uint32_t devices_count=0;
    REQUIRE(vkEnumeratePhysicalDevices(v.instance,&devices_count,NULL),
            "vkEnumeratePhysicalDevices");
    CHECK(devices_count>0,"No Vulkan devices in WSA");
    VkPhysicalDevice *devs=(VkPhysicalDevice*)calloc(devices_count,sizeof(*devs));
    CHECK(devs,"OOM device list");
    VkResult rr=vkEnumeratePhysicalDevices(v.instance,&devices_count,devs);
    if(rr!=VK_SUCCESS){free(devs);ERROR("Device list failed %d",rr);goto finish;}
    for(uint32_t i=0;i<devices_count&&!v.physical;i++){
        uint32_t n=0;
        vkGetPhysicalDeviceQueueFamilyProperties(devs[i],&n,NULL);
        VkQueueFamilyProperties *f=(VkQueueFamilyProperties*)calloc(n,sizeof(*f));
        if(!f)break;
        vkGetPhysicalDeviceQueueFamilyProperties(devs[i],&n,f);
        for(uint32_t q=0;q<n;q++){
            VkBool32 present=VK_FALSE;
            if((f[q].queueFlags&VK_QUEUE_GRAPHICS_BIT)&&f[q].queueCount&&
              vkGetPhysicalDeviceSurfaceSupportKHR(devs[i],q,v.surface,&present)==VK_SUCCESS&&present){
                v.physical=devs[i];v.qfamily=q;break;
            }
        }
        free(f);
    }
    free(devs);
    CHECK(v.physical,"No Vulkan graphics+present queue");
    VkPhysicalDeviceProperties props;
    vkGetPhysicalDeviceProperties(v.physical,&props);
    float priority=1.0f;
    VkDeviceQueueCreateInfo qi={0};
    qi.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
    qi.queueFamilyIndex=v.qfamily;qi.queueCount=1;qi.pQueuePriorities=&priority;
    const char* dext[]={VK_KHR_SWAPCHAIN_EXTENSION_NAME};
    VkDeviceCreateInfo di={0};
    di.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
    di.queueCreateInfoCount=1;di.pQueueCreateInfos=&qi;
    di.enabledExtensionCount=1;di.ppEnabledExtensionNames=dext;
    REQUIRE(vkCreateDevice(v.physical,&di,NULL,&v.device),"vkCreateDevice");
    vkGetDeviceQueue(v.device,v.qfamily,0,&v.queue);
    VkSurfaceCapabilitiesKHR cap;
    REQUIRE(vkGetPhysicalDeviceSurfaceCapabilitiesKHR(v.physical,v.surface,&cap),
            "vkGetPhysicalDeviceSurfaceCapabilitiesKHR");
    uint32_t nf=0;
    REQUIRE(vkGetPhysicalDeviceSurfaceFormatsKHR(v.physical,v.surface,&nf,NULL),
            "vkGetPhysicalDeviceSurfaceFormatsKHR");
    CHECK(nf>0,"No Vulkan surface formats");
    VkSurfaceFormatKHR *formats=(VkSurfaceFormatKHR*)calloc(nf,sizeof(*formats));
    CHECK(formats,"OOM surface formats");
    rr=vkGetPhysicalDeviceSurfaceFormatsKHR(v.physical,v.surface,&nf,formats);
    if(rr!=VK_SUCCESS){free(formats);ERROR("Surface formats failed %d",rr);goto finish;}
    VkSurfaceFormatKHR format=formats[0];
    for(uint32_t i=0;i<nf;i++)
        if(formats[i].format==VK_FORMAT_R8G8B8A8_UNORM ||
           formats[i].format==VK_FORMAT_B8G8R8A8_UNORM) {
            format=formats[i];break;
        }
    free(formats);
    uint32_t np=0;
    REQUIRE(vkGetPhysicalDeviceSurfacePresentModesKHR(v.physical,v.surface,&np,NULL),
            "vkGetPhysicalDeviceSurfacePresentModesKHR");
    CHECK(np>0,"No present modes");
    VkPresentModeKHR *modes=(VkPresentModeKHR*)calloc(np,sizeof(*modes));
    CHECK(modes,"OOM present modes");
    rr=vkGetPhysicalDeviceSurfacePresentModesKHR(v.physical,v.surface,&np,modes);
    if(rr!=VK_SUCCESS){free(modes);ERROR("Present modes failed %d",rr);goto finish;}
    int immediate_supported=0;
    for(uint32_t i=0;i<np;i++) if(modes[i]==VK_PRESENT_MODE_IMMEDIATE_KHR)
        immediate_supported=1;
    free(modes);
    v.mode=(VK_BENCH_PREFER_IMMEDIATE&&immediate_supported)?
        VK_PRESENT_MODE_IMMEDIATE_KHR:VK_PRESENT_MODE_FIFO_KHR;
    if(cap.currentExtent.width!=UINT32_MAX) {
        v.width=cap.currentExtent.width;v.height=cap.currentExtent.height;
    } else {
        v.width=clamp_u32((uint32_t)ANativeWindow_getWidth(ctx->window),
                          cap.minImageExtent.width,cap.maxImageExtent.width);
        v.height=clamp_u32((uint32_t)ANativeWindow_getHeight(ctx->window),
                          cap.minImageExtent.height,cap.maxImageExtent.height);
    }
    CHECK(v.width&&v.height,"Surface has zero-sized extent");
    CHECK(cap.supportedUsageFlags&VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
          "Surface does not support color attachment");
    VkCompositeAlphaFlagBitsKHR alpha=VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR;
    if(!(cap.supportedCompositeAlpha&alpha)) {
        VkCompositeAlphaFlagBitsKHR flags[]={
          VK_COMPOSITE_ALPHA_PRE_MULTIPLIED_BIT_KHR,
          VK_COMPOSITE_ALPHA_POST_MULTIPLIED_BIT_KHR,
          VK_COMPOSITE_ALPHA_INHERIT_BIT_KHR};
        for(int i=0;i<3;i++)if(cap.supportedCompositeAlpha&flags[i]){
            alpha=flags[i];break;
        }
    }
    CHECK(cap.supportedCompositeAlpha&alpha,"No composite alpha");
    uint32_t want_images=cap.minImageCount+1;
    if(cap.maxImageCount&&want_images>cap.maxImageCount)want_images=cap.maxImageCount;
    VkSwapchainCreateInfoKHR si={0};
    si.sType=VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR;
    si.surface=v.surface;si.minImageCount=want_images;
    si.imageFormat=format.format;si.imageColorSpace=format.colorSpace;
    si.imageExtent=(VkExtent2D){v.width,v.height};si.imageArrayLayers=1;
    si.imageUsage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;
    si.imageSharingMode=VK_SHARING_MODE_EXCLUSIVE;
    si.preTransform=cap.currentTransform;si.compositeAlpha=alpha;
    si.presentMode=v.mode;si.clipped=VK_TRUE;
    REQUIRE(vkCreateSwapchainKHR(v.device,&si,NULL,&v.swapchain),
            "vkCreateSwapchainKHR");
    REQUIRE(vkGetSwapchainImagesKHR(v.device,v.swapchain,&v.count,NULL),
            "vkGetSwapchainImagesKHR count");
    CHECK(v.count>0&&v.count<=12,"Unsupported swapchain image count");
    v.images=calloc(v.count,sizeof(*v.images));v.views=calloc(v.count,sizeof(*v.views));
    v.fb=calloc(v.count,sizeof(*v.fb));v.cmds=calloc(v.count,sizeof(*v.cmds));
    v.completed=calloc(v.count,sizeof(*v.completed));
    v.image_fences=calloc(v.count,sizeof(*v.image_fences));
    CHECK(v.images&&v.views&&v.fb&&v.cmds&&v.completed&&v.image_fences,
          "OOM swapchain memory");
    REQUIRE(vkGetSwapchainImagesKHR(v.device,v.swapchain,&v.count,v.images),
            "vkGetSwapchainImagesKHR images");

    VkAttachmentDescription att={0};
    att.format=format.format;att.samples=VK_SAMPLE_COUNT_1_BIT;
    att.loadOp=VK_ATTACHMENT_LOAD_OP_CLEAR;att.storeOp=VK_ATTACHMENT_STORE_OP_STORE;
    att.stencilLoadOp=VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    att.stencilStoreOp=VK_ATTACHMENT_STORE_OP_DONT_CARE;
    att.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED;
    att.finalLayout=VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
    VkAttachmentReference ref={0,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
    VkSubpassDescription sub={0};
    sub.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS;
    sub.colorAttachmentCount=1;sub.pColorAttachments=&ref;
    VkSubpassDependency dep={0};
    dep.srcSubpass=VK_SUBPASS_EXTERNAL;dep.dstSubpass=0;
    dep.srcStageMask=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
    dep.dstStageMask=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
    dep.dstAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
    VkRenderPassCreateInfo ri={0};
    ri.sType=VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO;
    ri.attachmentCount=1;ri.pAttachments=&att;
    ri.subpassCount=1;ri.pSubpasses=&sub;
    ri.dependencyCount=1;ri.pDependencies=&dep;
    REQUIRE(vkCreateRenderPass(v.device,&ri,NULL,&v.renderpass),
            "vkCreateRenderPass");

    VkCommandPoolCreateInfo pci={0};
    pci.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
    pci.queueFamilyIndex=v.qfamily;
    REQUIRE(vkCreateCommandPool(v.device,&pci,NULL,&v.pool),"vkCreateCommandPool");
    VkCommandBufferAllocateInfo ai={0};
    ai.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    ai.commandPool=v.pool;ai.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    ai.commandBufferCount=v.count;
    REQUIRE(vkAllocateCommandBuffers(v.device,&ai,v.cmds),"vkAllocateCommandBuffers");
    for(uint32_t i=0;i<v.count;i++) {
        VkImageViewCreateInfo vi={0};
        vi.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
        vi.image=v.images[i];vi.viewType=VK_IMAGE_VIEW_TYPE_2D;
        vi.format=format.format;
        vi.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
        vi.subresourceRange.levelCount=1;vi.subresourceRange.layerCount=1;
        REQUIRE(vkCreateImageView(v.device,&vi,NULL,&v.views[i]),"vkCreateImageView");
        VkFramebufferCreateInfo fi={0};
        fi.sType=VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO;
        fi.renderPass=v.renderpass;fi.attachmentCount=1;fi.pAttachments=&v.views[i];
        fi.width=v.width;fi.height=v.height;fi.layers=1;
        REQUIRE(vkCreateFramebuffer(v.device,&fi,NULL,&v.fb[i]),
                "vkCreateFramebuffer");
        VkCommandBufferBeginInfo bi={0};
        bi.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
        bi.flags=VK_COMMAND_BUFFER_USAGE_SIMULTANEOUS_USE_BIT;
        REQUIRE(vkBeginCommandBuffer(v.cmds[i],&bi),"vkBeginCommandBuffer");
        VkClearValue clear={0};
        clear.color.float32[0]=(i%2)?0.02f:0.09f;
        clear.color.float32[1]=0.26f;
        clear.color.float32[2]=(i%2)?0.38f:0.55f;
        clear.color.float32[3]=1.0f;
        VkRenderPassBeginInfo begin={0};
        begin.sType=VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO;
        begin.renderPass=v.renderpass;begin.framebuffer=v.fb[i];
        begin.renderArea.extent=(VkExtent2D){v.width,v.height};
        begin.clearValueCount=1;begin.pClearValues=&clear;
        vkCmdBeginRenderPass(v.cmds[i],&begin,VK_SUBPASS_CONTENTS_INLINE);
        vkCmdEndRenderPass(v.cmds[i]);
        REQUIRE(vkEndCommandBuffer(v.cmds[i]),"vkEndCommandBuffer");
        VkSemaphoreCreateInfo sem={0};
        sem.sType=VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;
        REQUIRE(vkCreateSemaphore(v.device,&sem,NULL,&v.completed[i]),
                "vkCreateSemaphore present");
    }
    for(int i=0;i<MAX_IN_FLIGHT;i++){
        VkSemaphoreCreateInfo sem={0};
        sem.sType=VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;
        REQUIRE(vkCreateSemaphore(v.device,&sem,NULL,&v.acquired[i]),
                "vkCreateSemaphore acquire");
        VkFenceCreateInfo fence={0};
        fence.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
        fence.flags=VK_FENCE_CREATE_SIGNALED_BIT;
        REQUIRE(vkCreateFence(v.device,&fence,NULL,&v.fences[i]),"vkCreateFence");
    }
    INFO("VK_READY width=%u height=%u gpu=%s image_count=%u fifo=%d immediate_available=%d present_mode=%d",
         v.width,v.height,props.deviceName,v.count,VK_PRESENT_MODE_FIFO_KHR,
         immediate_supported,(int)v.mode);

    double start=wall_seconds(),measure_from=start+RIGOR_WARMUP_SECONDS;
    double finish_time=measure_from+RIGOR_TEST_SECONDS;
    double measure_window=measure_from;
    double cpu_measure_from=0.0;
    uint64_t frames=0,window_frames=0;
    double total_cpu=0.0,window_cpu=0.0;
    double sum_acquire=0.0,sum_present=0.0;
    uint32_t flight=0;
    while(!atomic_load(&ctx->stop)) {
        double now=wall_seconds();
        if (now>=finish_time)break;
        double pcpu=cpu_seconds();
        rr=vkWaitForFences(v.device,1,&v.fences[flight],VK_TRUE,UINT64_MAX);
        if(rr!=VK_SUCCESS){ERROR("wait fence %d",rr);break;}
        uint32_t idx=0;
        double acq_start=wall_seconds();
        rr=vkAcquireNextImageKHR(v.device,v.swapchain,UINT64_MAX,
                                 v.acquired[flight],VK_NULL_HANDLE,&idx);
        double acq_ms=(wall_seconds()-acq_start)*1000;
        if(rr==VK_ERROR_OUT_OF_DATE_KHR){INFO("VK_OUT_OF_DATE at acquire");break;}
        if(rr!=VK_SUCCESS&&rr!=VK_SUBOPTIMAL_KHR){ERROR("vkAcquireNextImageKHR %d",rr);break;}
        if(v.image_fences[idx]) {
            rr=vkWaitForFences(v.device,1,&v.image_fences[idx],VK_TRUE,UINT64_MAX);
            if(rr!=VK_SUCCESS){ERROR("image fence %d",rr);break;}
        }
        v.image_fences[idx]=v.fences[flight];
        rr=vkResetFences(v.device,1,&v.fences[flight]);
        if(rr!=VK_SUCCESS){ERROR("reset fence %d",rr);break;}
        VkPipelineStageFlags stage=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
        VkSubmitInfo submit={0};
        submit.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO;
        submit.waitSemaphoreCount=1;submit.pWaitSemaphores=&v.acquired[flight];
        submit.pWaitDstStageMask=&stage;submit.commandBufferCount=1;
        submit.pCommandBuffers=&v.cmds[idx];
        submit.signalSemaphoreCount=1;submit.pSignalSemaphores=&v.completed[idx];
        rr=vkQueueSubmit(v.queue,1,&submit,v.fences[flight]);
        if(rr!=VK_SUCCESS){ERROR("vkQueueSubmit %d",rr);break;}
        VkPresentInfoKHR present={0};
        present.sType=VK_STRUCTURE_TYPE_PRESENT_INFO_KHR;
        present.waitSemaphoreCount=1;present.pWaitSemaphores=&v.completed[idx];
        present.swapchainCount=1;present.pSwapchains=&v.swapchain;
        present.pImageIndices=&idx;
        double present_start=wall_seconds();
        rr=vkQueuePresentKHR(v.queue,&present);
        double present_ms=(wall_seconds()-present_start)*1000;
        if(rr==VK_ERROR_OUT_OF_DATE_KHR){INFO("VK_OUT_OF_DATE at present");break;}
        if(rr!=VK_SUCCESS&&rr!=VK_SUBOPTIMAL_KHR){ERROR("vkQueuePresentKHR %d",rr);break;}
        double t=wall_seconds();
        double d_cpu=cpu_seconds()-pcpu;
        if(t>=measure_from){
            if(cpu_measure_from==0.0)cpu_measure_from=t;
            frames++;window_frames++;total_cpu+=d_cpu;window_cpu+=d_cpu;
            sum_acquire+=acq_ms;sum_present+=present_ms;
            if(t-measure_window>=1.0){
                double dt=t-measure_window;
                INFO("VK_WINDOW fps=%.3f frames=%llu elapsed=%.3f thread_cpu_ms_per_frame=%.4f",
                     (double)window_frames/dt,(unsigned long long)window_frames,dt,
                     window_frames?window_cpu*1000.0/window_frames:0.0);
                measure_window=t;window_frames=0;window_cpu=0.0;
            }
        }
        flight=(flight+1)%MAX_IN_FLIGHT;
    }
    double elapsed=wall_seconds()-measure_from;
    if(elapsed>0.0&&frames) {
        INFO("VK_RESULT fps=%.3f frames=%llu seconds=%.3f thread_cpu_ms_per_frame=%.5f acquire_wall_ms_per_frame=%.5f present_wall_ms_per_frame=%.5f present_mode=%s resolution=%ux%u",
             (double)frames/elapsed,(unsigned long long)frames,elapsed,
             total_cpu*1000.0/frames,sum_acquire/frames,sum_present/frames,
             v.mode==VK_PRESENT_MODE_IMMEDIATE_KHR?"IMMEDIATE":"FIFO",
             v.width,v.height);
    } else ERROR("VK_RESULT invalid frames=%llu elapsed=%.2f",(unsigned long long)frames,elapsed);
finish:
    destroy_vulkan(&v);
    INFO("VK_STOP finished benchmark; no game files or resources touched");
    return NULL;
}

static void on_window_created(ANativeActivity* activity,ANativeWindow* window) {
    VkBenchState *ctx=(VkBenchState*)activity->instance;
    if (!ctx||ctx->started)return;
    ctx->window=window;
    ANativeWindow_acquire(window);
    atomic_store(&ctx->stop,0);
    ctx->started=1;
    if(pthread_create(&ctx->thread,NULL,run_vulkan,ctx)) {
        ERROR("Failed to start Vulkan thread");
        ANativeWindow_release(window);ctx->window=NULL;ctx->started=0;
    }
}
static void stop_worker(VkBenchState *ctx) {
    if (!ctx||!ctx->started)return;
    atomic_store(&ctx->stop,1);
    pthread_join(ctx->thread,NULL);
    ctx->started=0;
    if(ctx->window){ANativeWindow_release(ctx->window);ctx->window=NULL;}
}
static void on_window_destroyed(ANativeActivity* activity,ANativeWindow* window) {
    (void)window;
    stop_worker((VkBenchState*)activity->instance);
}
static void on_destroy(ANativeActivity* activity) {
    VkBenchState *ctx=(VkBenchState*)activity->instance;
    stop_worker(ctx);
    free(ctx);
    activity->instance=NULL;
}
void ANativeActivity_onCreate(ANativeActivity *activity,
                             void *savedState,size_t savedStateSize) {
    (void)savedState;(void)savedStateSize;
    VkBenchState *ctx=(VkBenchState*)calloc(1,sizeof(*ctx));
    if(!ctx){ERROR("OOM state");return;}
    ctx->activity=activity;
    atomic_init(&ctx->stop,0);
    activity->instance=ctx;
    activity->callbacks->onNativeWindowCreated=on_window_created;
    activity->callbacks->onNativeWindowDestroyed=on_window_destroyed;
    activity->callbacks->onDestroy=on_destroy;
    INFO("VK_INIT NativeActivity created; waiting for Android surface");
}
