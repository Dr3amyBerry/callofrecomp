# Entorno local de trabajo

La reorganización conserva el código y el comportamiento del juego. Las rutas
antiguas siguen disponibles mediante junctions de Windows para preservar los
cachés de CMake, scripts y comandos existentes.

| Carpeta | Contenido |
| --- | --- |
| `src/`, `include/`, `tests/` | Código del host y sus pruebas |
| `android/` | Integración Android, launcher y CMake |
| `tools/` | Herramientas de análisis, recompilación y mantenimiento |
| `analysis/`, `docs/` | Evidencia compartible y documentación |
| `web/` | Empaquetador público |
| `.local/references/` | Quake3e, openmohaa, gl4es y opencod1 descargados con Git |
| `.local/dependencies/` | Dependencias fijadas de la build Android |
| `.local/builds/` | Compilaciones actuales y empaquetado locales; `history/` conserva ensayos de build pasados, sin pretender que sus cachés CMake sean reutilizables tras moverlas |
| `.local/private/` | Instalación original, decompilación, Ghidra y salidas privadas |
| `.local/toolchains/` | Android Performance Analyzer 0.9.0 para Windows, con su JBR |
| `.local/downloads/` | ZIP oficial de APA |
| `.local/profiles/` | Lugar reservado para proyectos y capturas de rendimiento |

**Ruta recomendada a las IAs:** [AGENTS](../AGENTS.md) → [estado vigente](PROJECT_STATUS.md) → [roadmap](ROADMAP.md) → [registro acumulativo](OPTIMIZATION_LEDGER.md). Las más de cien notas y decenas de scripts locales de experimentos no deben leerse como una cola actual. Búsqueda dirigida por nombre de transformación, APK/ELF Build ID, escena y fecha; ignorar por defecto `.local/builds/`, `references/`, `dependencies/`, `toolchains/`, `downloads/`, `decomp/` y snapshots de terceros. Los scripts y capturas privados se preservan, no se deduplican automáticamente.

Se archivaron siete conjuntos históricos: cuatro árboles de builds de CFG14 en `.local/builds/history/cfg14/` y tres releases anteriores en `.local/builds/history/releases/`. El release v0.2.3, los objetos generados activos y las junctions permanecieron donde los necesitan las herramientas. Ver el inventario local `.local/catalog/BUILDS.md` y `.local/catalog/SCRIPTS.md`.

Todo `.local/` está excluido de Git. No subir recursos del juego, APK privado,
fuentes generadas del original ni capturas privadas.

VS Code oculta las rutas antiguas de compatibilidad con `.vscode/settings.json`.
Los archivos locales se navegan desde `.local/`; las búsquedas y los monitores
de archivos excluyen las compilaciones y los datos privados para evitar duplicados
y trabajo innecesario del editor.

## Referencias descargadas

Las copias incluyen los submódulos declarados y conservan sus licencias originales.
Son referencias de consulta; no están integradas en el juego ni compiladas como
motores adicionales. GL4ES de consulta está separado de la copia de build con
el parche local.

| Repositorio | Revisión descargada |
| --- | --- |
| [Quake3e](https://github.com/ec-/Quake3e) | `fe07ae0eb34aad954715c74ec0cd76baa48a0419` |
| [openmohaa](https://github.com/openmoh/openmohaa) | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| [gl4es](https://github.com/ptitSeb/gl4es) | `ec16bedd8819c475326f4f1a3063772c6d986e06` |
| [opencod1](https://github.com/opencod1/opencod1) | `718e994af62ca2cbc79d911bab73c445637b94e7` |

El inventario local y el hash del instalador están en
`.local/environment-manifest.json`.

## Android Performance Analyzer

Distribución oficial instalada de forma portable en
`.local/toolchains/android-performance-analyzer/apa-windows/`.
ZIP verificado por CRC; SHA-256:
`6e93f6fda0c4b4d53e5cdec75ed38d4085476bdbe0b131fe7e43b28bcb473dc3`.

Abrir cuando se vaya a medir:

```powershell
powershell -ExecutionPolicy Bypass -File tools/open_performance_analyzer.ps1
```

El launcher configura `ANDROID_HOME` únicamente para ese proceso si falta.
Guardar los proyectos de captura en `.local/profiles/`. Según la
[guía oficial](https://developer.android.com/android-performance-analyzer/quickstart),
el perfilador de sistema requiere un teléfono compatible con Android 12 o superior
y depuración ADB. La instalación no implica que un dispositivo haya pasado la
validación ni que se haya registrado una captura.

## Compatibilidad de carpetas

`tools/organize_workspace.ps1` organiza las carpetas de manera repetible y valida
que los movimientos permanezcan dentro del proyecto. Los alias antiguos se
ocultan en Explorer. No borrar junctions de forma recursiva.

Windows bloqueó el movimiento físico de `build-retrotouch/` y `recomp_out/`.
Se conservan en su lugar y se accede a ellas también desde `.local/builds/` y
`.local/private/` mediante junctions inversos. No se cerraron aplicaciones ni
se borraron archivos para forzar el movimiento.

**Capturas, mediciones y scripts privados:** [convención obligatoria para ChatGPT y MCP](guides/LOCAL_ARTIFACTS.md). La ruta nueva es `.local/profiles/runs/`; la herramienta `tools/local_workspace.py` crea sesiones y consulta un índice, y `tools/local_capture.py` guarda PNG persistentes. Las rutas antiguas se conservan para reproducir estudios y no interrumpir a otra IA.


**Lotes privados 2026-10-15:** **200 scripts históricos** archivados en dos tandas bajo `.local/profiles/history/scripts/`; quedan **353** scripts Python sueltos. La segunda tanda tiene un manifiesto SHA256 independiente (`.local/catalog/archived_legacy_scripts_2026-10-15_batch02.json`). El inventario y la auditoría SHA están en `.local/catalog/`, junto con `verification_report.json`. [Procedimiento y criterios de restauración](guides/LOCAL_ARTIFACTS.md). Para ejecutar de nuevo: `python tools/local_workspace.py refresh` y `python tools/verify_local_artifacts.py --save`.
