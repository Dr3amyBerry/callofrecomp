# Renderer API inventory

This is the first broad inventory of GL/WGL API-name strings referenced by executable code in the supplied `CoDSP.exe` 1.5 baseline.

The inventory is intentionally phrased as **referenced API-name strings**. A candidate absolute string reference is not, by itself, proof that every name is successfully resolved or used on every hardware path.

## Scope

Using the strict name pattern:

```regex
^(?:wgl|gl)[A-Z][A-Za-z0-9_]*$
```

the executable contains **506 unique GL/WGL-style API-name strings with candidate references from executable sections**:

- **486** `gl*` names
- **20** `wgl*` names

Suffix-oriented extension counts inside that referenced set include:

| Suffix | referenced names |
|---|---:|
| `ARB` | 82 |
| `EXT` | 5 |
| `NV` | 26 |
| `ATI` | 31 |

There are also hundreds of unsuffixed `gl*` names, covering the fixed-function/core desktop OpenGL interface used by this generation of renderer.

## Referenced WGL surface

The observed WGL-name set is:

```text
wglAllocateMemoryNV
wglCopyContext
wglCreateContext
wglCreateLayerContext
wglDeleteContext
wglDescribeLayerPlane
wglFreeMemoryNV
wglGetCurrentContext
wglGetCurrentDC
wglGetExtensionsStringEXT
wglGetLayerPaletteEntries
wglGetProcAddress
wglMakeCurrent
wglRealizeLayerPalette
wglSetLayerPaletteEntries
wglShareLists
wglSwapIntervalEXT
wglSwapLayerBuffers
wglUseFontBitmaps
wglUseFontOutlines
```

Not all of these will need a one-for-one Android replacement. Several belong to Windows-only context, font, layer-plane, or swap-control facilities.

## High-level Android classification

### Platform-only WGL operations

These belong to the Win32/WGL integration layer and should not survive as public renderer requirements on Android:

- context creation/current-context management
- layer-plane operations
- Windows font-to-display-list helpers
- Windows WGL extension querying
- WGL swap interval
- WGL-specific memory extensions

They should be replaced behind a platform graphics interface.

### Desktop fixed-function OpenGL

The binary references the broad classic OpenGL surface, including immediate-mode/fixed-function families such as:

- `glVertex*`
- `glTexCoord*`
- matrix stack operations
- fixed-function lighting/material/fog
- client-state arrays
- classic texture environment/state calls

Android OpenGL ES does not expose the entire desktop fixed-function API. This is therefore a significant compatibility boundary: the port should not simply rename imports. The renderer-facing compatibility layer will need either:

1. translation of the subset actually exercised by CoD into GLES-compatible operations; or
2. a reconstructed renderer path that expresses the same game behavior through a modern backend.

The exact decision should be driven by call-site usage, not by the presence of API-name strings alone.

### Legacy vendor extensions

The executable also contains substantial ARB/NV/ATI-era extension handling. These are strong candidates for capability-path pruning or replacement after we establish which paths the base single-player renderer actually selects.

## Reproducible scan

`tools/string_xrefs.py` can regenerate the API-name/xref inventory from the original executable:

```bash
python tools/string_xrefs.py originals/CoDSP.exe \
  --regex '^(?:wgl|gl)[A-Z][A-Za-z0-9_]*$' \
  --json analysis/local/gl_string_xrefs.json
```

The next renderer-analysis step is to connect these name references to the function-pointer globals populated by the dynamic resolver and then map actual call sites to determine the minimum renderer API required for first boot.
