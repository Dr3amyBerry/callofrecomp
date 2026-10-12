# Portable Miles boundary

The engine remains the recompilation of the original `CoDSP.exe`; replace its
Miles imports with a portable SDL audio backend, retaining original sound assets.
Guest callbacks and guest pointers must never execute on the audio thread.

## Evidence from the pinned executable

- `0x00445C80`: startup, file callbacks and digital-driver initialization.
- `0x004416B0`: `open_digital_driver(rate, format, channels, flags)`; format
  1 means 8-bit and 2 means 16-bit. The engine requests 11/22/44 kHz.
- `0x004417F0`: provider enumeration outputs iterator, provider and guest name.
  Successful provider open returns zero. The positional provider exposes
  maximum sample count and reports unsupported EAX properties with `-1`.
- `0x00441B80`: allocate 32 digital and up to 32 positional sample handles.
- `0x00442500` family: sample status 2 is finished; playing uses another state.
- `0x00445A30`: `WAV_info` returns a nine-word structure: format, data address,
  data bytes, rate, bits, channels, sample frames, block size, initial address.
- `0x00442800` family: sample format flags 0/1 are 8/16-bit mono, 2/3 stereo,
  and 5/7 are IMA ADPCM mono/stereo.

## Implementation phases

1. SDL device startup, providers, owned PCM sample buffers, volume/pan/rate,
   loop and playback state, WAV metadata and deterministic mixer tests.
2. Decode compressed WAV/MP3 and implement streams through original filesystem
   callbacks; validate loading and playback of original sound assets.
3. Positional attenuation/panning and effects, shutdown/restart, decoder and
   resource limits. Exercise menu, campaign map and sustained gameplay.

The audio callback mixes host-owned PCM only. Guest entry points execute on the
engine thread. SDL's device lock serializes changes with the callback. Unsupported
codecs fail explicitly; they must not silently report successful playback.

SDL's WAV reader and conversion APIs are documented at
https://wiki.libsdl.org/SDL2/SDL_LoadWAV_RW and
https://wiki.libsdl.org/SDL2/SDL_ConvertAudio.

## Verified desktop checkpoint (2026-10-12)

The real engine opens a 44,100 Hz stereo float SDL device, initializes its
32 positional channels and parses all UI menus through ui/pregame.menu.
This establishes resource loading and driver startup, not audible playback or
a visible working menu. CTest passes 11/11, including deterministic PCM mixing,
loop/pause/end states, 8-bit byte offsets, x87 float return ABI, WAV metadata,
resampling, output bounds and malformed metadata rejection.

The latest engine run stops at missing recompiled entry `0x0050B990` after
passing the verified `0x00518050` callback. Indirect-code coverage remains a
separate blocker from the unimplemented Miles imports.

The mixer retains positions but does not yet apply spatial attenuation. EAX,
reverb and preferences are unsupported; the corresponding setters currently
return without implementing effects. MP3 streams and double-buffer sample
loading remain unimplemented. Do not treat device startup as full Miles
compatibility.
