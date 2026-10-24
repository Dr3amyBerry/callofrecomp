#include "audio.h"
#include "gl_thunks.h"
#include <SDL.h>
#include <stdlib.h>
#include <stdio.h>
#define MINIMP3_IMPLEMENTATION
#define MINIMP3_FLOAT_OUTPUT
#define MINIMP3_NO_STDIO
#include "../third_party/minimp3/minimp3_ex.h"

#define SAMPLE_BASE 0x7E000000u
#define DRIVER 0x7E100001u
#define PROVIDER 0x7E200001u
#define SAMPLE_MAX 256
#define AUDIO_LIMIT (64u << 20)

typedef struct {
    float *pcm;
    uint32_t frames;
    int state; // 0 free, 1 reserved by buffer_ready, 2 queued
} pcm_buffer;
typedef struct {
    int allocated, format, playing;
    float *pcm, volume, pan;
    uint32_t frames, rate, loops;
    double cursor;
    float position[3];
    pcm_buffer buffers[2];
    int buffered, active_buffer, eof;
    mp3dec_ex_t *stream;
    unsigned char *compressed;
    float decoded[2304];
    uint32_t decoded_frames, source_rate;
    uint64_t stream_frame;
    int is_stream;
} sample;
static sample samples[SAMPLE_MAX];
static SDL_AudioDeviceID device;
static uint32_t output_rate = 44100;
static char audio_error[256];
static uint32_t file_callbacks[4];

static void lock(void) { if (device) SDL_LockAudioDevice(device); }
static void unlock(void) { if (device) SDL_UnlockAudioDevice(device); }
static sample *lookup(uint32_t handle) {
    uint32_t i = handle - SAMPLE_BASE;
    return i && i <= SAMPLE_MAX && samples[i - 1].allocated ? &samples[i - 1] : NULL;
}
static void error(const char *s) { snprintf(audio_error, sizeof audio_error, "%s", s); }
static int guest_range(uint32_t address, uint32_t size) {
    if (!address || size > AUDIO_LIMIT || (uint64_t)address + size > (1ull << 32)) return 0;
    for (uint64_t p = address; p < (uint64_t)address + size; p = (p & ~4095ull) + 4096)
        if (!guest_committed((uint32_t)p)) return 0;
    return 1;
}
static void clear_pcm(sample *s) {
    if (s->stream) { mp3dec_ex_close(s->stream); free(s->stream); s->stream = NULL; }
    free(s->compressed); s->compressed = NULL;
    s->decoded_frames = 0; s->stream_frame = 0;
    s->is_stream = 0;
    free(s->pcm); s->pcm = NULL;
    for (int i = 0; i < 2; i++) { free(s->buffers[i].pcm); s->buffers[i] = (pcm_buffer){0}; }
    s->frames = 0; s->cursor = 0; s->playing = 0;
    s->buffered = 0; s->active_buffer = 0; s->eof = 0;
}
static float *current_pcm(sample *s, uint32_t *frames) {
    if (s->stream) {
        while (!s->decoded_frames || s->cursor >= s->decoded_frames) {
            s->cursor -= s->decoded_frames; s->stream_frame += s->decoded_frames;
            int channels = s->stream->info.channels;
            size_t n = mp3dec_ex_read(s->stream, s->decoded, 1152 * channels);
            s->decoded_frames = (uint32_t)(n / channels);
            if (!n) {
                if (s->loops == 1 || s->stream->last_error || mp3dec_ex_seek(s->stream, 0)) {
                    s->playing = 0; *frames = 0; return NULL;
                }
                if (s->loops > 1) s->loops--;
                s->stream_frame = 0;
                n = mp3dec_ex_read(s->stream, s->decoded, 1152 * channels);
                s->decoded_frames = (uint32_t)(n / channels);
                if (!n) { s->playing = 0; *frames = 0; return NULL; }
            }
            if (channels == 1) for (int i = (int)s->decoded_frames - 1; i >= 0; i--)
                s->decoded[2*i] = s->decoded[2*i+1] = s->decoded[i];
        }
        *frames = s->decoded_frames; return s->decoded;
    }
    if (s->buffered) {
        for (int i = 0; i < 2; i++) {
            pcm_buffer *b = &s->buffers[s->active_buffer];
            if (b->state != 2) { s->cursor = 0; if (s->eof) s->playing = 0; *frames = 0; return NULL; }
            if (s->cursor < b->frames) { *frames = b->frames; return b->pcm; }
            s->cursor -= b->frames; b->state = 0;
            s->active_buffer ^= 1;
        }
        s->cursor = 0;
        if (s->eof) s->playing = 0;
        *frames = 0; return NULL;
    }
    if (!s->frames) { *frames = 0; return NULL; }
    while (s->cursor >= s->frames) {
        if (s->loops == 1) { s->playing = 0; *frames = 0; return NULL; }
        if (s->loops > 1) s->loops--;
        s->cursor -= s->frames;
    }
    *frames = s->frames; return s->pcm;
}

// Reference per-frame mixer: current_pcm() is consulted for every output frame.
static __attribute__((unused)) void mix_voice_scalar(sample *s, float *output, uint32_t frames, uint32_t rate) {
    float left = s->volume * (s->pan > 0.5f ? 2.0f * (1.0f - s->pan) : 1.0f);
    float right = s->volume * (s->pan < 0.5f ? 2.0f * s->pan : 1.0f);
    const double step = (double)s->rate / rate;
    for (uint32_t f = 0; f < frames; f++) {
        uint32_t count;
        float *pcm = current_pcm(s, &count);
        if (!pcm || !count || !s->playing) break;
        uint32_t p = (uint32_t)s->cursor;
        output[2 * f] += pcm[2 * p] * left;
        output[2 * f + 1] += pcm[2 * p + 1] * right;
        s->cursor += step;
    }
    uint32_t ignored; current_pcm(s, &ignored);
}
// Opt-in CODRECOMP_AUDIO_MIX_SPAN: identical arithmetic and state, but
// current_pcm() runs only when the cursor leaves the current span. Whenever
// cursor < count, current_pcm() has no side effect in the plain, buffered and
// stream paths (it returns the same pointer/count), so skipping it is exact.
static __attribute__((unused)) void mix_voice_span(sample *s, float *output, uint32_t frames, uint32_t rate) {
    float left = s->volume * (s->pan > 0.5f ? 2.0f * (1.0f - s->pan) : 1.0f);
    float right = s->volume * (s->pan < 0.5f ? 2.0f * s->pan : 1.0f);
    const double step = (double)s->rate / rate;
    uint32_t f = 0;
    while (f < frames) {
        uint32_t count;
        float *pcm = current_pcm(s, &count);
        if (!pcm || !count || !s->playing) break;
        double cursor = s->cursor;
        do {
            uint32_t p = (uint32_t)cursor;
            output[2 * f] += pcm[2 * p] * left;
            output[2 * f + 1] += pcm[2 * p + 1] * right;
            cursor += step;
            f++;
        } while (f < frames && cursor < count);
        s->cursor = cursor;
    }
    uint32_t ignored; current_pcm(s, &ignored);
}
#if defined(CODRECOMP_AUDIO_MIX_SPAN)
#define mix_voice mix_voice_span
#else
#define mix_voice mix_voice_scalar
#endif

void audio_mix(float *output, uint32_t frames, uint32_t rate) {
    memset(output, 0, (size_t)frames * 2 * sizeof(float));
    if (!rate) return;
    for (int i = 0; i < SAMPLE_MAX; i++) {
        sample *s = &samples[i];
        if (!s->allocated || s->playing != 4) continue;
        mix_voice(s, output, frames, rate);
    }
    for (uint32_t i = 0; i < frames * 2; i++) {
        if (output[i] > 1) output[i] = 1;
        if (output[i] < -1) output[i] = -1;
    }
}
static void callback(void *unused, Uint8 *output, int bytes) {
    (void)unused;
    audio_mix((float *)output, (uint32_t)bytes / (2 * sizeof(float)), output_rate);
}

#define K(name) static uint32_t k_##name(uint32_t esp)
#define A(i) ARG(esp, i)
#define S(i) ((const char *)G(A(i)))
K(startup) { (void)esp; if (SDL_InitSubSystem(SDL_INIT_AUDIO)) { error(SDL_GetError()); return 0; } return 1; }
K(open_driver) {
    (void)esp;
    if (device) return DRIVER;
    SDL_AudioSpec want = {0}, have;
    want.freq = 44100; want.channels = 2; want.format = AUDIO_F32SYS;
    want.samples = 1024; want.callback = callback;
    device = SDL_OpenAudioDevice(NULL, 0, &want, &have, SDL_AUDIO_ALLOW_FREQUENCY_CHANGE);
    if (!device) { error(SDL_GetError()); return 0; }
    output_rate = (uint32_t)have.freq;
    SDL_PauseAudioDevice(device, 0);
    printf("codrecomp: SDL audio %u Hz stereo float\n", output_rate);
    return DRIVER;
}
K(shutdown) {
    (void)esp;
    if (device) SDL_CloseAudioDevice(device);
    device = 0;
    for (int i = 0; i < SAMPLE_MAX; i++) { clear_pcm(&samples[i]); memset(&samples[i], 0, sizeof(sample)); }
    SDL_QuitSubSystem(SDL_INIT_AUDIO);
    return 0;
}
K(file_callbacks) { for (int i = 0; i < 4; i++) file_callbacks[i] = A(i); return 0; }
static int decode_stream(sample *s, unsigned char **bytes, uint32_t length) {
    if (length >= 12 && !memcmp(*bytes, "RIFF", 4) && !memcmp(*bytes + 8, "WAVE", 4)) {
        SDL_AudioSpec spec; Uint8 *pcm = NULL; Uint32 count = 0;
        if (!SDL_LoadWAV_RW(SDL_RWFromConstMem(*bytes, (int)length), 1, &spec, &pcm, &count)) return 0;
        if (!count || count > AUDIO_LIMIT || spec.channels < 1 || spec.channels > 2
                || spec.freq < 1000 || spec.freq > 384000) { SDL_FreeWAV(pcm); return 0; }
        SDL_AudioCVT cvt;
        if (SDL_BuildAudioCVT(&cvt, spec.format, spec.channels, spec.freq, AUDIO_F32SYS, 2, spec.freq) < 0
                || (uint64_t)count * cvt.len_mult > AUDIO_LIMIT) { SDL_FreeWAV(pcm); return 0; }
        cvt.len = (int)count; cvt.buf = malloc((size_t)count * cvt.len_mult);
        if (!cvt.buf) { SDL_FreeWAV(pcm); return 0; }
        memcpy(cvt.buf, pcm, count); SDL_FreeWAV(pcm);
        if (SDL_ConvertAudio(&cvt) || !cvt.len_cvt || cvt.len_cvt % (2 * sizeof(float))) { free(cvt.buf); return 0; }
        s->pcm = (float *)cvt.buf; s->frames = (uint32_t)cvt.len_cvt / (2 * sizeof(float));
        s->source_rate = s->rate = (uint32_t)spec.freq;
    } else {
        s->stream = calloc(1, sizeof *s->stream);
        if (!s->stream || mp3dec_ex_open_buf(s->stream, *bytes, length, MP3D_SEEK_TO_SAMPLE)
                || !s->stream->samples || s->stream->info.channels < 1 || s->stream->info.channels > 2
                || s->stream->info.hz < 1000 || s->stream->info.hz > 384000) return 0;
        s->source_rate = s->rate = (uint32_t)s->stream->info.hz;
        s->compressed = *bytes; *bytes = NULL;
    }
    s->is_stream = 1; return 1;
}
K(open_stream) {
    // Invoke the original filesystem only on the engine thread, outside the SDL lock.
    for (int i = 0; i < 4; i++) if (!file_callbacks[i]) { error("stream filesystem callbacks unavailable"); return 0; }
    uint32_t scratch = guest_heap_alloc(65536), out = guest_heap_alloc(4);
    if (!scratch || !out) { guest_heap_free(scratch); guest_heap_free(out); return 0; }
    uint32_t a[3] = {A(1), out, 0};
    uint32_t opened = guest_call(file_callbacks[0], 2, a), handle = mem32(out);
    unsigned char *bytes = NULL; uint32_t result = 0;
    sample candidate = {.allocated=1, .volume=1, .pan=0.5f, .loops=1};
    if (opened && handle) {
        a[0] = handle; a[1] = 0; a[2] = 2;
        uint32_t length = guest_call(file_callbacks[2], 3, a);
        a[2] = 0;
        uint32_t rewind = guest_call(file_callbacks[2], 3, a);
        if (length && length <= AUDIO_LIMIT && rewind == 0 && (bytes = malloc(length))) {
            uint32_t offset = 0;
            while (offset < length) {
                a[0] = handle; a[1] = scratch; a[2] = length-offset < 65536 ? length-offset : 65536;
                uint32_t n = guest_call(file_callbacks[3], 3, a);
                if (!n || n > a[2]) break;
                memcpy(bytes + offset, G(scratch), n); offset += n;
            }
            if (offset == length && decode_stream(&candidate, &bytes, length)) {
                lock();
                for (int i = 0; i < SAMPLE_MAX; i++) if (!samples[i].allocated) {
                    samples[i] = candidate; candidate = (sample){0};
                    result = SAMPLE_BASE+i+1; break;
                }
                unlock();
            }
        }
        a[0] = handle; guest_call(file_callbacks[1], 1, a);
    }
    clear_pcm(&candidate);
    free(bytes); guest_heap_free(scratch); guest_heap_free(out);
    if (!result) error("unable to open or decode audio stream");
    return result;
}
static void stream_seek(sample *s, uint64_t frame) {
    uint64_t total = s->stream->samples / s->stream->info.channels;
    if (frame > total) frame = total;
    if (!mp3dec_ex_seek(s->stream, frame * s->stream->info.channels)) {
        s->stream_frame = frame; s->decoded_frames = 0; s->cursor = 0;
    }
}
K(start_stream) { lock(); sample *s = lookup(A(0)); if (s && s->is_stream) { if (s->stream) stream_seek(s, 0); else s->cursor = 0; s->playing = 4; } unlock(); return 0; }
K(pause_stream) { lock(); sample *s = lookup(A(0)); if (s && s->is_stream) s->playing = A(1) ? 8 : 4; unlock(); return 0; }
K(stream_ms_position) {
    lock(); sample *s = lookup(A(0));
    if (s && s->is_stream) {
        uint64_t total = s->stream ? s->stream->samples / s->stream->info.channels : s->frames;
        uint64_t position = (s->stream ? s->stream_frame : 0) + (uint64_t)s->cursor;
        if (guest_range(A(1), 4)) wr(G(A(1)), 4, total * 1000 / s->source_rate);
        if (guest_range(A(2), 4)) wr(G(A(2)), 4, position * 1000 / s->source_rate);
    }
    unlock(); return 0;
}
K(set_stream_ms_position) { lock(); sample *s = lookup(A(0)); if (s && s->is_stream) { uint64_t frame = (uint64_t)A(1) * s->source_rate / 1000; if (s->stream) stream_seek(s, frame); else s->cursor = fmin(s->frames, frame); } unlock(); return 0; }
K(last_error) { (void)esp; return guest_strdup(audio_error); }
K(enumerate) {
    if (mem32(A(0))) return 0;
    wr(G(A(0)), 4, 1); wr(G(A(1)), 4, PROVIDER);
    wr(G(A(2)), 4, guest_strdup("Miles Fast 2D Positional Audio"));
    return 1;
}
K(attribute) {
    int32_t value = !strcmp(S(1), "Maximum supported samples") ? 32 : -1;
    wr(G(A(2)), 4, (uint32_t)value); return 1;
}
K(allocate) {
    (void)esp;
    lock();
    uint32_t h = 0;
    for (int i = 0; i < SAMPLE_MAX; i++) if (!samples[i].allocated) {
        samples[i] = (sample){.allocated = 1, .rate = 22050, .volume = 1, .pan = 0.5f, .loops = 1};
        h = SAMPLE_BASE + i + 1; break;
    }
    unlock(); return h;
}
K(release) {
    lock(); sample *s = lookup(A(0));
    if (s) { clear_pcm(s); memset(s, 0, sizeof *s); }
    unlock(); return 0;
}
K(init) {
    lock(); sample *s = lookup(A(0));
    if (s) { clear_pcm(s); *s = (sample){.allocated = 1, .rate = 22050, .volume = 1, .pan = 0.5f, .loops = 1}; }
    unlock(); return 0;
}
K(type) { lock(); sample *s = lookup(A(0)); if (s) s->format = (int)A(1); unlock(); return 0; }
static int set_pcm(sample *s, uint32_t data, uint32_t bytes) {
    clear_pcm(s);
    if (!guest_range(data, bytes) || (s->format & 4)) { error("unsupported or invalid PCM sample"); return 0; }
    uint32_t channels = (s->format & 2) ? 2 : 1, width = (s->format & 1) ? 2 : 1;
    uint32_t frames = bytes / (channels * width);
    if (bytes % (channels * width) || (uint64_t)frames * 2 * sizeof(float) > AUDIO_LIMIT) {
        error("invalid or oversized PCM sample"); return 0;
    }
    float *pcm = malloc((size_t)frames * 2 * sizeof(float));
    if (!pcm && frames) return 0;
    for (uint32_t f = 0; f < frames; f++) for (uint32_t c = 0; c < 2; c++) {
        uint32_t address = data + (f * channels + (channels == 1 ? 0 : c)) * width;
        pcm[f * 2 + c] = width == 2 ? (float)(int16_t)rd(G(address), 2) / 32768.0f
                                  : ((float)(uint8_t)rd(G(address), 1) - 128.0f) / 128.0f;
    }
    s->pcm = pcm; s->frames = frames;
    return 1;
}
K(address) { lock(); sample *s = lookup(A(0)); uint32_t ok = s ? set_pcm(s, A(1), A(2)) : 0; unlock(); return ok; }
K(set_rate) { lock(); sample *s = lookup(A(0)); if (s && A(1) && A(1) <= 384000) s->rate = A(1); unlock(); return 0; }
K(rate) { lock(); sample *s = lookup(A(0)); uint32_t v = s ? s->rate : 0; unlock(); return v; }
static float clamp01(float v) { return !isfinite(v) || v < 0 ? 0 : v > 1 ? 1 : v; }
K(set_volume_pan) { lock(); sample *s = lookup(A(0)); if (s) { s->volume = clamp01(F32(A(1))); s->pan = clamp01(F32(A(2))); } unlock(); return 0; }
K(set_volume) { lock(); sample *s = lookup(A(0)); if (s) s->volume = clamp01(F32(A(1))); unlock(); return 0; }
K(volume) {
    lock(); sample *s = lookup(A(0)); float v = s ? s->volume : 0; unlock();
    for (int i = 7; i > 0; i--) wr(R + 0x1100 + i * 16, 10, rd(R + 0x1100 + (i - 1) * 16, 10));
    wr(R + 0x1100, 10, d2f(v, 10)); // x86 float result is returned in x87 ST0
    return 0;
}
K(volume_pan) { lock(); sample *s = lookup(A(0)); if (s) { if (A(1)) wr(G(A(1)), 4, d2f(s->volume, 4)); if (A(2)) wr(G(A(2)), 4, d2f(s->pan, 4)); } unlock(); return 0; }
K(loops) { lock(); sample *s = lookup(A(0)); if (s) s->loops = A(1); unlock(); return 0; }
K(start) { lock(); sample *s = lookup(A(0)); if (s && (!s->buffered || s->playing != 4)) { s->cursor = 0; s->playing = s->frames || s->buffered ? 4 : 0; } unlock(); return 0; }
K(resume) { lock(); sample *s = lookup(A(0)); if (s && (s->frames || s->buffered)) s->playing = 4; unlock(); return 0; }
K(stop) { lock(); sample *s = lookup(A(0)); if (s) s->playing = 8; unlock(); return 0; }
K(end) { lock(); sample *s = lookup(A(0)); if (s) { s->playing = 0; s->cursor = s->frames; if (s->buffered) { s->eof = 1; for (int i = 0; i < 2; i++) s->buffers[i].state = 0; } } unlock(); return 0; }
K(status) { lock(); sample *s = lookup(A(0)); uint32_t v = s && s->playing ? (uint32_t)s->playing : 2; unlock(); return v; }
K(ms_position) {
    lock(); sample *s = lookup(A(0));
    if (s && s->rate) { if (A(1)) wr(G(A(1)), 4, (uint64_t)s->frames * 1000 / s->rate); if (A(2)) wr(G(A(2)), 4, (uint64_t)s->cursor * 1000 / s->rate); }
    unlock(); return 0;
}
K(set_ms_position) { lock(); sample *s = lookup(A(0)); if (s) s->cursor = fmin(s->frames, (double)A(1) * s->rate / 1000); unlock(); return 0; }
K(position) { lock(); sample *s = lookup(A(0)); if (s) for (int i = 0; i < 3; i++) s->position[i] = F32(A(i + 1)); unlock(); return 0; }
K(get_position) { lock(); sample *s = lookup(A(0)); if (s) for (int i = 0; i < 3; i++) if (A(i + 1)) wr(G(A(i + 1)), 4, d2f(s->position[i], 4)); unlock(); return 0; }
static uint32_t frame_bytes(const sample *s) { return ((s->format & 1) ? 2 : 1) * ((s->format & 2) ? 2 : 1); }
K(length) { lock(); sample *s = lookup(A(0)); uint32_t v = s ? s->frames * frame_bytes(s) : 0; unlock(); return v; }
K(offset) { lock(); sample *s = lookup(A(0)); uint32_t v = s ? (uint32_t)s->cursor * frame_bytes(s) : 0; unlock(); return v; }
K(set_offset) { lock(); sample *s = lookup(A(0)); if (s) s->cursor = fmin(s->frames, A(1) / frame_bytes(s)); unlock(); return 0; }
K(wav_info) {
    uint32_t data = A(0), info = A(1);
    if (!guest_range(info, 36) || !guest_range(data, 12) || mem32(data) != 0x46464952u || mem32(data + 8) != 0x45564157u) return 0;
    uint64_t total = (uint64_t)mem32(data + 4) + 8;
    if (total > AUDIO_LIMIT || !guest_range(data, (uint32_t)total)) return 0;
    /* Miles metadata borrows the WAV payload. Copying every PCM file into the
     * guest heap leaked an entire sound bank each time a map was loaded. */
    uint32_t fmt = 0, payload = 0, payload_size = 0;
    for (uint64_t offset = 12; offset + 8 <= total;) {
        uint32_t chunk = data + (uint32_t)offset, length = mem32(chunk + 4);
        if ((uint64_t)length > total - offset - 8) return 0;
        if (mem32(chunk) == 0x20746d66u && length >= 16) fmt = chunk + 8;
        if (mem32(chunk) == 0x61746164u && !payload) {
            payload = chunk + 8; payload_size = length;
        }
        offset += 8ull + length + (length & 1);
    }
    if (fmt && payload && rd(G(fmt), 2) == 1) {
        uint32_t channels = (uint32_t)rd(G(fmt + 2), 2);
        uint32_t rate = mem32(fmt + 4), bits = (uint32_t)rd(G(fmt + 14), 2);
        uint32_t block = channels * (bits / 8);
        if ((channels != 1 && channels != 2) || (bits != 8 && bits != 16)
                || rate < 1000 || rate > 384000 || !payload_size
                || rd(G(fmt + 12), 2) != block || payload_size % block) return 0;
        uint32_t words[9] = {1, payload, payload_size, rate, bits, channels,
            payload_size / block, block, payload};
        memcpy(G(info), words, sizeof words);
        return 1;
    }
    SDL_AudioSpec spec; Uint8 *bytes = NULL; Uint32 count = 0;
    if (!SDL_LoadWAV_RW(SDL_RWFromConstMem(G(data), (int)total), 1, &spec, &bytes, &count)) { error(SDL_GetError()); return 0; }
    if (!count || count > AUDIO_LIMIT || spec.channels < 1 || spec.channels > 2
            || spec.freq < 1000 || spec.freq > 384000) { SDL_FreeWAV(bytes); error("unsupported WAV metadata"); return 0; }
    SDL_AudioCVT cvt;
    if (SDL_BuildAudioCVT(&cvt, spec.format, spec.channels, spec.freq, AUDIO_S16SYS, spec.channels, spec.freq) < 0) { SDL_FreeWAV(bytes); return 0; }
    if ((uint64_t)count * cvt.len_mult > AUDIO_LIMIT) { SDL_FreeWAV(bytes); error("decoded WAV exceeds limit"); return 0; }
    cvt.len = (int)count; cvt.buf = malloc((size_t)count * cvt.len_mult);
    if (!cvt.buf) { SDL_FreeWAV(bytes); return 0; }
    memcpy(cvt.buf, bytes, count); SDL_FreeWAV(bytes);
    if (SDL_ConvertAudio(&cvt)) { free(cvt.buf); return 0; }
    uint32_t guest = guest_alloc((uint32_t)cvt.len_cvt);
    memcpy(G(guest), cvt.buf, (size_t)cvt.len_cvt); free(cvt.buf);
    uint32_t words[9] = {1, guest, (uint32_t)cvt.len_cvt, (uint32_t)spec.freq, 16, spec.channels,
        (uint32_t)cvt.len_cvt / (2 * spec.channels), (uint32_t)(2 * spec.channels), guest};
    memcpy(G(info), words, sizeof words);
    return 1;
}
K(info) {
    uint32_t p = A(1); lock(); sample *s = lookup(A(0));
    uint32_t result = 0;
    if (s) {
        clear_pcm(s);
        if (guest_range(p, 36) && mem32(p) == 1 && mem32(p + 12) >= 1000
                && mem32(p + 12) <= 384000 && (mem32(p + 16) == 8 || mem32(p + 16) == 16)
                && (mem32(p + 20) == 1 || mem32(p + 20) == 2)) {
            s->format = (mem32(p + 16) == 16) + (mem32(p + 20) == 2 ? 2 : 0);
            s->rate = mem32(p + 12); result = set_pcm(s, mem32(p + 4), mem32(p + 8));
        } else error("unsupported or invalid sample metadata");
    }
    unlock(); return result;
}
static Uint8 *convert_info(uint32_t info, uint32_t rate, uint32_t format, uint32_t *size) {
    if (!guest_range(info, 36) || mem32(info) != 1 || !rate || rate > 384000 || format > 3) return NULL;
    uint32_t src = mem32(info + 4), bytes = mem32(info + 8), src_rate = mem32(info + 12);
    uint32_t bits = mem32(info + 16), channels = mem32(info + 20);
    if (!guest_range(src, bytes) || src_rate < 1000 || src_rate > 384000 || channels < 1 || channels > 2 || (bits != 8 && bits != 16)) return NULL;
    SDL_AudioCVT cvt;
    if (SDL_BuildAudioCVT(&cvt, bits == 16 ? AUDIO_S16SYS : AUDIO_U8, (Uint8)channels, (int)src_rate,
            (format & 1) ? AUDIO_S16SYS : AUDIO_U8, (format & 2) ? 2 : 1, (int)rate) < 0) return NULL;
    if ((uint64_t)bytes * cvt.len_mult > AUDIO_LIMIT) return NULL;
    cvt.len = (int)bytes; cvt.buf = malloc((size_t)bytes * cvt.len_mult);
    if (!cvt.buf) return NULL;
    memcpy(cvt.buf, G(src), bytes);
    if (SDL_ConvertAudio(&cvt)) { free(cvt.buf); return NULL; }
    *size = (uint32_t)cvt.len_cvt; return cvt.buf;
}
K(processed_size) {
    uint32_t bytes = 0;
    Uint8 *pcm = convert_info(A(3), A(0), A(1), &bytes);
    free(pcm); return bytes;
}
K(process) {
    uint32_t bytes = 0;
    Uint8 *pcm = convert_info(A(5), A(2), A(3), &bytes);
    if (!pcm || bytes > A(1) || !guest_range(A(0), A(1))) { free(pcm); return 0; }
    memcpy(G(A(0)), pcm, bytes);
    if (A(1) > bytes) memset(G(A(0) + bytes), 0, A(1) - bytes);
    free(pcm); return 1;
}
K(minimum_buffer) {
    uint32_t rate = A(1), format = A(2);
    if (rate < 1000 || rate > 384000 || format > 3) return 0;
    uint32_t width = ((format & 1) ? 2 : 1) * ((format & 2) ? 2 : 1);
    uint32_t bytes = (uint32_t)(((uint64_t)2048 * rate + output_rate - 1) / output_rate) * width;
    return bytes < 4096 ? 4096 : (bytes + 31) & ~31u;
}
K(buffer_ready) {
    lock(); sample *s = lookup(A(0)); uint32_t slot = UINT32_MAX;
    if (s) for (int i = 0; i < 2; i++) if (!s->buffers[i].state) {
        s->buffers[i].state = 1; slot = (uint32_t)i; break;
    }
    unlock(); return slot;
}
K(load_buffer) {
    lock(); sample *s = lookup(A(0)); uint32_t slot = A(1), result = 0;
    if (s && slot < 2 && s->buffers[slot].state != 2) {
        if (!A(3)) { s->eof = 1; s->buffers[slot].state = 0; result = 1; }
        else {
            sample copy = {.format = s->format};
            if (set_pcm(&copy, A(2), A(3))) {
                if (!s->buffered) { free(s->pcm); s->pcm = NULL; s->frames = 0; s->cursor = 0; s->buffered = 1; s->active_buffer = (int)slot; }
                pcm_buffer *b = &s->buffers[slot]; free(b->pcm);
                *b = (pcm_buffer){copy.pcm, copy.frames, 2};
                if (s->buffers[s->active_buffer].state != 2) { s->active_buffer = (int)slot; s->cursor = 0; }
                s->eof = 0; if (s->playing != 8) s->playing = 4; result = 1;
            }
        }
    }
    if (!result) {
        error("invalid or occupied audio buffer");
        if (s && slot < 2 && s->buffers[slot].state != 2) {
            s->buffers[slot].state = 0;
            if (s->buffered && s->buffers[0].state != 2 && s->buffers[1].state != 2) s->playing = 0;
        }
    }
    unlock(); return result;
}
K(zero) { (void)esp; return 0; }

#define M(name, fn, pop) {"mss32.dll", "_AIL_" name "@" #pop, k_##fn, pop}
const thunk_def audio_thunks[] = {
    M("open_stream", open_stream, 12), M("close_stream", release, 4), M("start_stream", start_stream, 4),
    M("pause_stream", pause_stream, 8), M("stream_status", status, 4),
    M("stream_playback_rate", rate, 4), M("set_stream_playback_rate", set_rate, 8),
    M("stream_volume_pan", volume_pan, 12), M("set_stream_volume_pan", set_volume_pan, 12),
    M("set_stream_loop_count", loops, 8), M("stream_ms_position", stream_ms_position, 12),
    M("set_stream_ms_position", set_stream_ms_position, 8), M("set_stream_reverb_levels", zero, 12),
    M("startup", startup, 0), M("shutdown", shutdown, 0), M("open_digital_driver", open_driver, 16),
    M("set_file_callbacks", file_callbacks, 16), M("set_redist_directory", zero, 4), M("set_preference", zero, 8),
    M("last_error", last_error, 0), M("enumerate_3D_providers", enumerate, 12), M("open_3D_provider", zero, 4),
    M("close_3D_provider", zero, 4), M("3D_provider_attribute", attribute, 12),
    M("set_3D_distance_factor", zero, 8), M("set_DirectSound_HWND", zero, 8),
    M("allocate_sample_handle", allocate, 4), M("allocate_3D_sample_handle", allocate, 4),
    M("release_sample_handle", release, 4), M("init_sample", init, 4),
    M("set_sample_type", type, 12), M("set_sample_address", address, 12), M("set_3D_sample_info", info, 8),
    M("set_sample_adpcm_block_size", zero, 8), M("set_sample_playback_rate", set_rate, 8),
    M("set_3D_sample_playback_rate", set_rate, 8), M("sample_playback_rate", rate, 4), M("3D_sample_playback_rate", rate, 4),
    M("set_sample_volume_pan", set_volume_pan, 12), M("sample_volume_pan", volume_pan, 12),
    M("set_3D_sample_volume", set_volume, 8), M("3D_sample_volume", volume, 4),
    M("set_sample_loop_count", loops, 8), M("set_3D_sample_loop_count", loops, 8),
    M("start_sample", start, 4), M("start_3D_sample", start, 4), M("resume_sample", resume, 4), M("resume_3D_sample", resume, 4),
    M("stop_sample", stop, 4), M("end_sample", end, 4), M("stop_3D_sample", stop, 4), M("end_3D_sample", end, 4),
    M("sample_status", status, 4), M("3D_sample_status", status, 4),
    M("sample_ms_position", ms_position, 12), M("set_sample_ms_position", set_ms_position, 8),
    M("sample_position", offset, 4), M("3D_sample_offset", offset, 4), M("set_3D_sample_offset", set_offset, 8),
    M("minimum_sample_buffer_size", minimum_buffer, 12), M("sample_buffer_ready", buffer_ready, 4),
    M("load_sample_buffer", load_buffer, 16),
    M("3D_sample_length", length, 4), M("set_3D_position", position, 16), M("3D_position", get_position, 16),
    M("WAV_info", wav_info, 8), M("set_sample_reverb_levels", zero, 12), M("set_3D_sample_effects_level", zero, 8),
    M("size_processed_digital_audio", processed_size, 16), M("process_digital_audio", process, 24),
    M("set_3D_sample_distances", zero, 12), M("set_3D_room_type", zero, 8), M("set_digital_master_room_type", zero, 8),
    M("digital_CPU_percent", zero, 4), M("set_3D_sample_preference", zero, 12), M("set_3D_provider_preference", zero, 12),
    {0, 0, 0, 0}
};
