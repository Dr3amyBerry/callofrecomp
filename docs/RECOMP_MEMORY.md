# Guest memory lifecycle

The runtime reserves a 4 GiB host address window for 32-bit guest addresses.
Engine resource allocations must be reclaimed across restarts and map loading.
The previous monotonic allocator and no-op HeapFree/VirtualFree exhausted its
256 MiB arena during the original `spmap training` path.

Heap allocations remain in `0x60000000..0x70000000`, aligned to 16 bytes with
the existing size header. Host-owned hash metadata records live blocks; a sorted
free list coalesces adjacent spans. Free invalidates the allocation; later
allocation reuses its space. Realloc preserves bytes, frees moved allocations,
and preserves the original allocation on failure. In-place-only growth fails
when the current span cannot hold the new size. Freed heap pages remain committed
for reuse, with total committed space bounded by the unchanged arena.

Virtual reservations occupy a separate `0x80000000..0xF0000000` arena, with
64 KiB allocation bases and 4 KiB page ranges. Reserve leaves pages inaccessible;
commit enables access. Decommit releases physical pages and makes them
inaccessible while retaining the reservation. Release requires the exact base
and zero size, returns the reservation to the address pool, and releases backing
pages. Recommit yields zeroed memory. Platform operations use Windows decommit
or POSIX madvise/mprotect; no host pointer is returned to guest code.

These semantics follow Microsoft's [VirtualAlloc](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualalloc),
[VirtualFree](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualfree)
and [HeapReAlloc](https://learn.microsoft.com/en-us/windows/win32/api/heapapi/nf-heapapi-heaprealloc)
contracts for the exercised paths. This is not a complete Win32 memory subsystem:
HeapCreate still exposes one shared heap, HeapDestroy/VirtualProtect are existing
stubs, allocation protection modes are not modeled, and MEM_TOP_DOWN does not
alter placement. Nonzero fixed virtual reservations must lie in the dedicated
arena. Error-code/exception-generation and multithreaded heap semantics remain
unfinished. Unknown allocation flags fail instead of claiming support.

The synthetic CTest verifies repeated allocation/release beyond arena capacity,
reuse and coalescing, realloc contents and failure preservation, reservation
without commit, decommit/recommit zeros, release validation, adjacent-region
boundaries and overflow rejection. The original training run passes its former
heap-exhaustion point and now stops at a CRT floating-point exception
(`RaiseException(c000008f)`, return address `0x00524BE3`). Gameplay remains
unverified at that checkpoint; the floating-point runtime was the next investigation.

The subsequent PC campaign run exposed overlap between the four-MiB guest stack
(`0x0FD00000..0x10100000`) and the original TIB/CPUID scratch pages. A large
`gamex86` stack frame overwrote the SEH chain; the next CRT setjmp crashed reading
`0xEF7AF00C`. TIB and scratch now occupy `0x0FC10000` and `0x0FC00000`, below the
stack. A regression fails on the old overlap (exit 26) and checks that writing the
entire declared stack preserves the thread block and CPUID page. CTest: 12/12.

With this layout the real `pathfinder` probe passes client initialization, starts
the mission and accepts timed W input; the user confirms mission 1 controls work.
The isolated ADS pacing issue was traced to CPU calibration disabling prediction;
see [engine clocks](RECOMP_CLOCKS.md). An optional
`CODRECOMP_TRACE_FAULT` environment variable retains the last 64 dispatch PCs,
stack pointers and SEH values, printed with registers only after a fault.
