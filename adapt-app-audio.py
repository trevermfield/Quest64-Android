"""Audio after the app was in the background. Usage: python3 -I adapt-app-audio.py <engine-dir>

Symptom: after switching to another app and back the sound is distorted. SDL pauses the audio device while the app is in
the background but the game keeps producing sound, so SDL's queue grows without limit. The engine's latency guard shifts
by (queued microseconds / 100000), which is undefined for 32 or more and indexes far outside the buffer for large
values: noise. Fix: when more than 400 ms are queued, drop the queue first (never audible in normal play, where
the queue stays near 100 ms), and cap the shift.
"""
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / "src/main/main.cpp"
text = path.read_text()
old = "    uint32_t skip_factor = cur_queued_microseconds / 100000;\n"
new = """    if (cur_queued_microseconds > 400000) {
        // The device was paused (app in the background) or fell far behind: start over instead of piling up sound.
        SDL_ClearQueuedAudio(audio_device);
        cur_queued_microseconds = 0;
    }
    uint32_t skip_factor = cur_queued_microseconds / 100000;
    if (skip_factor > 4) {
        skip_factor = 4;
    }
"""
assert text.count(old) == 1, f"adapt-app-audio: anchor found {text.count(old)} times"
path.write_text(text.replace(old, new))
print("audio queue overflow guard added")

# Part 2: while the app is not in front, do not feed the (paused) audio device at all, and start from an empty queue
# when the app returns. Without this, the sound that the running game made in the background is still queued on return
# and the latency guard above thins it out by dropping samples (audible as chirping/distorted sound for a while).
text = path.read_text()
decl = "void queue_samples(int16_t* audio_data, size_t sample_count) {\n"
assert text.count(decl) == 1, f"adapt-app-audio: queue_samples anchor found {text.count(decl)} times"
text = text.replace(decl, """// Set from Java (ZeldaSDLActivity.nativeSetAppAudioActive) when the app leaves or returns to the front.
std::atomic<int> q64_audio_active{1};
// Fast-forward factor (1 = normal): the game makes sound faster than it can be played, so it is left out meanwhile.
std::atomic<int> q64_fast_forward{1};
static bool q64_audio_was_off = false;

""" + decl + """    if (q64_audio_active.load() == 0 || q64_fast_forward.load() > 1) {
        q64_audio_was_off = true;
        return;
    }
    if (q64_audio_was_off) {
        q64_audio_was_off = false;
        SDL_ClearQueuedAudio(audio_device);
    }
""")
inc = "#include <cstdio>\n"
assert text.count(inc) == 1
text = text.replace(inc, inc + "#include <atomic>\n", 1)
path.write_text(text)

life = pathlib.Path(sys.argv[1]) / "src/android/android_lifecycle.cpp"
t = life.read_text()
old = """    jboolean active) {
    __android_log_print(ANDROID_LOG_VERBOSE, kLogTag, "audio active=%d", active ? 1 : 0);
"""
assert t.count(old) == 1, f"adapt-app-audio: lifecycle anchor found {t.count(old)} times"
t = t.replace(old, old + "    q64_audio_active.store(active ? 1 : 0);\n")
inc2 = "#include <android/log.h>\n"
assert t.count(inc2) == 1
t = t.replace(inc2, inc2 + "#include <atomic>\nextern std::atomic<int> q64_audio_active;\n", 1)
life.write_text(t)
print("audio paused while the app is in the background")
