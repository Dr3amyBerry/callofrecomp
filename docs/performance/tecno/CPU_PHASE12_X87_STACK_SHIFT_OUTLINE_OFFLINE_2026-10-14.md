# Fase 12 — Consolidación estructural de movimientos de pila x87 en ARM64 (sin TECNO)

**Estado:** implementada, integrada como opt-in de compilación, verificada por equivalencia diferencial y comparaciones de código ARM64 **offline**. No medida ni habilitada como mejora de FPS real. Fecha: 2026-10-14.

## Hipótesis basada en el cuello de botella

La referencia física Camp Toccoa/Equilibrado mantiene unos **26 FPS y ~37 ms CPU/frame**, por lo que el objetivo de 60 FPS permanece abierto. Dos perfiles Simpleperf **históricos**, sin nuevos accesos ADB, localizaron trabajo entre geometría, visibilidad, estructuras y copias de estado. Dentro del subconjunto p4 analizado, `memcpy` aparece como marco DWARF interno en 409/974 y 353/840 muestras recuperadas a PC invitado (aprox. 42 %); `rd`/`wr` están incluidos en esos recuentos, **no son tiempos adicionales**.

Como guía de atribución de cuerpos originales, sin convertir muestras en milisegundos falsamente precisos:

| Grupo original | Perfil físico v1 (de 7.953 muestras CPU) | Perfil físico v2 (de 6.541) |
| --- | ---: | ---: |
| Geometría `0x0041B8F0` + `0x004196F0` | 511 | 379 |
| Visibilidad `0x004D94C0`, `0x004D8280`, `0x004D8420`, `0x004D6BC0` | 667 | 555 |
| Recorrido `0x0047BD40` | 213 | 193 |
| Copia `0x0042B0A0` | 166 | 117 |

Son **muestras con asignación aproximada a cuerpos originales**, no tiempo exclusivo, ni toda la CPU, ni cuota atribuible a una variante del compilador; no se infieren milisegundos por frame sin medición física. Esta información sirvió para seleccionar una mejora transversal de representación y tamaño de código en lugar de parches a una sola operación.

## Cambio de código implementado

Analizando las **333.208 instrucciones originales** de CoDSP 1.5 se encontraron **18.194 grupos** aptos de **siete** movimientos consecutivos `COPY r10 <- r10` de la pila x87: 9.041 push y 9.153 pop. Son dos secuencias exactas muy repetidas. Sus registros se distribuyen en direcciones `R+0x1100..R+0x1170`, cada 16 bytes, de los cuales **solo 10 bytes se copian**; el padding de seis bytes es observable y permanece intacto.

El generador `tools/recomp/pcode2c.py` ofrece `--x87-stack-shift-outline` para sustituir cada grupo de siete instrucciones por una llamada a `codsp_x87_shift_push` o `codsp_x87_shift_pop`, con los índices p-code y etiquetas originales **sin desplazar**. El motor conserva funciones auxiliares reutilizables en `tools/recomp/runtime/x87_stack_shift.h`; ejecutan siete copias de 10 bytes en el orden original con `memcpy`, **sin concatenar ranuras ni copiar el padding**.

Guardas y reversibilidad:

- **Solo** CoDSP.exe 1.5 con hash de p-code validado; sin intervenir módulos ajenos; opción OFF por defecto.
- Un salto interno al medio del grupo o una operación eliminada bloquea la fusión. No se combina con caché de registros ni poda de escrituras de registro, cuyo aliasing exige una auditoría independiente.
- `tools/recomp/patch_codsp_x87_shift.py` aplica y revierte el cambio en los **doce** C privados generados, preserva saltos, espacios y finales de línea. Se rechazó aplicar dos veces sin restaurar. El build Android recibe `--x87-stack-shift-outline` (solo ARM64); en una build sin él, restaura automáticamente los grupos antes de otros parches. No se permite combinarlo con conversiones p4 que exigen hashes exactos.
- Se verificó la transformación y posterior restauración **byte a byte de las 12 fuentes** en memoria, sin modificar los archivos originales. El generated C no pasa a Git.

## Resultado real de compilación NDK, sin extrapolar FPS

Con `clang --target=aarch64-linux-android26 -O1 -gline-tables-only -fPIC`, la **partición p4 completa de CoDSP** (misma entrada privada, compilada A/B) cambió:

| Artefacto | A normal | B outlined | Diferencia |
| --- | ---: | ---: | ---: |
| `.text` AArch64 p4 completo | **1.998.764 B** | **1.774.024 B** | **−224.740 B (−11,244 %)** |
| Archivo C privado p4 | 7.828.713 B | 7.275.268 B | −553.445 B |

Un laboratorio que reconstruye intervalos específicos de las instrucciones originales también compiló y midió:

| Región de la muestra | A `.text` | B `.text` | Delta |
| --- | ---: | ---: | ---: |
| Geometría | 51.348 B | 45.656 B | −5.692 B |
| Traversal p4 | 210.288 B | 187.452 B | −22.836 B |
| Visibilidad | 227.032 B | 202.820 B | −24.212 B |

Las cifras de las tres muestras **no deben sumarse** al p4 completo ni confundirse con el ahorro global de `libmain.so`. Los resultados demuestran menos bytes AArch64 en el objeto, no menos ciclos, menos misses I-cache ni más FPS. La llamada a una rutina `noinline` también puede tener coste; un perfil físico futuro decidirá si compensa. Ninguna modificación de resolución, modelos, HUD, texturas, físicas, calidad o partidas.

## Pruebas y límites

- Se ejecutaron pruebas sintéticas que contrastan **R completo (0x2000 bytes), RAM, U y PC** entre código generado original y fusión, con 1.000 estados por dos puntos de entrada, a `-O0/-O1/-O2`, incluyendo relleno no cero y ambas direcciones. Son pruebas diferenciales del runtime recompilado, **no un oráculo completo independiente Intel x86**.
- Tests adicionales verifican coincidencia exacta, rechazo de saltos internos/alias/cambios parciales y aplicación/restauración byte a byte LF/CRLF y hash de origen. **Suite completa: 269 tests Python ejecutados, 4 omitidos, 0 fallidos; 35/35 CTest en compilación host.**
- La auditoría completa del p-code no detectó saltos relativos locales fuera de su rango de operación. Los 12 C originales se restauraron por igualdad exacta en la prueba del parcheador.
- Capturas, binarios del juego, `.o`, perfiles y fuentes C generadas siguen exclusivamente bajo `.local/profiles/`/ `recomp_out/`, ignorados por Git. **No se tocó el TECNO ni WSA, no se instaló una APK.**
- El experimento **continúa desactivado por defecto**. Para una eventual build candidata, seleccionar `--hot-x87-transform --x87-normal-f2d --x87-stack-shift-outline` en ARM64 una vez preparados los privados legítimos; ninguna ganancia jugable debe afirmarse sin A/B/A físico.

**Conclusión:** se ha sustituido trabajo de generación repetido por rutinas nativas compartidas, con reducción mensurable ~11 % del código AArch64 de p4 y controles de equivalencia disponibles. Esto sí es un cambio estructural de alcance amplio, pero los **60 FPS todavía no están demostrados**.
