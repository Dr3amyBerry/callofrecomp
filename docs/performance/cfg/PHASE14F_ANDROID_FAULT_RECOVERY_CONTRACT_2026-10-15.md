# Fase 14F — Contrato de recuperación segura de fallos guest en Android ARM64

**Fecha:** 2026-10-15 · **Estado:** arquitectura diseñada y auditoría de código realizada; **NO HAY IMPLEMENTACIÓN DE RECUPERACIÓN DEL SO ANDROID**. El candidato CFG14 permanece OFF y con error fatal de construcción si alguien solicita ON.

## 1. Realidad del runtime auditado

Se examinaron `tools/recomp/runtime/guest.c`, `tools/recomp/recomp_rt.h`, `android/CMakeLists.txt` y `tools/recomp/build_android.py`:

- `MEM` reserva mediante `mmap` un espacio de direcciones invitadas de **4 GiB** en Android, inicialmente `PROT_NONE`. `guest_commit` usa `mprotect(...,PROT_READ|PROT_WRITE)` y `guest_decommit` vuelve a `PROT_NONE`. La tabla `committed` indica páginas comprometidas pero no representa todos los permisos y efectos posibles de una falta.
- `G(a)` convierte el offset guest de 32 bits directamente a `MEM + addr`. **Una lectura/escritura nativa no comprometida produce SIGSEGV/SIGBUS en el proceso host**, no automáticamente una excepción Win32 correctamente entregada al x86 emulado.
- `R[0x2000]`, `U[0x400000]`, `PC` y `MEM` son **globales**, no almacenamiento separado por guest thread. No se ha demostrado seguridad ante ejecución concurrente ni interrupciones asíncronas.
- El handler Unix `on_fault` actual imprime diagnósticos y termina vía `_exit(3)`; **no desoptimiza ni devuelve control al dispatcher**.
- La instalación `sigaction(SIGSEGV/SIGBUS)` está encerrada en `#ifndef __ANDROID__`: se excluye en Android para no interferir con ART, Java/JNI y la transición al código nativo. **No se debe eliminar ese guard o añadir un handler global sin un estudio de seguridad del runtime**.
- El dispatcher conserva `dispatch_index_find(...)` y `all_chunks[found].fn()` para cualquier PC original. Esta ruta es imprescindible para una recuperación eventual; por sí sola **no puede reparar una página no comprometida ni entregar una excepción guest**.
- Tanto CMake como el constructor Python mantienen **bloqueo fatal de CFG14 ON** desde 14D, aparte de OFF por defecto.

La herramienta `tools/recomp/diagnostics/audit_cfg_runtime_recovery.py` produce un diagnóstico de fuente verificable y reporta explícitamente **`ready_to_enable_CFG14_on_Android=false`**. Su exit code 0 significa que **las barreras siguen intactas**, NO que la recuperación está implementada. Si se elimina uno de esos guardas, devuelve error 4. Archivo privado de evidencia: `.local/profiles/phase14f_android_recovery_readiness_v1.json`.

## 2. Contrato exacto para una futura transición segura

### Entrada al fast path

Solo se admitirán originales, hashes de CoDSP 1.5 y PC líderes autorizados. Se exige que el motor pueda identificar un único ejecutor del guest (o tener estado totalmente aislado por hilo). El código experimental no debe cambiar la semántica x87, los gráficos, los guardados o el tratamiento de excepciones por defecto.

### Antes de un acceso guest que puede fallar

1. Terminar todos los efectos de las **instrucciones x86 ya completadas**.
2. Volcar a `R` los registros cacheados **modificados** desde la última frontera; preservar banderas y estado restante.
3. Poner `PC` en la **dirección x86 original de la instrucción a punto de ejecutarse**, nunca en la entrada del bloque.
4. No adelantar efectos de esta misma instrucción que el x86 original aún no habría ejecutado si la lectura fallase. El caso de CF/OF antes del LOAD de `0x0041C073` ya tiene una solución offline restringida; otras secuencias se rechazan.
5. Mantener en `MEM` las escrituras `STORE` anteriores **exactamente una vez**. No reservar efectos pendientes para un nuevo intento ni volver a ejecutar instrucciones previas desde el líder.

### Cómo detectar el acceso inválido de manera segura

**Preferencia inicial: validación explícita de memoria invitada ANTES de tocar la dirección host**, no un `siglongjmp` ad hoc desde un SIGSEGV de Java/ART:

- Usar aritmética de **64 bits** para validar `guest_addr + width` sin wrap a 32 bits. El rango debe quedar dentro de los **4 GiB**; incluir los dos extremos de cualquier acceso que cruce una página de 4 KiB.
- Comprobar compromiso y **permisos de lectura/escritura** de **todas** las páginas del rango. La tabla actual `committed` no modela todos esos permisos; ampliar el gestor de memoria y sincronizarlo con `guest_commit`, `guest_decommit` y regiones virtuales.
- Definir reglas de concurrencia: o ejecución guest estrictamente de un solo hilo demostrada, o metadatos de páginas con generación/bloqueo junto a contextos R/PC propios. Un chequeo seguido de un acceso host sin protección frente a `decommit` concurrente tiene una carrera **TOCTOU**.
- Las instrucciones con accesos múltiples, acceso atómico, STORE parcial antes de otra lectura o cambios de memoria entre accesos **no son automáticamente reiniciables**. Rechazarlas hasta modelar de forma explícita su atomicidad.
- Un fallo de acceso no puede asumir que la página será reparable. Si permanece descomprometida, hace falta entregar el error al **modelo de excepciones guest/SEH** correcto o tratarlo como no resuelto; no se debe lanzar indefinidamente el mismo SIGSEGV. El runtime actual no ofrece un SEH guest completo validado.

### Handoff al dispatcher

Se necesita una interfaz explícita que modele un resultado de acceso (`OK`, `GUEST_FAULT_READ`, `GUEST_FAULT_WRITE`, `ADDRESS_OVERFLOW`, `UNSUPPORTED`), con:

- PC guest de la instrucción fallida; dirección guest y ancho de acceso; tipo `READ`/`WRITE`; contexto R/flags coherente y propiedad del hilo.
- Lista de efectos ya comprometidos **antes de esa instrucción**. Es un contrato de validación, no un registro que vuelva a aplicar esos STORE.
- Si una excepción guest se resuelve (página preparada, handler guest atendido), **reanudar desde el PC original interior mediante el traductor A** sin caché; NO volver a entrar a la superregión acelerada. Si no se resuelve, seguir la política de excepción fatal/guest existente, sin simular una recuperación exitosa.
- Fuera de la región reservada de `MEM`, cualquier fallo host auténtico es responsabilidad del runtime/ART y no debe ser interceptado como fallo x86.

El ensayo de fase 14E ya verificó **120/120** reanudaciones desde la instrucción que fallaba, con Unicorn x86 y el traductor A, sin repetir las seis STORE del bloque. Esto prueba **el contrato lógico para ese bloque**, pero **no demuestra el handoff de un dispositivo Android real**.

### Opción alternativa: señales host

Un handler SIGSEGV de proceso completo sería una segunda ruta, **no autorizada por este plan actual**, y requeriría: encadenar/coordinarse con los handlers ART/Java/native existentes, contexto por hilo, pila alternativa de señales, operaciones asíncronamente seguras, comprobación de si la dirección es realmente de `MEM`, salida controlada sin ejecutar código nativo parcialmente, recuperación de registros/PC del guest y pruebas de carreras/recursión. **No usar `printf`, malloc, JNI ni `longjmp` indiscriminado desde un handler de señales**. Ningún test offline actual prueba esas garantías.

## 3. Reglas de aceptación para desbloquear CFG14

Se necesitan **todas** las verificaciones siguientes:

1. **Unicorn original**: GPR, EFLAGS completos necesarios, x87 cuando aplique, R y RAM equivalentes en entrada, salida y cada posible fault del bloque elegido; original PC y tamaño de la instrucción identificados sin adivinanzas.
2. **Memoria host**: páginas decomprometidas, permisos de lectura y escritura, accesos que cruzan páginas, límites de 0/4 GiB, alias, STORE previo al fault, prefijos repetidos, datos modificados durante la ejecución y falta fuera de `MEM`.
3. **Recuperación de dispatcher Android**: tras falta realmente generada o detectada en dispositivo, al resolverla se vuelve al **PC interior** y a la traducción original; las escrituras anteriores no se duplican, el PC no queda en el líder ni se entra en bucles de fallo.
4. **ART/JNI y threads**: ningún crash capturado por error, handlers de Android respetados, sin carreras ni pérdida de R/PC. Los fallos del host que no son de `MEM` no se interpretan como x86.
5. **Calidad de código y rendimiento**: evaluar el sobrecoste por cada consulta de permisos/checkpoint y la frecuencia real de la región. Solo mantener el fast path si mejora el **ms de CPU/frame** bajo mismas condiciones A/B/A/B con el TECNO; sin ganancias reproducibles se descarta.

**No habilitar CMake ON ni `--cfg14-geom-region` antes de completar estas garantías**. Un test de fuente que encuentre `sigaction` o `siglongjmp` no equivale a las pruebas de seguridad requeridas.

**Regresión del contrato de seguridad:** `tests/test_cfg_runtime_recovery_readiness.py` tiene seis casos sintéticos que comprueban protección de CMake, bloqueo del constructor, ausencia intencional de handler Android, fallback original y estado R/PC global. La suite total de repositorio pasó **369 tests Python (4 omitidos) y 35/35 CTest**. Este resultado valida el **bloqueo y el diagnóstico**, no una implementación Android del contrato.


## 4. Decisión ejecutiva

La superregión sin acceso guest RAM más larga encontrada hoy tiene **solo ocho instrucciones**, y las tres evaluadas con el x86 original no mejoran la calidad estática ARM64 al cachear R. El bloque con memoria que sí obtuvo equivalencia bajo falta de página requiere más escrituras/código ARM64 para sus checkpoints y aún no tiene recuperación real Android. Por ahora, **ninguna de las dos variantes justifica un despliegue**.

Siguiente prioridad técnica de mayor utilidad: perfiles reproducibles de CPU guest/host para localizar regiones **más grandes, estables y algorítmicamente optimizables** (geometría, visibilidad, colisiones), oráculo original por camino y medición física antes de tocar el runtime de producción. Mantener el contrato de fallo como requisito de seguridad para cualquier optimización futura con memoria guest.

**Sin APK experimental nueva, sin cambios gráficos y sin FPS nuevos verificados.**
