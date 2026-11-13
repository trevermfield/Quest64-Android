"""Android window edits for rt64 and plume. Usage: python3 -I adapt-rt64-window.py <path to lib/rt64>

1. plume: let the SDL Vulkan option apply on Android like on Linux.
2. plume: make the SDL window type win over the Android native-window type (plume's Vulkan code already
   prefers SDL when it is enabled, so the two must agree).
3. rt64: the Android window-bounds branch was never implemented; use SDL's display mode (as the Zelda fork does).
Each edit asserts that its target text exists, so a version bump fails loudly.
"""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])


def edit(rel, old, new):
    path = root / rel
    text = path.read_text()
    assert text.count(old) == 1, f"adapt-rt64-window: expected exactly one match in {rel}: {old[:60]!r}"
    path.write_text(text.replace(old, new))


edit(
    "src/contrib/plume/CMakeLists.txt",
    'string(COMPARE EQUAL ${CMAKE_SYSTEM_NAME} "Linux" IS_LINUX)',
    'string(COMPARE EQUAL ${CMAKE_SYSTEM_NAME} "Linux" IS_LINUX)\n'
    'if (CMAKE_SYSTEM_NAME STREQUAL "Android")\n'
    '    set(IS_LINUX TRUE)\n'
    'endif()',
)

edit(
    "src/contrib/plume/plume_render_interface_types.h",
    "#elif defined(__ANDROID__)\n    typedef ANativeWindow* RenderWindow;\n"
    "#elif defined(PLUME_SDL_VULKAN_ENABLED)\n    typedef SDL_Window *RenderWindow;",
    "#elif defined(PLUME_SDL_VULKAN_ENABLED)\n    typedef SDL_Window *RenderWindow;\n"
    "#elif defined(__ANDROID__)\n    typedef ANativeWindow* RenderWindow;",
)

android_bounds = """        if (SDL_VideoInit(nullptr) != 0) {
            printf("Failed to init SDL2 video: %s\\n", SDL_GetError());
            assert(false && "Failed to init SDL2 video");
            return;
        }
        SDL_DisplayMode dm;
        if (SDL_GetCurrentDisplayMode(0, &dm) != 0) {
            printf("Failed to get SDL2 current display mode: %s\\n", SDL_GetError());
            assert(false && "Failed to get SDL2 current display mode");
            return;
        }
        bounds.left = 0;
        bounds.top = 0;
        bounds.width = dm.w;
        bounds.height = dm.h;
"""

edit(
    "src/hle/rt64_application_window.cpp",
    '        static_assert(false && "Android unimplemented");\n#   elif defined(__linux__) || defined(__APPLE__)',
    android_bounds + "#   elif defined(__linux__) || defined(__APPLE__)",
)

print("plume and rt64 window code adapted for Android")
