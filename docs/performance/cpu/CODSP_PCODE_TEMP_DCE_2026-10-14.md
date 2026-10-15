# CoDSP p-code → C: eliminación de temporales muertos (2026-10-14)

**Objetivo final:** 60 FPS sostenidos en el spawn de Camp Toccoa (TECNO CK6n, Equilibrado). **Todavía no alcanzado.**
**Resultado de esta fase:** el análisis nuevo es semánticamente conservador y reduce el C fuente, pero **no demuestra ninguna ganancia de FPS**: Clang `-O1` ya eliminaba las mismas operaciones en las rutas estudiadas. El experimento está **OFF por defecto**.

## Trabajo de traductor (sin parches manuales sobre el C generado)

El generador `tools/recomp/pcode2c.py` ya utilizaba `flag_liveness.dead_flag_writes` para descartar escrituras de flags x86 demostrablemente muertos. El nuevo análisis `tools/recomp/temp_liveness.py` determina si una operación de enteros que escribe a varnodes únicos `u` resulta igualmente muerta, incluyendo cadenas cuyos únicos consumidores eran escrituras de flags ya eliminadas.

Salvaguardas concretas:
- Requiere `temporary_layout(ops) is not None`, prueba previa de que **cada byte** leído del temporal fue definido localmente en todas las rutas de entrada. No se usa con almacenamiento `U` global.
- Liveness byte a byte, puntos fijos sobre bucles, ramas `CBRANCH` y saltos relativos dentro de cada instrucción; calcula la transitividad de los consumidores.
- Solo elimina operaciones enteras del conjunto `PURE` sin operando directo en memoria; mantiene `LOAD`, `STORE`, divisiones, conversiones/comparaciones flotantes y operaciones desconocidas/externas. `CALLOTHER` y mnemónicos desconocidos observan conservadoramente todos los bytes únicos.
- Mantiene índices y etiquetas de p-code. Sustituye operaciones por `;` sin mover líneas fuente ni saltos.
- Parámetros nuevos **opt-in** `--prune-dead-temporaries --dead-temp-parts 1,8`, para aplicar el nuevo análisis exclusivamente a las particiones calientes de geometría `p1` (incluye `0x0041B8F0`) y visibilidad `p8` (familia `0x004Dxxxx`). Nada cambia si el flag no se pasa.

Reproducción con binario original y p-code PRIVADOS, nunca publicados:

```
python tools/recomp/pcode2c.py recomp_out/codsp.pcode "Call of Duty Deluxe Edition/CoDSP.exe" --parts 12 -o recomp_out/codsp_recomp.c --prune-dead-temporaries --dead-temp-parts 1,8
```

Para producción no aplicar esta regeneración directamente sobre fuentes `recomp_out` con wrappers experimentales (NaN/copy32/FCOM) sin respaldarlos. El estudio mantuvo versiones A y B aisladas bajo `.local/profiles/dce_codegen_A` y `_B` y copias privadas de `p1/p8`.

## Datos medidos (en esta sesión)

El p-code CoDSP privado tenía 333.208 instrucciones Ghidra. La diferencia del C generado, **además** de la eliminación de banderas que ya existía, fue:

| Partición | Operaciones p-code (estáticas) | Operaciones únicas eliminadas | Bytes menos en C generado |
|---|---:|---:|---:|
| `p1` geometría | 147.999 | 15.555 | 590.531 |
| `p8` visibilidad | 146.666 | 17.149 | 657.117 |
| **Total** | **294.665** | **32.704** | **1.247.648** |

No equivale a 32.704 operaciones ejecutadas **por frame**: son sitios estáticos en el generador. Las etiquetas de instrucción y el número de líneas permanecen idénticos entre A/B (262.609 en p1 y 261.193 en p8). La compilación AArch64 de ambos C fue correcta.

### Resultado decisivo: Clang ya lo elimina

Se compilaron realmente las dos particiones experimentales con el mismo perfil que la referencia Android `-O1`, `CODRECOMP_HOT_X87_FASTPATH=ON`, resto de experimentos OFF. El build Android terminó firmado/verificado V2/V3. Se extrajo `lib/arm64-v8a/libmain.so` de la APK x87 de referencia y de la APK experimental, y se hizo un SHA-256 **de los bytes de la sección nativa `.text`**, no del archivo entero:

| Medida | Referencia A | Nueva DCE B |
|---|---|---|
| Tamaño de `.text` | 41.779.524 bytes | 41.779.524 bytes |
| SHA-256 de `.text` | `8846b89d11b406b63c859300eda395cac5a7d93d97781d8cadfa62d499fc1777` | **Idéntico** |

La APK completa tiene otro SHA-256, pero el **código máquina ejecutable** de `libmain.so` es idéntico byte a byte. Esto explica por qué quitar esos temporales del fuente no acelera el trabajo ARM64 en esta compilación. No se atribuye mejora de FPS ni se pretende presentar un benchmarking de juego inexistente para este cambio. Las distintas secciones de datos podrían seguir teniendo diferencias, pero no encontramos una ruta de CPU modificada.

### Pruebas semánticas

- `tests/test_temp_liveness.py`: ramas que se reúnen, temporales parcialmente superpuestos, bucles, lecturas peligrosas retenidas, efectos externos, preservación de etiquetas y código C compilado en `-O1` y `-O2`.
- Un oráculo diferencial de C compilado para el TECNO ARM64 comparó 2.048 estados aleatorios de registros, memoria y PC: **todos iguales**.
- Conteo de 32.704 eliminaciones comprobado contra `recomp_out/codsp.pcode`.
- Suite final: **109 pruebas Python correctas (4 omitidas)** y **31/31 pruebas CTest aprobadas**.

## Conclusión y siguiente trabajo

La hipótesis inicial «el traductor calcula flags y temporales que no necesita» era cierta **en el C generado**, pero no necesariamente en el ARM64 final: **Clang ya hacía esa eliminación**. Seguir creando parches de «código muerto» sin verificar el ensamblador desperdiciaría ciclos de investigación.

El siguiente paso con posibilidad de ganar FPS es recolectar un perfil actualizado del TECNO en la APK estable y localizar **operaciones que sobreviven en `.text`**, especialmente:
1. conversiones `d2f/f2d` e implementaciones binary80 en geometría y visibilidad;
2. accesos a memoria y `rd/wr` repetidos que puedan requerir análisis de alias/lifetime;
3. costes del dispatcher, saltos de estado y llamadas al runtime en funciones `0x0041B8F0`, `0x004196F0` y `0x004Dxxxx`.

Exigir evidencia en instrucciones ARM64 cambiadas y resultados A/B/A/B/A antes de habilitar una nueva ruta. **No** activar FCOM: la prueba anterior B2 cayó a 19,8 FPS pese a la mejoría transitoria B1.

**Estado de cierre verificado:** el generador nuevo permanece experimental OFF; los archivos privados p1/p8 se restauraron bit a bit, la APK x87 estable se recompiló y su sección nativa `.text` recuperó exactamente el SHA-256 original. El TECNO conserva la versión estable; no se instaló ninguna APK DCE experimental. Meta de 60 FPS **ABIERTA**.
