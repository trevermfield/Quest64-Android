"""Android swapchain fixes for plume (rt64's Vulkan layer). Usage: python3 -I adapt-plume-surface.py <path to lib/rt64>

Found by running the first APK on the tablet (Galaxy Tab S8, Adreno): the log said
"No compatible surface formats were found." and every vkCreateSwapchainKHR then failed. The device's surface does
not offer the pixel format rt64 asks for, so on Android we fall back to the first format the surface offers and
tell the swapchain which format that really is. Same approach as the Zelda64Recomp-Android fork, ported to
plume's code. Each edit asserts that its anchor exists exactly once.
"""
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / "src/contrib/plume/plume_vulkan.cpp"
text = path.read_text()


def edit(old, new):
    global text
    assert text.count(old) == 1, f"adapt-plume-surface: expected exactly one match: {old[:70]!r} (found {text.count(old)})"
    text = text.replace(old, new)


# 1. Helper: map a Vulkan surface format back to plume's RenderFormat.
edit(
    "    VulkanSwapChain::VulkanSwapChain(VulkanCommandQueue *commandQueue,",
    """#if defined(__ANDROID__)
    static RenderFormat fromVkSurfaceFormat(VkFormat vkFormat, RenderFormat fallback) {
        switch (vkFormat) {
        case VK_FORMAT_R8G8B8A8_UNORM:
            return RenderFormat::R8G8B8A8_UNORM;
        case VK_FORMAT_B8G8R8A8_UNORM:
            return RenderFormat::B8G8R8A8_UNORM;
        default:
            return fallback;
        }
    }
#endif

    VulkanSwapChain::VulkanSwapChain(VulkanCommandQueue *commandQueue,""",
)

# 2. If the requested format is not offered, use the first one the surface offers (Android only).
edit(
    """        if (compatibleSurfaceFormats.empty()) {
            fprintf(stderr, "No compatible surface formats were found.\\n");
            return;
        }
""",
    """#if defined(__ANDROID__)
        if (compatibleSurfaceFormats.empty() && surfaceFormatCount > 0) {
            // Prefer a format we know how to name; otherwise take the first one offered.
            for (uint32_t i = 0; i < surfaceFormatCount; i++) {
                if ((surfaceFormats[i].format == VK_FORMAT_R8G8B8A8_UNORM) || (surfaceFormats[i].format == VK_FORMAT_B8G8R8A8_UNORM)) {
                    compatibleSurfaceFormats.emplace_back(surfaceFormats[i]);
                    break;
                }
            }

            if (compatibleSurfaceFormats.empty()) {
                compatibleSurfaceFormats.emplace_back(surfaceFormats[0]);
            }
        }
#endif

        if (compatibleSurfaceFormats.empty()) {
            fprintf(stderr, "No compatible surface formats were found.\\n");
            return;
        }
""",
)

# 3. Record the format that was really picked.
edit(
    """        if (pickedSurfaceFormat.format == VK_FORMAT_UNDEFINED) {
            pickedSurfaceFormat = compatibleSurfaceFormats[0];
        }
""",
    """        if (pickedSurfaceFormat.format == VK_FORMAT_UNDEFINED) {
            pickedSurfaceFormat = compatibleSurfaceFormats[0];
        }

#if defined(__ANDROID__)
        this->format = fromVkSurfaceFormat(pickedSurfaceFormat.format, this->format);
#endif
""",
)

# 4. On Android the surface dictates the swapchain size when it reports a fixed current extent.
edit(
    """        vkGetPhysicalDeviceSurfaceCapabilitiesKHR(commandQueue->device->physicalDevice, surface, &surfaceCapabilities);
""",
    """        vkGetPhysicalDeviceSurfaceCapabilitiesKHR(commandQueue->device->physicalDevice, surface, &surfaceCapabilities);
#if defined(__ANDROID__)
        if ((surfaceCapabilities.currentExtent.width != UINT32_MAX) && (surfaceCapabilities.currentExtent.height != UINT32_MAX)) {
            width = surfaceCapabilities.currentExtent.width;
            height = surfaceCapabilities.currentExtent.height;
        }
#endif
""",
)

path.write_text(text)
print("plume swapchain adapted for Android")
