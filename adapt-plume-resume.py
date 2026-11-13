"""Swapchain recovery after the app was in the background. Usage: python3 -I adapt-plume-resume.py <path to lib/rt64>

Symptom on the Galaxy S25 Ultra: leave the game for another app, come back, and the screen is black until the app is
restarted. The same thing happened right after the ROM picker (which is also a separate screen on top of the game).
Android destroys the game's window surface when the app is not in front and gives it a new one when it returns.
plume kept using the old VkSurfaceKHR, so vkCreateSwapchainKHR failed forever with SURFACE_LOST (0xC4653600) and then
NATIVE_WINDOW_IN_USE (0xC46535FF): thousands of attempts, black screen. Two flaws:
  1. A failed vkCreateSwapchainKHR left the retired swapchain (which still holds the window) leaked and unusable.
  2. The surface was never rebuilt from the window SDL now provides.
On Android, when creating the swapchain fails, destroy the old swapchain, rebuild the surface with
SDL_Vulkan_CreateSurface, and try once more. Other platforms are unchanged.
"""
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / "src/contrib/plume/plume_vulkan.cpp"
text = path.read_text()

old = """        VkResult res = vkCreateSwapchainKHR(commandQueue->device->vk, &createInfo, nullptr, &vk);
        if (res != VK_SUCCESS) {
            fprintf(stderr, "vkCreateSwapchainKHR failed with error code 0x%X.\\n", res);
            return false;
        }
"""
new = """#if defined(__ANDROID__) && defined(PLUME_SDL_VULKAN_ENABLED)
        VkSwapchainKHR previousSwapchain = vk;
        VkResult res = vkCreateSwapchainKHR(commandQueue->device->vk, &createInfo, nullptr, &vk);
        if (res != VK_SUCCESS) {
            // While the app is in the background Android has taken the window away: SDL's native window is null and
            // creating a surface from it crashes inside libvulkan (CreateAndroidSurfaceKHR). Wait until a window exists.
            SDL_SysWMinfo androidWmInfo;
            SDL_VERSION(&androidWmInfo.version);
            if (SDL_GetWindowWMInfo(renderWindow, &androidWmInfo) == SDL_FALSE || androidWmInfo.info.android.window == nullptr) {
                vk = previousSwapchain;
                return false;
            }
            fprintf(stderr, "vkCreateSwapchainKHR failed with error code 0x%X; rebuilding the surface.\\n", res);
            // The window may have been replaced (app left and came back). Drop the old swapchain, which still holds
            // the old window, then make a new surface from the window SDL has now and try once more.
            if (previousSwapchain != VK_NULL_HANDLE) {
                vkDestroySwapchainKHR(commandQueue->device->vk, previousSwapchain, nullptr);
            }
            vk = VK_NULL_HANDLE;
            createInfo.oldSwapchain = VK_NULL_HANDLE;
            VulkanInterface *androidInterface = commandQueue->device->renderInterface;
            if (surface != VK_NULL_HANDLE) {
                vkDestroySurfaceKHR(androidInterface->instance, surface, nullptr);
                surface = VK_NULL_HANDLE;
            }
            if (SDL_Vulkan_CreateSurface(renderWindow, androidInterface->instance, &surface) == SDL_FALSE) {
                fprintf(stderr, "SDL_Vulkan_CreateSurface failed with error %s.\\n", SDL_GetError());
                surface = VK_NULL_HANDLE;
                return false;
            }
            createInfo.surface = surface;
            res = vkCreateSwapchainKHR(commandQueue->device->vk, &createInfo, nullptr, &vk);
            if (res != VK_SUCCESS) {
                vk = VK_NULL_HANDLE;
                fprintf(stderr, "vkCreateSwapchainKHR failed again with error code 0x%X.\\n", res);
                return false;
            }
            fprintf(stderr, "Swapchain recreated on a new surface.\\n");
        }
#else
        VkResult res = vkCreateSwapchainKHR(commandQueue->device->vk, &createInfo, nullptr, &vk);
        if (res != VK_SUCCESS) {
            fprintf(stderr, "vkCreateSwapchainKHR failed with error code 0x%X.\\n", res);
            return false;
        }
#endif
"""
assert text.count(old) == 1, f"adapt-plume-resume: anchor found {text.count(old)} times"
text = text.replace(old, new)
inc = '#include "plume_vulkan.h"\n'
assert text.count(inc) == 1, "adapt-plume-resume: include anchor"
text = text.replace(inc, inc + '#if defined(__ANDROID__) && defined(PLUME_SDL_VULKAN_ENABLED)\n#include <SDL_syswm.h>\n#endif\n')
path.write_text(text)
print("plume swapchain recovery after surface loss added for Android")
