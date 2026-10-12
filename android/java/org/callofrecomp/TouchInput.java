package org.callofrecomp;

/** Game-owned mapping. JNI only queues events; callbacks never run the engine. */
final class TouchInput {
    interface Sink { void send(int kind, int code, int x, int y); }
    private final Sink sink;
    private final boolean[] keys = new boolean[512], buttons = new boolean[4];
    TouchInput(Sink sink) { this.sink = sink; }
    private void key(int code, boolean pressed) {
        if (keys[code] == pressed) return;
        keys[code] = pressed; sink.send(1, code, pressed ? 1 : 0, 0);
    }
    private void button(int code, boolean pressed) {
        if (buttons[code] == pressed) return;
        buttons[code] = pressed; sink.send(2, code, pressed ? 1 : 0, 0);
    }
    void action(String action, boolean pressed) {
        switch (action) {
            case "fire": button(1, pressed); break;
            case "aim": button(3, pressed); break;
            case "reload": key(21, pressed); break;
            case "use": key(9, pressed); break;
            case "jump": key(44, pressed); break;
            case "crouch": key(6, pressed); break;
            case "weapon_next": key(17, pressed); break; // N, bound to weapnext
            case "melee": key(25, pressed); break; // V, bound to +melee
            case "grenade": key(33, pressed); break; // 4, original grenade slot
            case "menu": key(41, pressed); break;
            default: break;
        }
    }
    void move(float x, float y) {
        // Release before pressing: opposite directions must never overlap.
        int[] codes = {4, 7, 26, 22};
        boolean[] wanted = {x < -.18f, x > .18f, y < -.18f, y > .18f};
        for (int i = 0; i < codes.length; i++) if (!wanted[i]) key(codes[i], false);
        for (int i = 0; i < codes.length; i++) if (wanted[i]) key(codes[i], true);
    }
    void look(float dx, float dy) {
        int x = Math.max(-32768, Math.min(32767, Math.round(dx * 720)));
        int y = Math.max(-32768, Math.min(32767, Math.round(dy * 720)));
        if (x != 0 || y != 0) sink.send(3, 0, x, y);
    }
    void releaseAll() {
        for (int i = 1; i < keys.length; i++) if (keys[i]) key(i, false);
        for (int i = 1; i < buttons.length; i++) if (buttons[i]) button(i, false);
        sink.send(4, 1, 0, 0);
    }
}
