#!/usr/bin/env bash
# Downloads the Zelda64Recomp-Android fork at the commit we studied and extracts only the Android
# parts (Gradle project, native lifecycle code, CI helper scripts) into ./overlay. Nothing is built.
# The fork is GPL-licensed (see its COPYING); the files stay out of this repo and are fetched on demand.
set -euo pipefail
FORK_URL=https://github.com/linkzenic/Zelda64Recomp-Android.git
FORK_SHA=41b2bb73443b8fe94ce22ac16416b408466d3bde
OUT="${1:-$(cd "$(dirname "$0")" && pwd)/overlay}"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
git clone --quiet "$FORK_URL" "$tmp/fork"
git -C "$tmp/fork" checkout --quiet "$FORK_SHA"
rm -rf "$OUT"; mkdir -p "$OUT/src"
cp -r "$tmp/fork/android" "$OUT/android"
cp -r "$tmp/fork/src/android" "$OUT/src/android"
cp -r "$tmp/fork/tools" "$OUT/tools"
cp "$tmp/fork/COPYING" "$OUT/COPYING-android-fork"
echo "Overlay written to $OUT"
echo "Zelda-specific names (package io.github.zelda64recomp, ZeldaSDLActivity, bundled_mods/*) still need renaming for Quest 64."
