# CoD 1.5 SP startup searchpath helper: indexed scan

Source: SHA-256-pinned original `CoDSP.exe`
(`c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47`).

An executable routine at **VA `0x004250E0`** (40 bytes including the final
return) is independently verified with SHA-256
`4bab47e5b8163d26f05c3f0d73239b64b8569d16585fbfc2be0d86db7bf5cb4b`.
Its two relative calls both target the helper at **VA `0x00424E10`**.

Observed behavior of this routine, without interpreting unknown arguments:

- First, invoke `0x00424E10` with two immediate argument values `0, 0`
  (and other live register values).
- Then initialize a loop register to `13`.
- Call the same helper with immediate selector `1` and a descending index,
  from `13` through `0`, inclusive (14 iterations).
- The startup code calls `0x004250E0` from several sites in the area
  `0x00425AE4–0x00425C49`.

This strongly supports an **indexed searchpath discovery pattern**, but the
compiler register inputs, lookup table at `0x00564B08`, flags for node
construction, language selection and exact PK3 filename resolution need
separate tracing. **Do not infer that this means every PK3 has precisely 14
patch levels, nor replace the current VFS mount policy from this alone.**

Reproduce the observed scan without committing original binary bytes:

```bash
python tools/searchpath_startup_probe.py originals/CoDSP.exe \
  --json analysis/local/searchpath_startup.json
```

The output is JSON metadata only. The parser is fail-closed on unmatched
control flow and is covered by synthetic unit tests; with the original
binary available, set `CODRECOMP_ORIGINALS` for an additional real-data check.

Next: trace the helper at `0x00424E10` and the node constructors around
`0x00424D2F` and `0x0042506A` to determine which indexed sources become
PK3, loose-file or localization entries and the exact order they are inserted.
