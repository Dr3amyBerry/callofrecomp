# Campaign verification

Use owned Call of Duty 1.5 files. Reports, extracted scripts, profiles and
game logs belong under ignored `analysis/local` or `recomp_out` directories.

`python tools/recomp/audit_campaign.py --help` describes the resource audit.
It validates PK3 CRCs, BSP headers, script entrypoints, static script dependencies
and literal mission destinations. The baseline graph contains 33 reachable
maps: 26 gameplay/training maps, six briefing maps and credits. Static validation
cannot prove that objectives, AI triggers or scripted encounters work in play.

Run `python tools/recomp/probe_campaign.py --help` for the native startup probe.
Each map receives a separate profile and log. A successful result requires a
normal exit, the correct server map, client game initialization and no detected
fatal/script error. Reports record the engine SHA-256 and explicitly leave
`completion_verified` false. Briefing dismissal and complete objective sequences
require separate interactive verification.

During the 2026-10-12 sweep, Brecourt and Hurtgen stalled. Brecourt's original
angle-normalization loop received infinity because the runtime stored an IEEE
double in a ten-byte x87 slot. The embedded original math library reads those
slots as binary80. The runtime now encodes the explicit significand and exponent
correctly, while arithmetic still uses double precision and range. It does not
implement full x87 extended-precision arithmetic or exception semantics.

The format is documented in Intel's
[floating-point reference sheet](https://cdrdv2-public.intel.com/786447/floating-point-reference-sheet-for-intel-architecture.pdf).
Regression coverage includes literal encodings, subnormals, special values,
rounding boundaries, unsupported encodings and neighboring-byte preservation.
A private probe against the original game function reproduced an infinite yaw
before the fix and six correct vector angles afterward. Both previously stalled
maps subsequently initialized and exited normally with rebuilt native objects.

Do not equate a forced-success fixture with completing a mission. Such a fixture
can isolate victory UI and next-map handling, but bypasses the objective sequence.
Likewise, loading all 33 maps does not certify that the campaign is completable.

The numeric-fix sweep initialized all 33 maps normally. It preceded the final
DLL/audio lifecycle changes. A separate transition fixture exposed stale
navigation data because `FreeLibrary` did nothing. An isolated DLL reload
experiment advanced training → us_intro → pathfinder before exhausting memory.
The final runtime implements reference counts, detach/unload, dispatch removal,
zeroed reloads, reusable TLS slots and reclamation of private CRT heaps. PCM WAV metadata
now borrows its original payload, avoiding a duplicated sound bank per load.
Non-PCM conversion still uses the existing decoded-buffer allocation path.

Reference-count and detach behavior follows Microsoft's
[FreeLibrary contract](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-freelibrary).
Synthetic tests cover repeated load/unload, BSS reset, stale dispatch rejection,
heap isolation/destruction and borrowed PCM metadata. Per the user's flash-mode
instruction, final visual and gameplay validation is delegated to the user;
see [manual checks](MANUAL_PLAYTEST.md). No full mission completion is certified.
