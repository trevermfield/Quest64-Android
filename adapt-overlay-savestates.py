"""Save state buttons for the Android project. Usage: python3 -I adapt-overlay-savestates.py <engine-dir>

Adds the native code and the helpers for save states (Save, Slot and Load are in the Menu, see adapt-overlay-options.py) (savestates/q64_save_states.cpp, compiled into the game library). The runtime's part is
quest64-android-runtime-savestates.patch. States are written to <app folder>/savestates/slotN.state.
Each edit asserts its anchor exists once.
"""
import pathlib
import shutil
import sys

engine = pathlib.Path(sys.argv[1])
here = pathlib.Path(__file__).resolve().parent

# 1. native source into the engine and into the Android source list
shutil.copyfile(here / "savestates/q64_save_states.cpp", engine / "src/android/q64_save_states.cpp")
cmake = engine / "CMakeLists.txt"
text = cmake.read_text()
anchor = "        ${CMAKE_SOURCE_DIR}/src/android/android_logging.cpp\n"
assert text.count(anchor) == 1, f"adapt-overlay-savestates: CMake anchor found {text.count(anchor)} times"
cmake.write_text(text.replace(anchor, anchor + "        ${CMAKE_SOURCE_DIR}/src/android/q64_save_states.cpp\n"))

# 3. Java
java = engine / "android/app/src/main/java/io/github/zelda64recomp/ZeldaSDLActivity.java"
text = java.read_text()
native_anchor = "    public static native void nativeSetAppAudioActive(boolean active);\n"
assert text.count(native_anchor) == 1, "adapt-overlay-savestates: native anchor"
text = text.replace(native_anchor, native_anchor + """    public static native void nativeSaveState();
    public static native void nativeLoadState();
    public static native void nativeSetStateSlot(int slot);
    public static native int nativeGetStateSlot();
    public static native long nativeStateSlotTime(int slot);
    public static native String nativeStateSlotElements(int slot);
    public static native String nativeStateStatus();
""")
method_anchor = "    private void setupToggleButton() {\n"
assert text.count(method_anchor) == 1, "adapt-overlay-savestates: method anchor"
text = text.replace(method_anchor, """    private int stateDp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private android.graphics.drawable.GradientDrawable stateBox(int fill, int stroke, int radiusDp) {
        android.graphics.drawable.GradientDrawable box = new android.graphics.drawable.GradientDrawable();
        box.setColor(fill);
        box.setCornerRadius(stateDp(radiusDp));
        box.setStroke(stateDp(1), stroke);
        return box;
    }

    // "Fire 3  Earth 2  Water 1  Wind 4" in the elements' colours, from "earth,fire,wind,water".
    private android.widget.TextView stateElementsLine(String csv, android.graphics.Typeface font) {
        String[] v = csv.split(",");
        String[] labels = { "Fire", "Earth", "Water", "Wind" };
        String[] values = { v[1], v[0], v[3], v[2] };
        int[] colors = { 0xFFF86039, 0xFFE9CD35, 0xFF17D6E8, 0xFF45D043 };
        android.text.SpannableStringBuilder text = new android.text.SpannableStringBuilder();
        for (int k = 0; k < 4; k++) {
            int start = text.length();
            text.append(labels[k]);
            text.setSpan(new android.text.style.ForegroundColorSpan(colors[k]), start, text.length(), 0);
            text.append(" " + values[k] + (k < 3 ? "    " : ""));
        }
        android.widget.TextView line = new android.widget.TextView(this);
        line.setText(text);
        line.setTextColor(0xFFF2F2F2);
        line.setTypeface(font);
        line.setTextSize(13);
        line.setPadding(0, stateDp(3), 0, 0);
        return line;
    }

    // The slot list, in the colours and fonts of the game's own menus (assets/scss/styles/vars/_colors.scss).
    private void showStateSlotPicker(java.util.function.IntConsumer onPicked) {
        final int colorPanel = 0xFF121018;
        final int colorText = 0xFFF2F2F2;
        final int colorDim = 0x99FFFFFF;
        final int colorPrimary = 0xFFB97DF2;
        final int colorPrimaryFill = 0x33B97DF2;
        final int colorBorder = 0x33FFFFFF;
        final int colorUsed = 0xFF45D043;
        android.graphics.Typeface regular = android.graphics.Typeface.DEFAULT;
        android.graphics.Typeface bold = android.graphics.Typeface.DEFAULT_BOLD;
        try {
            File assets = new File(getFilesDir(), "program/assets");
            regular = android.graphics.Typeface.createFromFile(new File(assets, "LatoLatin-Regular.ttf"));
            bold = android.graphics.Typeface.createFromFile(new File(assets, "LatoLatin-Bold.ttf"));
        } catch (Exception e) {
            Log.w(TAG, "Game fonts not available for the slot list", e);
        }
        java.text.DateFormat format = java.text.DateFormat.getDateTimeInstance(java.text.DateFormat.MEDIUM, java.text.DateFormat.SHORT);
        final android.app.Dialog dialog = new android.app.Dialog(this, android.R.style.Theme_Translucent_NoTitleBar_Fullscreen);

        FrameLayout scrim = new FrameLayout(this);
        scrim.setBackgroundColor(0xE608070D);
        scrim.setOnClickListener((view) -> dialog.dismiss());

        android.widget.LinearLayout panel = new android.widget.LinearLayout(this);
        panel.setOrientation(android.widget.LinearLayout.VERTICAL);
        panel.setBackground(stateBox(colorPanel, colorBorder, 8));
        panel.setPadding(stateDp(20), stateDp(16), stateDp(20), stateDp(16));
        panel.setClickable(true);

        android.widget.TextView title = new android.widget.TextView(this);
        title.setText("Save state slot");
        title.setTextColor(colorText);
        title.setTypeface(bold);
        title.setTextSize(20);
        title.setPadding(0, 0, 0, stateDp(10));
        panel.addView(title);

        android.widget.ScrollView scroll = new android.widget.ScrollView(this);
        android.widget.LinearLayout list = new android.widget.LinearLayout(this);
        list.setOrientation(android.widget.LinearLayout.VERTICAL);
        int chosen = nativeGetStateSlot();
        for (int i = 1; i <= 9; i++) {
            final int slotNumber = i;
            long saved = nativeStateSlotTime(i);
            android.widget.LinearLayout row = new android.widget.LinearLayout(this);
            row.setOrientation(android.widget.LinearLayout.VERTICAL);
            android.widget.LinearLayout header = new android.widget.LinearLayout(this);
            header.setOrientation(android.widget.LinearLayout.HORIZONTAL);
            header.setGravity(android.view.Gravity.CENTER_VERTICAL);
            row.addView(header);
            row.setPadding(stateDp(12), stateDp(9), stateDp(12), stateDp(9));
            boolean current = (i == chosen);
            row.setBackground(stateBox(current ? colorPrimaryFill : 0x00000000, current ? colorPrimary : 0x00000000, 6));

            android.widget.TextView name = new android.widget.TextView(this);
            name.setText("Slot " + i);
            name.setTextColor(colorText);
            name.setTypeface(bold);
            name.setTextSize(16);
            name.setMinWidth(stateDp(78));
            header.addView(name);

            android.widget.TextView info = new android.widget.TextView(this);
            info.setText(saved == 0 ? "Empty" : "Used - " + format.format(new java.util.Date(saved * 1000L)));
            info.setTextColor(saved == 0 ? colorDim : colorUsed);
            info.setTypeface(regular);
            info.setTextSize(14);
            header.addView(info);
            String elements = nativeStateSlotElements(i);
            if (elements != null && elements.split(",").length == 4) {
                row.addView(stateElementsLine(elements, regular));
            }

            row.setOnClickListener((view) -> {
                nativeSetStateSlot(slotNumber);
                onPicked.accept(slotNumber);
                dialog.dismiss();
            });
            android.widget.LinearLayout.LayoutParams rowParams = new android.widget.LinearLayout.LayoutParams(
                    android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                    android.widget.LinearLayout.LayoutParams.WRAP_CONTENT);
            rowParams.bottomMargin = stateDp(4);
            list.addView(row, rowParams);
        }
        scroll.addView(list);
        panel.addView(scroll, new android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

        android.widget.TextView cancel = new android.widget.TextView(this);
        cancel.setText("Cancel");
        cancel.setTextColor(colorText);
        cancel.setTypeface(bold);
        cancel.setTextSize(14);
        cancel.setGravity(android.view.Gravity.CENTER);
        cancel.setPadding(stateDp(12), stateDp(8), stateDp(12), stateDp(8));
        cancel.setBackground(stateBox(0x1ABEB8DB, colorBorder, 6));
        cancel.setOnClickListener((view) -> dialog.dismiss());
        android.widget.LinearLayout.LayoutParams cancelParams = new android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT);
        cancelParams.topMargin = stateDp(8);
        panel.addView(cancel, cancelParams);

        int maxHeight = (int) (getResources().getDisplayMetrics().heightPixels * 0.9f);
        FrameLayout.LayoutParams panelParams = new FrameLayout.LayoutParams(stateDp(380), FrameLayout.LayoutParams.WRAP_CONTENT, android.view.Gravity.CENTER);
        panel.setMinimumHeight(0);
        scrim.addView(panel, panelParams);
        scroll.setLayoutParams(new android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT, Math.min(stateDp(330), maxHeight - stateDp(130))));

        dialog.setContentView(scrim);
        dialog.setOnDismissListener((d) -> applyImmersiveFullscreen());
        dialog.show();
    }

    private void showStateStatus() {
        final boolean[] shown = { false };
        for (int delay : new int[] { 1200, 4000 }) {
            mainHandler.postDelayed(() -> {
                if (shown[0]) {
                    return;
                }
                String text = nativeStateStatus();
                if (text != null && !text.isEmpty() && !text.endsWith("...")) {
                    shown[0] = true;
                    Toast.makeText(this, text, Toast.LENGTH_SHORT).show();
                }
            }, delay);
        }
    }

""" + method_anchor)
java.write_text(text)
print("save state buttons added")
