// Differential oracle: span mixer == per-frame reference mixer, bit for bit,
// including every mutated voice field. Compiles audio.c against a stub SDL.
#include <stdio.h>
#include <stdlib.h>
#include "../tools/recomp/runtime/audio.c"

int SDL_InitSubSystem(Uint32 f) { (void)f; return 0; }
void SDL_QuitSubSystem(Uint32 f) { (void)f; }
const char *SDL_GetError(void) { return ""; }
SDL_AudioDeviceID SDL_OpenAudioDevice(const char *a, int b, const SDL_AudioSpec *c, SDL_AudioSpec *d, int e) { (void)a;(void)b;(void)c;(void)d;(void)e; return 0; }
void SDL_CloseAudioDevice(SDL_AudioDeviceID d) { (void)d; }
void SDL_PauseAudioDevice(SDL_AudioDeviceID d, int p) { (void)d;(void)p; }
void SDL_LockAudioDevice(SDL_AudioDeviceID d) { (void)d; }
void SDL_UnlockAudioDevice(SDL_AudioDeviceID d) { (void)d; }
SDL_RWops *SDL_RWFromConstMem(const void *m, int n) { (void)m;(void)n; return 0; }
SDL_AudioSpec *SDL_LoadWAV_RW(SDL_RWops *r, int f, SDL_AudioSpec *s, Uint8 **b, Uint32 *n) { (void)r;(void)f;(void)s;(void)b;(void)n; return 0; }
void SDL_FreeWAV(Uint8 *b) { (void)b; }
int SDL_BuildAudioCVT(SDL_AudioCVT *c, SDL_AudioFormat a, Uint8 b, int d, SDL_AudioFormat e, Uint8 f, int g) { (void)c;(void)a;(void)b;(void)d;(void)e;(void)f;(void)g; return -1; }
int SDL_ConvertAudio(SDL_AudioCVT *c) { (void)c; return -1; }

static uint32_t seed = 12345;
static uint32_t rnd(void) { seed = seed * 1664525u + 1013904223u; return seed >> 8; }
static float rndf(void) { return (float)(rnd() % 20001) / 10000.0f - 1.0f; }

typedef void (*voice_fn)(sample *, float *, uint32_t, uint32_t);
static void run(voice_fn fn, float *out, uint32_t frames, uint32_t rate) {
    memset(out, 0, (size_t)frames * 2 * sizeof(float));
    for (int i = 0; i < SAMPLE_MAX; i++) {
        sample *s = &samples[i];
        if (!s->allocated || s->playing != 4) continue;
        fn(s, out, frames, rate);
    }
}
static float *make_pcm(uint32_t frames) {
    float *p = malloc((size_t)frames * 2 * sizeof(float));
    for (uint32_t i = 0; i < frames * 2; i++) p[i] = rndf();
    return p;
}

static sample snap[SAMPLE_MAX], after[SAMPLE_MAX];
int main(void) {
    for (int round = 0; round < 300; round++) {
        memset(samples, 0, sizeof samples);
        int voices = 6 + (int)(rnd() % 10);
        for (int i = 0; i < voices; i++) {
            sample *s = &samples[i];
            s->allocated = 1; s->playing = 4; s->volume = (float)(rnd() % 100) / 50.0f;
            s->pan = (float)(rnd() % 101) / 100.0f; s->rate = 8000 + rnd() % 40000;
            s->loops = rnd() % 4;
            s->cursor = (double)(rnd() % 1000) / 7.0;
            switch (rnd() % 3) {
            case 0: s->frames = 1 + rnd() % 300; s->pcm = make_pcm(s->frames); s->cursor = fmod(s->cursor, s->frames + 5); break;
            case 1: s->buffered = 1; s->eof = rnd() & 1; s->active_buffer = rnd() & 1;
                for (int b = 0; b < 2; b++) { s->buffers[b].frames = 1 + rnd() % 200; s->buffers[b].pcm = make_pcm(s->buffers[b].frames); s->buffers[b].state = (rnd() % 4) ? 2 : 0; }
                s->cursor = fmod(s->cursor, 150); break;
            default: s->frames = 0; break;
            }
        }
        memcpy(snap, samples, sizeof samples);
        float a[2048], b[2048];
        for (int call = 0; call < 8; call++) {
            uint32_t frames = 1 + rnd() % 1024, rate = 11025 + rnd() % 40000;
            memcpy(samples, snap, sizeof samples);
            run(mix_voice_scalar, a, frames, rate);
            memcpy(after, samples, sizeof samples);
            memcpy(samples, snap, sizeof samples);
            run(mix_voice_span, b, frames, rate);
            if (memcmp(a, b, (size_t)frames * 2 * sizeof(float))) { printf("FAIL output round=%d call=%d\n", round, call); return 1; }
            for (int i = 0; i < voices; i++) {
                const sample *x = &after[i], *y = &samples[i];
                int bad = x->playing != y->playing || x->loops != y->loops || x->active_buffer != y->active_buffer ||
                    x->eof != y->eof || memcmp(&x->cursor, &y->cursor, sizeof x->cursor) ||
                    memcmp(x->buffers, y->buffers, sizeof x->buffers);
                if (bad) { printf("FAIL state round=%d call=%d voice=%d\n", round, call, i); return 1; }
            }
            memcpy(snap, after, sizeof samples);  // continue from the post-call state
        }
        for (int i = 0; i < voices; i++) { free(snap[i].pcm); free(snap[i].buffers[0].pcm); free(snap[i].buffers[1].pcm); }
    }
    puts("recomp_audio_mix_span_smoke ok");
    return 0;
}
