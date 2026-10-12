package org.callofrecomp;

import android.os.Bundle;
import android.view.ViewGroup;
import org.libsdl.app.SDLActivity;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

public final class GameActivity extends SDLActivity {
    private TouchControls controls;
    public static native int nativeInput(int kind, int control, int x, int y);
    @Override protected String[] getLibraries() { return new String[]{"SDL2", "GL", "main"}; }
    @Override protected String[] getArguments() {
        // SDL supplies argv[0] itself; these begin at argv[1].
        return new String[]{LauncherActivity.originals(this).getAbsolutePath(),
            LauncherActivity.profile(this).getAbsolutePath(), "+set", "com_introplayed", "1",
            "+set", "cg_nopredict", "0", "+set", "cl_language",
            Installation.language(LauncherActivity.originals(this)), "+exec", "android_touch.cfg"};
    }
    @Override protected void onCreate(Bundle saved) {
        // '+' binding commands cannot be passed as startup command arguments:
        // the original startup parser splits them into new console commands.
        File main = new File(LauncherActivity.profile(this), "main");
        main.mkdirs();
        try (FileOutputStream cfg = new FileOutputStream(new File(main, "android_touch.cfg"))) {
            cfg.write(("bind MOUSE2 \"+toggleads\"\n" +
                "bind n \"weapnext\"\nbind v \"+melee\"\n").getBytes(StandardCharsets.UTF_8));
        } catch (IOException error) { throw new IllegalStateException("No se pudieron guardar los controles", error); }
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
