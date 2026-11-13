#!/usr/bin/env bash
# Makes rt64's CMakeLists.txt build for Android (the newer rt64 that Quest 64 pins already has Android Vulkan
# support in plume; only the build file needs changes). Usage: adapt-rt64.sh <path to lib/rt64>
# Each edit is checked, so a version bump of rt64 that moves things around fails loudly instead of silently.
set -euo pipefail
F="${1:?path to lib/rt64}/CMakeLists.txt"

need() { grep -qF -- "$1" "$F" || { echo "adapt-rt64: expected text not found: $1" >&2; exit 1; }; }

# 1. Shader embedding runs at build time on the BUILD machine: use the host file_to_c, not the Android one.
need "COMMAND file_to_c "
sed -i 's/COMMAND file_to_c /COMMAND ${ZELDA_HOST_FILE_TO_C} /' "$F"

# 2. The root CMake defines an nfd stub on Android; do not pull in the GTK-based desktop file dialog.
need "add_subdirectory(src/contrib/nativefiledialog-extended)"
sed -i 's#^add_subdirectory(src/contrib/nativefiledialog-extended)#if (NOT TARGET nfd)\n    add_subdirectory(src/contrib/nativefiledialog-extended)\nendif()#' "$F"

# 3. The shader compiler runs on the build machine: choose it by HOST cpu, not the Android target cpu.
need 'if (CMAKE_SYSTEM_PROCESSOR STREQUAL "x86_64")'
sed -i 's/if (CMAKE_SYSTEM_PROCESSOR STREQUAL "x86_64")/if (CMAKE_HOST_SYSTEM_PROCESSOR STREQUAL "x86_64")/' "$F"

# 4. Use the SDL Vulkan window path on Android too.
need 'if (CMAKE_SYSTEM_NAME MATCHES "Linux" AND RT64_SDL_WINDOW_VULKAN)'
sed -i 's/if (CMAKE_SYSTEM_NAME MATCHES "Linux" AND RT64_SDL_WINDOW_VULKAN)/if ((CMAKE_SYSTEM_NAME MATCHES "Linux" OR CMAKE_SYSTEM_NAME MATCHES "Android") AND RT64_SDL_WINDOW_VULKAN)/' "$F"

echo "rt64 CMakeLists.txt adapted for Android: $F"

# 5. plume and rt64 window code (see the python file for the details).
python3 -I "$(cd "$(dirname "$0")" && pwd)/adapt-rt64-window.py" "${1}"

# 6. plume swapchain: accept the pixel format the Android surface offers (found by running the first APK).
python3 -I "$(cd "$(dirname "$0")" && pwd)/adapt-plume-surface.py" "${1}"

# 7a. Descriptor pool fix for Adreno (bindless texture sets were allocated with too small a pool).
python3 -I "$(cd "$(dirname "$0")" && pwd)/adapt-plume-descriptors.py" "${1}"

# 7b. Diagnostics for the descriptor-pool failure seen on the first real run past the launcher.
python3 -I "$(cd "$(dirname "$0")" && pwd)/adapt-plume-diagnostics.py" "${1}"

# 7c. Recover the swapchain after the app was in the background (black screen on return).
python3 -I "$(cd "$(dirname "$0")" && pwd)/adapt-plume-resume.py" "${1}"
