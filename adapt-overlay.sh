#!/usr/bin/env bash
# Adapts the Zelda64Recomp-Android overlay (already copied into the engine checkout) for Quest 64.
# Usage: adapt-overlay.sh <engine-dir>
# Internal identifiers (java package io.github.zelda64recomp, class ZeldaSDLActivity, ZELDA_* CMake and env names)
# are left alone on purpose so the first build changes as little as possible. Only user-visible names,
# the storage folder, and Zelda-only content are changed.
set -euo pipefail
E="${1:?engine dir}"

# Zelda mods bundled into the APK: not wanted.
rm -rf "$E/android/app/src/main/assets/bundled_mods"

# Quest 64 has no njpgdsp RSP microcode; the Zelda build checked for it.
sed -i "/rsp\/njpgdspMain.cpp/d" "$E/android/app/build.gradle"

# Names shown to the user and the public storage folder.
files=$(grep -rlE "Zelda64( |Recompiled|\"| folder)|/sdcard/Zelda64" "$E/android" "$E/src/android" --include=*.java --include=*.xml --include=*.cpp --include=*.gradle || true)
for f in $files; do
  sed -i \
    -e 's/Zelda64 Recompiled/Quest 64 Recompiled/g' \
    -e 's/Zelda64Recompiled/Quest64Recompiled/g' \
    -e 's#/sdcard/Zelda64#/sdcard/Quest64#g' \
    -e 's/PUBLIC_FOLDER_NAME = "Zelda64"/PUBLIC_FOLDER_NAME = "Quest64"/' \
    -e 's/Zelda64 folder/Quest64 folder/g' \
    "$f"
done
sed -i "s/rootProject.name = 'Zelda64RecompAndroid'/rootProject.name = 'Quest64RecompAndroid'/" "$E/android/settings.gradle"
# Quest 64 icon, no Zelda bundled-mod seeding, own version number.
python3 -I "$(cd "$(dirname "$0")" && pwd)/adapt-overlay-polish.py" "$E"

# Crash handler records fault address and registers (debugging aid).
python3 -I "$(cd "$(dirname "$0")" && pwd)/adapt-overlay-crashinfo.py" "$E"

# Fixed debug signing key, so each new build installs over the previous one.
python3 -I "$(cd "$(dirname "$0")" && pwd)/adapt-overlay-signing.py" "$E"

# Save state buttons and their native code.
python3 -I "$(cd "$(dirname "$0")" && pwd)/adapt-overlay-savestates.py" "$E"

# Menu (touch-control options, backup), fast-forward, auto-hide for gamepads.
python3 -I "$(cd "$(dirname "$0")" && pwd)/adapt-overlay-options.py" "$E"

echo "Overlay adapted for Quest 64 in $E"
