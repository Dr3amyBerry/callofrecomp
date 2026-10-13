package org.callofrecomp;

import android.os.Bundle;
import android.content.Context;
import android.graphics.Rect;
import android.view.ViewGroup;
import android.view.View;
import android.os.Handler;
import android.os.Looper;
import android.graphics.Color;
import android.view.Gravity;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import org.libsdl.app.SDLActivity;
import org.libsdl.app.SDLSurface;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

public final class GameActivity extends SDLActivity {
    private TouchControls controls;
    private View loading;
    private TextView loadingText;
    private final Handler loadingHandler = new Handler(Looper.getMainLooper());
    private int loadingPhase = -1;
    public static native int nativeLoadState();
    private final Runnable updateLoading = new Runnable() {
        @Override public void run() {
            int phase = nativeLoadState();
            if (phase != loadingPhase) {
                loadingPhase = phase;
                loading.setVisibility(phase == 0 ? View.GONE : View.VISIBLE);
                String[] messages = {"", "Preparando el motor…", "Leyendo archivos del juego…",
                    "Preparando gráficos…", "Cargando el menú…", "Cargando la misión…", "Preparando la imagen…"};
                loadingText.setText(messages[Math.max(0, Math.min(phase, messages.length - 1))]);
            }
            loadingHandler.postDelayed(this, 250);
        }
    };
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
        setWindowStyle(true);
        if (mLayout != null) {
            controls = new TouchControls(this);
            mLayout.addView(controls, new ViewGroup.LayoutParams(-1, -1));
            FrameLayout overlay = new FrameLayout(this);
            overlay.setBackgroundColor(Color.rgb(20, 23, 17)); overlay.setClickable(true);
            LinearLayout box = new LinearLayout(this); box.setOrientation(LinearLayout.VERTICAL);
            box.setGravity(Gravity.CENTER); box.setPadding(40, 30, 40, 30);
            loadingText = new TextView(this); loadingText.setText("Preparando el motor…");
            loadingText.setTextColor(Color.WHITE); loadingText.setTextSize(20); box.addView(loadingText);
            ProgressBar progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
            progress.setIndeterminate(true);
            int width = (int)(260 * getResources().getDisplayMetrics().density);
            box.addView(progress, new LinearLayout.LayoutParams(width, -2));
            overlay.addView(box, new FrameLayout.LayoutParams(-2, -2, Gravity.CENTER));
            loading = overlay; mLayout.addView(overlay, new ViewGroup.LayoutParams(-1, -1));
            loadingHandler.post(updateLoading);
        }
    }
    @Override protected void onResume() {
        super.onResume();
        if (loading != null) { loadingHandler.removeCallbacks(updateLoading); loadingHandler.post(updateLoading); }
    }
    @Override protected void onPause() {
        loadingHandler.removeCallbacks(updateLoading);
        if (controls != null) controls.releaseAll();
        super.onPause();
    }
    @Override protected void onDestroy() {
        loadingHandler.removeCallbacks(updateLoading); super.onDestroy();
    }
    @Override public void onWindowFocusChanged(boolean focus) {
        if (!focus && controls != null) controls.releaseAll();
        super.onWindowFocusChanged(focus);
    }
}
