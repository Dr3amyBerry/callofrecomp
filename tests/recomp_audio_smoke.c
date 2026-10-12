#include <stdio.h>
#include <stdlib.h>
#include "audio.h"

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
    puts("portable PCM audio passed");
    return 0;
}
