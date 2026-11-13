"""Make the Android crash handler record where and why it crashed. Usage: python3 -I adapt-overlay-crashinfo.py <engine-dir>

The Zelda fork's handler only wrote "Native crash signal 11". For debugging the first Eltale Odyssey run (SIGSEGV in
guPerspective right after Start game) we need the fault address, the program counter and the registers, so this
switches the handlers to sigaction/SA_SIGINFO and writes them to the crash file and to logcat (tag ZeldaNative).
Not async-signal-safe in the strict sense (uses snprintf); acceptable for crash diagnostics. aarch64 only.
"""
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / "src/android/android_logging.cpp"
text = path.read_text()


def edit(old, new):
    global text
    assert text.count(old) == 1, f"adapt-overlay-crashinfo: expected one match: {old[:60]!r} (found {text.count(old)})"
    text = text.replace(old, new)


edit("#include <signal.h>\n", "#include <signal.h>\n#include <ucontext.h>\n")

edit(
    """void signal_handler(int signal_number) {
    char message[128];
    std::snprintf(message, sizeof(message), "Native crash signal %d", signal_number);
    zelda64::android::write_crash_file(message);
    signal(signal_number, SIG_DFL);
    raise(signal_number);
}
""",
    """void signal_handler(int signal_number, siginfo_t* info, void* context) {
    char message[2048];
    int length = std::snprintf(message, sizeof(message), "Native crash signal %d code %d fault_addr %p\\n", signal_number,
        info != nullptr ? info->si_code : -1, info != nullptr ? info->si_addr : nullptr);
#if defined(__aarch64__)
    if (context != nullptr && length > 0 && length < int(sizeof(message))) {
        const ucontext_t* uc = static_cast<const ucontext_t*>(context);
        length += std::snprintf(message + length, sizeof(message) - size_t(length), "pc=%016llx sp=%016llx lr=%016llx\\n",
            (unsigned long long)uc->uc_mcontext.pc, (unsigned long long)uc->uc_mcontext.sp, (unsigned long long)uc->uc_mcontext.regs[30]);
        for (int i = 0; i < 29 && length > 0 && length < int(sizeof(message)) - 80; i++) {
            length += std::snprintf(message + length, sizeof(message) - size_t(length), "x%d=%016llx%s", i,
                (unsigned long long)uc->uc_mcontext.regs[i], (i % 4 == 3) ? "\\n" : " ");
        }
        if (length > 0 && length < int(sizeof(message)) - 2) {
            message[length++] = '\\n';
            message[length] = '\\0';
        }
    }
#endif
    // Add the memory map lines for libmain.so and for the region holding the fault address.
    {
        static char maps[1 << 16];
        int fd = open("/proc/self/maps", O_RDONLY);
        if (fd >= 0) {
            ssize_t total = 0;
            ssize_t got = 0;
            while (total < ssize_t(sizeof(maps)) - 1 && (got = read(fd, maps + total, sizeof(maps) - 1 - size_t(total))) > 0) {
                total += got;
            }
            close(fd);
            maps[total] = '\\0';
            const unsigned long long fault = info != nullptr ? (unsigned long long)(uintptr_t)info->si_addr : 0ULL;
            char* line = maps;
            while (line != nullptr && *line != '\\0' && length > 0 && length < int(sizeof(message)) - 200) {
                char* next = std::strchr(line, '\\n');
                if (next != nullptr) {
                    *next = '\\0';
                }
                unsigned long long low = 0;
                unsigned long long high = 0;
                if (std::sscanf(line, "%llx-%llx", &low, &high) == 2 && ((fault >= low && fault < high) || std::strstr(line, "libmain.so") != nullptr)) {
                    length += std::snprintf(message + length, sizeof(message) - size_t(length), "map: %.150s\\n", line);
                }
                line = next != nullptr ? next + 1 : nullptr;
            }
        }
    }
    zelda64::android::write_crash_file(message);
    __android_log_print(ANDROID_LOG_ERROR, kLogTag, "%s", message);
    signal(signal_number, SIG_DFL);
    raise(signal_number);
}
""",
)

edit(
    """    signal(SIGABRT, signal_handler);
    signal(SIGBUS, signal_handler);
    signal(SIGFPE, signal_handler);
    signal(SIGILL, signal_handler);
    signal(SIGSEGV, signal_handler);
""",
    """    struct sigaction action = {};
    action.sa_sigaction = signal_handler;
    action.sa_flags = SA_SIGINFO;
    sigemptyset(&action.sa_mask);
    const int handled_signals[] = {SIGABRT, SIGBUS, SIGFPE, SIGILL, SIGSEGV};
    for (int signal_number : handled_signals) {
        sigaction(signal_number, &action, nullptr);
    }
""",
)

path.write_text(text)
print("crash handler now records fault address and registers")
