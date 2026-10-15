# Fase 14 — Arquitectura de recompilación por regiones CFG (plan maestro)

**Inicio:** 2026-10-14. **Rama:** `main`. **Estado:** 14A IMPLEMENTADA y auditada contra p-code + Capstone x86 original; 14B AÚN PENDIENTE en equivalencia de estado completo. **TECNO:** no disponible y no requerido para las etapas offline. **Meta de 60 FPS:** pendiente; no confundir validación estructural con ms/frame.

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

### 14B — Verificación independiente x86 y contrato de frontera (**verificación estática x86 iniciada; estado completo pendiente**)

- [x] Verificar con Capstone las **3.326 instrucciones** reales (límites y anchuras) y **342 transferencias** decodificables contra Ghidra p-code: **0 discrepancias**. Cuatro instrucciones con p-code vacío quedan bloqueadas; esta verificación **no prueba** equivalencia de estados.
- [ ] Extender el oráculo Unicorn/Capstone del prólogo existente a regiones de flujo de control **acotadas y alcanzables**; comprobar que los bytes reales x86 y el p-code coinciden en límites de instrucciones y destinos de saltos donde se puedan verificar.
- [ ] Establecer `live-in/live-out` byte a byte de `R`, efectos de RAM, bandera y estado x87. Añadir barreras para `CALLOTHER`, memoria aliasable, accesos externos y trampas; no almacenar registros virtuales en variables locales sin las guardas.
- [ ] Verificar rutas de fallthrough, rama tomada/no tomada, bucles, salidas dinámicas y reentrada desde el dispatcher.

**Aceptación 14B:** oráculo independiente para las regiones elegidas, mutaciones negativas detectadas, estados finales iguales, rutas irresueltas explícitas.

### 14C — Arquitectura de regiones y SSA

- [ ] Construir región a partir de **subgrafo CFG** cerrado con entradas conocidas, salidas de estado etiquetadas y caminos indirectos como fallbacks.
- [ ] Usar SSA/análisis de vivacidad sobre bytes arquitectónicos, con selección de caché de registros por región (no 1.500 instrucciones por chunk), guardando estado en cada salida y carga en cada punto de entrada independiente.
- [ ] Optimizar patrones completos de movimiento de datos, comparación geométrica o recorrido solo cuando la regla sea inequívoca y rentable; siempre mantener la traducción p-code original como fallback reversible.

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

**Primera entrega 14A completada:** recuperación de **450 bloques** en siete cuerpos originales (3.326 instrucciones), con informe privado, pruebas sintéticas y chequeo independiente de Capstone de 342 controles directos/indirectos. **Análisis, no optimización ejecutable.** Ver [informe de 14A](PHASE14_CFG_INITIAL_RECOVERY_2026-10-14.md). Las etapas 14B–14E siguen pendientes hasta cumplir criterios.
