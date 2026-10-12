# Absolute touch mapping for the verified SP UI

The baseline is `analysis/baselines/cod1_sp_pc_1_5.json`. This mapping is specific
to that UI image, not a guessed cross-version interface.

- `uix86.dll` vmMain command 4 dispatches at `0x400079D6` to `0x4000C660`.
- That routine adds integer deltas to cursor globals `0x401C0470` (X) and
  `0x401C0474` (Y), then clamps them to 0..640 and 0..480 respectively.
- Engine mouse coordinates are screen-relative; rendering scales the original
  UI coordinate system. Treating a 1280x720 touch as a raw mouse delta therefore
  does not place the UI cursor at the touched point.

The engine host reads the current UI cursor and converts a normalized touch into
a delta in the original 640x480 space. The window shim replaces its pending mouse
delta relative to the last SetCursorPos warp. Replacing rather than adding is
essential when down/move/up arrive before one engine frame.

The delta goes through the original IN_MouseMove and VM_Call path. Calling the
UI vmMain directly from the event pump bypasses the engine's current VM syscall
context and failed on WSA during hover. The final adapter only reads cursor
globals; it never executes guest code during SDL event pumping.

Activation also belongs to each guest game window: the splash and renderer share
one SDL window, but have distinct original WndProcs. Resetting activation when
the renderer becomes the input target ensures it gets WM_ACTIVATE/WM_SETFOCUS
even when Android emits no second SDL focus event.

Validation: the batched absolute-touch smoke failed before replacing the delta
and passed after it; WSA x86-64 direct taps open Options, return to main and
start the original training map. Keyboard/relative gameplay input keeps its
existing path. Physical ARM64 validation remains separate.
