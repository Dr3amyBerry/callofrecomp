// Minimal SDL declarations so tests/recomp_audio_mix_span_smoke.c can compile
// tools/recomp/runtime/audio.c without SDL. Mixer-only; never used by APKs.
#pragma once
#include <stdint.h>
typedef uint8_t Uint8; typedef uint32_t Uint32; typedef uint32_t SDL_AudioDeviceID;
typedef uint16_t SDL_AudioFormat;
typedef struct { int freq; SDL_AudioFormat format; Uint8 channels; Uint32 size; uint16_t samples;
    void (*callback)(void *, Uint8 *, int); void *userdata; } SDL_AudioSpec;
typedef struct { int needed, len, len_cvt, len_mult; Uint8 *buf; } SDL_AudioCVT;
typedef struct SDL_RWops SDL_RWops;
#define AUDIO_F32SYS 0x8120
#define AUDIO_S16SYS 0x8010
#define AUDIO_U8 0x0008
#define SDL_AUDIO_ALLOW_FREQUENCY_CHANGE 1
#define SDL_INIT_AUDIO 0x10
int SDL_InitSubSystem(Uint32); void SDL_QuitSubSystem(Uint32); const char *SDL_GetError(void);
SDL_AudioDeviceID SDL_OpenAudioDevice(const char *, int, const SDL_AudioSpec *, SDL_AudioSpec *, int);
void SDL_CloseAudioDevice(SDL_AudioDeviceID); void SDL_PauseAudioDevice(SDL_AudioDeviceID, int);
void SDL_LockAudioDevice(SDL_AudioDeviceID); void SDL_UnlockAudioDevice(SDL_AudioDeviceID);
SDL_RWops *SDL_RWFromConstMem(const void *, int);
SDL_AudioSpec *SDL_LoadWAV_RW(SDL_RWops *, int, SDL_AudioSpec *, Uint8 **, Uint32 *);
void SDL_FreeWAV(Uint8 *); int SDL_BuildAudioCVT(SDL_AudioCVT *, SDL_AudioFormat, Uint8, int, SDL_AudioFormat, Uint8, int);
int SDL_ConvertAudio(SDL_AudioCVT *);
