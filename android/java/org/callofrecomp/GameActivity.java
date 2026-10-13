package org.callofrecomp;

import android.os.Bundle;
import android.content.Context;
import android.graphics.Rect;
import android.view.ViewGroup;
import org.libsdl.app.SDLActivity;
import org.libsdl.app.SDLSurface;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

public final class GameActivity extends SDLActivity {
    private TouchControls controls;
    public static native int nativeInput(int kind, int control, int x, int y);
    @Override protected String[] getLibraries() { return new String[]{"SDL2", "GL", "main"}; }
    @Override protected SDLSurface createSDLSurface(Context context) {
        return new PerformanceSurface(context, LauncherActivity.performanceMode(context));
    }
    @Override protected String[] getArguments() {
        Rect buffer = mSurface.getHolder().getSurfaceFrame();
        // SDL supplies argv[0] itself; these begin at argv[1].
        java.util.ArrayList<String> arguments = new java.util.ArrayList<>(java.util.Arrays.asList(
            LauncherActivity.originals(this).getAbsolutePath(),
            LauncherActivity.profile(this).getAbsolutePath(), "+set", "com_introplayed", "1",
            "+set", "com_maxfps", "60", "+set", "cg_nopredict", "0", "+set", "cl_language",
            Installation.language(LauncherActivity.originals(this)),
            "+set", "r_customwidth", Integer.toString(buffer.width()),
            "+set", "r_customheight", Integer.toString(buffer.height()),
            "+exec", "android_touch.cfg"));
        java.util.Collections.addAll(arguments, RenderProfile.graphicsArguments(LauncherActivity.performanceMode(this)));
        return arguments.toArray(new String[0]);
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
