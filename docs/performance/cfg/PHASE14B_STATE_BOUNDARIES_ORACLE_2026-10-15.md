# Fase 14B — Fronteras de estado por byte y oráculo x86 bifurcado (2026-10-15)

**Estado:** fase 14B **en curso**. Implementados análisis conservador de estado por bloque y una ampliación limitada del oráculo x86 original de `0x0041B8F0` a **dos rutas reales**. **No existe candidato de optimización listo para habilitar en la APK**; no se ha utilizado el TECNO ni se ha medido reducción de ms/frame o FPS.

## 1. Objetivo y entradas verificadas

El plan maestro [fase 14](PHASE14_CFG_ARCHITECTURE_MASTER_PLAN_2026-10-14.md) exige pasar de chunks arbitrarios de 1.500 instrucciones a **regiones CFG de funciones originales** y verificar que las fronteras no pierdan R/EFLAGS/x87/RAM/PC.

Entradas privadas y verificadas por hash:

- CoDSP.exe SP 1.5: `c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47`.
- `recomp_out/codsp.pcode`: `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e`.
- `recomp_out/codsp_function_map_v2.json`: `f6d56b4d167df2fb66a9f18ff8624e6b48fd363eadcbd05e62fa2598cd03ab4c`.

Los binarios y C/DLL traducidos se guardaron únicamente en carpetas privadas ignoradas `.local/profiles/`; los archivos públicos incluyen solo los analizadores y tests sintéticos.

## 2. Oráculo independiente: 20 y 27 instrucciones en dos rutas

Nueva herramienta: `tools/recomp/diagnostics/verify_cfg_branch_oracle.py`.

Se mantiene el prefijo original auditado `[0x0041B8F0,0x0041B941)` de **20 instrucciones** y su primer `JE` a `0x0041BCE0`. Cuando el salto se toma, se ejecutan también las **siete instrucciones reales** `[0x0041BCE0,0x0041BCF5)` y se detiene el emulador **antes del primer `FLD`**. Cuando no se toma, se detiene en `0x0041B941`, también antes de entrar en las operaciones x87.

La referencia usa **Unicorn x86 de 32 bits sobre los bytes originales**, decodificados y cotejados por **Capstone**. La alternativa compila una DLL privada desde `pcode2c.Gen` real, sin copiar ni reinventar la semántica de las instrucciones.

**Resultado reproducido en el equipo conectado:**

| Rama | Longitud ejecutada | Casos deterministas | Comparación |
| --- | ---: | ---: | --- |
| `JE` no tomado | 20 instrucciones | 256 | **256/256 PASS** |
| `JE` tomado | 27 instrucciones | 256 | **256/256 PASS** |
| **Total** | Dos rutas reales | **512** | **512/512 PASS** |

Comprobación caso por caso: **8 GPR (EAX, ECX, EDX, EBX, ESP, EBP, ESI, EDI)**, flags **CF/PF/ZF/SF/OF**, PC final exacto, bytes de **tres regiones de memoria invitada** (pila, datos ECX y estáticos) y ausencia de escrituras inesperadas a otros bytes del array `R[0x2000]` fuera de los GPR/flags modelados.

Control de falsos positivos: se compiló **otra DLL privada deliberadamente alterada** con el PC de destino equivocado en la ruta tomada (`0x41BCF4` en vez de `0x41BCF5`). El oráculo **detectó** la alteración; la rama no tomada no alterada continuó pasando. El artefacto negativo permanece ignorado bajo `.local/profiles/phase14b_mutation_pc_negative_v1`.

**Límites del PASS:** No se ha comparado **AF** porque el traductor original no la materializa, **ni el estado x87 de 80 bits, status/control/tag, ni excepciones**; los caminos acaban justamente antes de tocar la FPU. La RAM comprobada está limitada a regiones mapeadas/sembradas; no se verifican alias arbitrarios. No es una verificación de las 553 instrucciones ni de los otros 87 bloques.

## 3. Contrato conservador de estado: 7 funciones, 450 bloques

Nuevo módulo puro `tools/recomp/region_state_contract.py` y CLI `tools/recomp/diagnostics/analyze_region_state.py`.

- Por instrucción x86, el analizador respeta **saltos relativos dentro del p-code**, condicionales y bucles; calcula `read-before-def` (MAY), `must-write` (intersección entre caminos) y `may-write` **por byte del array R**.
- Por bloque CFG, calcula `live-in/live-out` conservadores con punto fijo; para toda salida externa al dispatcher, `live-out` incluye el **estado R completo**. Se conserva el derecho del dispatcher a entrar en **cualquier PC x86**, no solo en la entrada de la función.
- Una instrucción sin p-code, una operación desconocida, un destino inválido o un `CALLOTHER` invalida afirmaciones de exclusión de estados desconocidos. `LOAD/STORE` marca que los alias de memoria aún no están demostrados; `CALL/RETURN/BRANCHIND/CALLIND` exige preservar semántica entre dispatcher/funciones.
- Se reportan rangos exactos de bytes, distinguiendo los registros generales, flags y slots x87; no se confunden bytes muertos con bytes seguros de eliminar. Todos los informes prohíben promoción automática a producción.

Resultado sobre cuerpos calientes originales:

| Función | Bloques | Bytes `R` potencialmente leídos | Bytes potencialmente escritos | Barreras críticas |
| --- | ---: | ---: | ---: | --- |
| `0x0041B8F0` | 88 | 122 | 127 | **187 LOAD, 67 STORE, 3 salidas externas** |
| `0x004196F0` | 71 | 127 | 127 | LOAD/STORE y 5 RETURN |
| `0x0047BD40` | 86 | 8.192¹ | 131 | p-code faltante, CALL/RETURN |
| `0x004D8280` | 24 | 126 | 131 | LOAD/STORE y CALL/RETURN |
| `0x004D94C0` | 23 | 8.192¹ | 131 | p-code faltante |
| `0x004D8420` | 58 | 8.192¹ | 131 | p-code faltante |
| `0x004D6BC0` | 100 | 8.192¹ | 131 | p-code faltante, CALLIND |

¹ Es el **techo conservador** `R[0x2000]`, no 8.192 bytes realmente utilizados: las instrucciones sin p-code pueden tener efectos desconocidos. No interpretar un techo como tráfico de memoria medido.

En `0x0041B8F0` se registran **80 bytes x87 leídos/escritos** (en los slots arquitectónicos observados); por ello el oráculo de dos caminos previos a x87 **no** autoriza optimizar el cuerpo completo.

Informe privado: `.local/profiles/phase14b_state_contracts_v1.json`. Ruta privada del oráculo: `.local/profiles/phase14b_two_path_oracle_v1/summary.json`. Ambos se han ejecutado realmente y están excluidos de Git.

## 4. Pruebas

- `tests/test_region_state_contract.py`: escrituras parciales, alias de bytes, salto condicional que omite escritura, ciclos micro-CFG, regiones con salida y `R` observable, Ghidra B ambiguo, operaciones desconocidas y vacío de p-code.
- `tests/test_verify_cfg_branch_oracle.py`: rama sintética, generación real de `pcode2c.Gen`, rechazo de target incorrecto y operaciones opacas, límites de ventana previos a x87 y conjunto exacto de bytes observados.
- Laboratorio privado: **512 comparaciones** entre código x86 original ejecutado en Unicorn y C recompilado con LLVM-MinGW, más control negativo detectado.

**Validación final verificada:** 301 pruebas Python ejecutadas, 4 omitidas, 0 fallidas; compilación host correcta y **35/35 CTest** aprobados. `git diff --check` se ejecuta antes de publicar. Estos tests no sustituyen el ensayo A/B de CPU en el dispositivo.

## 5. Siguiente objetivo de ingeniería

1. Extender el oráculo independiente de `0x0041B8F0` **más allá del primer `FLD`**, verificando registros x87 **binary80 y status/control/tag** (no solo float32 final), las rutas condicionales y los epílogos hacia `0x00523CD9`.
2. Identificar fronteras **sin alias peligrosos** dentro del CFG y determinar conjuntos de estado realmente vivos a cada entrada **incluidas entradas por PC interior y retorno indirecto**; comprobarlos con Unicorn.
3. Solo con evidencia suficiente implementar una versión A/B de compilación **por región** y fallback al p-code. Comparar instrucción AArch64 dinámica cuando exista infraestructura, no vender bytes de código como FPS.
4. El criterio final, con TECNO, continúa siendo **ms CPU/frame A/B/A** y fidelidad gráfica / de partida.

**No hubo cambios en `pcode2c.py`, runtime Android, GL4ES, geometría de juego ni guardados**. Ningún FPS adicional queda demostrado y la fase 14B permanece parcial.
