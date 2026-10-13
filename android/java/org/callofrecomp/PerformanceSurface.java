package org.callofrecomp;

import android.content.Context;
import android.graphics.Matrix;
import android.util.DisplayMetrics;
import android.view.MotionEvent;
import android.view.SurfaceHolder;
import org.libsdl.app.SDLSurface;

/** Lower EGL-buffer resolution, with Android scaling it across the full view. */
final class PerformanceSurface extends SDLSurface {
    private final int mode;
    private boolean started;
    PerformanceSurface(Context context, int mode) {
        super(context); this.mode = mode;
        DisplayMetrics metrics = context.getResources().getDisplayMetrics();
        configure(metrics.widthPixels, metrics.heightPixels);
    }
    private void configure(int width, int height) {
        int[] size = RenderProfile.size(width, height, mode);
        getHolder().setFixedSize(size[0], size[1]);
    }
    @Override protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        if (!started && w > 0 && h > 0) configure(w, h);
    }
    @Override public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) {
        started = true;
        super.surfaceChanged(holder, format, width, height);
    }
    @Override public boolean onTouch(android.view.View view, MotionEvent event) {
        // SDL divides coordinates by buffer dimensions, whereas Android supplies
        // view pixels. RetroTouch/menu overlays already use normalized positions.
        MotionEvent scaled = MotionEvent.obtain(event);
        Matrix transform = new Matrix();
        transform.setScale(mWidth / Math.max(1, getWidth()), mHeight / Math.max(1, getHeight()));
        scaled.transform(transform);
        try { return super.onTouch(view, scaled); }
        finally { scaled.recycle(); }
    }
}
