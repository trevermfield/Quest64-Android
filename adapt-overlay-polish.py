"""Quest 64 polish for the Android project. Usage: python3 -I adapt-overlay-polish.py <engine-dir>

1. Replaces the Zelda launcher icons with the Elements gems icon set (research/android-port/icons, made by make-icons.py).
2. Stops the app trying to seed the Zelda "bundled mods": those files no longer ship, and the attempt only logged
   "Failed to extract bundled program assets / FileNotFoundException bundled_mods/ProxyMM_KV.nrm" on every start.
   (It ran after the real program assets were copied, so nothing was lost, but the error was noise.)
3. Gives the app its own version (0.4.2, code 19) instead of the Zelda fork's 0.1.6, which is shown in the launcher.
4. ROM picker: the Zelda fork limits the Android file chooser to a few MIME types, and phones label a .z64 file
   differently depending on the file manager, so the ROM could be greyed out. Show every file instead; the game
   checks the ROM itself.
5. First run: after the user turns on "All files access" the app restarts itself (the Zelda fork asked the user to
   restart by hand, and the game window that was open during the settings trip was dead), and the prompts say what to do.
6. ROM picker: the system file chooser destroys the game's drawing surface and plume then fails to recreate the swapchain
   (vkCreateSwapchainKHR NATIVE_WINDOW_IN_USE, thousands of times: black screen). After a ROM of the right size was copied
   in, restart the app a few seconds later (time for the game to validate and store it).
Each edit asserts its anchor exists once.
"""
import pathlib
import re
import shutil
import sys

engine = pathlib.Path(sys.argv[1])
here = pathlib.Path(__file__).resolve().parent

# 1. icons
res = engine / "android/app/src/main/res"
icons = here / "icons"
count = 0
for png in icons.rglob("*.png"):
    target = res / png.relative_to(icons)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(png, target)
    count += 1
assert count >= 6, f"adapt-overlay-polish: expected the icon set, found {count} files in {icons}"

# 2. Java: do not seed the Zelda bundled mods.
java = engine / "android/app/src/main/java/io/github/zelda64recomp/ZeldaSDLActivity.java"
text = java.read_text()
call = "            seedBundledAndroidMods(appDataDir);\n"
assert text.count(call) == 1, f"adapt-overlay-polish: seed call found {text.count(call)} times"
java.write_text(text.replace(call, "            // Zelda's bundled mods are not shipped with the Quest 64 build, so there is nothing to seed.\n"))

# 3. version
gradle = engine / "android/app/build.gradle"
g = gradle.read_text()
for old, new in (("versionCode 7", "versionCode 19"), ("'0.1.6-android-sdl-probe' : '0.1.6'", "'0.4.2-android-sdl-probe' : '0.4.2'")):
    assert g.count(old) == 1, f"adapt-overlay-polish: {old!r} found {g.count(old)} times"
    g = g.replace(old, new)
gradle.write_text(g)

# 4. ROM picker shows all files
text = java.read_text()
mime = """                intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[] {
                        "application/octet-stream",
                        "application/x-n64-rom",
                        "application/vnd.nintendo.snes.rom"
                });
"""
assert text.count(mime) == 1, f"adapt-overlay-polish: ROM mime filter found {text.count(mime)} times"
java.write_text(text.replace(mime, ""))

# 5. First-run flow: restart by itself once storage access is granted, clearer prompts.
text = java.read_text()
done_re = re.compile(r'Toast\.makeText\(this, "[A-Za-z0-9 ]+ folder is ready\. Restart the app to use it for mods and saves\.", Toast\.LENGTH_LONG\)\.show\(\);')
assert len(done_re.findall(text)) == 1, "adapt-overlay-polish: folder-ready toast not found once"
text = done_re.sub('Toast.makeText(this, "Access granted. Restarting Quest 64 Recompiled...", Toast.LENGTH_LONG).show();\n        restartApp();', text)
ask_re = re.compile(r'Toast\.makeText\(this, "Grant all files access to use /sdcard/[A-Za-z0-9]+ for mods and saves\.", Toast\.LENGTH_LONG\)\.show\(\);')
assert len(ask_re.findall(text)) == 1, "adapt-overlay-polish: access prompt toast not found once"
text = ask_re.sub('Toast.makeText(this, "Turn on \\"Allow access to manage all files\\" for this app, then press Back. The game restarts by itself.", Toast.LENGTH_LONG).show();', text)
anchor = "    private void handlePickedFile(Uri uri) {\n"
assert text.count(anchor) == 1, "adapt-overlay-polish: handlePickedFile anchor"
method = """    private void restartApp() {
        try {
            Intent launch = getPackageManager().getLaunchIntentForPackage(getPackageName());
            if (launch == null) {
                return;
            }
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
            Log.i(TAG, "Storage access granted; restarting so the game uses the public folder");
            startActivity(launch);
            android.os.Process.killProcess(android.os.Process.myPid());
        } catch (Exception e) {
            Log.w(TAG, "Automatic restart failed; restart the app by hand", e);
        }
    }

"""
text = text.replace(anchor, method + anchor)
java.write_text(text)

# 6. Restart after a ROM pick (the picker left the game without a usable surface).
text = java.read_text()
done = "            nativeOnFileDialogResult(true, outputFile.getAbsolutePath());\n"
assert text.count(done) == 1, f"adapt-overlay-polish: ROM result call found {text.count(done)} times"
text = text.replace(done, done + """            if (outputFile.length() == 16L * 1024 * 1024) {
                new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(this::restartApp, 3000);
            }
""")
java.write_text(text)

print(f"polish applied: {count} icon files, bundled-mod seeding off, ROM picker unfiltered, version 0.4.2")
