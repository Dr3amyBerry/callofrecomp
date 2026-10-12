package org.callofrecomp;

import android.os.Bundle;
import android.view.ViewGroup;
import org.libsdl.app.SDLActivity;

public final class GameActivity extends SDLActivity {
    private TouchControls controls;
    public static native int nativeInput(int kind, int control, int x, int y);
    @Override protected String[] getLibraries() { return new String[]{"SDL2", "GL", "main"}; }
    @Override protected String[] getArguments() {
        // SDL supplies argv[0] itself; these begin at argv[1].
        return new String[]{LauncherActivity.originals(this).getAbsolutePath(),
            LauncherActivity.profile(this).getAbsolutePath(), "+set", "com_introplayed", "1",
            "+set", "cg_nopredict", "0", "+set", "cl_language",
            Installation.language(LauncherActivity.originals(this))};
    }
    @Override protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        if (mLayout != null) {
            controls = new TouchControls(this);
            mLayout.addView(controls, new ViewGroup.LayoutParams(-1, -1));
        }
    }
    @Override protected void onPause() {
        if (controls != null) controls.releaseAll();
        super.onPause();
    }
    @Override public void onWindowFocusChanged(boolean focus) {
        if (!focus && controls != null) controls.releaseAll();
        super.onWindowFocusChanged(focus);
    }
}
