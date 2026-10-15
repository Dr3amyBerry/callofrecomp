# Fase 14 — Fuentes de referencia para CFG y sustitución estructural (2026-10-14)

**Estado:** preparación terminada: tres repositorios nuevos descargados mediante RigorCore Dev MCP, tres repositorios previamente descargados inspeccionados y reutilizados. **Fase 14 de CFG aún no implementada; ninguna mejora de FPS afirmada**.

## Destino y control de versiones

Todas las fuentes externas permanecen bajo `.local/references/`, excluida por `.gitignore`, sin submódulos, código vendorizado ni activos comerciales incorporados a `main`. Nuevas descargas `--depth 1 --filter=blob:none --sparse --single-branch`, sin submódulos, con árboles limitados a subsistemas útiles. Se verificó `origin`, `git rev-parse HEAD`, limpieza de `git status --porcelain`, existencia de archivos relevantes y licencias presentes. El manifiesto privado exacto está en `.local/references/phase14_reference_manifest.json`.

| Referencia | Commit verificado | Carpeta local | Estado y utilidad |
| --- | --- | --- | --- |
| [ioquake3](https://github.com/ioquake/ioq3) | `87a99d18206e878a20289f05ac3c16005dcae5c3` | `.local/references/ioq3` | **Nueva, sparse**. BSP, trazas, partición espacial, render |
| [iocod (KILLTUBE)](https://github.com/KILLTUBE/iocod) | `f8da04bd8ac5efd2b8aa4c21cf7d94d4e16a15f8` | `.local/references/iocod` | **Nueva, sparse**. Compatibilidad CoD1, especialmente formato BSP y render |
| [QEMU/TCG](https://github.com/qemu/qemu) | `8ee6c77176cfee03be0ec7665b6652b2f31f1531` | `.local/references/qemu-tcg` | **Nueva, sparse**. Diseño de bloques, optimización y materialización de estado |
| [OpenCoD1](https://github.com/opencod1/opencod1) | `718e994af62ca2cbc79d911bab73c445637b94e7` | `.local/references/opencod1` | **Existente, reutilizada**. Colisiones, estáticos y visor BSP en reimplementación CoD MP |
| [OpenMoHAA](https://github.com/openmoh/openmohaa) | `a2f340195975f4f042e28a60b62561dd9a0b2700` | `.local/references/openmohaa` | **Existente, reutilizada**. BSP y trazas del motor derivado de Quake 3 |
| [Quake3e](https://github.com/ec-/Quake3e) | `fe07ae0eb34aad954715c74ec0cd76baa48a0419` | `.local/references/Quake3e` | **Existente, reutilizada**. Alternativas del renderizador y trazas BSP |

### Rutas relevantes verificadas

- `ioq3/code/qcommon/cm_trace.c`, `cm_load.c`, `cm_patch.c`, `code/renderergl1/tr_world.c`, `code/renderergl2/tr_bsp.c`.
- `iocod/code/qcommon/cm_trace.c`, `cm_load.c`, `code/renderergl2/tr_bsp_cod1.c` (diferencias específicas CoD1).
- `qemu-tcg/tcg/optimize.c`, `docs/devel/tcg.rst`, `docs/devel/tcg-ops.rst`.
- `opencod1/src/qcommon/cm_trace.c`, `src/renderer/tr_world.c`; `openmohaa/code/qcommon/cm_trace.c`; `Quake3e/code/qcommon/cm_trace.c`.

**Precauciones:** ioquake3, iocod, Quake3e y OpenMoHAA contienen licencias GPL-2.0; QEMU tiene un mosaico de licencias por archivo, con `COPYING` GPL-2 y `LICENSE` como descripción. La licencia de OpenCoD1 debe revisarse explícitamente antes de reutilizar código porque no se identificó una licencia raíz en esta inspección. Todas las fuentes son **referencias de estudio**: no copiar, enlazar ni distribuir código GPL dentro de CallofRecomp sin analizar obligaciones de licencia. No están incluidas las fuentes originales de CoD 1.5 single-player ni los assets del juego.

## Siguiente trabajo técnico, no iniciado en este bloque

1. Construir **CFG real por función original** usando `recomp_out/codsp.pcode`, mapa Ghidra ya auditado, targets de `BRANCH/CBRANCH/RETURN` y saltos entre chunks. No equiparar 1.500 instrucciones arbitrarias con una función; `0x0041B8F0` tiene dos intervalos y comparte chunk con otras funciones.
2. Priorizar los cuerpos físicos muestreados `0x0041B8F0`, `0x004196F0`, `0x0047BD40`, `0x004D8280`, `0x004D94C0`; la etiqueta de función y semántica BSP/colisión son hipótesis hasta conectar llamadas/datos con evidencia del binario privado.
3. Demostrar entradas/salidas, alias de memoria, registros y EFLAGS/x87 por región; extender el oráculo **x86 Unicorn independiente** existente más allá de las 20 instrucciones de prólogo verificadas.
4. Solo después implementar versiones A/B de un **grupo de bloques CFG coherente**. Medir carga/store y código nativo ARM64, además de pruebas diferenciales completas; no extrapolar a milisegundos ni FPS hasta que esté disponible el TECNO.

**No se modificó el motor recompilado, Android, el renderizador, los archivos comerciales ni los guardados.** Las descargas no agregan dependencias a la APK; su objetivo es la fase 14 posterior.
