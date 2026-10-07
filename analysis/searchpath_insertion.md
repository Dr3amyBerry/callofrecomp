# Deterministic model of an SP searchpath insertion routine

The original `CoDSP.exe` contains a 55-byte routine at `VA 0x004248B0`
(`RVA 0x248B0`) which inserts a 20-byte searchpath node into a linked list.
The input binary is pinned to SHA-256
`c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47`.

Direct observations: `[node+0]` is the next link; `[node+0x0C]` determines
which branch is taken; list head is at `0x013F9E3C`.

**Exact branch behavior at 0x004248B0:**

1. If the incoming node's `+0x0C` value is zero, or the list is empty:
   insert at the head.
2. Otherwise, keep the existing head and advance past the consecutive
   **zero-class successors** of that head. Insert immediately after
   that run, ahead of the first nonzero-class successor, or at the tail.

Note this is **not ordinary sorting**: when all nodes have nonzero fields,
the first node remains the head; newly added nonzero nodes insert in second
position. For example three consecutive insertions `(A,1),(B,1),(C,1)`
produce `A,C,B`, not `C,B,A`. With a later `(D,0)`, the order becomes
`D,A,C,B`.

The code in `src/searchpath_order.cpp` is an **independent behavioral model**
of this one function, NOT a claim that all original mount discovery, package
priority, language selection, loose-file handling, or startup rules are mapped.
The field at `+0x0C` is deliberately named `class_flag` rather than
`localized`: its meaning still requires verification.

To reproduce the routine fingerprint without distributing original code bytes:

```bash
python tools/searchpath_order_probe.py originals/CoDSP.exe \
  --json analysis/local/searchpath_order.json
```

The tool rejects other builds or modified code. CTest target
`searchpath_order_smoke` exercises the modeled insertion cases with synthetic
nodes. **This model is not yet wired into the VFS** because the engine's
creation of all searchpaths and their class fields must be reconstructed first.
