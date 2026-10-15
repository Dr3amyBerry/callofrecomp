# Fase 15 — Perfiles TECNO originales, presupuesto por fotograma y oportunidades transversales

**Fecha:** 2026-10-15 · **Proyecto:** `callofrecomp` · **Rama:** `main`

**Estado:** análisis retrospectivo de dos capturas físicas Simpleperf de TECNO CK6n, comprobación de procedencia de ELF, clasificación detallada de las instrucciones guest más muestreadas y experimento de código ARM64 de `POPCOUNT`. **No se cambió el juego, no se construyó ni instaló una APK, no se ha medido FPS nuevo.** Las optimizaciones experimentales de CFG14 continúan BLOQUEADAS.

## 1. Evidencia física verificada y calibración

Se analizaron **dos capturas originales distintas** de `task-clock:u` (~350 Hz), sobre Camp Toccoa con los mismos gráficos y un punto de spawn similar, archivadas bajo `.local/profiles/`. El análisis **comprobó directamente el Build ID registrado en cada `perf.data` contra el ELF sin strip** y recontó muestras de usuario y de `libmain.so`, sin confiar solo en resúmenes JSON:

| Captura física archivada | Muestras del proceso | Muestras `libmain.so` | Build ID exacto |
| --- | ---: | ---: | --- |
| A1 | **7.953** | **6.675** | `80dc3884c64e395f87d7975f200d34edccf648fd` |
| A2 | **6.541** | **5.491** | `80dc3884c64e395f87d7975f200d34edccf648fd` |

Los archivos `perf.data` tienen **hashes SHA-256 diferentes**, así que no se han contado dos copias de la misma captura. Sus recuentos coinciden con los informes originales. También se verificaron el p-code y el mapa Ghidra B mediante SHA-256.

**Referencia separada de una sesión 3D:** **38,895 ms de CPU/fotograma**, **24,70 FPS de mediana**, calidad Equilibrado. La fase 10 tuvo otra referencia de ~37,1 ms/fotograma y ~26 FPS. **El registro de fotogramas y Simpleperf no se capturaron simultáneamente**, por lo cual cualquier conversión de muestras a milisegundos es solo ilustrativa. No sumar tiempos por función como si fueran exclusivos.

### La meta real

Para lograr 60 FPS bajo una hipótesis **puramente CPU-bound**, el tiempo total debería pasar de 38,895 ms a 16,667 ms/fotograma. La reducción requerida sería **57,15 % del tiempo CPU total**. Esto no descarta un cuello de GPU adicional: no hay contadores GPU Mali accesibles en las capturas.

Las **ocho funciones originales** seleccionadas por recurrencia de muestras en ambos perfiles son `0x0041B8F0`, `0x004196F0`, `0x0047BD40`, `0x004D94C0`, `0x004D8280`, `0x004D8420`, `0x004D6BC0` y la novedad `0x0042B0A0`. Al sumar exclusivamente los samples con una etiqueta de cuerpo Ghidra **única**, representan:

- A1: **1.557 de 7.953** muestras del proceso (**19,578 %**).
- A2: **1.244 de 6.541** (**19,018 %**).

Si esos labels fueran tiempos exclusivos y pudiera **eliminarse hipotéticamente el 100 % de su coste**, quedarían 31,28–31,50 ms CPU/frame y la cota CPU-only sería apenas ~31,8–32 FPS. **No es una predicción de FPS**, solo una comparación Amdahl idealizada. Por tanto, ni siquiera la eliminación completa de las ocho funciones bastaría para cumplir 60 FPS. La estrategia NO puede depender solo de aceleraciones locales de pocos bloques.

## 2. Ranking repetido y coste estructural del p-code

| Función original | Muestras A1/A2 | Área probable | Instrucciones x86 | x87 involucrado |
| --- | --- | --- | ---: | --- |
| `0x0041B8F0` | 270 / 196 | Geometría/colisiones | 553 | 274 instrucciones |
| `0x004196F0` | 241 / 183 | Geometría | 602 | 397 |
| `0x0047BD40` | 213 / 193 | Estructuras/estado | 604 | 241 |
| `0x004D94C0` | 207 / 191 | Visibilidad | 129 | 40 |
| `0x004D8280` | 167 / 128 | Visibilidad | 136 | 40 |
| `0x004D8420` | 151 / 125 | Visibilidad | 303 | 60 |
| `0x0042B0A0` | 166 / 117 | Índices/estado entero | 104 | **0** |
| `0x004D6BC0` | 142 / 111 | Visibilidad | 999 | 494 |

Las etiquetas de funciones se deducen de cuerpos originales Ghidra B e instrucciones C optimizadas: su clasificación es **aproximada, no tiempo exclusivo ni garantía de llamadas por fotograma**.

**Nueva función relevante: `0x0042B0A0`.** Su cuerpo original de 104 instrucciones produce 530 microoperaciones de p-code, con 31 LOAD, 24 STORE y 30 POPCOUNT, **sin varnodes x87**. Aparece en ambas sesiones; el PC `0x0042B11E` concentra muestras y contiene índice entero + acceso RAM. Es candidata de investigación con oráculo x86 por función, **no es todavía candidata de reemplazo nativo seguro**, y su cuota observada individual es demasiado pequeña para resolver el presupuesto total.

## 3. Atribución de muestras a instrucción original, NO a microoperación

La herramienta `tools/recomp/diagnostics/attribute_cpu_hot_microops.py` volvió a leer los dos `perf.data`, resolvió PCs nativos con `llvm-addr2line` sobre el ELF original, y comprobó de forma **exacta** los totales resueltos y las primeras etiquetas/funciones contra sus informes archivados. Esa comprobación rechaza una fuente generada cuyo orden de líneas se haya movido.

Cada PC invitado se cruzó con el p-code original verificado y se clasificó por **presencia de tipos de operadores**. La presencia de FLOAT, LOAD, POPCOUNT, x87 físico, o escritura de flags puede solaparse en una sola instrucción. Una muestra puede estar asociada a toda esa instrucción, **sin poder atribuir tiempo a una de sus microoperaciones**.

| Categoría EXCLUSIVA por instrucción etiquetada, dentro de las ocho funciones | A1 | A2 |
| --- | ---: | ---: |
| Algún estado arquitectónico x87 (`R+0x1000..0x1200`) | **1.255** | **1.005** |
| Sin x87, con operaciones RAM guest | 191 | 150 |
| Sin x87 ni RAM guest | 111 | 89 |
| **Total seleccionado** | **1.557** | **1.244** |

Entre las muestras de estas ocho funciones **80,6 % en A1 y 80,8 % en A2** está asociado a una instrucción que toca estado x87; el 78–79 % también aparece asociado a una instrucción con alguna operación de memoria. Estos porcentajes **NO se deben sumar**: se solapan ampliamente.

**Conclusión:** estudiar estado, copias y conversión x87 *sin cambiar el valor binary80*, junto con transferencia de registros, es una prioridad transversal más fundamentada que continuar fusionando superregiones enteras de 6–8 instrucciones.

## 4. Experimento de POPCOUNT especializado por ancho: resultado NEGATIVO

Entre los ocho cuerpos originales se contaron **565 microoperaciones POPCOUNT**. Esto sugería reemplazar `popc(u128)` por `__builtin_popcount` de 8/16/32 bits o `__builtin_popcountll` de 64 bits cuando el tamaño del operando original está declarado.

Se compiló una prueba **privada y sintética**, sin editar `pcode2c.py` ni `recomp_rt.h`, con versiones actuales y variantes por 8, 16, 32, 64 y 128 bits en Android NDK `-O1` y `-O2`. **20.495 entradas deterministas (4.099 por ancho)** produjeron el mismo POPCOUNT. Sin embargo, los tamaños de función ARM64 fueron **idénticos** para referencia y candidato:

| Ancho de entrada | Bytes referencia `-O1` / `-O2` | Bytes especializada `-O1` / `-O2` |
| --- | ---: | ---: |
| 8 bits | 24 / 24 | 24 / 24 |
| 16 bits | 24 / 24 | 24 / 24 |
| 32 bits | 24 / 24 | 24 / 24 |
| 64 bits | 20 / 20 | 20 / 20 |
| 128 bits | 36 / 36 | 36 / 36 |

**Decisión: rechazar la modificación.** Clang ya produce código del mismo tamaño para la versión actual cuando el ancho se conoce; no se ha demostrado ninguna reducción de trabajo ARM64 real, mucho menos FPS. No reutilizar el conteo de 565 operaciones como estimación dinámica de tiempo.

Evidencia de la prueba (fuente C sintética, objeto ARM64, DLL host, resumen JSON) en `.local/profiles/phase15_popcount_width_results_v1/`, ignorada por Git.

## 5. Herramientas nuevas, pruebas y seguridad

- `tools/recomp/diagnostics/prioritize_profiled_cpu.py`: compara dos capturas físicas **solo cuando** ambas tienen Build ID verificado, distinto hash de `perf.data`, recuentos exactos y fuentes originales p-code + mapa pinneadas. Ordena ocho funciones por cuota estable de muestras, incorpora complejidad por microoperaciones y calcula un techo Amdahl **meramente hipotético**.
- `tools/recomp/diagnostics/attribute_cpu_hot_microops.py`: recompone la atribución completa de PCs host→C generado→instrucción original, detecta drift en líneas de fuente y clasifica por presencia x87/memoria/flags/aritmética. No infiere coste exclusivo de cada tipo.
- `tests/test_prioritize_profiled_cpu.py` y `tests/test_attribute_cpu_hot_microops.py`: muestras sintéticas de rankings, duplicados, capturas truncadas, incoherencias de totales, cuerpos x87, categorías solapadas y límites de atribución. **No requieren el juego ni perfiles privados para la suite normal**.

Reproducción sobre el entorno local existente y permisos del usuario, sin tocar ADB:

```powershell
python tools/recomp/diagnostics/prioritize_profiled_cpu.py --out .local/profiles/phase15_prioridades_nuevas.json
python tools/recomp/diagnostics/attribute_cpu_hot_microops.py --slot v1 --out .local/profiles/phase15_A1_nuevo.json
python tools/recomp/diagnostics/attribute_cpu_hot_microops.py --slot v2 --out .local/profiles/phase15_A2_nuevo.json
```

Evidencia JSON privada de esta fase: `.local/profiles/phase15_dual_tecno_cpu_priority_v1.json`, `.local/profiles/phase15_native_guest_microops_A1_v1.json` y `.local/profiles/phase15_native_guest_microops_A2_v1.json`. No se almacenan PEM/binarios del juego en Git ni se publica `perf.data`.

**Regresión final:** `python -m unittest discover -s tests` ejecutó **382 pruebas (4 omitidas, ninguna fallida)** y `ctest --test-dir .local/builds/build --output-on-failure` aprobó **35/35** tras una compilación host correcta. Se verificaron también `py_compile` de ambas herramientas y `git diff --check`. Las comparaciones experimentales POPCOUNT de 20.495 valores y los análisis Simpleperf originales son pruebas independientes de esa suite.

## 6. Siguiente bloque de ingeniería con mayor probabilidad de impacto

1. **Perfil exhaustivo transversal x87:** no repetir el experimento normal→binary80 aproximado, porque se conoce que puede cambiar bits, NaN, CW/SW y excepciones. Medir en ARM64 real (con TECNO conectado) qué instrucciones nativas ejecutan las secuencias x87 frecuentes: materialización de stack, `FLOAT2FLOAT`, lecturas `rd/wr`, `memcpy`, y ramas; atribuir por PC nativo y familia de operación. Solo usar muestras atribuidas como indicio para examinar el código ensamblador, **no como prueba causal de microoperación**.
2. **Candidatos verdaderamente seguros:** fusionar copias exactas de bytes en regiones donde no haya side entries ni eventos guest observables; analizar la presión de registros ARM64 y el número de operaciones nativas emitidas. En toda propuesta exigir equivalencia **original Unicorn x86**, 8 GPR, EFLAGS, **binary80 completo**, TOP, CW, SW, tag word, todas las regiones RAM tocadas, PC y fallos, sin degradar precisión.
3. **Geometría entera `0x0042B0A0`:** comprobar efectos de alias, flags y memoria de 104 instrucciones, buscar patrón de indexación común a otras funciones. La optimización local deberá tener un **límite superior de beneficio estimado** antes de invertir en un fast path.
4. **Retomar A/B/A/B físico:** instalar solo una candidata segura con permiso y TECNO disponible; medir CPU ms/frame y FPS en misma escena, frecuencia/temperatura y gráficos. Si no reduce de forma reproducible el trabajo total, **revertir** y conservar únicamente la auditoría.

**No hay nueva aceleración de FPS demostrada.** El TECNO **no figura en ADB** durante esta fase; se detecta solamente WSA x86_64. Los flag experimentales anteriores permanecen apagados, incluido CFG14 que está BLOQUEADO en CMake y constructor.
