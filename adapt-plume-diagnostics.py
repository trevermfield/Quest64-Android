"""Diagnostics for the Android descriptor-pool failure. Usage: python3 -I adapt-plume-diagnostics.py <path to lib/rt64>

First run past the launcher on the Galaxy Tab S8 printed "vkAllocateDescriptorSets failed with error code
0xC4642878" (= VK_ERROR_OUT_OF_POOL_MEMORY, -1000069000) and then crashed with SIGSEGV. This adds a printout of the
failing set's layout (range types, counts, boundless size) and the GPU's update-after-bind descriptor limits, so the next
run shows which set does not fit. Diagnostic only: it does not change behaviour. Android only.
"""
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / "src/contrib/plume/plume_vulkan.cpp"
text = path.read_text()

old = """        VkResult res = vkAllocateDescriptorSets(device->vk, &allocateInfo, &vk);
        if (res != VK_SUCCESS) {
            fprintf(stderr, "vkAllocateDescriptorSets failed with error code 0x%X.\\n", res);
            return;
        }
"""
new = """        VkResult res = vkAllocateDescriptorSets(device->vk, &allocateInfo, &vk);
        if (res != VK_SUCCESS) {
            fprintf(stderr, "vkAllocateDescriptorSets failed with error code 0x%X.\\n", res);
#if defined(__ANDROID__)
            fprintf(stderr, "  [diag] set: lastRangeIsBoundless=%d boundlessRangeSize=%u ranges=%u\\n",
                int(desc.lastRangeIsBoundless), boundlessRangeSize, desc.descriptorRangesCount);
            for (uint32_t i = 0; i < desc.descriptorRangesCount; i++) {
                const RenderDescriptorRange &r = desc.descriptorRanges[i];
                fprintf(stderr, "  [diag] range %u: renderType=%d vkType=%d binding=%u count=%u immutable=%d\\n",
                    i, int(r.type), int(toVk(r.type)), r.binding, r.count, int(r.immutableSampler != nullptr));
            }
            for (const auto &it : typeCounts) {
                fprintf(stderr, "  [diag] pool size: vkType=%d count=%u\\n", int(it.first), it.second);
            }
            VkPhysicalDeviceDescriptorIndexingProperties idxProps = {};
            idxProps.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DESCRIPTOR_INDEXING_PROPERTIES;
            VkPhysicalDeviceProperties2 props2 = {};
            props2.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2;
            props2.pNext = &idxProps;
            vkGetPhysicalDeviceProperties2(device->physicalDevice, &props2);
            fprintf(stderr, "  [diag] limits: inAllPools=%u perStageSamplers=%u perStageSampledImages=%u perStageUniformBuffers=%u perStageStorageBuffers=%u perStageStorageImages=%u\\n",
                idxProps.maxUpdateAfterBindDescriptorsInAllPools, idxProps.maxPerStageDescriptorUpdateAfterBindSamplers,
                idxProps.maxPerStageDescriptorUpdateAfterBindSampledImages, idxProps.maxPerStageDescriptorUpdateAfterBindUniformBuffers,
                idxProps.maxPerStageDescriptorUpdateAfterBindStorageBuffers, idxProps.maxPerStageDescriptorUpdateAfterBindStorageImages);
            fprintf(stderr, "  [diag] limits: setSamplers=%u setSampledImages=%u setUniformBuffers=%u setStorageBuffers=%u setStorageImages=%u\\n",
                idxProps.maxDescriptorSetUpdateAfterBindSamplers, idxProps.maxDescriptorSetUpdateAfterBindSampledImages,
                idxProps.maxDescriptorSetUpdateAfterBindUniformBuffers, idxProps.maxDescriptorSetUpdateAfterBindStorageBuffers,
                idxProps.maxDescriptorSetUpdateAfterBindStorageImages);
            fflush(stderr);
#endif
            return;
        }
"""
assert text.count(old) == 1, f"adapt-plume-diagnostics: anchor found {text.count(old)} times"
path.write_text(text.replace(old, new))
print("plume descriptor diagnostics added")
