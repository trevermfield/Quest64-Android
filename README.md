# Quest 64 Recompiled for Android (unofficial, experimental)

Patches and build scripts that make [Quest 64: Recompiled](https://github.com/zmarotrix/Quest64-Recomp)
(the engine fork used by Eltale Odyssey, itself built on [Rainchus's Quest 64 recomp](https://github.com/Rainchus/Quest64-Recomp))
run natively on Android, without Winlator.

Tested on a Galaxy Tab S8 (Snapdragon 8 Gen 1 / Adreno) and a Galaxy S25 Ultra: the vanilla game and the Eltale Odyssey
mod run. Not tested: Bluetooth gamepads on every device, other brands of phone, long play sessions.

This is an unofficial community project. It is not affiliated with or endorsed by the Quest 64 recomp authors.

**AI disclosure:** most of the code in this repository was written with AI assistance (Claude Code) and then tested on
real devices by the author. Read the patches before you trust them; they are small and commented.

## What it adds

- The game runs as a normal Android app (arm64, Vulkan), with touch controls and Bluetooth/USB gamepad support through SDL.
- In-app ROM picker. The first start asks for "All files access" and restarts itself once it is granted.
- Leaving the app and coming back keeps the game going (screen and sound are rebuilt).
- **Save states**: 9 slots, with the elements' levels and the time shown for each slot. The game's own saves are separate
  and keep working.
- **Fast-forward** (2x to 4x, sound off while it is on).
- **Menu button**: save states, fast-forward, touch-control opacity, size and position, hide the touch controls when a
  gamepad is connected, and a one-tap backup of saves and states to Downloads.
- Mods (`.nrm`) from the Mods menu; code mods run through the live recompiler, so no Android-specific mod build is needed.

## Important: no game files here, and builds must stay private

This repository contains **only patches and scripts**: no ROM, no game code, no APK.

Building needs C code translated from a Quest 64 ROM by N64Recomp. That output is derived from the game and is
copyrighted, so **neither it nor any APK built from it is published here** (this includes GitHub Actions artifacts of a
public repository, which any signed-in GitHub user can download). Build only in a **private** copy. The workflow refuses
to run in a public repository.

You need your own legally obtained Quest 64 (USA 1.0) ROM, `.z64`, md5 `ea552e33973468233a0712c251abdb6b`.

## Credits and licenses

GPL-3.0 (see `LICENSE`). Built on:
- [Quest64-Recomp](https://github.com/zmarotrix/Quest64-Recomp) / [Rainchus/Quest64-Recomp](https://github.com/Rainchus/Quest64-Recomp), the recompilation project,
- [N64: Recompiled](https://github.com/N64Recomp/N64Recomp), [N64ModernRuntime](https://github.com/N64Recomp/N64ModernRuntime), [RT64](https://github.com/rt64/rt64),
- [linkzenic/Zelda64Recomp-Android](https://github.com/linkzenic/Zelda64Recomp-Android), whose Android project (Gradle build, SDL activity, touch overlay) is fetched at build time and adapted. Its code is not stored here.
- [CBFD-Recompiled](https://github.com/sciaschi/CBFD-Recompiled) (MIT licence), whose save-state runtime patch and host code were ported to this runtime
  (`quest64-android-runtime-savestates.patch`, `savestates/q64_save_states.cpp`).

## How to build (your own private copy)

1. Create a **private** GitHub repository and push this repository's contents to it.
2. Make the generated sources from your ROM on any Linux machine (or Ubuntu in Termux/proot):
   `tools/generate-sources.sh /path/to/quest64_us.z64`. This builds N64Recomp, runs it on your ROM and writes
   `quest64-generated-sources.zip`.
3. In your private repo, create a release named/tagged `android-generated-sources` and attach that zip.
4. Optional: set the repository variable `Q64_APP_ID` (default `org.quest64recomp.android`). For a debug build that updates in place, set the
   secret `Q64_DEBUG_KEYSTORE_B64` (base64 of a PKCS12 debug keystore, password `android`, alias `androiddebugkey`). For a signed release
   build set `Q64_RELEASE_KEYSTORE_B64`, `Q64_RELEASE_KEYSTORE_PASSWORD`, `Q64_RELEASE_KEY_ALIAS`, `Q64_RELEASE_KEY_PASSWORD` and run the
   workflow with **release** on. Keep your release key safe: if it is lost, installs can no longer be updated.
5. Run the **Build Android APK** workflow. The APK is in the run's artifacts (about 10 to 20 minutes).

## Using the app

1. Install the APK and open it. Allow **All files access** when asked (it is needed for the `/sdcard/Quest64` folder that holds
   your ROM copy, mods and saves). The app restarts itself.
2. Choose **Select ROM** and pick your Quest 64 ROM. The app copies it into its own folder and checks it.
3. Press **Start game**. Optional mods go in the Mods menu or `/sdcard/Quest64/mods/`.
4. Saves: `/sdcard/Quest64/saves`; save states: `/sdcard/Quest64/savestates`. Log: `/sdcard/Quest64/Quest64Recompiled.log`; crash report next to it.

Save states restore the game's own memory only. Mods keep some state outside it, so a mod may be out of sync after loading a state;
vanilla is the safest.

## What the patches do

| File | Purpose |
|---|---|
| `quest64-android-app.patch` | Android changes to the engine's app code and CMake (shared library target, 720p/ARM defaults, UI). |
| `quest64-android-runtime-*.patch`, `adapt-runtime-mprotect.py` | Runtime: mod library paths, 720p/1080p resolution options, patching recompiled code under Android's SELinux (pages stay writable and executable, because Android refuses to re-add execute permission after a write), and save states (with an adjustable frame pace for fast-forward). |
| `quest64-android-slotmap.patch` | `posix_memalign` allocator for Android. |
| `adapt-rt64*.sh/py`, `adapt-plume-*.py` | RT64/plume: SDL window on Android, surface-format fallback, Adreno descriptor-pool sizing (without it, Vulkan returns `OUT_OF_POOL_MEMORY`), and rebuilding the Vulkan surface and swapchain after the app comes back to the front. |
| `adapt-overlay*.sh/py` | Adapts the fetched Zelda Android project: Quest 64 names, icon, version, signing, ROM picker, first-run flow, crash report, save-state and Menu buttons. |
| `adapt-app-audio.py` | Sound while the app is in the background or fast-forwarding: nothing is queued, and the queue is emptied when it comes back (otherwise distorted sound). |
| `adapt-app-autostart.py` | Debug aid: a file `/sdcard/Quest64/autostart` starts the game without the menu. |
| `savestates/q64_save_states.cpp` | Native side of save states, slot information and the speed control. |

Engine pins: `zmarotrix/Quest64-Recomp` at `e5a3b991e82a87e87c49e4b5f05b182403e541e6`; Android project from
`linkzenic/Zelda64Recomp-Android` at `41b2bb73443b8fe94ce22ac16416b408466d3bde`. Other versions may need the patches updated.

## Known limits

- Early beta. Tested on two Samsung devices (Adreno).
- Internal names from the Zelda project remain (`ZeldaSDLActivity`, `io.github.zelda64recomp`).
- The icon is built from the engine's own `icons/512.png`.
- Save states and mods: see above.
