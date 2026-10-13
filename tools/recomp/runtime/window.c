// USER32 / GDI32 / WGL shims on top of SDL2: one window with an OpenGL
// context, a Win32-style message queue fed from SDL events, and dispatch of
// messages to the guest's WndProc. Works on Windows and Android hosts.
#include <SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#ifdef __ANDROID__
#include <gl4esinit.h>
#endif

#include "gl_thunks.h"
#include "frame_pacing.h"

#define HDC_MAIN 0x00002001u
#define HGLRC_MAIN 0x00003001u
#define HWND_BASE 0x00001001u

static SDL_Window *win;
static SDL_GLContext ctx;
static int win_w = 640, win_h = 480, desk_w = 1280, desk_h = 720;
static uint32_t cursor_x, cursor_y;
static uint32_t warp_x, warp_y;
static int cursor_count, active;

static void disable_driver_vsync(void) {
    if (SDL_GL_SetSwapInterval(0) < 0) {
        static int warned;
        if (!warned) {
            fprintf(stderr, "Frame pacing: driver could not disable VSync: %s\n", SDL_GetError());
            warned = 1;
        }
    }
}

// ---------------------------------------------------------------- classes / windows

static struct { char name[64]; uint32_t proc; } classes[16];
static int class_count;
static struct { uint32_t proc; int game; } windows[64];
static int window_count;
static uint32_t game_hwnd;  // receives input; HWND_BASE until the game window exists

static int window_index(uint32_t hwnd) {
    int i = (int)(hwnd - HWND_BASE);
    return i >= 0 && i < window_count ? i : -1;
}

static uint32_t send_to(uint32_t hwnd, uint32_t msg, uint32_t wp, uint32_t lp) {
    int i = window_index(hwnd);
    if (i < 0 || !windows[i].proc) return 0;
    uint32_t a[4] = {hwnd, msg, wp, lp};
    return guest_call(windows[i].proc, 4, a);
}

static uint32_t send(uint32_t msg, uint32_t wp, uint32_t lp) { return send_to(game_hwnd, msg, wp, lp); }

// Engine console output arrives as text sent to the Win32 console's edit control.
static void console_text(const char *s) {
    fputs(s, stdout);
    fflush(stdout);
}

#define K(name) static uint32_t k_##name(uint32_t esp)
#define A(i) ARG(esp, i)
#define S(i) ((const char *)G(A(i)))

K(RegisterClassA) {
    uint32_t wc = A(0);
    if (class_count < 8) {
        const char *n = (const char *)G(mem32(wc + 36));
        snprintf(classes[class_count].name, 64, "%s", n);
        classes[class_count++].proc = mem32(wc + 4);
    }
    return 0xC000u + (uint32_t)class_count;
}

static void sdl_init(void) {
    static int done;
    if (done) return;
    done = 1;
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS)) guest_fatal("SDL_Init: %s", SDL_GetError());
#ifdef __ANDROID__
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 2);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);
    SDL_SetHint(SDL_HINT_TOUCH_MOUSE_EVENTS, "0");
#endif
    SDL_DisplayMode dm;
    if (!SDL_GetDesktopDisplayMode(0, &dm)) { desk_w = dm.w; desk_h = dm.h; }
}

K(CreateWindowExA) {
    sdl_init();
    const char *cls = A(1) > 0xFFFF ? S(1) : "";
    uint32_t proc = 0;
    for (int i = 0; i < class_count; i++)
        if (!strcasecmp(classes[i].name, cls)) proc = classes[i].proc;
    // Win32 controls and the dedicated console are not rendered; everything else is the game window.
    int game = strcasecmp(cls, "static") && strcasecmp(cls, "edit") && strcasecmp(cls, "button") &&
               !strstr(cls, "Console");
    if (window_count == 64) guest_fatal("too many windows");
    uint32_t hwnd = HWND_BASE + (uint32_t)window_count;
    windows[window_count].proc = proc;
    windows[window_count++].game = game;
    if (!win) {  // a hidden SDL window backs every GL context, even the early probe
        SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
        SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24);
        SDL_GL_SetAttribute(SDL_GL_STENCIL_SIZE, 8);
        win = SDL_CreateWindow("Call of Duty", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, win_w, win_h,
                               SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
        if (!win) guest_fatal("SDL_CreateWindow: %s", SDL_GetError());
    }
    int w = (int)A(6), h = (int)A(7);
    if (game && w > 16 && h > 16 && w < 16384) {
        win_w = w;
        win_h = h;
        SDL_SetWindowSize(win, win_w, win_h);
        SDL_SetWindowPosition(win, SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED);
        if (A(2)) SDL_SetWindowTitle(win, S(2));
        // The splash and game share one SDL window, but each original WndProc
        // needs its own activation. Android may emit no second focus event.
        if (game_hwnd != hwnd) active = 0;
        game_hwnd = hwnd;
    }
    printf("codrecomp: window %08x %dx%d class=%s proc=%08x%s\n", hwnd, w, h, cls, proc, game && game_hwnd == hwnd ? " [game]" : "");
    fflush(stdout);
    uint32_t cs = guest_alloc(48);  // CREATESTRUCTA
    wr(G(cs), 4, A(11));
    send_to(hwnd, 0x0001, 0, cs);  // WM_CREATE
    return hwnd;
}

K(DestroyWindow) {
    int i = window_index(A(0));
    if (i >= 0) windows[i].proc = 0;
    if (A(0) == game_hwnd && win) SDL_HideWindow(win);  // keep window + context for a vid_restart
    return 1;
}

K(ShowWindow) {
    int i = window_index(A(0));
    if (i < 0 || !windows[i].game || !A(1)) return 1;
    SDL_ShowWindow(win);
    if (!active) {
        active = 1;
        send(0x0006, 1, 0);  // WM_ACTIVATE(WA_ACTIVE)
        send(0x0007, 0, 0);  // WM_SETFOCUS
    }
    return 1;
}

K(GetWindowRect) {
    int x = 0, y = 0;
    if (win) SDL_GetWindowPosition(win, &x, &y);
    uint32_t r[4] = {(uint32_t)x, (uint32_t)y, (uint32_t)(x + win_w), (uint32_t)(y + win_h)};
    memcpy(G(A(1)), r, 16);
    return 1;
}

K(SetWindowPos) {
    if (win && !(A(6) & 1) && (int)A(4) > 0) {  // !SWP_NOSIZE
        win_w = (int)A(4);
        win_h = (int)A(5);
        SDL_SetWindowSize(win, win_w, win_h);
    }
    return 1;
}

K(MoveWindow) {
    if (win && (int)A(3) > 0) { win_w = (int)A(3); win_h = (int)A(4); SDL_SetWindowSize(win, win_w, win_h); }
    return 1;
}

K(GetSystemMetrics) {
    sdl_init();
    return A(0) == 0 ? (uint32_t)desk_w : A(0) == 1 ? (uint32_t)desk_h : 0;
}

K(GetWindowLongA) {
    int i = window_index(A(0));
    return i >= 0 && (int32_t)A(1) == -4 ? windows[i].proc : 0;
}
K(SetWindowLongA) {
    int i = window_index(A(0));
    if (i < 0 || (int32_t)A(1) != -4) return 0;
    uint32_t old = windows[i].proc;
    windows[i].proc = A(2);
    return old;
}
K(SendMessageA) {
    uint32_t msg = A(1), lp = A(3);
    if ((msg == 0x000C || msg == 0x00C2) && lp) console_text((const char *)G(lp));  // WM_SETTEXT / EM_REPLACESEL
    if (msg == 0x000C || msg == 0x00C2) return 1;
    return send_to(A(0), msg, A(2), lp);
}
K(CallWindowProcA) {
    if (A(0) < 0x00400000u || A(0) >= 0xF0000000u) return 0;  // DefWindowProc thunk or invalid
    uint32_t a[4] = {A(1), A(2), A(3), A(4)};
    return guest_call(A(0), 4, a);
}

K(SetWindowTextA) {
    int i = window_index(A(0));
    if (i >= 0 && windows[i].game && win) SDL_SetWindowTitle(win, S(1));
    else if (A(1)) console_text(S(1));
    return 1;
}
K(GetWindowTextA) {
    if (A(2)) wr(G(A(1)), 1, 0);
    return 0;
}

// ---------------------------------------------------------------- cursor

K(GetCursorPos) { wr(G(A(0)), 4, cursor_x); wr(G(A(0) + 4), 4, cursor_y); return 1; }
K(SetCursorPos) { warp_x = cursor_x = A(0); warp_y = cursor_y = A(1); return 1; }
K(ShowCursor) {
    cursor_count += A(0) ? 1 : -1;
    if (win) SDL_SetRelativeMouseMode(cursor_count < 0 ? SDL_TRUE : SDL_FALSE);
    return (uint32_t)cursor_count;
}

// ---------------------------------------------------------------- messages

typedef struct { uint32_t msg, wp, lp; } qmsg;
static qmsg queue[256];
static int q_head, q_tail;
static uint32_t mouse_buttons;
static uint32_t touch_x, touch_y, pending_menu_position;
static int touch_position_ready, pending_menu_click;
int (*window_menu_pointer)(int x, int y, int *dx, int *dy);

static void post(uint32_t msg, uint32_t wp, uint32_t lp) {
    int next = (q_tail + 1) % 256;
    if (next == q_head) return;  // drop on overflow
    queue[q_tail] = (qmsg){msg, wp, lp};
    q_tail = next;
}

// SDL (USB HID) scancode -> PC set-1 scancode (| 0x100 = extended) and VK code.
static void key_codes(SDL_Scancode sc, uint32_t *scan, uint32_t *vk) {
    static const unsigned char letters[26] = {30, 48, 46, 32, 18, 33, 34, 35, 23, 36, 37, 38, 50,
                                              49, 24, 25, 16, 19, 31, 20, 22, 47, 17, 45, 21, 44};
    *scan = 0;
    *vk = 0;
    if (sc >= SDL_SCANCODE_A && sc <= SDL_SCANCODE_Z) { *scan = letters[sc - SDL_SCANCODE_A]; *vk = 'A' + (sc - SDL_SCANCODE_A); return; }
    if (sc >= SDL_SCANCODE_1 && sc <= SDL_SCANCODE_0) { *scan = 2 + (sc - SDL_SCANCODE_1); *vk = sc == SDL_SCANCODE_0 ? '0' : '1' + (sc - SDL_SCANCODE_1); return; }
    if (sc >= SDL_SCANCODE_F1 && sc <= SDL_SCANCODE_F10) { *scan = 59 + (sc - SDL_SCANCODE_F1); *vk = 0x70 + (sc - SDL_SCANCODE_F1); return; }
    static const struct { SDL_Scancode sc; uint16_t scan; uint8_t vk; } map[] = {
        {SDL_SCANCODE_RETURN, 28, 0x0D}, {SDL_SCANCODE_ESCAPE, 1, 0x1B}, {SDL_SCANCODE_BACKSPACE, 14, 0x08},
        {SDL_SCANCODE_TAB, 15, 0x09}, {SDL_SCANCODE_SPACE, 57, 0x20}, {SDL_SCANCODE_MINUS, 12, 0xBD},
        {SDL_SCANCODE_EQUALS, 13, 0xBB}, {SDL_SCANCODE_LEFTBRACKET, 26, 0xDB}, {SDL_SCANCODE_RIGHTBRACKET, 27, 0xDD},
        {SDL_SCANCODE_BACKSLASH, 43, 0xDC}, {SDL_SCANCODE_SEMICOLON, 39, 0xBA}, {SDL_SCANCODE_APOSTROPHE, 40, 0xDE},
        {SDL_SCANCODE_GRAVE, 41, 0xC0}, {SDL_SCANCODE_COMMA, 51, 0xBC}, {SDL_SCANCODE_PERIOD, 52, 0xBE},
        {SDL_SCANCODE_SLASH, 53, 0xBF}, {SDL_SCANCODE_CAPSLOCK, 58, 0x14}, {SDL_SCANCODE_F11, 87, 0x7A},
        {SDL_SCANCODE_F12, 88, 0x7B}, {SDL_SCANCODE_PAUSE, 69, 0x13}, {SDL_SCANCODE_INSERT, 0x152, 0x2D},
        {SDL_SCANCODE_HOME, 0x147, 0x24}, {SDL_SCANCODE_PAGEUP, 0x149, 0x21}, {SDL_SCANCODE_DELETE, 0x153, 0x2E},
        {SDL_SCANCODE_END, 0x14F, 0x23}, {SDL_SCANCODE_PAGEDOWN, 0x151, 0x22}, {SDL_SCANCODE_RIGHT, 0x14D, 0x27},
        {SDL_SCANCODE_LEFT, 0x14B, 0x25}, {SDL_SCANCODE_DOWN, 0x150, 0x28}, {SDL_SCANCODE_UP, 0x148, 0x26},
        {SDL_SCANCODE_KP_DIVIDE, 0x135, 0x6F}, {SDL_SCANCODE_KP_MULTIPLY, 55, 0x6A}, {SDL_SCANCODE_KP_MINUS, 74, 0x6D},
        {SDL_SCANCODE_KP_PLUS, 78, 0x6B}, {SDL_SCANCODE_KP_ENTER, 0x11C, 0x0D}, {SDL_SCANCODE_KP_1, 79, 0x61},
        {SDL_SCANCODE_KP_2, 80, 0x62}, {SDL_SCANCODE_KP_3, 81, 0x63}, {SDL_SCANCODE_KP_4, 75, 0x64},
        {SDL_SCANCODE_KP_5, 76, 0x65}, {SDL_SCANCODE_KP_6, 77, 0x66}, {SDL_SCANCODE_KP_7, 71, 0x67},
        {SDL_SCANCODE_KP_8, 72, 0x68}, {SDL_SCANCODE_KP_9, 73, 0x69}, {SDL_SCANCODE_KP_0, 82, 0x60},
        {SDL_SCANCODE_KP_PERIOD, 83, 0x6E}, {SDL_SCANCODE_LCTRL, 29, 0x11}, {SDL_SCANCODE_RCTRL, 0x11D, 0x11},
        {SDL_SCANCODE_LSHIFT, 42, 0x10}, {SDL_SCANCODE_RSHIFT, 54, 0x10}, {SDL_SCANCODE_LALT, 56, 0x12},
        {SDL_SCANCODE_RALT, 0x138, 0x12},
    };
    for (size_t i = 0; i < sizeof map / sizeof map[0]; i++)
        if (map[i].sc == sc) { *scan = map[i].scan; *vk = map[i].vk; return; }
}

#define INPUT_CODE 0x434F4400
int window_push_input(int kind, int control, int x, int y) {
    if (!(SDL_WasInit(SDL_INIT_EVENTS)) || kind < 0 || kind > 4) return 0;
    if (kind == 0 && (control < 0 || control > 2 || x < 0 || x > 65535 || y < 0 || y > 65535)) return 0;
    if (kind == 1 && (control <= 0 || control >= SDL_NUM_SCANCODES || (x != 0 && x != 1))) return 0;
    if (kind == 2 && ((control != SDL_BUTTON_LEFT && control != SDL_BUTTON_RIGHT && control != SDL_BUTTON_MIDDLE) || (x != 0 && x != 1))) return 0;
    if (kind == 3 && (control || x < -32768 || x > 32767 || y < -32768 || y > 32767)) return 0;
    if (kind == 4 && (control < 0 || control > 1 || x < 0 || x > 65535 || y < 0 || y > 65535)) return 0;
    SDL_Event e = {0};
    e.type = SDL_USEREVENT;
    e.user.code = INPUT_CODE + kind;
    e.user.data1 = (void *)(intptr_t)control;
    e.user.data2 = (void *)(uintptr_t)((uint32_t)(uint16_t)x | (uint32_t)(uint16_t)y << 16);
    return SDL_PushEvent(&e) == 1;
}

static void pump(void) {
    SDL_Event e;
    // Leave room for the largest expansion (SDL_TEXTINPUT's 31 characters).
    // Keep remaining events in SDL's queue until the guest drains its messages.
    while ((q_head - q_tail - 1 + 256) % 256 >= 32 && SDL_PollEvent(&e)) {
        if (e.type == SDL_USEREVENT && e.user.code >= INPUT_CODE && e.user.code <= INPUT_CODE + 4) {
            int kind = e.user.code - INPUT_CODE, control = (int)(intptr_t)e.user.data1;
            uint32_t packed = (uint32_t)(uintptr_t)e.user.data2;
            int x = packed & 65535, y = packed >> 16;
            memset(&e, 0, sizeof e);
            if (kind == 0 || kind == 4) {
                if (kind == 4 && control == 1) { pending_menu_click = 0; continue; }
                uint32_t target_x = (uint32_t)((uint64_t)x * (win_w - 1) / 65535);
                uint32_t target_y = (uint32_t)((uint64_t)y * (win_h - 1) / 65535);
                if (!touch_position_ready) { touch_x = win_w / 2; touch_y = win_h / 2; touch_position_ready = 1; }
                // IN_MouseMove reads the delta from the warped center; UI then
                // adds that delta to its own cursor. Preserve the last target.
                int dx = (int)(target_x - touch_x), dy = (int)(target_y - touch_y);
                if (window_menu_pointer && window_menu_pointer(x, y, &dx, &dy)) {
                    // Multiple touches before IN_MouseMove are one absolute
                    // target. Replace the pending delta from the last warp.
                    cursor_x = warp_x + (uint32_t)dx; cursor_y = warp_y + (uint32_t)dy;
                } else { cursor_x += (uint32_t)dx; cursor_y += (uint32_t)dy; }
                touch_x = target_x; touch_y = target_y;
                uint32_t lp = target_x | target_y << 16;
                post(0x0200, mouse_buttons, lp);
                if (kind == 4) { pending_menu_click = 1; pending_menu_position = lp; }
                else if (control) {
                    if (control == 1) mouse_buttons |= 1; else mouse_buttons &= ~1u;
                    post(control == 1 ? 0x0201 : 0x0202, mouse_buttons, lp);
                }
                continue;
            } else if (kind == 1) {
                e.type = x ? SDL_KEYDOWN : SDL_KEYUP;
                e.key.keysym.scancode = (SDL_Scancode)control;
            } else if (kind == 2) {
                e.type = x ? SDL_MOUSEBUTTONDOWN : SDL_MOUSEBUTTONUP;
                e.button.button = (Uint8)control;
            } else {
                e.type = SDL_MOUSEMOTION;
                e.motion.xrel = (int16_t)x; e.motion.yrel = (int16_t)y;
            }
        }
        switch (e.type) {
        case SDL_QUIT: post(0x0010, 0, 0); break;  // WM_CLOSE
        case SDL_KEYDOWN:
        case SDL_KEYUP: {
            uint32_t scan, vk, down = e.type == SDL_KEYDOWN;
            key_codes(e.key.keysym.scancode, &scan, &vk);
            if (!scan) break;
            uint32_t lp = 1 | (scan & 0xFF) << 16 | (scan & 0x100 ? 1u << 24 : 0) | (down ? (e.key.repeat ? 1u << 30 : 0) : 3u << 30);
            int alt = vk == 0x12 || (e.key.keysym.mod & KMOD_ALT);
            post(down ? (alt ? 0x0104 : 0x0100) : (alt ? 0x0105 : 0x0101), vk, lp);
            if (down && (vk == 0x0D || vk == 0x08 || vk == 0x09 || vk == 0x1B)) post(0x0102, vk, lp);  // WM_CHAR
            break;
        }
        case SDL_TEXTINPUT:
            for (const unsigned char *c = (const unsigned char *)e.text.text; *c; c++)
                if (*c < 0x80) post(0x0102, *c, 1);
            break;
        case SDL_MOUSEMOTION:
            cursor_x += (uint32_t)e.motion.xrel;
            cursor_y += (uint32_t)e.motion.yrel;
            post(0x0200, mouse_buttons, (cursor_x & 0xFFFF) | cursor_y << 16);
            break;
        case SDL_MOUSEBUTTONDOWN:
        case SDL_MOUSEBUTTONUP: {
            int down = e.type == SDL_MOUSEBUTTONDOWN;
            if (e.button.button != SDL_BUTTON_LEFT && e.button.button != SDL_BUTTON_RIGHT
                    && e.button.button != SDL_BUTTON_MIDDLE) break;
            uint32_t base = e.button.button == SDL_BUTTON_LEFT ? 0x0201 : e.button.button == SDL_BUTTON_RIGHT ? 0x0204 : 0x0207;
            uint32_t bit = e.button.button == SDL_BUTTON_LEFT ? 1 : e.button.button == SDL_BUTTON_RIGHT ? 2 : 0x10;
            // SDL_GetMouseState is the latest state, possibly after queued UP.
            if (down) mouse_buttons |= bit; else mouse_buttons &= ~bit;
            post(base + (down ? 0 : 1), mouse_buttons, (cursor_x & 0xFFFF) | cursor_y << 16);
            break;
        }
        case SDL_MOUSEWHEEL: post(0x020A, (uint32_t)(e.wheel.y * 120) << 16, 0); break;
        case SDL_WINDOWEVENT:
            if (e.window.event == SDL_WINDOWEVENT_FOCUS_GAINED) post(0x0006, 1, 0);
            if (e.window.event == SDL_WINDOWEVENT_FOCUS_LOST) { mouse_buttons = 0; pending_menu_click = 0; post(0x0006, 0, 0); }
            break;
        }
    }
}

static int take(uint32_t out, int remove) {
    if (q_head == q_tail) return 0;
    qmsg m = queue[q_head];
    if (remove) q_head = (q_head + 1) % 256;
    uint32_t v[7] = {game_hwnd, m.msg, m.wp, m.lp, SDL_GetTicks(), cursor_x, cursor_y};
    memcpy(G(out), v, sizeof v);
    return 1;
}

K(PeekMessageA) {
    if (q_head == q_tail) pump();
    return take(A(0), A(4) & 1);
}

K(GetMessageA) {
    while (q_head == q_tail) {
        SDL_WaitEventTimeout(NULL, 10);
        pump();
    }
    take(A(0), 1);
    return mem32(A(0) + 4) != 0x0012;  // WM_QUIT
}

K(DispatchMessageA) {
    uint32_t m = A(0);
    if (mem32(m + 4) == 0x0012) return 0;
    return send_to(mem32(m), mem32(m + 4), mem32(m + 8), mem32(m + 12));
}

K(PostQuitMessage) { (void)esp; post(0x0012, 0, 0); return 0; }
K(RegisterWindowMessageA) { (void)esp; static uint32_t n = 0xC100; return n++; }

// wsprintfA(buf, fmt, ...) is cdecl and variadic: format with guest varargs.
K(wsprintfA) {
    char out[1025];
    const char *f = S(1);
    uint32_t arg = 2;
    size_t o = 0;
    for (; *f && o < 1024; f++) {
        if (*f != '%') { out[o++] = *f; continue; }
        char spec[32] = "%";
        size_t sl = 1;
        f++;
        while (*f && strchr("-+ #0123456789.lh", *f) && sl < 30) spec[sl++] = *f++;
        if (!*f) break;
        spec[sl++] = *f;
        spec[sl] = 0;
        if (*f == '%') { out[o++] = '%'; continue; }
        uint32_t v = ARG(esp, arg++);
        int n = *f == 's' ? snprintf(out + o, 1025 - o, spec, v ? (const char *)G(v) : "(null)")
                          : snprintf(out + o, 1025 - o, spec, v);
        o += n > 0 ? (size_t)n : 0;
        if (o > 1024) o = 1024;
    }
    out[o] = 0;
    memcpy(G(A(0)), out, o + 1);
    return (uint32_t)o;
}

// ---------------------------------------------------------------- display modes

K(EnumDisplaySettingsA) {
    static const int modes[][2] = {{640, 480}, {800, 600}, {1024, 768}, {1280, 720}, {1280, 1024}, {1920, 1080}};
    int32_t i = (int32_t)A(1);
    int w, h;
    sdl_init();
    if (i < 0) { w = desk_w; h = desk_h; }
    else if (i < 6) { w = modes[i][0]; h = modes[i][1]; }
    else return 0;
    uint32_t dm = A(2);
    memset(G(dm + 40), 0, 116);
    wr(G(dm + 36), 2, 156);
    wr(G(dm + 40), 4, 0x5C0000);  // DM_BITSPERPEL | DM_PELSWIDTH | DM_PELSHEIGHT | DM_DISPLAYFREQUENCY
    wr(G(dm + 104), 4, 32);
    wr(G(dm + 108), 4, (uint32_t)w);
    wr(G(dm + 112), 4, (uint32_t)h);
    wr(G(dm + 120), 4, 60);
    return 1;
}

// ---------------------------------------------------------------- GDI / WGL

K(DescribePixelFormat) {
    if (A(3) && A(2) >= 40) {
        uint8_t pfd[40] = {40, 0, 1, 0, 0x25, 0, 0, 0, 0, 32, 8, 16, 8, 8, 8, 0, 8, 24};
        pfd[23] = 24;  // depth
        pfd[24] = 8;   // stencil
        memcpy(G(A(3)), pfd, 40);
    }
    return 1;  // one pixel format available
}

K(GetDeviceCaps) {
    sdl_init();
    switch (A(1)) {
    case 8: return (uint32_t)desk_w;    // HORZRES
    case 10: return (uint32_t)desk_h;   // VERTRES
    case 12: return 32;                 // BITSPIXEL
    case 14: return 1;                  // PLANES
    case 88: case 90: return 96;        // LOGPIXELSX/Y
    case 116: return 60;                // VREFRESH
    default: return 0;
    }
}

K(GetDeviceGammaRamp) {
    for (int c = 0; c < 3; c++)
        for (int i = 0; i < 256; i++) wr(G(A(1) + (uint32_t)(c * 512 + i * 2)), 2, (uint32_t)(i << 8 | i));
    return 1;
}

K(SwapBuffers) {
    (void)esp;
    /* Pace presentation itself, including the first frame after a stall.
     * The original millisecond limiter rounds 60 Hz to 16 ms. */
    if (win && shim_realtime) {
        static Uint64 previous;
        int interval = SDL_GL_GetSwapInterval(), refresh = 0;
        if (interval != 0) {
            SDL_DisplayMode mode;
            int display = SDL_GetWindowDisplayIndex(win);
            if (display >= 0 && SDL_GetCurrentDisplayMode(display, &mode) == 0)
                refresh = mode.refresh_rate;
        }
        int use_vsync = frame_vsync_caps_60(interval, refresh);
        static int last_interval, last_refresh;
        if (interval != 0 && (interval != last_interval || refresh != last_refresh)) {
            fprintf(stderr, "Frame pacing: effective swap interval=%d display=%d Hz; %s\n",
                interval, refresh, use_vsync ? "using VSync alone (at most 60 FPS)"
                : "WARNING: retaining strict host cap; driver VSync may reduce FPS");
        }
        last_interval = interval; last_refresh = refresh;
        Uint64 frequency = SDL_GetPerformanceFrequency();
        Uint64 now = SDL_GetPerformanceCounter();
        Uint64 delay = use_vsync ? 0 : frame_delay_ticks(previous, now, frequency);
        Uint64 deadline = now + delay;
        while (delay) {
            Uint64 ms = delay * 1000 / frequency;
            SDL_Delay(ms > 1 ? (Uint32)(ms - 1) : 0);
            now = SDL_GetPerformanceCounter();
            delay = now < deadline ? deadline - now : 0;
        }
        SDL_GL_SwapWindow(win);
        previous = SDL_GetPerformanceCounter();
    } else if (win) SDL_GL_SwapWindow(win);
    if (pending_menu_click) {
        pending_menu_click = 0;
        mouse_buttons |= 1; post(0x0201, mouse_buttons, pending_menu_position);
        mouse_buttons &= ~1u; post(0x0202, mouse_buttons, pending_menu_position);
    }
    static int stats = -1;
    if (stats < 0) stats = getenv("CODRECOMP_FRAME_STATS") != NULL;
    if (stats) {
        static Uint64 previous, start;
        static uint32_t frames;
        static double sum, minimum = 1e30, maximum;
        Uint64 now = SDL_GetPerformanceCounter(), frequency = SDL_GetPerformanceFrequency();
        if (previous) {
            double ms = (double)(now - previous) * 1000 / frequency;
            sum += ms; frames++;
            if (ms < minimum) minimum = ms;
            if (ms > maximum) maximum = ms;
            if (now - start >= frequency) {
                printf("frame stats: fps=%.1f ms avg=%.2f min=%.2f max=%.2f\n",
                    frames * 1000 / sum, sum / frames, minimum, maximum);
                fflush(stdout);
                frames = 0; sum = maximum = 0; minimum = 1e30; start = now;
            }
        } else start = now;
        previous = now;
    }
    return 1;
}

#ifdef __ANDROID__
static void framebuffer_size(int *w, int *h) { SDL_GL_GetDrawableSize(win, w, h); }
static void *getproc(const char *n) { return gl4es_GetProcAddress(n); }
#else
static void *getproc(const char *n) { return SDL_GL_GetProcAddress(n); }
#endif

K(wglCreateContext) {
    (void)esp;
    if (!win) guest_fatal("wglCreateContext before window");
    if (!ctx) {
        ctx = SDL_GL_CreateContext(win);
        if (!ctx) guest_fatal("SDL_GL_CreateContext: %s", SDL_GetError());
        /* One host clock owns pacing; a second VSync wait can halve FPS. */
        disable_driver_vsync();
#ifdef __ANDROID__
        set_getprocaddress(SDL_GL_GetProcAddress);
        set_getmainfbsize(framebuffer_size);
        initialize_gl4es();
#endif
        gl_load(getproc);
        printf("codrecomp: GL %s / %s\n", (const char *)((const unsigned char *(*)(unsigned))getproc("glGetString"))(0x1F01),
               (const char *)((const unsigned char *(*)(unsigned))getproc("glGetString"))(0x1F02));
        fflush(stdout);
    }
    return HGLRC_MAIN;
}

K(wglMakeCurrent) {
    if (A(1) && ctx) SDL_GL_MakeCurrent(win, ctx);
    return 1;
}
K(wglDeleteContext) { (void)esp; return 1; }
K(wglGetCurrentContext) { (void)esp; return ctx ? HGLRC_MAIN : 0; }
K(wglGetCurrentDC) { (void)esp; return ctx ? HDC_MAIN : 0; }
K(wglSwapIntervalEXT) { (void)esp; disable_driver_vsync(); return 1; }

static uint32_t gl_proc(const char *name) {
    for (const thunk_def *d = gl_thunks; d->name; d++)
        if (!strcmp(d->name, name)) return thunk_address(d->dll, d->name, d->fn, d->pop);
    return 0;
}
K(wglGetProcAddress) {
    const char *n = S(0);
    if (!strcmp(n, "wglSwapIntervalEXT")) return thunk_address("opengl32.dll", "wglSwapIntervalEXT", k_wglSwapIntervalEXT, 4);
    return gl_proc(n);
}

void gl_missing(const char *name) { guest_fatal("host OpenGL lacks %s", name); }

// Keep the extension string within the legacy renderer's buffers and expose
// only the compatibility paths this bridge supports, when the driver has them.
uint32_t gl_guest_string(unsigned int name, const void *host) {
    static uint32_t cache[8];
    static const char *allowed[] = {
        "GL_ARB_multitexture", "GL_EXT_compiled_vertex_array", "GL_ARB_texture_env_add",
        "GL_EXT_texture_env_add", "GL_ARB_texture_env_combine", "GL_EXT_texture_env_combine",
        "GL_ARB_texture_compression", "GL_EXT_texture_compression_s3tc",
        "GL_ARB_texture_env_dot3", "GL_ARB_texture_cube_map", NULL
    };
    unsigned idx = name - 0x1F00;  // VENDOR, RENDERER, VERSION, EXTENSIONS
    if (idx > 3) return 0;
    if (!cache[idx]) {
        const char *s = host ? (const char *)host : "";
        char ext[1024] = "";
        if (idx == 3) {
            for (int i = 0; allowed[i]; i++) {
                const char *p = s;
                size_t n = strlen(allowed[i]);
                while ((p = strstr(p, allowed[i]))) {
                    if ((p == s || p[-1] == ' ') && (p[n] == ' ' || !p[n])) {
                        if (*ext) strcat(ext, " ");
                        strcat(ext, allowed[i]);
                        break;
                    }
                    p += n;
                }
            }
            s = ext;
        }
        cache[idx] = guest_strdup(s);
    }
    return cache[idx];
}

K(One) { (void)esp; return 1; }
K(Zero) { (void)esp; return 0; }
K(Hwnd) { (void)esp; return game_hwnd; }
K(Hdc) { (void)esp; return HDC_MAIN; }

#define U(name, fn, pop) {"USER32.dll", #name, k_##fn, pop}
#define D(name, fn, pop) {"GDI32.dll", #name, k_##fn, pop}
#define W(name, fn, pop) {"opengl32.dll", #name, k_##fn, pop}
const thunk_def window_thunks[] = {
    U(RegisterClassA, RegisterClassA, 4), U(CreateWindowExA, CreateWindowExA, 48), U(DestroyWindow, DestroyWindow, 4),
    U(ShowWindow, ShowWindow, 8), U(UpdateWindow, One, 4), U(SetForegroundWindow, One, 4), U(SetFocus, Hwnd, 4),
    U(GetForegroundWindow, Hwnd, 0), U(GetDesktopWindow, Hwnd, 0), U(GetDC, Hdc, 4), U(ReleaseDC, One, 8),
    U(GetWindowRect, GetWindowRect, 8), U(SetWindowPos, SetWindowPos, 28), U(MoveWindow, MoveWindow, 24),
    U(AdjustWindowRect, One, 12), U(GetSystemMetrics, GetSystemMetrics, 4), U(GetWindowLongA, GetWindowLongA, 8),
    U(SetWindowLongA, SetWindowLongA, 12), U(SendMessageA, SendMessageA, 16), U(CallWindowProcA, CallWindowProcA, 20), U(DefWindowProcA, Zero, 16),
    U(SetWindowTextA, SetWindowTextA, 8), U(GetWindowTextA, GetWindowTextA, 12), U(InvalidateRect, One, 12),
    U(CloseWindow, One, 4), U(GetCursorPos, GetCursorPos, 4), U(SetCursorPos, SetCursorPos, 8),
    U(ShowCursor, ShowCursor, 4), U(ClipCursor, One, 4), U(SetCapture, Hwnd, 4), U(ReleaseCapture, One, 0),
    U(PeekMessageA, PeekMessageA, 20), U(GetMessageA, GetMessageA, 16), U(TranslateMessage, Zero, 4),
    U(DispatchMessageA, DispatchMessageA, 4), U(PostQuitMessage, PostQuitMessage, 4),
    U(RegisterWindowMessageA, RegisterWindowMessageA, 4), U(wsprintfA, wsprintfA, 0),
    U(EnumDisplaySettingsA, EnumDisplaySettingsA, 12), U(ChangeDisplaySettingsA, Zero, 8),
    U(LoadIconA, One, 8), U(LoadCursorA, One, 8), U(LoadImageA, One, 24), U(SetTimer, One, 16),
    U(RegisterHotKey, One, 16), U(UnregisterHotKey, One, 8), U(SystemParametersInfoA, One, 16),
    U(MapVirtualKeyA, Zero, 8), U(OpenClipboard, Zero, 4), U(CloseClipboard, One, 0), U(GetClipboardData, Zero, 4),
    D(ChoosePixelFormat, One, 8), D(DescribePixelFormat, DescribePixelFormat, 16), D(SetPixelFormat, One, 12),
    D(SwapBuffers, SwapBuffers, 4), D(GetDeviceCaps, GetDeviceCaps, 8), D(GetDeviceGammaRamp, GetDeviceGammaRamp, 8),
    D(SetDeviceGammaRamp, One, 8), D(CreateFontA, One, 56), D(DeleteDC, One, 4), D(SetTextColor, Zero, 8),
    D(SetBkColor, Zero, 8), D(CreateSolidBrush, One, 4),
    W(wglCreateContext, wglCreateContext, 4), W(wglMakeCurrent, wglMakeCurrent, 8),
    W(wglDeleteContext, wglDeleteContext, 4), W(wglGetCurrentContext, wglGetCurrentContext, 0),
    W(wglGetCurrentDC, wglGetCurrentDC, 0), W(wglGetProcAddress, wglGetProcAddress, 4),
    W(wglSwapIntervalEXT, wglSwapIntervalEXT, 4), W(wglShareLists, One, 8),
    {0, 0, 0, 0},
};
