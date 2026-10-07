# Dynamic OpenGL loader findings

This note records the first confirmed renderer/platform boundary in the supplied `CoDSP.exe` 1.5 baseline.

## Result

Desktop OpenGL is **not linked through a normal static `opengl32.dll` PE import descriptor**. The engine explicitly loads the library at runtime and resolves OpenGL/WGL entry points by name.

This is now an **observed** property of the executable, not an inference from renderer strings.

## Relevant PE import slots

The updated `tools/pe_inspect.py` now records each imported symbol's IAT RVA/VA. In the supplied baseline the relevant KERNEL32 imports are:

| IAT VA | Imported function |
|---:|---|
| `0x00533178` | `FreeLibrary` |
| `0x0053317C` | `GetProcAddress` |
| `0x00533180` | `LoadLibraryA` |

These addresses explain both the native VM loader and the OpenGL loader without relying on guessed API names.

## OpenGL library load

The string `opengl32.dll` is stored at VA `0x00552658`.

Observed engine code:

```text
0x004501D3  push 0x00552658           ; "opengl32.dll"
0x004501D8  call dword ptr [0x533180] ; LoadLibraryA
0x004501DE  mov ebp, eax
0x004501E0  test ebp, ebp
```

The returned module handle is retained in `EBP`.

Immediately afterward the engine loads the `GetProcAddress` IAT pointer into `ESI`:

```text
0x004501E8  mov esi, dword ptr [0x53317C] ; GetProcAddress
```

and resolves at least:

| Name | string VA |
|---|---:|
| `wglCreateContext` | `0x00552644` |
| `wglMakeCurrent` | `0x00552634` |
| `wglDeleteContext` | `0x00552620` |
| `glGetString` | `0x00552614` |

This code path establishes the Windows WGL context/bootstrap layer.

## Renderer GL dispatch-table construction

A later renderer initialization path repeatedly calls `GetProcAddress` using the stored OpenGL module handle at `0x01830CCC` and stores the resulting pointers in engine globals.

One directly observed example is:

```text
0x004C006E  push 0x00543598           ; "wglGetProcAddress"
0x004C0073  push dword ptr [0x1830CCC]
0x004C007E  call esi                  ; GetProcAddress resolver
```

The surrounding function performs the same operation for a large sequence of GL/WGL symbol-name strings and stores each returned address into renderer function-pointer globals.

## Porting consequence

The Android port should not attempt to preserve the Win32 loader itself.

This gives us a clean platform seam:

```text
original PC
LoadLibraryA("opengl32.dll")
        ↓
GetProcAddress("gl*"/"wgl*")
        ↓
renderer function-pointer table

Android port
platform graphics backend
        ↓
resolve / bind GLES or Vulkan implementation
        ↓
portable renderer-facing dispatch layer
```

The immediate next renderer task is to inventory the function-pointer table and separate:

1. core OpenGL functions whose behavior can map directly;
2. WGL-only context/swap/pixel-format operations that must be replaced;
3. extension functions that need GLES/Vulkan equivalents or compatibility implementations.

## Reproducibility

`tools/pe_inspect.py` now emits IAT addresses for imports, so the `LoadLibraryA` / `GetProcAddress` / `FreeLibrary` identification is reproducible from the original executable rather than maintained as an undocumented manual annotation.
