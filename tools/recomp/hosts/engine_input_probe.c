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
    }
    fflush(stdout);
    stage++;
    return stage == 1 ? 15000 : stage == 2 ? 3000 : 0;
}

int main(int argc, char **argv) {
    if (SDL_InitSubSystem(SDL_INIT_TIMER)) return 3;
    if (!SDL_AddTimer(45000, probe, NULL)) return 3;
    return engine_main(argc, argv);
}
