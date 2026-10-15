# Fase 14A — CFG de siete funciones originales y comprobación independiente de PC x86

**Fecha:** 2026-10-14. **Estado:** recuperación estructural de siete cuerpos **implementada y ejecutada**, verificación independiente de límites y destinos directos **ejecutada**. **No** se ha optimizado todavía el motor de ejecución ni se han medido FPS.

## Entradas originales, oráculo y límites

- `CoDSP.exe` del usuario, SHA-256 `c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47`.
- P-code original `recomp_out/codsp.pcode`, SHA-256 `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e`.
- Mapa de cuerpos Ghidra `recomp_out/codsp_function_map_v2.json`, SHA-256 `f6d56b4d167df2fb66a9f18ff8624e6b48fd363eadcbd05e62fa2598cd03ab4c`.
- Archivos propietarios, código C generado, PE, muestras, mapas completos y reportes detallados **permanecen privados** en rutas ignoradas por Git. Las herramientas públicas solo contienen algoritmos y pruebas con datos sintéticos.

El analizador `tools/recomp/region_cfg.py` reconoce **micro-branches dentro de una instrucción original**, `BRANCH/CBRANCH/CALL`, retornos y saltos indirectos, sucesores directos, fallthrough exacto y advertencias de p-code faltante. Usa rangos Ghidra B **discontinuos**, rechaza propietarios ambiguos y nunca confunde el chunk arbitrario de 1.500 instrucciones con el cuerpo de una función. Divide en bloques básicos y registra entradas externas directas, salidas, accesos y barreras.

El verificador `tools/recomp/diagnostics/verify_cfg_against_x86.py` **decodifica independientemente los bytes x86 reales con Capstone**, una instrucción por dirección, sin volver a utilizar el p-code para obtener los targets del lado x86. Contrasta tamaños, instrucciones de control, targets inmediatos, retornos y saltos/llamadas indirectas con el micro-CFG recuperado.

**Resultado de la primera ejecución:**

| Entrada original | Instrucciones x86 | Bloques CFG | Control x86 coincidente | Entradas directas externas conocidas | Salidas indirectas/no resueltas | P-code faltante |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0x0041B8F0` geometría | 553 | 88 | 75 | 2 | 0 | 0 |
| `0x004196F0` geometría | 602 | 71 | 58 | 2 | 5 | 0 |
| `0x0047BD40` estructuras | 604 | 86 | 66 | 1 | 6 | **1** |
| `0x004D8280` visibilidad | 136 | 24 | 19 | 3 | 1 | 0 |
| `0x004D94C0` visibilidad | 129 | 23 | 18 | 1 | 2 | **1** |
| `0x004D8420` visibilidad | 303 | 58 | 44 | 1 | 4 | **1** |
| `0x004D6BC0` visibilidad | 999 | 100 | 62 | 1 | 5 | **1** |
| **TOTAL** | **3.326** | **450** | **342** | — | — | **4** |

**Todas las 3.326 instrucciones fueron decodificadas por Capstone con límites compatibles** con el p-code, y los 342 controles comparables coincidieron en clase/destino: **0 discrepancias** en este subconjunto. **Las cuatro instrucciones con p-code vacío NO quedaron verificadas en su semántica**, aunque sus límites x86 sí coincidieron. Tampoco se han probado flags, registros, memoria ni bytes x87 con este verificador: su garantía es **exclusivamente estructural**.

### Huecos y límites reales que bloquean una sustitución nativa

Los cuatro PCs con instrucción x86 reconocida pero **sin p-code exportado** están en `0x0047C31F`, `0x004D959F`, `0x004D84FF` y `0x004D6FFF`. No se genera un NOP ni se inventa el efecto de esas instrucciones; quedan como rutas desconocidas.

En `0x0041B8F0`, las tres salidas externas directas salen de `0x0041C012`, `0x0041C07A` y `0x0041C090` hacia **`0x00523CD9`**. Los dos CALL externos conocidos llegan a la entrada de la función. Antes de compilar toda esta función como una región cerrada hay que determinar y modelar **el contrato de esas tres salidas**; la dirección de destino puede representar un trampolín o epílogo compartido, no debe adivinarse. El dispatcher actual sigue admitiendo cualquier PC de instrucción, incluidos los interiores.

### Una diferencia importante: alcance directo vs retornos supuestos

Las llamadas `CALL` transfieren inmediatamente al destino; el control suele regresar después mediante un `RETURN` calculado y el dispatcher. Por tanto, un CFG intraprocedimental que solo recorre aristas inmediatas declarará muchos PCs inalcanzables. El informe conserva DOS conteos:

- `direct_reachable_instructions`: alcanzabilidad usando solo aristas directas inmediatas.
- `may_return_reachable_instructions`: límite superior orientativo que además **supone** que las llamadas pueden regresar a la siguiente instrucción invitada; **no equivale a un salto real al salir de CALL ni justifica borrar código**.

Ejemplo real: la función `0x004D6BC0` tiene 999 instrucciones, pero solo 2 son accesibles siguiendo exclusivamente transferencias inmediatas; con continuaciones hipotéticas de llamadas se alcanza 933. Ninguna cifra autoriza borrar las restantes, ya que el dispatcher puede entrar directamente en PCs internos.

### Decisión de ingeniería

La función **`0x0041B8F0` es la primera candidata a fase 14B**, por tener **553/553 instrucciones alcanzables mediante aristas directas**, 88 bloques, sin huecos de p-code ni saltos dinámicos reportados. **Sin embargo, registra tres salidas estáticas hacia fuera de su cuerpo y dos entradas directas externas**, además de cualquier entrada dinámica por el dispatcher. Eso impide transformarla como función cerrada sin un contrato explícito para cada frontera; no se ha realizado tal sustitución.

`0x0047BD40` y tres funciones de visibilidad están condicionadas por huecos en la exportación original. Los saltos indirectos y continuaciones de llamadas deben seguir siendo fallback hasta probarlos.

## Herramientas reproducibles

Desde raíz de `callofrecomp`, en un entorno con los archivos privados versionados por SHA:

```powershell
python tools/recomp/diagnostics/analyze_cfg_regions.py --out .local/profiles/phase14_cfg_siguiente.json
python tools/recomp/diagnostics/verify_cfg_against_x86.py --pe ".local/private/Call of Duty Deluxe Edition/CoDSP.exe" --out .local/profiles/phase14_cfg_x86_siguiente.json
```

Los destinos `--out` deben ser **nuevos** dentro de `.local/profiles/`; nunca se sobrescribe evidencia anterior. No existe modo para saltarse el SHA del binario original auditado. El resultado privado ya verificado quedó bajo:

- `.local/profiles/phase14_cfg_initial_20261014.json` (CFG completo)
- `.local/profiles/phase14_cfg_capstone_initial_20261014.json` (decodificación x86 independiente)

Ambos informes contienen únicamente metadatos de grafo/direcciones, **no bytes o pseudocódigo original**. Los reportes no son exportados a Git.

## Pruebas y criterios de fallo

- `tests/test_region_cfg.py`: micro saltos relativos con índices de op, ciclos, condicionales, ramas externas, entradas de otras funciones, rango Ghidra discontinuo, etiquetas compartidas, propiedad ambigua, instrucción que cruza B, p-code faltante, rutas desconocidas y bloqueo de salida fuera de `.local/profiles`.
- `tests/test_verify_cfg_against_x86.py`: diferencias inyectadas en target del salto y tamaño de instrucción, controles directos/indirectos, decodificación ausente y p-code faltante. Las pruebas no necesitan el juego ni Capstone.
- Validación real independiente del PE para las siete funciones: **3.326 límites correctos, 342 transferencias coincidentes, 0 discrepancias**; no se interpreta como equivalencia matemática o rendimiento.
- Regresión de repositorio: **287 pruebas Python, 4 omitidas y 0 fallidas; 35/35 CTest** tras compilar el host. Pruebas de regresión con mutaciones intencionales que detectan destinos y longitudes incorrectas.

## Pendiente después de esta entrega

1. **14B:** contrato de entradas/salidas y análisis de vivacidad por byte para `0x0041B8F0`, respetando escritura arquitectónica de `R`, EFLAGS, x87, RAM, trampolines y alias. Extender Unicorn original a rutas con ramas y bucles más allá del prólogo previamente probado.
2. **14C:** implementar región A/B optativa con fallback, SSA de registros y comparaciones diferenciales del estado completo frente al x86 original. Revisar ARM64 en rutas realmente calientes, no solo tamaño estático.
3. **14D:** identificar semánticamente BSP, visibilidad, colisiones y movimiento de datos antes de sustituir funciones. El vínculo entre offsets y algoritmos aún es hipótesis.
4. **14E:** cuando esté disponible TECNO, medir CPU ms/frame A/B/A con condiciones idénticas; **no afirmar** que esta fase haya aumentado FPS.

**Seguridad:** sin acceso al teléfono, sin instalar APK, sin afectar partidas, interfaz, gráficos ni librerías de ejecución. `pcode2c.py` y Android no se modificaron en esta fase; todo el nuevo código es análisis y validación offline.
