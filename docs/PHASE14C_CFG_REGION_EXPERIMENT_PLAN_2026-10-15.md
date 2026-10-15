# Fase 14C — Plan de regiones CFG verificables (2026-10-15)

**Estado:** fase iniciada. Prioridad: regiones completas, no parches x87 por instrucción. La meta sigue siendo reducir ms CPU/frame; no hay medición nueva del TECNO.

## Evidencia que guía la selección

Se cruzaron los siete cuerpos originales calientes del PE CoDSP 1.5 con el CFG Ghidra B + p-code previamente verificados. El primer filtro conservador encontró **227 bloques / 855 instrucciones** sin operaciones x87, CALL/CALLIND, BRANCHIND/RETURN, CALLOTHER ni p-code vacío dentro del bloque. De estas, muchas contienen LOAD/STORE que deben conservarse en orden original y con la misma semántica. **Son candidatas para laboratorio, no para despliegue.**

| Función | Bloques candidatos | Instrucciones elegibles para exploración |
| --- | ---: | ---: |
| `0x0041B8F0` geometría | 34 | 156 |
| `0x004196F0` geometría | 18 | 58 |
| `0x0047BD40` estructuras | 48 | 227 |
| `0x004D8280` visibilidad | 17 | 63 |
| `0x004D94C0` visibilidad | 15 | 53 |
| `0x004D8420` visibilidad | 42 | 143 |
| `0x004D6BC0` visibilidad | 53 | 155 |

La exploración se limita a **un bloque CFG por región prototipo**, no a todos los bloques simultáneamente; evitar el problema de presión de registros encontrado al intentar retener estado x86 por chunks de 1500 instrucciones. Primer objetivo: `0x0041C017`, bloque completo de **29 instrucciones originales / 97 operaciones p-code** con 16 LOAD, 6 STORE, un control condicional al final. Segundo bloque a contrastar: `0x0047BD40` (15 instrucciones / 53 operaciones).

## Entregas y condiciones de decisión

1. **14C-A: selección y cierre de entradas.** Herramienta reproducible sobre CFG completo y cuerpos Ghidra B, SHA-256 del juego, entradas de dispatcher en **cada PC interior**, salidas directas exactas y peligros explícitos. Las ramas opacas, CALL/RETURN/CALLOTHER, escrituras x87 o p-code faltante descalifican inmediatamente el bloque.
2. **14C-B: emisor offline A/B de una región completa.** Dos variantes aisladas generadas desde exactamente el mismo p-code original:
   - **A** traducción original (`pcode2c.Gen`) con accesos arquitectónicos a `R` por instrucción.
   - **B** selección de registros arquitectónicos disjuntos e inmutabilidad de la secuencia de p-code, con entrada independiente `L_PC` que recarga caché desde R y entrada interna `B_PC` para continuar dentro del bloque sin recargas; volcado de escrituras **en toda salida**, también branch condicional. El dispatcher puede llegar a cualquier instrucción interior.
   - No se modifican el runtime, `pcode2c.py`, la APK ni los flags por defecto. Solo archivos derivados bajo `.local/profiles/`.
3. **14C-C: diferencial de estado completo y compilación ARM64.** Host C compilado con LLVM-MinGW, validar para entradas a **todos los PCs de la región**, varias semillas y condiciones de rama, con igualdad byte a byte `R`, memoria simulada acotada y `PC`; las operaciones originales siguen en orden. La memoria del laboratorio puede plegar direcciones para evitar reservar 4 GiB: sirve para A/B del lowering, **no** como oráculo independiente de comportamiento x86 o de alias del juego. Si el bloque utiliza `U` global, rechazar antes de medir. Compilar ambas versiones con el mismo NDK AArch64 `-O1 -ffp-contract=off` y contrastar tamaño/loads/stores estáticos de todo el bloque, sin inferir ciclos ejecutados ni FPS.
4. **14C-D: selección de una integración productiva futura.** Solo integrar opción **OFF** a generador si el prototipo mejora efectivamente la calidad de código ARM64 sin regresiones y se amplía con oráculo independiente de x86/alias real. Caso contrario, documentar y **descartar** el prototipo en vez de crear un flag sin valor.

## Riesgos bloqueantes

- El estado del juego es observable tras toda salida. Solo guardar registros completos, sin solapamientos de vistas byte/word, con valor inicial válido en entrada de **cualquier instrucción**.
- Guest `LOAD/STORE` no se elimina, reordena o fusiona. El laboratorio puede mostrar igualdad entre variantes con la misma memoria plegada, pero no prueba ausencia de alias ni rendimiento del juego real.
- Las escrituras EFLAGS, accesos parciales y saltos locales micro-pcode deben mantener su semántica y orden exactos. `U` y registros x87 quedan intactos.
- `0x0041B8F0` tiene tres saltos al epílogo compartido `0x00523CD9` comprobado en fase 14B. No puede omitirse ni transformarse en retorno ARM64 local.
- Resultado A/B estático no equivale a una mejora de ms/frame. Cualquier implementación debe conservar fallback para rutas fuera del subgrafo y se mantendrá OFF hasta evidencia dinámica.

**Documentación de salida:** un informe por prototipo, recuento real de pruebas y código nativo A/B, candidatos descartados y pasos siguientes.
