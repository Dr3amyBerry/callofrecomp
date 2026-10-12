package org.callofrecomp;

import android.content.Context;
import android.view.Gravity;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.View;
import android.widget.Button;
import android.widget.FrameLayout;
import com.ast.retrotouch.RetroTouchAdapter;
import com.ast.retrotouch.RetroTouchControl;
import com.ast.retrotouch.RetroTouchLayout;
import com.ast.retrotouch.RetroTouchMode;
import com.ast.retrotouch.RetroTouchView;
import java.util.ArrayList;
import java.util.List;

/** RetroTouch owns drawing, multitouch and editing; this bridge owns CoD input. */
final class TouchControls extends FrameLayout {
    private final TouchInput input = new TouchInput((kind, code, x, y) ->
        GameActivity.nativeInput(kind, code, x, y));
    private final RetroTouchView retro;
    private final MenuPointer menu;
    private final Button toggle;
    private boolean visible;

    TouchControls(Context context) {
        super(context);
        menu = new MenuPointer(context);
        addView(menu, new LayoutParams(-1, -1));
        retro = new RetroTouchView(context);
        addView(retro, new LayoutParams(-1, -1));
        String[][] actions = {{"fire", "DISPARO"}, {"aim", "APUNTAR"},
            {"reload", "RECARGA"}, {"use", "USAR"}, {"jump", "SALTAR"},
            {"crouch", "AGACHAR"}, {"weapon_next", "SIG. ARMA"},
            {"grenade", "GRANADA"}, {"melee", "GOLPE"}, {"menu", "MENÚ"},
            {"prone", "TUMBARSE"}, {"lean_left", "INCL. IZQ."},
            {"lean_right", "INCL. DER."}, {"objectives", "OBJETIVOS"}};
        for (String[] action : actions) retro.registerAction(action[0], action[1]);
        // Reference FPS layout: left movement and utilities, right look/weapon/
        // stance/fire/aim. Control sizes are relative to the short screen edge.
        List<RetroTouchControl> layout = new ArrayList<>();
        layout.add(RetroTouchControl.lookZone("look", .72f, .48f, .56f, .96f));
        layout.add(RetroTouchControl.moveStick("move", .16f, .76f, .25f));
        layout.add(RetroTouchControl.button("menu_button", "menu", "MENÚ", .07f, .09f, .11f));
        layout.add(RetroTouchControl.button("use_button", "use", "USAR", .07f, .30f, .11f));
        layout.add(RetroTouchControl.button("reload_button", "reload", "RECARGA", .17f, .40f, .11f));
        layout.add(RetroTouchControl.button("melee_button", "melee", "GOLPE", .07f, .49f, .11f));
        layout.add(RetroTouchControl.button("grenade_button", "grenade", "GRANADA", .27f, .44f, .11f));
        layout.add(RetroTouchControl.button("prone_button", "prone", "TUMBARSE", .30f, .59f, .11f));
        layout.add(RetroTouchControl.button("lean_left_button", "lean_left", "INCL.\nIZQ.", .17f, .22f, .10f));
        layout.add(RetroTouchControl.button("lean_right_button", "lean_right", "INCL.\nDER.", .28f, .22f, .10f));
        layout.add(RetroTouchControl.button("objectives_button", "objectives", "OBJETIVOS", .40f, .15f, .11f));
        layout.add(RetroTouchControl.button("weapon_button", "weapon_next", "SIG.\nARMA", .90f, .25f, .13f));
        layout.add(RetroTouchControl.button("jump_button", "jump", "SALTAR", .94f, .46f, .12f));
        layout.add(RetroTouchControl.button("crouch_button", "crouch", "AGACHAR", .94f, .64f, .12f));
        layout.add(RetroTouchControl.button("fire_button", "fire", "DISPARO", .83f, .72f, .15f));
        layout.add(RetroTouchControl.button("aim_button", "aim", "APUNTAR", .83f, .91f, .12f));
        retro.setGameplayLayout(new RetroTouchLayout("callofrecomp_sp_training_v1", layout));
        retro.setLookWhileHoldingAction("fire", true);
        retro.setAutoHideOnController(false);
        retro.setListener(new RetroTouchAdapter() {
            @Override public void onAction(String action, boolean pressed) {
                if (action.equals("menu") && pressed) {
                    input.action("menu", true); input.action("menu", false);
                    // Let RetroTouch finish its pointer callback before resetting
                    // its pointer collection and switching to touch pass-through.
                    post(() -> showControls(false));
                } else input.action(action, pressed);
            }
            @Override public void onMove(float x, float y) { input.move(x, y); }
            @Override public void onLook(float x, float y) { input.look(x, y); }
            @Override public void onEditorStateChanged(boolean editing) {
                if (editing) input.releaseAll();
            }
        });
        toggle = new Button(context);
        toggle.setTextSize(11); toggle.setAlpha(.72f);
        toggle.setContentDescription("Mostrar u ocultar controles táctiles");
        toggle.setOnClickListener(v -> showControls(!visible));
        int size = Math.round(48 * getResources().getDisplayMetrics().density);
        // Leave RetroTouch's movable settings icon in the upper-right accessible.
        addView(toggle, new LayoutParams(size * 3, size, Gravity.TOP | Gravity.CENTER_HORIZONTAL));
        showControls(false);
    }
    private void showControls(boolean show) {
        releaseAll(); visible = show;
        retro.setMode(show ? RetroTouchMode.GAMEPLAY : RetroTouchMode.OFF);
        menu.setVisibility(show ? View.GONE : View.VISIBLE);
        toggle.setText(show ? "OCULTAR" : "CONTROLES");
    }
    void releaseAll() {
        retro.resetInputState(); input.releaseAll(); menu.cancel();
    }
    private static final class MenuPointer extends View {
        private int pointer = -1, x, y;
        MenuPointer(Context context) { super(context); setFocusable(false); }
        void cancel() { pointer = -1; GameActivity.nativeInput(4, 1, 0, 0); }
        private void position(float px, float py) {
            x = Math.max(0, Math.min(65535, Math.round(px * 65535 / Math.max(1, getWidth()))));
            y = Math.max(0, Math.min(65535, Math.round(py * 65535 / Math.max(1, getHeight()))));
            GameActivity.nativeInput(0, 0, x, y);
        }
        @Override public boolean onTouchEvent(MotionEvent e) {
            int action = e.getActionMasked(), index = e.getActionIndex();
            if (action == MotionEvent.ACTION_CANCEL) { cancel(); return true; }
            if (action == MotionEvent.ACTION_DOWN) {
                pointer = e.getPointerId(index); position(e.getX(index), e.getY(index));
            } else if (action == MotionEvent.ACTION_MOVE && pointer != -1) {
                int p = e.findPointerIndex(pointer);
                if (p >= 0) position(e.getX(p), e.getY(p));
            } else if ((action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_POINTER_UP)
                    && e.getPointerId(index) == pointer) {
                position(e.getX(index), e.getY(index));
                GameActivity.nativeInput(4, 0, x, y); pointer = -1;
            }
            return true;
        }
        @Override public boolean onGenericMotionEvent(MotionEvent e) {
            if (e.isFromSource(InputDevice.SOURCE_MOUSE) && e.getActionMasked() == MotionEvent.ACTION_HOVER_MOVE) {
                position(e.getX(), e.getY()); return true;
            }
            return super.onGenericMotionEvent(e);
        }
    }
}
