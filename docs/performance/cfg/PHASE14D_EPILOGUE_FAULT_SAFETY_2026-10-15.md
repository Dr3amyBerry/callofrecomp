# Fase 14D — Epílogo x86, fallos de página y bloqueo de la región CFG insegura

**Fecha:** 2026-10-15

**Estado de la fase:** *auditoría del epílogo y de excepciones finalizada parcialmente; optimización CFG aún NO elegible para ejecución en el juego*. El constructor Android rechaza el flag inseguro. No se ha instalado una APK con el cambio ni medido FPS nuevos.

## Actualización 14E — recuperación verificada offline, versión Android aún bloqueada

El diagnóstico 14D de **15/18 puntos de fallo inseguros** sigue correspondiendo al código cacheado original. Un nuevo generador experimental offline obtuvo **120/120** reanudaciones precisas desde el PC fallido con el x86 original y el traductor A sin caché. Aunque la corrección conserva RAM/R/PC y evita repetir STORE, **no se ha integrado la captura de señales del SO Android** y la versión segura tiene mayor coste de código ARM64. El flag CMake y builder permanecen BLOQUEADOS. [Informe 14E](PHASE14E_PRECISE_CHECKPOINTS_AND_RESUME_2026-10-15.md).


## 1. Oráculo original x86: éxito, error y primera llamada del manejador

Herramienta nueva: `tools/recomp/diagnostics/verify_shared_epilogue_paths_unicorn.py`. Usa los bytes **originales** de CoDSP.exe 1.5 verificados mediante PE y Capstone; el control es independiente del p-code y utiliza Unicorn x86 de 32 bits. El lado traducido compila en DLL privada la semántica de `pcode2c.Gen` sin escribir código propietario en Git. Hash del PE y del p-code fijados por la versión auditada.

Se compararon los **8 GPR**, `CF/PF/ZF/SF/OF`, PC exacto, R completo (`8192 bytes`), pila y 6 MiB de RAM invitada acotada. Se evita dejar TF (single-step) activo en estados sintéticos.

| Ruta | Comportamiento original ejecutado | Resultado |
| --- | --- | --- |
| Cookie correcto | `0x00523CD9 CMP` → `0x00523CDF JNE` no tomado → `0x00523CE1 RET`; recupera el retorno desde `ESP`, incrementa ESP 4 y escribe el destino a `R+0x284` en la traducción | **128/128 PASS** |
| Cookie incorrecto | CMP → JNE tomado → `0x00523CE2 JMP` → entrada de error `0x00523CA8` | **128/128 PASS** |
| Ruta de error ampliada | Los 3 primeros pasos originales del manejador, `PUSH 8`, `PUSH 0x533B68`, `CALL 0x51FF90`, incluidos sus 3 efectos sobre la pila y ESP | **64/64 PASS** |
| Éxito con oráculo ampliado | Se preserva la ruta normal al habilitar el chequeo adicional del error | **64/64 PASS** |

**No está verificado el cuerpo de las funciones llamadas por la ruta de error**, ni otras rutas del manejador tras el primer `CALL`, ni el estado AF: el traductor original todavía no materializa AF en esos casos. La comparación completa de R se ajusta a la semántica documentada de EIP sombra `R+0x284` al ejecutar RET.

Evidencia privada reproducible:
- `.local/profiles/phase14e_epilogue_both_128_v1/summary.json`
- `.local/profiles/phase14e_tail_error_first_call64_v1/summary.json`

Las pruebas sintéticas `tests/test_verify_shared_epilogue_paths_unicorn.py` comprueban rutas, destinos, EIP sombra, protección contra userops opacos y rechazo de saltos/calls incorrectos.

## 2. Auditoría REAL de excepciones de memoria

Herramienta nueva: `tools/recomp/diagnostics/audit_cfg_region_fault_state.py`.

1. Traza las lecturas y escrituras del original CoDSP.exe en Unicorn x86 durante las 29 instrucciones del bloque de geometría `0x0041C017`.
2. Para cada página nueva de 4 KiB se ejecuta nuevamente la ruta original con la página realmente **desmapeada**, registrando el punto de la excepción de lectura/escritura y el estado de GPR/EFLAGS/PC.
3. Una DLL *privada* del helper CFG mantiene el C traducido original, pero intercepta el **mismo acceso N a memoria** mediante `setjmp/longjmp` para observar R/PC **antes** de tocar la memoria. Esto no emula la entrega de señales del sistema Android: es una comparación controlada de frontera arquitectónica.
4. Compara la dirección exacta que falla y el estado arquitectónico de cinco flags, ocho registros generales y PC del traductor contra el original; no falsifica el destino del salto ni modifica el motor.

**Resultado de 3 semillas, 18 puntos de excepción realmente probados:**

| Caso | Observaciones |
| --- | --- |
| Primer acceso de memoria (`0x0041C017`) | 3/3 estados coinciden |
| Accesos posteriores (5 lugares distintos, incluidos `0x0041C01B` y `0x0041C023`) | **15/15 estados divergentes** |
| Total | **15/18 puntos inseguros** |

En `0x0041C023` faltaban escrituras arquitectónicas pendientes para **EAX, EDX** y el PC guardado seguía en la entrada del bloque, no en la instrucción que falló. En otros puntos faltaban EDX/PC. Esta divergencia existe aun cuando el bloque cacheado había pasado 40/40 casos de terminación **normal**.

**Control positivo:** la primera lectura de memoria antes de modificar registros no presenta diferencias. **Control negativo estricto:** `--require-safe` devuelve **código de rechazo 4** si existe **cualquier** divergencia. Se ejecutó este modo y rechazó correctamente 5/6 puntos observados en una semilla.

Evidencia privada:
- `.local/profiles/phase14e_fault_boundaries_3cases_v1/summary.json`
- `.local/profiles/phase14e_strict_fault_gate_v1/summary.json`

El archivo de test sintético `tests/test_cfg_region_fault_state.py` protege el criterio de aceptación de estas pruebas y rechaza reportes inconsistentes o incompletos.

**Conclusión de seguridad:** mientras la caché retenga registros que una excepción pueda hacer observables antes del flush, **NO ejecutar** la ruta acelerada en una APK de prueba del TECNO. Es necesario un mecanismo de abandono seguro `deopt`, con estado por instrucción y restauración de flags si un acceso a memoria falla, o seleccionar subgrafos sin accesos guest a memoria.

## 3. Integración y enlace Android

La fase anterior había configurado y compilado correctamente con NDK el helper ARM64 y el dispatcher con la macro `CODRECOMP_CFG14_GEOM_REGION`. El modo **OFF** no introduce ese helper ni referencia simbólica.

Se completó un **enlace integral Android ARM64 aislado** del candidato original ANTES de cerrar la barrera CMake: **Ninja 292/292, exit 0**. Artefacto privado ignorado `.local/builds/phase14d_cfg_on_v3/lib/libmain.so`, **229.834.608 bytes**, SHA-256:

`e05483e76f803f65f313d19a00d816c0fa7e5839f415d300abd5b3c3a43923e1`

`llvm-readelf` verificó un ELF compartido **AArch64 ET_DYN** con el símbolo `codsp_cfg14_geom_41c017` definido (3 entradas en la tabla de símbolos). El enlace incluye los módulos privados CoDSP/UI/CGAME/GAME, SDL y GL4ES. **No es una APK ni prueba de ejecución segura**.

**Barrera posterior al enlace:** `build_android.py` rechaza explícitamente `--cfg14-geom-region`, y `android/CMakeLists.txt` ahora rechaza CMake ON con `FAULT_STATE_UNSAFE`. Se verificó la negativa de **CMake real** para ON (exit 1 esperado) y la reconfiguración OFF normal (exit 0). El viejo binario experimental ON permanece como prueba privada de compatibilidad y **NO se instalará**.

**Regresión final:** **343 tests Python** ejecutados (4 omitidos y 0 fallidos), **35/35 CTest** aprobados. Se compiló y ensayó también un epílogo privado con salto de error alterado: el oráculo detectó el error y mantuvo PASS para la ruta de retorno intacta.

**Dispositivo disponible:** `adb devices -l` detectó solo **Windows Subsystem for Android (WSA x86_64)** en `127.0.0.1:58526`. **El TECNO ARM64 no está conectado**, por lo tanto no hay una comparación física válida de CPU ms/frame, ni se debe presentar WSA como sustituto.

## 4. Próxima decisión técnica

1. Diseñar **deoptimización antes de fallos de página**: nunca entregar un evento de memoria mientras R/PC sean observables con estado anterior al original. Esto requiere comprobar precondiciones de páginas, conservar el orden de efectos previos a LOAD/STORE y restaurar cualquier flag modificado antes de una lectura que falla.
2. Validar todos los puntos de falta de memoria contra Unicorn original, incluyendo alias y entradas interiores; el guard de seguridad deberá aprobar **100 % de los casos**, no solo casos normales.
3. Comparar la calidad del código ARM64 después de los checks. Si el coste excede el ahorro de cargas/escrituras, **descartar** esa aceleración y buscar regiones CFG completas puramente enteras sin acceso a memoria guest.
4. Solo con el estado seguro, repetir el enlace del candidato corregido y **construir una APK** de prueba para TECNO, con A/B/A/B de CPU ms/frame en idéntica escena y gráficos. El enlace del helper inseguro ya pasó, pero no autoriza despliegue.

**No hay nueva ganancia de FPS probada y el objetivo de 60 FPS continúa pendiente.**
