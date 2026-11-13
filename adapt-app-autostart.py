"""Debug aid: start the game without touching the launcher on Android. Usage: python3 -I adapt-app-autostart.py <engine-dir>
(run after quest64-android-app.patch)

On Android there is no command line, so --quick-start (which skips the launcher; see draw_hook in ui_state.cpp)
cannot be used, and input injected over adb does not reach the launcher menu. If a file named "autostart" exists in the
app folder (/sdcard/Quest64/autostart) this sets the same quick-start flag, so a script can launch the app and test a
game start. Delete the file for normal play.
"""
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / "src/main/main.cpp"
text = path.read_text()

anchor = "    // --quick-start skips the launcher (see draw_hook in ui_state.cpp).\n"
assert text.count(anchor) == 1, f"adapt-app-autostart: anchor found {text.count(anchor)} times"
block = """#if defined(__ANDROID__)
    // Debug aid: a file named "autostart" in the app folder starts the game without using the launcher menu.
    if (const char* autostart_folder = std::getenv("APP_FOLDER_PATH")) {
        std::error_code autostart_error;
        if (std::filesystem::exists(std::filesystem::path{autostart_folder} / "autostart", autostart_error)) {
            recompui::quick_start_requested = true;
        }
    }
#endif
"""
path.write_text(text.replace(anchor, block + anchor))
print("Android autostart marker file support added")
