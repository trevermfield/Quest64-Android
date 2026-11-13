"""Descriptor pool fix for Adreno. Usage: python3 -I adapt-plume-descriptors.py <path to lib/rt64>

Found on the Galaxy Tab S8 (Adreno): pressing Start game printed
  vkAllocateDescriptorSets failed with error code 0xC4642878   (VK_ERROR_OUT_OF_POOL_MEMORY)
for the "bindless" texture sets: one SAMPLED_IMAGE range with layout count 8192, allocated with a variable
descriptor count of only 1 or 4. plume sized each set's private pool from the variable count alone. This driver
accounts for the layout's maximum count instead, so the pool was too small. A pool with room for the layout's
maximum is always valid, so Android now sizes the pool for max(variable count, layout count).
The device's own limits (524288 per type) are far above 8192, so this is not a limit problem.
"""
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / "src/contrib/plume/plume_vulkan.cpp"
text = path.read_text()

old = "            typeCounts[toVk(lastDescriptorRange.type)] += boundlessRangeSize;\n"
new = """#if defined(__ANDROID__)
            // Adreno sizes variable-count allocations by the layout's maximum count; make the pool big enough for that.
            typeCounts[toVk(lastDescriptorRange.type)] += std::max(boundlessRangeSize, lastDescriptorRange.count);
#else
            typeCounts[toVk(lastDescriptorRange.type)] += boundlessRangeSize;
#endif
"""
assert text.count(old) == 1, f"adapt-plume-descriptors: anchor found {text.count(old)} times"
path.write_text(text.replace(old, new))
print("plume boundless descriptor pool sizing adapted for Android")
