// Save states for the Android build: three on-screen buttons (Save, Load, Slot) call the functions at the bottom.
//
// Adapted from the save-state host code of CBFD-Recompiled V0.1.6 (MIT licence; github.com/sciaschi/CBFD-Recompiled,
// its issue #94, and the copy in github.com/DahSidiAbdallah/ConkerBFDReloaded host/src/save_states.cpp). The runtime's
// side is quest64-android-runtime-savestates.patch (ported from that project's n64modernruntime_savestates.patch).
//
// A state is taken at a safe point, when every game thread but the running one waits, and loaded at a safe point
// where every thread is where it was in the state; so a request is done within a frame or so. The game's own save
// (the Controller Pak/EEPROM file) is not in a state. States are in <app folder>/savestates/slotN.state, and
// what happens is in <app folder>/savestates_log.txt and in the app log.
//
// The file: "Q64STATE", the file's version (u32), the program's version (u32 length, text), when it was taken
// (u64, seconds since 1970), then the runtime's state (u32 length, bytes).

#include <android/log.h>
#include <sys/stat.h>
#include <jni.h>

#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "librecomp/game.hpp"
#include "librecomp/save_states.hpp"
#include "ultramodern/ultramodern.hpp"
#include "ultramodern/save_states.hpp"
#include "zelda_config.h"

// Defined with the audio queue in main.cpp (adapt-app-audio.py).
extern std::atomic<int> q64_fast_forward;

namespace {
    using clock = std::chrono::steady_clock;

    constexpr char file_magic[8] = { 'Q', '6', '4', 'S', 'T', 'A', 'T', 'E' };
    constexpr uint32_t file_version = 1;
    constexpr int slot_count = 9;
    constexpr auto give_up_after = std::chrono::seconds(5);

    enum class Request { None, Save, Load };

    std::atomic<Request> request = Request::None;
    std::atomic<int> current_slot = 1;
    std::filesystem::path request_path;
    clock::time_point requested_at;
    std::vector<uint8_t> load_state;
    bool logged_not_now = false;
    std::string last_failure;
    uint32_t attempts = 0;
    bool callback_set = false;

    std::mutex status_mutex;
    std::string status_text;

    void set_status(const std::string& text) {
        std::lock_guard lock{status_mutex};
        status_text = text;
    }

    std::filesystem::path folder() {
        return zelda64::get_app_folder_path() / "savestates";
    }

    std::filesystem::path slot_path(int slot) {
        return folder() / ("slot" + std::to_string(slot) + ".state");
    }

    std::mutex log_mutex;
    void log_line(const char* format, ...) {
        static FILE* file = std::fopen((zelda64::get_app_folder_path() / "savestates_log.txt").string().c_str(), "w");
        std::lock_guard lock{log_mutex};
        va_list args;
        va_start(args, format);
        char line[4096];
        std::vsnprintf(line, sizeof(line), format, args);
        va_end(args);
        std::printf("[savestate] %s\n", line);
        std::fflush(stdout);
        __android_log_print(ANDROID_LOG_INFO, "Q64SaveState", "%s", line);
        if (file != nullptr) {
            std::fprintf(file, "%s\n", line);
            std::fflush(file);
        }
    }

    template <typename T> void put(std::vector<uint8_t>& out, const T& value) {
        const uint8_t* bytes = reinterpret_cast<const uint8_t*>(&value);
        out.insert(out.end(), bytes, bytes + sizeof(T));
    }

    void put_block(std::vector<uint8_t>& out, const void* data, size_t size) {
        put(out, (uint32_t)size);
        const uint8_t* bytes = static_cast<const uint8_t*>(data);
        out.insert(out.end(), bytes, bytes + size);
    }

    // Written on a thread of its own (a state is 8MB), to a temporary file first, so a file is never left half written.
    std::mutex write_mutex;
    void write_state(std::filesystem::path path, std::vector<uint8_t> state, int slot) {
        std::thread([path = std::move(path), state = std::move(state), slot]() {
            std::lock_guard lock{write_mutex};
            std::vector<uint8_t> out;
            out.reserve(state.size() + 256);
            out.insert(out.end(), file_magic, file_magic + sizeof(file_magic));
            put(out, file_version);
            const std::string version = recomp::get_project_version().to_string();
            put_block(out, version.data(), version.size());
            put(out, (uint64_t)std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count());
            put_block(out, state.data(), state.size());
            std::error_code ec;
            std::filesystem::create_directories(path.parent_path(), ec);
            std::filesystem::path temporary = path;
            temporary += ".new";
            {
                std::ofstream file(temporary, std::ios::binary | std::ios::trunc);
                file.write(reinterpret_cast<const char*>(out.data()), (std::streamsize)out.size());
                if (!file.good()) {
                    log_line("couldn't write %s", temporary.string().c_str());
                    set_status("Save failed: could not write the file");
                    return;
                }
            }
            std::filesystem::rename(temporary, path, ec);
            if (ec) {
                log_line("couldn't replace %s (%s)", path.string().c_str(), ec.message().c_str());
                set_status("Save failed: could not write the file");
                return;
            }
            log_line("written %s (%zu bytes)", path.string().c_str(), out.size());
            set_status("Saved to slot " + std::to_string(slot));
        }).detach();
    }

    // Reads a state file. False, with why, if there's none or it isn't one.
    bool read_state(const std::filesystem::path& path, std::vector<uint8_t>& state, std::string& version, std::string& error) {
        std::ifstream file(path, std::ios::binary);
        if (!file) {
            error = "no state at " + path.string();
            return false;
        }
        const std::vector<uint8_t> data((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
        size_t at = 0;
        auto get = [&](void* out, size_t size) {
            if (at + size > data.size()) {
                return false;
            }
            std::memcpy(out, data.data() + at, size);
            at += size;
            return true;
        };
        auto get_block = [&](std::vector<uint8_t>& out) {
            uint32_t size = 0;
            if (!get(&size, sizeof(size)) || at + size > data.size()) {
                return false;
            }
            out.assign(data.begin() + at, data.begin() + at + size);
            at += size;
            return true;
        };
        char magic[sizeof(file_magic)] = {};
        uint32_t version_number = 0;
        uint64_t taken = 0;
        std::vector<uint8_t> version_bytes;
        if (!get(magic, sizeof(magic)) || std::memcmp(magic, file_magic, sizeof(magic)) != 0 ||
            !get(&version_number, sizeof(version_number)) || version_number != file_version ||
            !get_block(version_bytes) || !get(&taken, sizeof(taken)) || !get_block(state)) {
            error = path.string() + " isn't a state this version can load";
            return false;
        }
        version.assign(version_bytes.begin(), version_bytes.end());
        return true;
    }

    void finish() {
        load_state.clear();
        load_state.shrink_to_fit();
        request = Request::None;
        ultramodern::save_states::set_safe_points_wanted(false);
    }

    bool gave_up(const char* what) {
        if (clock::now() - requested_at < give_up_after) {
            return false;
        }
        log_line("%s %s: gave up after %u tries: %s", what, request_path.string().c_str(), attempts, last_failure.c_str());
        set_status(std::string(what == std::string("save") ? "Save" : "Load") + " failed: " + last_failure);
        return true;
    }

    void on_safe_point(uint8_t* rdram) {
        const Request pending = request.load();
        if (pending == Request::None) {
            return;
        }
        attempts++;
        const char* what = pending == Request::Save ? "save" : "load";
        // Only with nothing on its way to the game; checked again, with the timers held, as it's done.
        if (!ultramodern::save_states::is_quiet()) {
            last_failure = "the game was busy";
            if (gave_up(what)) {
                finish();
            }
            return;
        }
        if (pending == Request::Save) {
            std::vector<uint8_t> state;
            std::string error;
            if (!recomp::save_states::capture(rdram, state, error)) {
                last_failure = error;
                if (gave_up(what)) {
                    finish();
                }
                return;
            }
            log_line("saved after %u tries", attempts);
            write_state(request_path, std::move(state), current_slot.load());
            finish();
            return;
        }
        std::string error;
        switch (recomp::save_states::restore(rdram, load_state, error)) {
            case recomp::save_states::LoadResult::Loaded:
                log_line("loaded %s after %u tries", request_path.string().c_str(), attempts);
                set_status("Loaded slot " + std::to_string(current_slot.load()));
                finish();
                break;
            case recomp::save_states::LoadResult::NotNow:
                if (!logged_not_now) {
                    logged_not_now = true;
                    log_line("load %s not now: %s\n%s%s", request_path.string().c_str(), error.c_str(),
                        recomp::save_states::describe_threads(rdram, load_state).c_str(),
                        recomp::save_states::describe_current_threads(rdram).c_str());
                }
                last_failure = error;
                if (gave_up(what)) {
                    finish();
                }
                break;
            case recomp::save_states::LoadResult::Invalid:
                log_line("load %s: %s", request_path.string().c_str(), error.c_str());
                set_status("Load failed: " + error);
                finish();
                break;
        }
    }

    void start(Request what, std::filesystem::path path) {
        if (!callback_set) {
            callback_set = true;
            ultramodern::save_states::set_safe_point_callback(on_safe_point);
        }
        request_path = std::move(path);
        requested_at = clock::now();
        attempts = 0;
        last_failure.clear();
        logged_not_now = false;
        request = what;
        ultramodern::save_states::set_safe_points_wanted(true);
    }
}

extern "C" {

JNIEXPORT void JNICALL Java_io_github_zelda64recomp_ZeldaSDLActivity_nativeSaveState(JNIEnv*, jclass) {
    if (!ultramodern::is_game_started()) {
        set_status("Start the game first");
        return;
    }
    if (request.load() != Request::None) {
        return;
    }
    set_status("Saving to slot " + std::to_string(current_slot.load()) + "...");
    start(Request::Save, slot_path(current_slot));
}

JNIEXPORT void JNICALL Java_io_github_zelda64recomp_ZeldaSDLActivity_nativeLoadState(JNIEnv*, jclass) {
    if (!ultramodern::is_game_started()) {
        set_status("Start the game first");
        return;
    }
    if (request.load() != Request::None) {
        return;
    }
    std::string version, error;
    const auto path = slot_path(current_slot);
    if (!read_state(path, load_state, version, error)) {
        log_line("%s", error.c_str());
        set_status("Slot " + std::to_string(current_slot.load()) + " is empty");
        return;
    }
    log_line("read %s: from version %s, %s", path.string().c_str(), version.c_str(),
        recomp::save_states::same_build(load_state) ? "this build" : "another build");
    set_status("Loading slot " + std::to_string(current_slot.load()) + "...");
    start(Request::Load, path);
}

JNIEXPORT void JNICALL Java_io_github_zelda64recomp_ZeldaSDLActivity_nativeSetStateSlot(JNIEnv*, jclass, jint slot) {
    if (slot >= 1 && slot <= slot_count) {
        current_slot = slot;
    }
}

JNIEXPORT jint JNICALL Java_io_github_zelda64recomp_ZeldaSDLActivity_nativeGetStateSlot(JNIEnv*, jclass) {
    return current_slot.load();
}

// When a slot was saved (seconds since 1970), or 0 if the slot is empty.
JNIEXPORT jlong JNICALL Java_io_github_zelda64recomp_ZeldaSDLActivity_nativeStateSlotTime(JNIEnv*, jclass, jint slot) {
    if (slot < 1 || slot > slot_count) {
        return 0;
    }
    struct stat info;
    if (stat(slot_path(slot).string().c_str(), &info) != 0 || info.st_size <= 0) {
        return 0;
    }
    return (jlong)info.st_mtime;
}

// The four element levels the slot was saved with, as "earth,fire,wind,water", or "" if the slot is empty or unreadable.
// They are read from the game's memory at the end of the state file: gPlayerMainData is at 0x8007BA80 and its
// elements[4] (Earth, Fire, Wind, Water) at +0x24. The memory is kept as the N64 stores it, so a byte's offset is
// its address with the low two bits flipped.
JNIEXPORT jstring JNICALL Java_io_github_zelda64recomp_ZeldaSDLActivity_nativeStateSlotElements(JNIEnv* env, jclass, jint slot) {
    if (slot < 1 || slot > slot_count) {
        return env->NewStringUTF("");
    }
    std::ifstream file(slot_path(slot), std::ios::binary | std::ios::ate);
    if (!file) {
        return env->NewStringUTF("");
    }
    const std::streamoff size = file.tellg();
    if (size < (std::streamoff)recomp::save_states::game_memory_size + 64) {
        return env->NewStringUTF("");
    }
    const std::streamoff memory_start = size - (std::streamoff)recomp::save_states::game_memory_size;
    std::string out;
    for (uint32_t i = 0; i < 4; i++) {
        const uint32_t address = 0x8007BAA4u + i;
        const uint32_t offset = (address & 0x7FFFFFFFu) ^ 3u;
        char value = 0;
        file.seekg(memory_start + offset);
        file.read(&value, 1);
        if (!file.good()) {
            return env->NewStringUTF("");
        }
        out += (i ? "," : "") + std::to_string((int)(unsigned char)value);
    }
    return env->NewStringUTF(out.c_str());
}

// Fast-forward: 1 is normal speed, 2 to 4 are faster. The sound is left out while it is on.
JNIEXPORT void JNICALL Java_io_github_zelda64recomp_ZeldaSDLActivity_nativeSetGameSpeed(JNIEnv*, jclass, jint multiplier) {
    if (multiplier < 1) {
        multiplier = 1;
    }
    q64_fast_forward = multiplier;
    ultramodern::set_speed_multiplier((uint32_t)multiplier);
}

// What the last request did (or is doing), for the message on the screen.
JNIEXPORT jstring JNICALL Java_io_github_zelda64recomp_ZeldaSDLActivity_nativeStateStatus(JNIEnv* env, jclass) {
    std::lock_guard lock{status_mutex};
    return env->NewStringUTF(status_text.c_str());
}

}
