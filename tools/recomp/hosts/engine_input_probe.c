// Explicit integration probe: deliver timed SDL input through the normal bridge.
// This host is selected only by build_engine.py --input-probe.
#include <SDL.h>
#define main engine_main
#include "engine_host.c"
#undef main

static Uint32 probe(Uint32 interval, void *unused) {
    (void)interval; (void)unused;
    static int stage;
    SDL_Event event = {0};
    if (stage == 0) {
        event.type = SDL_MOUSEBUTTONDOWN; event.button.button = SDL_BUTTON_LEFT;
        event.button.state = SDL_PRESSED;
        if (SDL_PushEvent(&event) != 1) { fprintf(stderr, "input probe: click DOWN insertion failed\n"); return 0; }
        event.type = SDL_MOUSEBUTTONUP; event.button.state = SDL_RELEASED;
        if (SDL_PushEvent(&event) != 1) { fprintf(stderr, "input probe: click UP insertion failed\n"); return 0; }
        puts("input probe: mission click queued");
    } else if (stage == 1 || stage == 2) {
        event.type = stage == 1 ? SDL_KEYDOWN : SDL_KEYUP;
        event.key.state = stage == 1 ? SDL_PRESSED : SDL_RELEASED;
        event.key.keysym.scancode = SDL_SCANCODE_W;
        event.key.keysym.sym = SDLK_w;
        if (SDL_PushEvent(&event) != 1) { fprintf(stderr, "input probe: W insertion failed\n"); return 0; }
        printf("input probe: W %s queued\n", stage == 1 ? "down" : "up");
    } else if (stage == 3 || stage == 4 || stage == 7 || stage == 8) {
        int down = stage == 3 || stage == 7;
        event.type = down ? SDL_MOUSEBUTTONDOWN : SDL_MOUSEBUTTONUP;
        event.button.button = stage < 7 ? SDL_BUTTON_LEFT : SDL_BUTTON_RIGHT;
        event.button.state = down ? SDL_PRESSED : SDL_RELEASED;
        if (SDL_PushEvent(&event) != 1) { fprintf(stderr, "input probe: weapon input insertion failed\n"); return 0; }
        printf("input probe: %s %s queued\n", stage < 7 ? "fire" : "aim", down ? "down" : "up");
    } else if (stage == 5 || stage == 6) {
        event.type = stage == 5 ? SDL_KEYDOWN : SDL_KEYUP;
        event.key.state = stage == 5 ? SDL_PRESSED : SDL_RELEASED;
        event.key.keysym.scancode = SDL_SCANCODE_R; event.key.keysym.sym = SDLK_r;
        if (SDL_PushEvent(&event) != 1) { fprintf(stderr, "input probe: reload insertion failed\n"); return 0; }
        printf("input probe: reload %s queued\n", stage == 5 ? "down" : "up");
    }
    fflush(stdout);
    static const Uint32 delays[] = {15000, 3000, 2000, 200, 800, 250, 1750, 2000, 0};
    return delays[stage++];
}

int main(int argc, char **argv) {
    if (SDL_InitSubSystem(SDL_INIT_TIMER)) return 3;
    if (!SDL_AddTimer(45000, probe, NULL)) return 3;
    return engine_main(argc, argv);
}
