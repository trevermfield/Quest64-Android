"""Log mprotect failures when mods patch game functions, and flush the instruction cache. Usage:
    python3 -I adapt-runtime-mprotect.py <path to lib/N64ModernRuntime>   (run AFTER quest64-android-runtime-mods.patch)

Why: with Eltale Odyssey loaded, pressing Start game crashes with SIGSEGV code 2 (SEGV_ACCERR) where fault address ==
pc: the CPU fetched an instruction from a page that is not executable. The game's code lives in libmain.so and a mod
replaces a function by flipping its page to read+write, writing a 16 byte jump, then flipping it back to read+exec
(librecomp/src/mods.cpp patch_func). The results of those mprotect calls are ignored, so a failure on Android (for
example SELinux refusing to make a modified library page executable again) would leave the page non-executable and
fail silently. This prints every failure with errno to stderr (which the Android app writes to its log) and flushes the
instruction cache after patching, as ARM64 requires. Diagnostic plus the cache flush; no other behaviour change.
"""
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / "librecomp/src/mods.cpp"
text = path.read_text()


def edit(old, new):
    global text
    assert text.count(old) == 1, f"adapt-runtime-mprotect: expected one match: {old[:70]!r} (found {text.count(old)})"
    text = text.replace(old, new)


edit(
    """    int result = mprotect((void*)page_start, page_end - page_start, PROT_READ | PROT_WRITE);
    *old_flags = 0;
    (void)result;
""",
    """#if defined(__ANDROID__)
    // Keep the page executable while it is written. Android's SELinux policy refuses to ADD execute permission back to a
    // library page that has been written to (execmod, errno 13), so dropping PROT_EXEC here left every patched page
    // non-executable and crashed the first call into it. Going to read+write+execute in one step never loses execute.
    int result = mprotect((void*)page_start, page_end - page_start, PROT_READ | PROT_WRITE | PROT_EXEC);
#else
    int result = mprotect((void*)page_start, page_end - page_start, PROT_READ | PROT_WRITE);
#endif
    *old_flags = 0;
    if (result != 0) {
        fprintf(stderr, "mods: unprotect mprotect(%p, %zu) failed: errno=%d (%s)\\n", (void*)page_start, size_t(page_end - page_start), errno, strerror(errno));
    }
""",
)

edit(
    """    int result = mprotect((void*)page_start, page_end - page_start, PROT_READ | PROT_EXEC);
    (void)result;
""",
    """    int result = mprotect((void*)page_start, page_end - page_start, PROT_READ | PROT_EXEC);
    if (result != 0) {
        fprintf(stderr, "mods: protect mprotect(%p, %zu, RX) failed: errno=%d (%s)\\n", (void*)page_start, size_t(page_end - page_start), errno, strerror(errno));
    }
    __builtin___clear_cache((char*)page_start, (char*)page_end);
""",
)

# errno / strerror need these on the POSIX branch.
if "#include <cerrno>" not in text:
    first_include = text.index("#include")
    text = text[:first_include] + "#include <cerrno>\n#include <cstring>\n#include <cstdio>\n" + text[first_include:]

path.write_text(text)
print("mods.cpp: mprotect failure logging and instruction cache flush added")
