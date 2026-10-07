# Puente conservador entre el ABI de archivos x86 y servicios nativos

## Objetivo y alcance

El puerto ahora incluye un **prototipo funcional de un puente de syscalls de lectura** sobre un mapa de memoria invitada de 32 bits. No ejecuta código x86 del juego, no convierte direcciones invitadas directamente en punteros nativos y **no es un motor Android funcional**.

Archivos implementados:

- `include/codrecomp/guest_memory.hpp` y `src/guest_memory.cpp`: mapa de regiones de memoria invitada.
- `include/codrecomp/legacy_fs_read_bridge.hpp` y `src/legacy_fs_read_bridge.cpp`: despachador selectivo de syscalls de archivos.
- `tests/guest_vm_bridge_smoke.cpp`: pruebas integradas con el VFS y `ReadOnlyHostAdapter` existentes.
- `analysis/fs_modes_and_searchpath_evidence.md`: evidencia binaria independiente para los modos y la búsqueda.

## ABI implementado

El protocolo de prueba recibe una secuencia de palabras de 32 bits: `[syscall_id, argumento_0, argumento_1, ...]`. Todos los punteros del invitado son **direcciones de 32 bits registradas en `GuestMemory`**; ningún entero se trata como una dirección del proceso host. El host conserva punteros nativos con el ancho propio de la plataforma.

| ID CoD 1.5 SP | Operación | Argumentos transportados en orden | Comportamiento del puente |
|---:|---|---|---|
| 21 | `G_FS_FOPEN_FILE` | `(path_guest_va, handle_out_guest_va, mode)` | Admite únicamente modo `0` (lectura); valida el string y los 4 bytes de destino; devuelve longitud y asigna handle opaco. |
| 22 | `G_FS_READ` | `(buffer_guest_va, byte_count, handle)` | Valida destino escribible y handle abierto, copia exactamente la longitud pedida; en éxito devuelve palabra `0`. |
| 37 | `G_FS_FCLOSE_FILE` | `(handle)` | Cierra el handle previamente abierto en el puente y devuelve palabra `0`. |

Los IDs 23 (escritura), 36 (rename), 40 (listado) y 41 (comandos de consola), y el resto de IDs **no se implementan aquí**: una llamada devuelve `unsupported_syscall` en lugar de simular éxito.

### Evidencia que respalda el modo 0

El ejecutable original `CoDSP.exe` compara el modo de apertura con `3`, despacha `0` hacia el helper de lectura (cadena `rb`), `1` hacia escritura (`wb`) y `2/3` hacia append (`ab`, con bandera adicional en `3`). La función de escritura consulta dicha bandera al finalizar la operación. Véase `analysis/fs_modes_and_searchpath_evidence.md` para VAs, direcciones de los helpers y comandos de reproducción.

## Validaciones y límites de seguridad

- `GuestMemory::map` rechaza mapeos nulos, vacíos, solapados y rangos que desborden el espacio invitado de 32 bits.
- Los accesos de lectura/escritura requieren un **único** segmento continuo que contenga todo el rango; no se acepta desbordamiento entre segmentos ni escritura sobre una región registrada como read-only.
- Las cadenas C deben terminar en NUL en la misma región antes del límite (1.024 bytes por defecto).
- Los valores de 32 bits del invitado se leen y escriben explícitamente en little-endian; se evita el cast entero→puntero.
- Solo se aceptan handles emitidos y aún abiertos por esta instancia del puente. Doble cierre y uso después del cierre fallan; el destructor cierra handles restantes.
- Máximo de **4.096** archivos abiertos por puente; máximo de **1 MiB** de lectura por llamada. El VFS existente mantiene un límite de 64 MiB por archivo cargado.
- Para leer, el puente usa un búfer temporal: solo modifica la memoria invitada cuando logra obtener los bytes solicitados. Una lectura incompleta/EOF informa `short_read` sin copiar bytes parciales; el cursor del backend puede haber avanzado.
- Errores del backend/validación están separados del `return_word` de la llamada emulada. La palabra `0xffffffff` en un error es una convención del adaptador y **no** una afirmación de que el motor original devuelva eso en todas las circunstancias.
- `GuestMemory` **no es propietario** de los buffers host mapeados: el llamador debe garantizar su tiempo de vida. El puente es de uso de un solo hilo mientras los mapeos son estables.

**Distinción esencial:** se validan syscalls contra una implementación nueva de servicios nativos; aún **no** se ha reconstruido el dispatcher completo de `CoDSP.exe`, la semántica integral de handles ni el código original de los módulos de juego.

## Pruebas repetibles

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

`guest_vm_bridge_smoke` usa archivos sintéticos y comprueba direcciones inválidas, solapamientos, permisos de memoria, cstrings sin NUL, palabras little-endian, apertura, lecturas parciales, EOF, handles independientes, límites y rechazo de escrituras. La suite completa consta ahora de **6 tests CTest**, incluyendo los unit tests de Python; GitHub Actions ha compilado y aprobado esos seis tests.

Los originales siguen exclusivamente en Drive/local; las pruebas de CI no requieren distribuir EXE, DLL ni PK3.

## Pendiente

1. Recuperar prioridad exacta de cada PK3/archivo suelto y overlays de idioma de la lista enlazada original; la prioridad provisional del VFS no equivale a la del juego.
2. Confirmar cómo representa el motor original los errores de lectura corta/EOF y cómo enumera los handles y sus flags.
3. Implementar seek, lectura por streaming y escritura en sandbox de guardados/configuración en una fase separada, con pruebas de recorrido y persistencia.
4. Validar integración del puente con un módulo reconstruido (no el DLL x86 original) y compilación Android NDK.
