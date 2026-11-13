#!/usr/bin/env bash
# Generates the ROM-derived C sources the build needs, from YOUR OWN Quest 64 (USA 1.0) ROM, and zips them.
# The output contains game code translated from the ROM: keep it private and never publish or commit it.
# Usage: tools/generate-sources.sh <path/to/quest64_us.z64> [output.zip]
# Needs: git cmake ninja-build zip g++ clang lld (clang must support the mips target, e.g. apt "clang" on Ubuntu).
set -euo pipefail
ROM="${1:?usage: generate-sources.sh <rom.z64> [out.zip]}"
OUT="$(realpath -m "${2:-quest64-generated-sources.zip}")"
ENGINE_REPO=https://github.com/zmarotrix/Quest64-Recomp.git
ENGINE_SHA=e5a3b991e82a87e87c49e4b5f05b182403e541e6
EXPECT_MD5=ea552e33973468233a0712c251abdb6b   # USA 1.0 .z64 (big-endian)
[ "$(md5sum "$ROM" | cut -d' ' -f1)" = "$EXPECT_MD5" ] || { echo "ROM md5 is not the USA 1.0 .z64 ($EXPECT_MD5)." >&2; exit 1; }
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
git clone --quiet "$ENGINE_REPO" "$W/e"; cd "$W/e"; git checkout --quiet "$ENGINE_SHA"
git submodule update --init --depth 1 lib/sf64decomp lib/rt64 Quest64Syms
git submodule update --init --depth 1 lib/N64ModernRuntime
git -C lib/N64ModernRuntime submodule update --init --recursive --depth 1
cp "$ROM" quest64.us.z64
cmake -S lib/N64ModernRuntime/N64Recomp -B "$W/tools" -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build "$W/tools" -j"$(nproc)"
cp "$W/tools/N64Recomp" "$W/tools/RSPRecomp" .
./N64Recomp us.rev0.toml
./RSPRecomp aspMain.toml
(cd patches && make CC=clang LD=ld.lld)
./N64Recomp patches.toml
rm -f "$OUT"; zip -qr "$OUT" RecompiledFuncs RecompiledPatches rsp/aspMain.cpp
echo "Wrote $OUT"; sha256sum "$OUT"
echo "PRIVATE: contains code derived from your ROM. Upload only to a private repo's release asset."
