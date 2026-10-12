#pragma once
#include "recomp_rt.h"

extern const thunk_def audio_thunks[];
// Mix host-owned sample buffers into interleaved stereo float output.
void audio_mix(float *output, uint32_t frames, uint32_t output_rate);
