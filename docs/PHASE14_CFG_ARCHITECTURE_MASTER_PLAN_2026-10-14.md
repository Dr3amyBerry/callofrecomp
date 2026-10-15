# Fase 14 — Arquitectura de recompilación por regiones CFG (plan maestro)

**Inicio:** 2026-10-14. **Rama:** `main`. **Estado:** 14A IMPLEMENTADA y auditada contra p-code + Capstone x86 original; 14B EN CURSO: oráculo de dos rutas y liveness conservador por byte implementados; equivalencia x87 y cuerpo completo pendientes. **TECNO:** no disponible y no requerido para las etapas offline. **Meta de 60 FPS:** pendiente; no confundir validación estructural con ms/frame.

**Checkpoint 14D (2026-10-15):** el epílogo `0x00523CD9` se verificó con Unicorn original en 128 retornos y 128 saltos al error; se comprobó adicionalmente la secuencia de 3 instrucciones del manejador hasta `CALL 0x0051FF90` en 64 casos por ruta. No obstante, el fast path de geometría tiene un **bloqueo crítico de equivalencia ante fallos guest**: 15 de 18 páginas desmapeadas observadas muestran R/PC divergente durante la ejecución de la caché. La opción Android ARM64 queda **BLOQUEADA además de OFF**, hasta implementar deoptimización segura. El TECNO no figura entre los dispositivos ADB y no se ha medido ningún FPS nuevo. [Informe 14D](PHASE14D_EPILOGUE_FAULT_SAFETY_2026-10-15.md).


**Checkpoint 14E (2026-10-15):** se ha añadido un generador **offline** con checkpoints arquitectónicos por instrucción original, incluyendo 2 operandos `m` absolutos y corrección del orden de CF/OF antes de LOAD. **24/24** fallos originales x86 coinciden en R/PC/RAM, y **120/120** reinicios desde el PC fallido con Unicorn y el traductor A no repiten las 6 STORE guest. El coste ARM64 estático del código corregido permanece superior: **652 B / 32 cargas / 62 stores** versus **404/32/22** inseguro. Los 68 bloques sin memoria encontrados son demasiado cortos; dos candidatos no aportan ahorro de código. **Sin recuperación real de señales Android y sin FPS medidos, el flag sigue BLOQUEADO.** [Informe 14E](PHASE14E_PRECISE_CHECKPOINTS_AND_RESUME_2026-10-15.md).


## 0. Decisiones técnicas y límites

1. **Unidad de optimización = región de control de flujo de funciones originales, no chunks arbitrarios de 1.500 instrucciones.** Un chunk de `pcode2c.py` puede contener múltiples funciones, huecos Ghidra y entradas independientes. Por ejemplo, `0x0041B8F0` contiene 553 instrucciones distribuidas en dos intervalos y comparte su chunk con otras funciones.
2. **Primera prioridad:** geometría `0x0041B8F0` y `0x004196F0`; después recorrido `0x0047BD40`; finalmente visibilidad `0x004D8280`, `0x004D94C0`, `0x004D8420` y `0x004D6BC0`. Esta prioridad se basa en muestras de Simpleperf físicas archivadas, no en milisegundos exclusivos.
3. **Semántica prioritaria:** entradas a cualquier PC invitado válido; control de flujo dentro de las microoperaciones p-code; EFLAGS/AF observable donde esté implementado, x87 de 80 bits, NaN, memoria y aliasing, llamadas y retornos, excepciones, código compartido y puntos de salida al dispatcher.
4. **Fallo seguro:** saltos indirectos, instrucción sin p-code, fuentes Ghidra ambiguas, targets no representados y microbranches no verificadas bloquean cualquier transformación automática. El análisis puede documentarlas pero no convertirlas silenciosamente en una arista probable.
5. **Fuentes externas de diseño, no de código copiado:** QEMU/TCG (`tcg/optimize.c`, documentación de translation blocks); ioq3, iocod, Quake3e, OpenMoHAA, OpenCoD1 para inferir estructuras BSP/visibilidad/colisión solo tras cotejarlas con el binario real. Repositorios fijados en [inventario](PHASE14_CFG_REFERENCE_SOURCES_2026-10-14.md). Licencias revisables antes de cualquier reutilización. Recursos privados y ejecutables fuera de Git.
6. **No activar `-O2` general, cachés de registros por chunk ni nueva conversión x87.** No modificar por defecto la APK, la resolución, shaders, físicas ni partidas. Experimentos reversibles y OFF hasta que se validen.

## 1. Etapas y criterios de aceptación

### 14A — Recuperación rigurosa del CFG real (**implementada; validación estructural completa para los siete cuerpos**)

- [x] Implementar biblioteca pública pura para deducir sucesores reales de cada instrucción a partir de su micro-CFG p-code, distinguiendo saltos relativos locales a microoperaciones, saltos directos a PC invitado, bifurcaciones condicionales, `CALL`, `RETURN` y ramas indirectas.
- [x] Cruzar cada instrucción con rangos Ghidra **B** del `codsp_function_map_v2.json`; nunca asignar intervalos basándose solo en la entrada `F`. Detectar ambigüedades, huecos, instrucciones fuera de rango y puntos de entrada adicionales desde otras funciones.
- [x] Construir bloques básicos y aristas entre ellos, bloques inaccesibles desde la entrada declarada y salidas directas/indirectas. Incorporar resúmenes conservadores de lecturas/escrituras de registros, flags, x87 y memoria.
- [x] Entregar CLI reproducible con salida JSON **solo a `.local/profiles`**, validación de SHA-256 del p-code original y del mapa del juego, y modo de pruebas sintéticas sin originales.
- [x] Probar CFG de bucles, trampolines, saltos locales condicionales, llamadas, retornos, entradas múltiples, huecos, código compartido y p-code faltante. Ejecutar sobre los siete cuerpos calientes con el dataset legítimo sin publicar código derivado.

**Aceptación 14A:** coherencia estructural, cobertura por PC exacta de cuerpos Ghidra, límites y todos los destinos identificables auditados. Un CFG derivado de Ghidra/p-code **no** es todavía un oráculo independiente x86.

### 14B — Verificación independiente x86 y contrato de frontera (**dos rutas con Unicorn y estado conservador por byte verificados; equivalencia completa pendiente**)

- [x] Verificar con Capstone las **3.326 instrucciones** reales (límites y anchuras) y **342 transferencias** decodificables contra Ghidra p-code: **0 discrepancias**. Cuatro instrucciones con p-code vacío quedan bloqueadas; esta verificación **no prueba** equivalencia de estados.
- [x] Extender de manera acotada el oráculo Unicorn a dos rutas reales: 20 instrucciones (salto no tomado) y 27 (tomado), con `512/512` estados verificables coincidentes en GPR, cinco banderas, PC y RAM mapeada; mutación deliberada del PC detectada. Ambas rutas terminan antes de x87.
- [ ] Extender ahora el oráculo al cuerpo x87, estado binary80, control/tag, epílogos y demás caminos; este resultado aún no prueba la función completa.
- [x] Implementar análisis conservador de `read-before-def`, `must-write`, `may-write` y `live-in/live-out` por byte del estado R en 450 bloques, con barreras para RAM, CALLOTHER, llamadas, retornos y p-code faltante. Prohibida la promoción automática.
- [ ] Demostrar alias y efectos completos de RAM, AF, x87 y estados de salida en regiones que se vayan a transformar.
- [ ] Verificar rutas de fallthrough, rama tomada/no tomada, bucles, salidas dinámicas y reentrada desde el dispatcher.

- [x] **Auditoría adicional 14B:** validación independiente de ST0 `binary80` real en cinco checkpoints y 256 casos cada uno: **167/256 divergencias** tras la segunda operación `FSUB`, pese a GPR/RAM coincidentes; la precisión extendida es un requisito pendiente, no un pase de equivalencia.
- [x] **Salida compartida verificada:** los tres JMP de `0x0041B8F0` alcanzan la función independiente `0x00523CD9`. Capstone x86 y p-code corroboran una comparación de valor global, retorno y camino de fallo; no puede borrarse ni fingir un `RET` local.
- [ ] Quedan pendientes igualdad `binary80` bajo entradas válidas, estado completo de FPU `FPCW/FPSW/FPTAG` y contrato de retorno/fallo antes de sustituir un cuerpo entero; un futuro A/B debe preservar fallback. [Detalles](PHASE14B_X87_BINARY80_SHARED_EPILOGUE_2026-10-15.md).

**Aceptación 14B:** oráculo independiente para las regiones elegidas, mutaciones negativas detectadas, estados finales iguales, rutas irresueltas explícitas.

### 14C — Arquitectura de regiones y SSA (**A/B OFFLINE de bloques con caché, fase productiva pendiente**)

- [ ] Construir región a partir de **subgrafo CFG** cerrado con entradas conocidas, salidas de estado etiquetadas y caminos indirectos como fallbacks.
- [ ] Usar SSA/análisis de vivacidad sobre bytes arquitectónicos, con selección de caché de registros por región (no 1.500 instrucciones por chunk), guardando estado en cada salida y carga en cada punto de entrada independiente.
- [ ] Optimizar patrones completos de movimiento de datos, comparación geométrica o recorrido solo cuando la regla sea inequívoca y rentable; siempre mantener la traducción p-code original como fallback reversible.

- [x] **Experimento parcial 14C:** 227 bloques sin x87/opaque; generar C A/B aislado de cada bloque CFG original con cache arquitectónica por campo disjunto, guardar estado a cada salida y probar entradas interiores. Con la política `start_only` y fallback simulado: **696+360** comparaciones A/B host iguales, junto con reducción de código y cargas ARM64 estáticos en dos bloques. Variante `all_entries` rechazada por regresiones de loads. [Resultados](PHASE14C_CFG_AB_OFFLINE_RESULTS_2026-10-15.md).
- [ ] **NO APROBADO PARA PRODUCCIÓN:** el A/B usa RAM sintética plegada, no sustituye Unicorn x86/alias real; el dispatcher Android aún no tiene guardia start_only ni fallback instalado. No afirmar mejora FPS.

- [x] **Avance 14C adicional:** oráculo independiente x86 original de bloque `0x0041C017` con direcciones guest exactas, **40/40** casos iniciales y otros **40/40** del helper final, incluyendo read-after-write real; con la versión de laboratorio antigua no se podían detectar estos alias. Guard de dispatcher por líder, fallback a código original, CMake ARM64 OFF default con hashes y builder explícito; CMake/Ninja ON/OFF y símbolos NDK verificados. **No se probó APK ni CPU/frame**, por tanto no es cierre de 14C de producción. [Informe](PHASE14C_REAL_X86_GUARDED_RUNTIME_2026-10-15.md).
- [ ] PENDIENTE: memoria fuera de la región mapeada, equivalencia bajo excepciones y epílogo completo, link integrado completo, juego real y A/B físico. No integrar en default.

**Aceptación 14C:** diferencial completo frente al traductor original y oráculo independiente, código ARM64 mejor en las rutas calientes seleccionadas, no solo menor C.

### 14D — Reemplazo funcional guiado por identificación de algoritmos

- [ ] Conectar rangos de CoDSP con BSP, árboles de visibilidad, trazas y colisiones mediante referencias de memoria, llamadas y correspondencia algorítmica auditada. **No asumir** que un offset implica un algoritmo.
- [ ] Prototipar funciones nativas equivalentes aisladas, nunca copiar código de terceros sin revisar licencia/compatibilidad, aplicar oráculo original completo a transiciones válidas.

**Aceptación 14D:** casos válidos equivalentes, diferencias justificadas por protocolo sin sacrificar jugabilidad.

### 14E — Rendimiento real y habilitación

- [ ] Fuera del TECNO: comparar compilación NDK ARM64, tamaño de código, perfiles host/ciclos simulados **si son representativos**, instrucciones de acceso a estado y presión de registros; no convertirlos a FPS.
- [ ] Con TECNO disponible: APK A/B/A/B/A, Camp Toccoa idéntico, misma resolución/calidad/autoguardado, termometría y estadísticas CPU/frame más ventanas lentas. Rollback verificado.
- [ ] Habilitar por defecto solo con ahorro real reproducible sin regresión en gameplay/seguridad.

## 2. Archivos previstos y estrategia de pruebas

- `tools/recomp/region_cfg.py`: modelo propio de CFG por instrucción y bloques con etiquetas de borde y tratamiento de lo desconocido.
- `tools/recomp/diagnostics/analyze_cfg_regions.py`: CLI para seleccionar funciones originales, verificar versión del juego y exportar informes privados de cobertura, peligros y puntos de frontera.
- `tests/test_region_cfg.py` y `tests/test_analyze_cfg_regions.py`: sintéticos de micro-CFG, Ghidra B, múltiples entradas y rechazo de análisis incompleto; fixtures sin bytes comerciales.
- `PROGRESS.md` y este informe: separar resultados reales, riesgos, experimentos rechazados y pasos pendientes. `.local/profiles/phase14_cfg_*.json` para informes privados; no subir P-code, binarios comerciales, C generados ni APK privada.

## 3. Riesgos que deben bloquear experimentos

- Cualquier salida al dispatcher hace `R/U/MEM/PC` potencialmente observable. La región debe sincronizar el estado.
- Una rama calculada (`BRANCHIND/CALLIND/RETURN`) puede reentrar por PCs no presentes en el subgrafo.
- Un rango Ghidra B indica propiedad del análisis estático, **no prueba** de ejecución exclusiva ni ausencia de entradas alternativas.
- El compilador LLVM ya elimina muchos temporales y una caché de chunk grande provocó *spills*. No repetir fases 12/13 sin nuevos datos.
- Los contratos x87 son más estrictos que equivalencia numérica aproximada: respetar bytes, padding y señales relevantes.

**Primera entrega 14A completada:** recuperación de **450 bloques** en siete cuerpos originales (3.326 instrucciones), con informe privado, pruebas sintéticas y chequeo independiente de Capstone de 342 controles directos/indirectos. **Análisis, no optimización ejecutable.** Ver [informe de 14A](PHASE14_CFG_INITIAL_RECOVERY_2026-10-14.md). 14B permanece parcial; 14C–14E siguen pendientes. Ver [informe 14B](PHASE14B_STATE_BOUNDARIES_ORACLE_2026-10-15.md).
