package org.callofrecomp;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.util.SparseArray;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.View;

final class TouchControls extends View {
    private static final int JOY = 100, LOOK = 101, MENU = 102;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final SparseArray<Finger> fingers = new SparseArray<>();
    private final int[] holds = new int[64];
    private boolean game, menuHeld;
    private int menuX, menuY;
    private static final String[] LABELS = {"DISPARO", "APUNTAR", "RECARGA", "USAR", "SALTAR", "AGACHAR", "ARMA"};
    private static final int[] KEYS = {-1, -3, 21, 9, 44, 6, 30};
    private static final class Finger {
        int role; float x, y; int joy;
        Finger(int r, float a, float b) { role = r; x = a; y = b; }
    }
    TouchControls(Context context) { super(context); setFocusable(false); }
    private void input(int kind, int control, int x, int y) { GameActivity.nativeInput(kind, control, x, y); }
    private void key(int key, boolean down) {
        int index = key < 0 ? 50 - key : key;
        if (down) { if (holds[index]++ == 0) input(key < 0 ? 2 : 1, Math.abs(key), 1, 0); }
        else if (holds[index] > 0 && --holds[index] == 0) input(key < 0 ? 2 : 1, Math.abs(key), 0, 0);
    }
    void releaseAll() {
        for (int i = 0; i < holds.length; i++) if (holds[i] != 0) {
            int code = i > 50 ? -(i - 50) : i;
            input(code < 0 ? 2 : 1, Math.abs(code), 0, 0); holds[i] = 0;
        }
        input(4, 1, 0, 0);
        menuHeld = false; fingers.clear(); invalidate();
    }
    private RectF button(int i) {
        float w = getWidth(), h = getHeight();
        return new RectF(w * (.59f + (i % 3) * .135f), h * (.56f + (i / 3) * .13f),
            w * (.715f + (i % 3) * .135f), h * (.675f + (i / 3) * .13f));
    }
    @Override protected void onDraw(Canvas canvas) {
        float w = getWidth(), h = getHeight(); paint.setTextSize(Math.max(12, h * .024f));
        box(canvas, new RectF(w * .77f, 0, w, h * .10f), game ? "MENÚ / PAUSA" : "CONTROLES");
        if (!game) return;
        paint.setColor(0x55303030); canvas.drawCircle(w * .18f, h * .72f, h * .16f, paint);
        paint.setColor(0xCCFFFFFF); canvas.drawText("MOVER", w * .13f, h * .73f, paint);
        for (int i = 0; i < LABELS.length; i++) box(canvas, button(i), LABELS[i]);
    }
    private void box(Canvas c, RectF r, String text) {
        paint.setColor(0x77303030); c.drawRoundRect(r, 8, 8, paint);
        paint.setColor(0xDDFFFFFF); paint.setTextAlign(Paint.Align.CENTER);
        c.drawText(text, r.centerX(), r.centerY() + paint.getTextSize() / 3, paint);
        paint.setTextAlign(Paint.Align.LEFT);
    }
    private void absolute(int action, float x, float y) {
        menuX = Math.max(0, Math.min(65535, Math.round(x * 65535 / Math.max(1, getWidth()))));
        menuY = Math.max(0, Math.min(65535, Math.round(y * 65535 / Math.max(1, getHeight()))));
        input(0, action, menuX, menuY);
    }
    private void joystick(Finger finger, float x, float y) {
        float dx = (x / getWidth() - .18f), dy = (y / getHeight() - .72f);
        int next = (dx < -.04f ? 1 : 0) | (dx > .04f ? 2 : 0) | (dy < -.05f ? 4 : 0) | (dy > .05f ? 8 : 0);
        int[] codes = {4, 7, 26, 22};
        for (int i = 0; i < 4; i++) if (((next ^ finger.joy) & (1 << i)) != 0) key(codes[i], (next & (1 << i)) != 0);
        finger.joy = next;
    }
    @Override public boolean onTouchEvent(MotionEvent event) {
        if (event.isFromSource(InputDevice.SOURCE_MOUSE)) return false;
        int action = event.getActionMasked(), index = event.getActionIndex();
        float x = event.getX(index), y = event.getY(index); int id = event.getPointerId(index);
        if (action == MotionEvent.ACTION_CANCEL) { releaseAll(); return true; }
        if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_POINTER_DOWN) {
            if (x > getWidth() * .77f && y < getHeight() * .10f) {
                releaseAll();
                if (game) { key(41, true); key(41, false); }
                game = !game; invalidate(); return true;
            }
            if (!game) {
                if (!menuHeld) { absolute(0, x, y); menuHeld = true; fingers.put(id, new Finger(MENU, x, y)); }
                return true;
            }
            int role = LOOK;
            for (int i = 0; i < LABELS.length; i++) if (button(i).contains(x, y)) { role = i; break; }
            if (role == LOOK && x < getWidth() * .36f) role = JOY;
            Finger f = new Finger(role, x, y); fingers.put(id, f);
            if (role < LABELS.length) key(KEYS[role], true);
            if (role == JOY) joystick(f, x, y);
        } else if (action == MotionEvent.ACTION_MOVE) {
            for (int i = 0; i < event.getPointerCount(); i++) {
                Finger f = fingers.get(event.getPointerId(i)); if (f == null) continue;
                float a = event.getX(i), b = event.getY(i);
                if (f.role == MENU) absolute(0, a, b);
                if (f.role == JOY) joystick(f, a, b);
                if (f.role == LOOK) input(3, 0, Math.max(-32768, Math.min(32767, Math.round((a - f.x) * 1280 / getWidth()))),
                    Math.max(-32768, Math.min(32767, Math.round((b - f.y) * 720 / getHeight()))));
                f.x = a; f.y = b;
            }
        } else if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_POINTER_UP) {
            Finger f = fingers.get(id);
            if (f != null) {
                if (f.role < LABELS.length) key(KEYS[f.role], false);
                if (f.role == JOY) {
                    int[] codes = {4, 7, 26, 22};
                    for (int i = 0; i < 4; i++) if ((f.joy & (1 << i)) != 0) key(codes[i], false);
                }
                if (f.role == MENU) { absolute(0, x, y); input(4, 0, menuX, menuY); menuHeld = false; }
                fingers.remove(id);
            }
        }
        return true;
    }
}
