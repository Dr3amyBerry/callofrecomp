# Fase 13 — Optimización de chunks calientes completos (ARM64, offline)

**Estado:** compilación A/B completa para geometría, recorrido y visibilidad, opción de construcción ARM64 incorporada y **desactivada por defecto**. **No hay medición nueva de FPS ni reducción demostrada de ms/frame.** Se trabajó sobre `main` con el TECNO expresamente fuera de uso.

## Objetivo y evidencia

El punto de referencia en el TECNO sigue siendo Camp Toccoa, Equilibrado, alrededor de **26 FPS** y **37 ms de CPU/frame**. La meta de 60 FPS exige aproximadamente 16,67 ms/frame en total. Para evitar otra cadena de parches de operaciones x87, la exploración se dirigió a **chunks recompilados completos de 1.500 instrucciones originales**, seleccionados con los dos perfiles CPU Simpleperf ya archivados. La atribución de perfiles a funciones/chunks es aproximada y no autoriza convertir muestras en tiempo exclusivo.

Puntos experimentales:

| Bloque original / chunk | Enfoque | A `.text` ARM64 `-O1` | B `.text` ARM64 `-O2` | A→B cargas `ld*` | A→B escrituras `st*` |
| --- | --- | ---: | ---: | ---: | ---: |
| **18** / geometría, desde `0x00419625` | 1.500 instrucciones | 419.044 B | **415.368 B** | **8.639→7.453** | **8.434→6.299** |
| **88** / estructuras, desde `0x0047B495` | 1.500 instrucciones | 233.172 B | **230.052 B** | **6.676→5.777** | **6.635→5.107** |
| **152** / visibilidad, desde `0x004D836A` | 1.500 instrucciones | 223.632 B | **241.268 B (REGRESIÓN)** | **6.280→8.590 (REGRESIÓN)** | 5.874→4.259 |

El código fue generado con la ruta de CoDSP original, compilado con Android NDK/Clang `--target=aarch64-linux-android26`, sin `-ffast-math`, con `-ffp-contract=off` y `-fPIC`, y auditado mediante `llvm-size -A` y `llvm-objdump -d`. **Son recuentos estáticos del binario; ni `ld*` ni `st*` se ejecutan necesariamente una vez por frame.** La comparación bajo `-Os` tampoco redujo la sección de texto en las tres muestras, así que también se descartó.

### Comprobación adicional: p4 completo

Se compiló también el **C privado íntegro de CoDSP p4**, exactamente el mismo archivo original para los dos niveles, sin tocar los recursos del juego:

| Estadística de toda p4 | A / `-O1` | B / `-O2` | Diferencia |
| --- | ---: | ---: | ---: |
| Sección nativa `.text` | 1.998.764 B | 1.979.316 B | **−19.448 B (−0,97 %)** |
| Cargas ARM64 estáticas | 82.258 | 77.931 | **−4.327 (−5,26 %)** |
| Escrituras ARM64 estáticas | 68.537 | 54.388 | **−14.149 (−20,64 %)** |
| Llamadas `bl` estáticas | 2.469 | 2.464 | −5 |

**No se deduce una ganancia de FPS de estas diferencias**, pero la partición completa confirma que el ahorro de accesos generado por `-O2` no se limita a una microfunción.

## Cambios de código conservados

- `android/CMakeLists.txt`: nueva opción `CODRECOMP_CORE_HOT_O2` (**OFF por defecto**). Aplica `-O2;-ffp-contract=off` **solo a CoDSP p0/p1/p4** (geometría y traversal del perfil). Verifica ARM64, `RECOMP_OPTIMIZATION=1`, presencia y SHA-256 de p-code CoDSP 1.5 original. Rechaza orígenes no verificados. No modifica física, geometría, visibilidad, texturas, efectos, NPC, calidad o material del juego.
- `tools/recomp/build_android.py`: `--core-hot-o2`, solo ARM64, para habilitar esta prueba desde el constructor sin cambiar el camino estándar. La versión normal queda inalterada.
- `tests/test_build_android_profiles.py` y `tests/test_core_hot_o2_policy.py`: errores de combinación, opción opt-in, selección exacta de particiones y protección del SHA.
- Configuración CMake **aislada y real con NDK**: verificado en `build.ninja` que `p0/p1/p4` terminan con `-O2`, que `p8/p10` terminan con `-O1` y que los tres O2 incluyen `-ffp-contract=off`. **No se construyó ni instaló ninguna APK con esta opción ni se midió CPU real.**

**Visibilidad `p8` deliberadamente excluida** del experimento: en el chunk 152, `-O2` agrandó `.text` e incrementó significativamente los `ld*` estáticos. El flag antiguo `--visibility-o2` sigue siendo un experimento aparte, no habilitado automáticamente.

## Alternativas grandes examinadas y descartadas

Se evitó dejar nuevas opciones ineficaces en `main`; las pruebas y resultados privados conservan sus trazas bajo `.local/profiles/`.

1. **Localizar valores temporales de p-code de instrucciones completas** en escalares C en ventanas amplias: miles de candidatos y equivalencia de R/RAM/U/PC en estados sintéticos con `-O0/-O1/-O2`, pero en tres regiones ARM64 el compilador ya realizaba casi la misma optimización: cambios de **−12 / +108 / 0 bytes**, sin reducción relevante de `ld*` o `st*`. Variante retirada.
2. **Mantener GPR/banderas entre hasta 1.500 instrucciones de chunk**: se protegieron alias, cargas en cada entrada de PC, salidas y saltos internos, pero las variables persistentes provocaron más spills. Incluso una caché de **un solo registro** produjo regresiones estáticas en las tres regiones (geometría: +28.996 B y +3.434 cargas; recorrido: +13.664 B; visibilidad: +11.304 B). Variante retirada.
3. **Eliminar cálculos temporales muertos a lo largo de chunks completos**: en geometría, recorrido y visibilidad se reconocieron 569/749/826 operaciones de p-code sin uso, pero la compilación ARM64 ya los eliminaba casi por completo. Diferencia total `.text`: −96 / 0 / 0 B. No se amplió el flag experimental previo.
4. **`-Os` por chunk completo**: no mejoró el tamaño del código frente a `-O1` en las tres regiones; no se añadió opción nueva.

Las tres vías descartadas no modifican la versión estable: el código experimental se revirtió antes de publicar.

## Validación y límites

El dispositivo TECNO, ADB, guardados y APK instalada **no se tocaron**. Se reutilizaron perfiles históricos. La prueba del constructor ARM64 de CMake y la selección real de los flags en Ninja pasaron. La suite Python completa ejecutó **272 tests, con 4 omitidos y 0 fallidos**, y la compilación host aprobó **35/35 CTest**. No se ha compilado una APK experimental completa con el flag nuevo. La configuración mantiene todos los ajustes gráficos idénticos; los binarios de juego y material original privado no se publican.

**Pendiente antes de afirmar mejora:** compilar/firmar una APK candidata con el flag explícito, contrastar equivalencia de gameplay visual y matemático, y cuando el teléfono esté disponible medir A/B/A física a misma escena, configuración y temperatura. No volver a abrir la vía de flags `-O2` en visibilidad sin una hipótesis dinámica nueva. El objetivo de 60 FPS sigue pendiente.

Archivos de análisis no publicados: `.local/profiles/phase13_chunk_native/`, `phase13_dce_native/`, `phase13_scalar_native/`, `phase13_p4_optlevels/` y scripts A/B relacionados.
