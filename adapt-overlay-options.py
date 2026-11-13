"""Touch-control options, fast-forward and backup for the Android project. Usage: python3 -I adapt-overlay-options.py <engine-dir>

Adds (after adapt-overlay-savestates.py):
  - a Menu button (top right) that opens a dialog in the game's menu colours: touch-control opacity and size, a switch for
    hiding the touch controls while a controller is connected, "Move buttons" (drag each control where you want it),
    "Reset layout", and "Back up saves and states" (a zip in Downloads);
  - fast-forward in the Menu (a speed list: 1x to 4x; the sound is off while it is on);
  - automatic hiding of the touch controls when a physical gamepad is connected.
Each edit asserts its anchor exists once.
"""
import pathlib
import sys

engine = pathlib.Path(sys.argv[1])


def replace_once(text, old, new, what):
    assert text.count(old) == 1, f"adapt-overlay-options: {what} found {text.count(old)} times"
    return text.replace(old, new)


java = engine / "android/app/src/main/java/io/github/zelda64recomp/ZeldaSDLActivity.java"
text = java.read_text()

# 2. native declaration
decl = "    public static native String nativeStateStatus();\n"
text = replace_once(text, decl, decl + "    public static native void nativeSetGameSpeed(int multiplier);\n", "native declaration anchor")

# 3. set up after the state buttons
call = "        addButtonTouchListener(overlayView.findViewById(R.id.buttonBack), ControllerButtons.BUTTON_BACK);\n"
text = replace_once(text, call, call + "        setupOptions();\n", "back button listener line")

# 4. visibility also follows the gamepad
vis = "        buttonGroup.setVisibility(hidden ? View.INVISIBLE : View.VISIBLE);\n"
text = replace_once(text, vis, '''        boolean autoHidden = preferences.getBoolean(PREF_AUTO_HIDE, true) && hasExternalGamepad();
        buttonGroup.setVisibility((hidden || autoHidden) ? View.INVISIBLE : View.VISIBLE);
''', "visibility line")

# 5. the new code
anchor = "    private void setupToggleButton() {\n"
code = r'''    private static final String PREF_AUTO_HIDE = "autoHideTouchControls";
    private static final String PREF_CONTROL_ALPHA = "touchControlAlpha";
    private static final String PREF_CONTROL_SIZE = "touchControlSize";
    private int fastForwardIndex = 0;
    private static final int[] GAME_SPEEDS = { 1, 2, 3, 4 };
    private static final String[] GAME_SPEED_NAMES = { "1x  Normal", "2x  Fast", "3x  Faster", "4x  Fastest" };
    private FrameLayout layoutEditor;

    private static final String[] TOUCH_UNIT_KEYS = { "joystick", "dpad", "actions", "l", "r", "z", "back", "start", "menu" };
    private int menuButtonId;

    private int[] touchUnitIds(int unit) {
        switch (unit) {
            case 0: return new int[] { R.id.left_joystick };
            case 1: return new int[] { R.id.dpad_cross, R.id.buttonDpadUp, R.id.buttonDpadDown, R.id.buttonDpadLeft, R.id.buttonDpadRight };
            case 2: return new int[] { R.id.action_button_cluster };
            case 3: return new int[] { R.id.buttonL };
            case 4: return new int[] { R.id.buttonR };
            case 5: return new int[] { R.id.buttonZ };
            case 6: return new int[] { R.id.buttonBack };
            case 7: return new int[] { R.id.buttonStart };
            default: return new int[] { menuButtonId };
        }
    }

    private boolean hasExternalGamepad() {
        try {
            for (int id : android.view.InputDevice.getDeviceIds()) {
                android.view.InputDevice device = android.view.InputDevice.getDevice(id);
                if (device == null || device.isVirtual()) {
                    continue;
                }
                int sources = device.getSources();
                if ((sources & android.view.InputDevice.SOURCE_GAMEPAD) == android.view.InputDevice.SOURCE_GAMEPAD
                        || (sources & android.view.InputDevice.SOURCE_JOYSTICK) == android.view.InputDevice.SOURCE_JOYSTICK) {
                    return true;
                }
            }
        } catch (Exception e) {
            Log.w(TAG, "Could not check for a gamepad", e);
        }
        return false;
    }

    private void setupOptions() {
        // Menu button, always visible (it is not in the group the eye button hides).
        Button menu = new Button(this);
        menuButtonId = View.generateViewId();
        menu.setId(menuButtonId);
        menu.setText("Menu");
        menu.setAllCaps(false);
        menu.setTextSize(11);
        menu.setTextColor(0x66FFFFFF);
        menu.setBackgroundResource(R.drawable.touch_rect_button);
        menu.setPadding(0, 0, 0, 0);
        menu.setMinHeight(0);
        menu.setMinimumHeight(0);
        menu.setMinWidth(0);
        menu.setMinimumWidth(0);
        FrameLayout.LayoutParams menuParams = new FrameLayout.LayoutParams(stateDp(58), stateDp(30),
                android.view.Gravity.TOP | android.view.Gravity.END);
        menuParams.topMargin = stateDp(8);
        menuParams.rightMargin = stateDp(120);
        menu.setOnClickListener((view) -> showOptionsDialog());
        ((FrameLayout) overlayView).addView(menu, menuParams);

        // Hide or show the touch controls when a gamepad comes or goes.
        android.hardware.input.InputManager inputManager =
                (android.hardware.input.InputManager) getSystemService(Context.INPUT_SERVICE);
        if (inputManager != null) {
            inputManager.registerInputDeviceListener(new android.hardware.input.InputManager.InputDeviceListener() {
                @Override
                public void onInputDeviceAdded(int deviceId) {
                    applyTouchControlsVisibility();
                }

                @Override
                public void onInputDeviceRemoved(int deviceId) {
                    applyTouchControlsVisibility();
                }

                @Override
                public void onInputDeviceChanged(int deviceId) {
                    applyTouchControlsVisibility();
                }
            }, mainHandler);
        }

        overlayView.addOnLayoutChangeListener((v, l, t, r, b, ol, ot, or, ob) -> positionMenuButton());
        applyTouchLayout();
        applyTouchControlsVisibility();
    }

    // The Menu button sits just left of the R button.
    private void positionMenuButton() {
        View rButton = overlayView.findViewById(R.id.buttonR);
        View menu = overlayView.findViewById(menuButtonId);
        if (rButton == null || menu == null || rButton.getWidth() == 0 || overlayView.getWidth() == 0) {
            return;
        }
        FrameLayout.LayoutParams params = (FrameLayout.LayoutParams) menu.getLayoutParams();
        int right = overlayView.getWidth() - rButton.getLeft() + stateDp(8);
        int top = rButton.getTop() + (rButton.getHeight() - params.height) / 2;
        if (params.rightMargin != right || params.topMargin != top) {
            params.rightMargin = right;
            params.topMargin = top;
            menu.setLayoutParams(params);
        }
    }

    // Opacity, size and position of each group of controls, from the saved settings.
    private void applyTouchLayout() {
        if (overlayView == null) {
            return;
        }
        overlayView.post(() -> {
            positionMenuButton();
            float alpha = preferences.getInt(PREF_CONTROL_ALPHA, 100) / 100f;
            float scale = preferences.getInt(PREF_CONTROL_SIZE, 100) / 100f;
            for (int unit = 0; unit < TOUCH_UNIT_KEYS.length; unit++) {
                String key = TOUCH_UNIT_KEYS[unit];
                float dx = preferences.getFloat("touchX_" + key, 0f);
                float dy = preferences.getFloat("touchY_" + key, 0f);
                int[] ids = touchUnitIds(unit);
                float left = Float.MAX_VALUE;
                float top = Float.MAX_VALUE;
                float right = -Float.MAX_VALUE;
                float bottom = -Float.MAX_VALUE;
                for (int id : ids) {
                    View view = overlayView.findViewById(id);
                    if (view == null) {
                        continue;
                    }
                    left = Math.min(left, view.getLeft());
                    top = Math.min(top, view.getTop());
                    right = Math.max(right, view.getRight());
                    bottom = Math.max(bottom, view.getBottom());
                }
                float centerX = (left + right) / 2f;
                float centerY = (top + bottom) / 2f;
                for (int id : ids) {
                    View view = overlayView.findViewById(id);
                    if (view == null) {
                        continue;
                    }
                    if (ids.length == 1) {
                        view.setPivotX(view.getWidth() / 2f);
                        view.setPivotY(view.getHeight() / 2f);
                    } else {
                        view.setPivotX(centerX - view.getLeft());
                        view.setPivotY(centerY - view.getTop());
                    }
                    view.setScaleX(scale);
                    view.setScaleY(scale);
                    view.setAlpha(alpha);
                    view.setTranslationX(dx);
                    view.setTranslationY(dy);
                }
            }
        });
    }

    private void resetTouchLayout() {
        SharedPreferences.Editor edit = preferences.edit();
        edit.remove(PREF_CONTROL_ALPHA);
        edit.remove(PREF_CONTROL_SIZE);
        for (String key : TOUCH_UNIT_KEYS) {
            edit.remove("touchX_" + key);
            edit.remove("touchY_" + key);
        }
        edit.apply();
        applyTouchLayout();
    }

    private int touchUnitAt(float x, float y) {
        for (int unit = TOUCH_UNIT_KEYS.length - 1; unit >= 0; unit--) {
            for (int id : touchUnitIds(unit)) {
                View view = overlayView.findViewById(id);
                if (view == null || view.getWidth() == 0) {
                    continue;
                }
                android.graphics.RectF bounds = new android.graphics.RectF(0, 0, view.getWidth(), view.getHeight());
                view.getMatrix().mapRect(bounds);
                bounds.offset(view.getLeft(), view.getTop());
                bounds.inset(-stateDp(6), -stateDp(6));
                if (bounds.contains(x, y)) {
                    return unit;
                }
            }
        }
        return -1;
    }

    // "Move buttons": a see-through layer over the controls; drag a control to move it, then Done.
    private void startLayoutEditor() {
        if (overlayView == null || layoutEditor != null) {
            return;
        }
        buttonGroup.setVisibility(View.VISIBLE);
        final FrameLayout editor = new FrameLayout(this);
        layoutEditor = editor;
        editor.setBackgroundColor(0x66000000);
        editor.setClickable(true);

        android.widget.LinearLayout bar = new android.widget.LinearLayout(this);
        bar.setOrientation(android.widget.LinearLayout.VERTICAL);
        bar.setGravity(android.view.Gravity.CENTER_HORIZONTAL);
        bar.setBackground(stateBox(0xF2121018, 0x33FFFFFF, 8));
        bar.setPadding(stateDp(18), stateDp(12), stateDp(18), stateDp(12));
        android.widget.TextView hint = new android.widget.TextView(this);
        hint.setText("Drag a control to move it");
        hint.setTextColor(0xFFF2F2F2);
        hint.setTextSize(15);
        bar.addView(hint);
        android.widget.LinearLayout buttons = new android.widget.LinearLayout(this);
        buttons.setOrientation(android.widget.LinearLayout.HORIZONTAL);
        buttons.setPadding(0, stateDp(8), 0, 0);
        android.widget.TextView reset = optionsButton("Reset", android.graphics.Typeface.DEFAULT_BOLD, () -> resetTouchLayout());
        android.widget.TextView done = optionsButton("Done", android.graphics.Typeface.DEFAULT_BOLD, () -> {
            ((FrameLayout) overlayView).removeView(editor);
            layoutEditor = null;
            applyTouchControlsVisibility();
        });
        buttons.addView(reset, new android.widget.LinearLayout.LayoutParams(stateDp(100), android.widget.LinearLayout.LayoutParams.WRAP_CONTENT));
        android.widget.LinearLayout.LayoutParams doneParams = new android.widget.LinearLayout.LayoutParams(stateDp(100), android.widget.LinearLayout.LayoutParams.WRAP_CONTENT);
        doneParams.leftMargin = stateDp(10);
        buttons.addView(done, doneParams);
        bar.addView(buttons);
        editor.addView(bar, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT,
                android.view.Gravity.CENTER));

        final int[] active = { -1 };
        final float[] last = new float[2];
        editor.setOnTouchListener((view, event) -> {
            switch (event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    active[0] = touchUnitAt(event.getX(), event.getY());
                    last[0] = event.getX();
                    last[1] = event.getY();
                    return true;
                case MotionEvent.ACTION_MOVE:
                    if (active[0] >= 0) {
                        float dx = event.getX() - last[0];
                        float dy = event.getY() - last[1];
                        last[0] = event.getX();
                        last[1] = event.getY();
                        for (int id : touchUnitIds(active[0])) {
                            View control = overlayView.findViewById(id);
                            if (control != null) {
                                control.setTranslationX(control.getTranslationX() + dx);
                                control.setTranslationY(control.getTranslationY() + dy);
                            }
                        }
                    }
                    return true;
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL:
                    if (active[0] >= 0) {
                        View first = overlayView.findViewById(touchUnitIds(active[0])[0]);
                        if (first != null) {
                            preferences.edit()
                                    .putFloat("touchX_" + TOUCH_UNIT_KEYS[active[0]], first.getTranslationX())
                                    .putFloat("touchY_" + TOUCH_UNIT_KEYS[active[0]], first.getTranslationY())
                                    .apply();
                        }
                        active[0] = -1;
                    }
                    return true;
                default:
                    return true;
            }
        });
        ((FrameLayout) overlayView).addView(editor, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
    }

    private android.widget.TextView optionsButton(String label, android.graphics.Typeface font, Runnable action) {
        android.widget.TextView button = new android.widget.TextView(this);
        button.setText(label);
        button.setTextColor(0xFFF2F2F2);
        button.setTypeface(font);
        button.setTextSize(14);
        button.setGravity(android.view.Gravity.CENTER);
        button.setPadding(stateDp(12), stateDp(9), stateDp(12), stateDp(9));
        button.setBackground(stateBox(0x1ABEB8DB, 0x33FFFFFF, 6));
        button.setOnClickListener((view) -> action.run());
        return button;
    }

    private android.widget.LinearLayout optionsSlider(String label, int min, int max, int value, android.graphics.Typeface font,
            java.util.function.IntConsumer onChange) {
        android.widget.LinearLayout row = new android.widget.LinearLayout(this);
        row.setOrientation(android.widget.LinearLayout.HORIZONTAL);
        row.setGravity(android.view.Gravity.CENTER_VERTICAL);
        android.widget.TextView name = new android.widget.TextView(this);
        name.setText(label);
        name.setTextColor(0xFFF2F2F2);
        name.setTypeface(font);
        name.setTextSize(15);
        name.setMinWidth(stateDp(80));
        row.addView(name);
        android.widget.SeekBar bar = new android.widget.SeekBar(this);
        bar.setMax(max - min);
        bar.setProgress(value - min);
        bar.setProgressTintList(android.content.res.ColorStateList.valueOf(0xFFB97DF2));
        bar.setThumbTintList(android.content.res.ColorStateList.valueOf(0xFFDABAF7));
        row.addView(bar, new android.widget.LinearLayout.LayoutParams(0, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        final android.widget.TextView shown = new android.widget.TextView(this);
        shown.setText(value + "%");
        shown.setTextColor(0x99FFFFFF);
        shown.setTypeface(font);
        shown.setTextSize(14);
        shown.setMinWidth(stateDp(48));
        shown.setGravity(android.view.Gravity.END);
        row.addView(shown);
        bar.setOnSeekBarChangeListener(new android.widget.SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(android.widget.SeekBar seekBar, int progress, boolean fromUser) {
                shown.setText((progress + min) + "%");
                if (fromUser) {
                    onChange.accept(progress + min);
                }
            }

            @Override
            public void onStartTrackingTouch(android.widget.SeekBar seekBar) {
            }

            @Override
            public void onStopTrackingTouch(android.widget.SeekBar seekBar) {
            }
        });
        return row;
    }

    private android.graphics.Typeface gameFont(boolean bold) {
        try {
            return android.graphics.Typeface.createFromFile(new File(getFilesDir(),
                    "program/assets/" + (bold ? "LatoLatin-Bold.ttf" : "LatoLatin-Regular.ttf")));
        } catch (Exception e) {
            return bold ? android.graphics.Typeface.DEFAULT_BOLD : android.graphics.Typeface.DEFAULT;
        }
    }

    // The fast-forward speed list: 1x to 4x, the current one outlined.
    private void showSpeedPicker(java.util.function.IntConsumer onPicked) {
        final android.graphics.Typeface boldFont = gameFont(true);
        final android.app.Dialog dialog = new android.app.Dialog(this, android.R.style.Theme_Translucent_NoTitleBar_Fullscreen);
        FrameLayout scrim = new FrameLayout(this);
        scrim.setBackgroundColor(0xE608070D);
        scrim.setOnClickListener((view) -> dialog.dismiss());

        android.widget.LinearLayout panel = new android.widget.LinearLayout(this);
        panel.setOrientation(android.widget.LinearLayout.VERTICAL);
        panel.setBackground(stateBox(0xFF121018, 0x33FFFFFF, 8));
        panel.setPadding(stateDp(20), stateDp(16), stateDp(20), stateDp(16));
        panel.setClickable(true);

        android.widget.TextView title = new android.widget.TextView(this);
        title.setText("Fast-forward speed");
        title.setTextColor(0xFFF2F2F2);
        title.setTypeface(boldFont);
        title.setTextSize(20);
        title.setPadding(0, 0, 0, stateDp(10));
        panel.addView(title);

        for (int i = 0; i < GAME_SPEEDS.length; i++) {
            final int index = i;
            boolean current = (i == fastForwardIndex);
            android.widget.TextView row = new android.widget.TextView(this);
            row.setText(GAME_SPEED_NAMES[i]);
            row.setTextColor(0xFFF2F2F2);
            row.setTypeface(boldFont);
            row.setTextSize(16);
            row.setPadding(stateDp(12), stateDp(10), stateDp(12), stateDp(10));
            row.setBackground(stateBox(current ? 0x33B97DF2 : 0x00000000, current ? 0xFFB97DF2 : 0x00000000, 6));
            row.setOnClickListener((view) -> {
                fastForwardIndex = index;
                nativeSetGameSpeed(GAME_SPEEDS[index]);
                onPicked.accept(index);
                dialog.dismiss();
            });
            android.widget.LinearLayout.LayoutParams rowParams = new android.widget.LinearLayout.LayoutParams(
                    android.widget.LinearLayout.LayoutParams.MATCH_PARENT, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT);
            rowParams.bottomMargin = stateDp(4);
            panel.addView(row, rowParams);
        }

        FrameLayout.LayoutParams panelParams = new FrameLayout.LayoutParams(stateDp(320), FrameLayout.LayoutParams.WRAP_CONTENT,
                android.view.Gravity.CENTER);
        scrim.addView(panel, panelParams);
        dialog.setContentView(scrim);
        dialog.setOnDismissListener((d) -> applyImmersiveFullscreen());
        dialog.show();
    }

    // The Menu dialog, in the colours and fonts of the game's own menus.
    private void showOptionsDialog() {
        android.graphics.Typeface regular = android.graphics.Typeface.DEFAULT;
        android.graphics.Typeface bold = android.graphics.Typeface.DEFAULT_BOLD;
        try {
            File assets = new File(getFilesDir(), "program/assets");
            regular = android.graphics.Typeface.createFromFile(new File(assets, "LatoLatin-Regular.ttf"));
            bold = android.graphics.Typeface.createFromFile(new File(assets, "LatoLatin-Bold.ttf"));
        } catch (Exception e) {
            Log.w(TAG, "Game fonts not available for the menu", e);
        }
        final android.graphics.Typeface boldFont = bold;
        final android.app.Dialog dialog = new android.app.Dialog(this, android.R.style.Theme_Translucent_NoTitleBar_Fullscreen);

        FrameLayout scrim = new FrameLayout(this);
        scrim.setBackgroundColor(0xE608070D);
        scrim.setOnClickListener((view) -> dialog.dismiss());

        android.widget.ScrollView scroll = new android.widget.ScrollView(this);
        scroll.setBackground(stateBox(0xFF121018, 0x33FFFFFF, 8));
        scroll.setClickable(true);
        android.widget.LinearLayout content = new android.widget.LinearLayout(this);
        content.setOrientation(android.widget.LinearLayout.VERTICAL);
        content.setPadding(stateDp(20), stateDp(16), stateDp(20), stateDp(16));
        scroll.addView(content);

        android.widget.TextView title = new android.widget.TextView(this);
        title.setText("Menu");
        title.setTextColor(0xFFF2F2F2);
        title.setTypeface(bold);
        title.setTextSize(20);
        content.addView(title);

        android.widget.TextView statesHeader = new android.widget.TextView(this);
        statesHeader.setText("Save states");
        statesHeader.setTextColor(0xFFB97DF2);
        statesHeader.setTypeface(bold);
        statesHeader.setTextSize(14);
        statesHeader.setPadding(0, stateDp(12), 0, stateDp(4));
        content.addView(statesHeader);

        android.widget.LinearLayout.LayoutParams fullWidth = new android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT);
        final android.widget.TextView slotRow = optionsButton("", bold, () -> { });
        slotRow.setText("Slot " + nativeGetStateSlot() + "   (tap to choose)");
        slotRow.setOnClickListener((view) -> showStateSlotPicker((slot) -> slotRow.setText("Slot " + slot + "   (tap to choose)")));
        content.addView(slotRow, fullWidth);

        android.widget.LinearLayout stateRow = new android.widget.LinearLayout(this);
        stateRow.setOrientation(android.widget.LinearLayout.HORIZONTAL);
        android.widget.TextView saveState = optionsButton("Save", bold, () -> {
            dialog.dismiss();
            nativeSaveState();
            showStateStatus();
        });
        android.widget.TextView loadState = optionsButton("Load", bold, () -> {
            dialog.dismiss();
            nativeLoadState();
            showStateStatus();
        });
        android.widget.LinearLayout.LayoutParams stateLeft = new android.widget.LinearLayout.LayoutParams(0, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        stateLeft.topMargin = stateDp(8);
        android.widget.LinearLayout.LayoutParams stateRight = new android.widget.LinearLayout.LayoutParams(0, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        stateRight.topMargin = stateDp(8);
        stateRight.leftMargin = stateDp(8);
        stateRow.addView(saveState, stateLeft);
        stateRow.addView(loadState, stateRight);
        content.addView(stateRow, fullWidth);

        android.widget.TextView speedHeader = new android.widget.TextView(this);
        speedHeader.setText("Fast-forward");
        speedHeader.setTextColor(0xFFB97DF2);
        speedHeader.setTypeface(bold);
        speedHeader.setTextSize(14);
        speedHeader.setPadding(0, stateDp(14), 0, stateDp(4));
        content.addView(speedHeader);
        final android.widget.TextView speedRow = optionsButton("", bold, () -> { });
        speedRow.setText("Speed: " + GAME_SPEED_NAMES[fastForwardIndex] + "   (tap to choose)");
        speedRow.setOnClickListener((view) -> showSpeedPicker((index) ->
                speedRow.setText("Speed: " + GAME_SPEED_NAMES[index] + "   (tap to choose)")));
        content.addView(speedRow, fullWidth);

        android.widget.TextView controlsHeader = new android.widget.TextView(this);
        controlsHeader.setText("Touch controls");
        controlsHeader.setTextColor(0xFFB97DF2);
        controlsHeader.setTypeface(bold);
        controlsHeader.setTextSize(14);
        controlsHeader.setPadding(0, stateDp(12), 0, stateDp(4));
        content.addView(controlsHeader);

        content.addView(optionsSlider("Opacity", 20, 100, preferences.getInt(PREF_CONTROL_ALPHA, 100), regular, (value) -> {
            preferences.edit().putInt(PREF_CONTROL_ALPHA, value).apply();
            applyTouchLayout();
        }));
        content.addView(optionsSlider("Size", 70, 150, preferences.getInt(PREF_CONTROL_SIZE, 100), regular, (value) -> {
            preferences.edit().putInt(PREF_CONTROL_SIZE, value).apply();
            applyTouchLayout();
        }));

        final android.widget.TextView autoHide = optionsButton("", bold, () -> { });
        final Runnable updateAutoHide = () -> autoHide.setText("Hide when a controller is connected:  "
                + (preferences.getBoolean(PREF_AUTO_HIDE, true) ? "On" : "Off"));
        updateAutoHide.run();
        autoHide.setOnClickListener((view) -> {
            preferences.edit().putBoolean(PREF_AUTO_HIDE, !preferences.getBoolean(PREF_AUTO_HIDE, true)).apply();
            updateAutoHide.run();
            applyTouchControlsVisibility();
        });
        android.widget.LinearLayout.LayoutParams wide = new android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT);
        wide.topMargin = stateDp(8);
        content.addView(autoHide, wide);

        android.widget.LinearLayout layoutRow = new android.widget.LinearLayout(this);
        layoutRow.setOrientation(android.widget.LinearLayout.HORIZONTAL);
        android.widget.TextView move = optionsButton("Move buttons", bold, () -> {
            dialog.dismiss();
            startLayoutEditor();
        });
        android.widget.TextView reset = optionsButton("Reset layout", bold, () -> {
            resetTouchLayout();
            dialog.dismiss();
            Toast.makeText(this, "Touch controls reset", Toast.LENGTH_SHORT).show();
        });
        android.widget.LinearLayout.LayoutParams half = new android.widget.LinearLayout.LayoutParams(0, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        android.widget.LinearLayout.LayoutParams halfRight = new android.widget.LinearLayout.LayoutParams(0, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        halfRight.leftMargin = stateDp(8);
        layoutRow.addView(move, half);
        layoutRow.addView(reset, halfRight);
        content.addView(layoutRow, wide);

        android.widget.TextView backupHeader = new android.widget.TextView(this);
        backupHeader.setText("Backup");
        backupHeader.setTextColor(0xFFB97DF2);
        backupHeader.setTypeface(bold);
        backupHeader.setTextSize(14);
        backupHeader.setPadding(0, stateDp(14), 0, stateDp(4));
        content.addView(backupHeader);
        content.addView(optionsButton("Back up saves and states", bold, () -> {
            dialog.dismiss();
            backupSavesAndStates();
        }), wide);

        android.widget.LinearLayout.LayoutParams closeParams = new android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT);
        closeParams.topMargin = stateDp(14);
        content.addView(optionsButton("Close", boldFont, () -> dialog.dismiss()), closeParams);

        FrameLayout.LayoutParams panelParams = new FrameLayout.LayoutParams(stateDp(430), FrameLayout.LayoutParams.WRAP_CONTENT,
                android.view.Gravity.CENTER);
        panelParams.topMargin = stateDp(12);
        panelParams.bottomMargin = stateDp(12);
        scrim.addView(scroll, panelParams);

        dialog.setContentView(scrim);
        dialog.setOnDismissListener((d) -> applyImmersiveFullscreen());
        dialog.show();
    }

    // A zip of the game's saves and the save states in the Downloads folder.
    private void backupSavesAndStates() {
        final File source = appDataDir;
        Toast.makeText(this, "Backing up...", Toast.LENGTH_SHORT).show();
        new Thread(() -> {
            String message;
            try {
                File downloads = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
                downloads.mkdirs();
                String stamp = new SimpleDateFormat("yyyyMMdd-HHmm", Locale.US).format(new Date());
                File zip = new File(downloads, "Quest64-backup-" + stamp + ".zip");
                int count = 0;
                try (java.util.zip.ZipOutputStream out = new java.util.zip.ZipOutputStream(new FileOutputStream(zip))) {
                    for (String folder : new String[] { "saves", "savestates" }) {
                        count += zipFolder(out, new File(source, folder), folder);
                    }
                }
                if (count == 0) {
                    zip.delete();
                    message = "Nothing to back up yet";
                } else {
                    message = "Backed up " + count + " files to Downloads/" + zip.getName();
                }
            } catch (Exception e) {
                Log.e(TAG, "Backup failed", e);
                message = "Backup failed: " + e.getMessage();
            }
            final String text = message;
            runOnUiThread(() -> Toast.makeText(this, text, Toast.LENGTH_LONG).show());
        }).start();
    }

    private int zipFolder(java.util.zip.ZipOutputStream out, File folder, String prefix) throws IOException {
        File[] files = folder.listFiles();
        if (files == null) {
            return 0;
        }
        int count = 0;
        for (File file : files) {
            if (file.isDirectory()) {
                count += zipFolder(out, file, prefix + "/" + file.getName());
                continue;
            }
            if (file.getName().endsWith(".new")) {
                continue;
            }
            out.putNextEntry(new java.util.zip.ZipEntry(prefix + "/" + file.getName()));
            try (java.io.FileInputStream in = new java.io.FileInputStream(file)) {
                byte[] buffer = new byte[65536];
                int read;
                while ((read = in.read(buffer)) > 0) {
                    out.write(buffer, 0, read);
                }
            }
            out.closeEntry();
            count++;
        }
        return count;
    }

'''
text = replace_once(text, anchor, code + anchor, "setupToggleButton anchor")
java.write_text(text)
print("options, fast-forward, auto-hide and backup added")
