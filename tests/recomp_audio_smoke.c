#include <stdio.h>
#include <stdlib.h>
#include "audio.h"

static unsigned char mp3[417 * 6];
static uint32_t file_offset, closes;
static uint32_t file_open(uint32_t esp) {
    if (strcmp((char *)G(ARG(esp, 0)), "silent.mp3")) return 0;
    wr(G(ARG(esp, 1)), 4, 7); file_offset = 0; return sizeof mp3;
}
static uint32_t file_close(uint32_t esp) { (void)esp; closes++; return 0; }
static uint32_t file_seek(uint32_t esp) {
    int64_t p = (int32_t)ARG(esp, 1);
    if (ARG(esp, 2) == 1) p += file_offset;
    if (ARG(esp, 2) == 2) p += sizeof mp3;
    if (p < 0 || p > sizeof mp3) return UINT32_MAX;
    return file_offset = (uint32_t)p;
}
static uint32_t file_read(uint32_t esp) {
    uint32_t n = ARG(esp, 2);
    if (n > sizeof mp3 - file_offset) n = sizeof mp3 - file_offset;
    if (n > 173) n = 173; // Deliberately short filesystem reads.
    memcpy(G(ARG(esp, 1)), mp3 + file_offset, n); file_offset += n; return n;
}

static uint32_t invoke(const char *name, int count, uint32_t *args) {
    uint32_t fn = shim_lookup("mss32.dll", name);
    if (!fn) { fprintf(stderr, "missing audio thunk %s\n", name); exit(1); }
    return guest_call(fn, count, args);
}

int main(void) {
    guest_init();
    shims_register(audio_thunks);
    uint32_t args[6] = {0};
    uint32_t sample = invoke("_AIL_allocate_sample_handle@4", 1, args);
    if (!sample) return 2;
    uint32_t pcm = guest_alloc(8);
    for (int i = 0; i < 4; i++) wr(G(pcm + 2 * i), 2, 16384);
    args[0] = sample; args[1] = 1; args[2] = 0;
    invoke("_AIL_set_sample_type@12", 3, args);
    args[1] = pcm; args[2] = 8;
    invoke("_AIL_set_sample_address@12", 3, args);
    args[1] = 22050;
    invoke("_AIL_set_sample_playback_rate@8", 2, args);
    args[1] = 0x3f800000; args[2] = 0x3f000000; // unity gain, centered
    invoke("_AIL_set_sample_volume_pan@12", 3, args);
    invoke("_AIL_start_sample@4", 1, args);
    float out[8];
    audio_mix(out, 4, 22050);
    for (int i = 0; i < 8; i++) if (fabsf(out[i] - 0.5f) > 0.001f) return 3;
    audio_mix(out, 1, 22050);
    if (invoke("_AIL_sample_status@4", 1, args) != 2) return 4;
    // A looping sample remains active; stopping it must produce silence.
    args[1] = 0;
    invoke("_AIL_set_sample_loop_count@8", 2, args);
    invoke("_AIL_start_sample@4", 1, args);
    audio_mix(out, 4, 22050);
    audio_mix(out, 4, 22050);
    if (invoke("_AIL_sample_status@4", 1, args) != 4) return 5;
    invoke("_AIL_stop_sample@4", 1, args);
    if (invoke("_AIL_sample_status@4", 1, args) != 8) return 9;
    invoke("_AIL_resume_sample@4", 1, args);
    if (invoke("_AIL_sample_status@4", 1, args) != 4) return 10;
    invoke("_AIL_end_sample@4", 1, args);
    audio_mix(out, 4, 22050);
    for (int i = 0; i < 8; i++) if (out[i] != 0) return 6;
    invoke("_AIL_release_sample_handle@4", 1, args);
    uint32_t info = guest_alloc(36);
    uint32_t words[9] = {1, pcm, 8, 22050, 16, 1, 4, 2, pcm};
    memcpy(G(info), words, sizeof words);
    args[0] = 11025; args[1] = 1; args[2] = 1; args[3] = info;
    uint32_t bytes = invoke("_AIL_size_processed_digital_audio@16", 4, args);
    if (bytes != 4) return 7;
    uint32_t converted = guest_alloc(bytes + 4);
    wr(G(converted + bytes), 4, 0x12345678);
    args[0] = converted; args[1] = bytes; args[2] = 11025; args[3] = 1; args[4] = 1; args[5] = info;
    if (!invoke("_AIL_process_digital_audio@24", 6, args) || mem32(converted + bytes) != 0x12345678) return 8;
    args[0] = 0;
    sample = invoke("_AIL_allocate_sample_handle@4", 1, args);
    args[0] = sample; args[1] = 0x3f400000; // 0.75 volume
    invoke("_AIL_set_3D_sample_volume@8", 2, args);
    wr(R + 0x1100, 10, d2f(0.25, 10));
    invoke("_AIL_3D_sample_volume@4", 1, args);
    if (f2d(rd(R + 0x1100, 10), 10) != 0.75 || f2d(rd(R + 0x1110, 10), 10) != 0.25) return 11;
    args[1] = 0;
    invoke("_AIL_set_sample_type@12", 3, args);
    uint32_t pcm8 = guest_alloc(4);
    const unsigned char bytes8[4] = {128, 192, 64, 128};
    memcpy(G(pcm8), bytes8, 4);
    args[1] = pcm8; args[2] = 4;
    invoke("_AIL_set_sample_address@12", 3, args);
    if (invoke("_AIL_3D_sample_length@4", 1, args) != 4) return 12;
    invoke("_AIL_start_sample@4", 1, args);
    args[1] = 2;
    invoke("_AIL_set_3D_sample_offset@8", 2, args);
    if (invoke("_AIL_3D_sample_offset@4", 1, args) != 2) return 13;
    // Rejected compressed replacement must not replay the previous PCM buffer.
    args[1] = 5;
    invoke("_AIL_set_sample_type@12", 3, args);
    args[1] = pcm8; args[2] = 4;
    invoke("_AIL_set_sample_address@12", 3, args);
    invoke("_AIL_start_sample@4", 1, args);
    if (invoke("_AIL_sample_status@4", 1, args) != 2) return 14;
    // Metadata is an independent entry point and must reject malformed rates.
    args[1] = info;
    wr(G(info + 12), 4, 0xffffffff);
    if (invoke("_AIL_set_3D_sample_info@8", 2, args)) return 15;
    wr(G(info + 12), 4, 22050);
    if (!invoke("_AIL_set_3D_sample_info@8", 2, args)) return 16;
    wr(G(info), 4, 17);
    if (invoke("_AIL_set_3D_sample_info@8", 2, args)) return 17;
    invoke("_AIL_start_sample@4", 1, args);
    if (invoke("_AIL_sample_status@4", 1, args) != 2) return 18;
    args[1] = 0;
    if (invoke("_AIL_set_3D_sample_info@8", 2, args)) return 19;
    // Decode an actual RIFF/WAV container, rather than fabricated metadata.
    uint32_t wav = guest_alloc(52);
    const unsigned char header[44] = {
        'R','I','F','F',44,0,0,0,'W','A','V','E','f','m','t',' ',
        16,0,0,0,1,0,1,0,0x22,0x56,0,0,0x44,0xac,0,0,2,0,16,0,
        'd','a','t','a',8,0,0,0
    };
    memcpy(G(wav), header, sizeof header);
    memcpy(G(wav + 44), G(pcm), 8);
    args[0] = wav; args[1] = info;
    if (!invoke("_AIL_WAV_info@8", 2, args) || mem32(info + 8) != 8
            || mem32(info + 12) != 22050 || mem32(info + 16) != 16
            || mem32(info + 20) != 1 || mem32(info + 24) != 4
            || memcmp(G(mem32(info + 4)), G(pcm), 8)) return 20;
    args[1] = 0;
    if (invoke("_AIL_WAV_info@8", 2, args)) return 21;
    args[0] = sample;
    invoke("_AIL_init_sample@4", 1, args);
    args[1] = 1; args[2] = 0;
    invoke("_AIL_set_sample_type@12", 3, args);
    args[1] = 22050;
    invoke("_AIL_set_sample_playback_rate@8", 2, args);
    // Native Miles 6 claims each free slot once and auto-starts queued buffers.
    if (invoke("_AIL_sample_buffer_ready@4", 1, args) != 0
            || invoke("_AIL_sample_buffer_ready@4", 1, args) != 1
            || invoke("_AIL_sample_buffer_ready@4", 1, args) != UINT32_MAX) return 22;
    args[1] = 0; args[2] = pcm; args[3] = 8;
    invoke("_AIL_load_sample_buffer@16", 4, args);
    args[1] = 1;
    invoke("_AIL_load_sample_buffer@16", 4, args);
    // The callback owns copies, so guest memory changes cannot alter playback.
    memset(G(pcm), 0, 8);
    audio_mix(out, 4, 22050);
    for (int i = 0; i < 8; i++) if (fabsf(out[i] - 0.5f) > 0.001f) return 23;
    if (invoke("_AIL_sample_buffer_ready@4", 1, args) != 0) return 24;
    if (invoke("_AIL_sample_position@4", 1, args) != 0) return 30;
    audio_mix(out, 4, 22050);
    for (int i = 0; i < 8; i++) if (fabsf(out[i] - 0.5f) > 0.001f) return 25;
    if (invoke("_AIL_sample_buffer_ready@4", 1, args) != 1) return 26;
    audio_mix(out, 4, 22050);
    for (int i = 0; i < 8; i++) if (out[i] != 0) return 27;
    // An underrun stays recoverable; a later valid buffer resumes automatically.
    for (int i = 0; i < 4; i++) wr(G(pcm + 2*i), 2, 16384);
    args[1] = 0;
    invoke("_AIL_load_sample_buffer@16", 4, args);
    audio_mix(out, 2, 22050);
    if (invoke("_AIL_sample_position@4", 1, args) != 4) return 28;
    invoke("_AIL_end_sample@4", 1, args);
    audio_mix(out, 2, 22050);
    if (out[0] != 0 || invoke("_AIL_sample_status@4", 1, args) != 2) return 29;
    invoke("_AIL_init_sample@4", 1, args);
    args[1] = 1; args[2] = 0;
    invoke("_AIL_set_sample_type@12", 3, args);
    args[1] = 0; args[2] = pcm; args[3] = 8;
    invoke("_AIL_load_sample_buffer@16", 4, args);
    args[1] = 1;
    invoke("_AIL_load_sample_buffer@16", 4, args);
    audio_mix(out, 4, 22050);
    args[1] = 0; args[3] = 0;
    invoke("_AIL_load_sample_buffer@16", 4, args);
    audio_mix(out, 4, 22050);
    if (invoke("_AIL_sample_status@4", 1, args) != 2) return 31;
    invoke("_AIL_init_sample@4", 1, args);
    for (int i = 0; i < 3; i++) {
        uint32_t slot = invoke("_AIL_sample_buffer_ready@4", 1, args);
        if (slot > 1) return 32;
        args[1] = slot; args[2] = 0; args[3] = 8;
        invoke("_AIL_load_sample_buffer@16", 4, args);
    }
    if (invoke("_AIL_sample_status@4", 1, args) != 2) return 33;
    invoke("_AIL_release_sample_handle@4", 1, args);
    for (int i = 0; i < 6; i++) {
        mp3[417*i] = 0xff; mp3[417*i+1] = 0xfb; mp3[417*i+2] = 0x90;
    }
    args[0] = thunk_address("test", "open", file_open, 8);
    args[1] = thunk_address("test", "close", file_close, 4);
    args[2] = thunk_address("test", "seek", file_seek, 12);
    args[3] = thunk_address("test", "read", file_read, 12);
    invoke("_AIL_set_file_callbacks@16", 4, args);
    args[0] = 0; args[1] = guest_strdup("silent.mp3"); args[2] = 0;
    uint32_t stream = invoke("_AIL_open_stream@12", 3, args);
    if (!stream || closes != 1) return 34;
    args[0] = stream; args[1] = info; args[2] = info + 4;
    invoke("_AIL_stream_ms_position@12", 3, args);
    if (mem32(info) < 150 || mem32(info) > 157 || mem32(info+4)) return 35;
    invoke("_AIL_start_stream@4", 1, args);
    audio_mix(out, 4, 44100);
    if (invoke("_AIL_stream_status@4", 1, args) != 4) return 36;
    args[1] = 1;
    invoke("_AIL_pause_stream@8", 2, args);
    if (invoke("_AIL_stream_status@4", 1, args) != 8) return 37;
    args[1] = 0;
    invoke("_AIL_pause_stream@8", 2, args);
    args[1] = 100;
    invoke("_AIL_set_stream_ms_position@8", 2, args);
    args[1] = info; args[2] = info + 4;
    invoke("_AIL_stream_ms_position@12", 3, args);
    if (mem32(info+4) != 100) return 38;
    for (int i = 0; i < 2000; i++) audio_mix(out, 4, 44100);
    if (invoke("_AIL_stream_status@4", 1, args) != 2) return 39;
    args[1] = 0;
    invoke("_AIL_set_stream_loop_count@8", 2, args);
    invoke("_AIL_start_stream@4", 1, args);
    for (int i = 0; i < 2000; i++) audio_mix(out, 4, 44100);
    if (invoke("_AIL_stream_status@4", 1, args) != 4) return 40;
    invoke("_AIL_close_stream@4", 1, args);
    if (invoke("_AIL_stream_status@4", 1, args) != 2) return 41;
    memset(mp3, 0, sizeof mp3);
    args[0] = 0; args[1] = guest_strdup("silent.mp3"); args[2] = 0;
    if (invoke("_AIL_open_stream@12", 3, args) || closes != 2) return 42;
    args[1] = guest_strdup("missing.mp3");
    if (invoke("_AIL_open_stream@12", 3, args) || closes != 2) return 43;
    puts("portable PCM and MP3 stream audio passed");
    return 0;
}
