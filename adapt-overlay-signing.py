"""Make debug APKs signed with one fixed key, so a new build installs over the old one (and keeps the app's
permissions) instead of needing an uninstall. Usage: python3 -I adapt-overlay-signing.py <engine-dir>

The key is a PKCS12 keystore (password "android", alias androiddebugkey) that the workflow creates, or restores from a secret.
It is a DEBUG key for personal builds, not a release key. The workflow passes its path in the
Q64_DEBUG_KEYSTORE environment variable.
"""
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / "android/app/build.gradle"
text = path.read_text()

old = "    signingConfigs {\n"
new = """    signingConfigs {
        debug {
            storeFile file(System.getenv('Q64_DEBUG_KEYSTORE') ?: 'debug.p12')
            storeType 'pkcs12'
            storePassword 'android'
            keyAlias 'androiddebugkey'
            keyPassword 'android'
        }
"""
assert text.count(old) == 1, f"adapt-overlay-signing: anchor found {text.count(old)} times"
path.write_text(text.replace(old, new))
print("debug signing config added")
