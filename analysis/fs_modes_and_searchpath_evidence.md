# Evidencia: modos FS y lista de búsqueda en Call of Duty 1.5 SP

**Binario analizado:** `CoDSP.exe`, SHA-256 `c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47`. Este mapa se aplica únicamente al perfil de PC 1.5 SP; no atribuirlo automáticamente a multijugador o United Offensive.

## Despachador de modos

El despachador en `VA 0x00425FD0` compara el modo con `3` (`0x00425FD5`) y salta por la tabla indexada `0x004260F0` (`0x00425FEE`). Las cuatro entradas están determinadas directamente por el ejecutable:

| Modo | Destino de la tabla | Función invocada | Cadena de modo comprobada | Semántica respaldada |
|---:|---:|---:|---|---|
| 0 | `0x00425FF5` | `0x004226A0` | `rb` (`0x005584E0`) | lectura binaria |
| 1 | `0x00426015` | `0x00422180` | `wb` (`0x005584BC`) | escritura binaria con truncado |
| 2 | `0x00426033` | `0x00422360` | `ab` (`0x00558434`) | append binario |
| 3 | `0x0042602B` → `0x00426033` | `0x00422360` | `ab` (`0x00558434`) | append con bandera adicional de sincronización |

Los destinos de llamadas son relativos `E8` en `0x00426009`, `0x00426019` y `0x00426037`. Las cadenas `rb`, `wb` y `ab` se pasan a la rutina del CRT que abre los archivos. El caso 3 escribe `1` en un estado local en `0x0042602B`; el caso 2 mantiene `0`; la bandera termina guardada en el campo del handle `0x014DFBE8` (`0x004260E1`). La ruta de escritura lee dicho campo en `0x00423140` y, si es distinto de cero, invoca `0x0051BD19` después de escribir (`0x0042314B`). Se considera **matched** la función *append con sincronización*, pero aún no se ha reconstruido todo el contrato de errores, flush y handles.

El texto de error original `FSH_FOpenFile: bad mode` está en `0x00557BDC`. La comparación excluye modos por encima de 3.

**Importante:** el puente actual implementa **solo modo 0**. Los modos 1, 2 y 3 se reconocen pero son rechazados, porque permitir escribir sin reproducir el sandbox de configuraciones/guardados sería prematuro.

## Orden de paquetes: qué sabemos

El motor mantiene una lista enlazada de fuentes de búsqueda con cabeza en `0x013F9E3C`. La ruta de lectura de `0x004226A0` carga la cabeza en `0x004226D9`, evalúa la entrada y avanza por el enlace de desplazamiento `+0` en `0x0042278E`, repitiendo la búsqueda.

El motor dispone de una rutina de inserción en `0x004248B0`: una rama inserta el nodo nuevo al principio (`0x004248DE–0x004248E0`); otra rama recorre nodos comprobando el campo `+0x0C` y lo inserta dentro de la lista (`0x004248C5–0x004248DD`). Otras rutas de construcción de la lista alrededor de `0x00424D2F` y `0x0042506A` repiten una lógica semejante.

Por ello **no podemos asumir que el filesystem original equivale a «último montaje gana»**. La prioridad depende de la posición real en esa lista, de los atributos de cada fuente y de las rutinas que la agregan. La VFS portable **sigue usando last-mounted-wins de manera provisional y explícita**, solo para facilitar pruebas; no está marcada como compatible con la prioridad original.

## Validación reproducible

Con una copia externa del `CoDSP.exe` del perfil citado:

```bash
sha256sum originals/CoDSP.exe
objdump -D -M intel --start-address=0x425fd0 --stop-address=0x4260ee originals/CoDSP.exe
objdump -D -M intel --start-address=0x422180 --stop-address=0x422440 originals/CoDSP.exe
objdump -D -M intel --start-address=0x4226a0 --stop-address=0x4227b2 originals/CoDSP.exe
objdump -D -M intel --start-address=0x4248b0 --stop-address=0x4248e7 originals/CoDSP.exe
objdump -D -M intel --start-address=0x423140 --stop-address=0x423157 originals/CoDSP.exe
```

Las direcciones son VAs para la imagen base `0x00400000`; los campos y rutas son **evidencia de desensamblado**. No se ha ejecutado el binario Windows ni confirmado empíricamente la prioridad combinando todos los PK3 originales.

## Trabajo pendiente

1. Seguir el ensamblado completo de las funciones que construyen y ordenan la lista de búsqueda, incluidos nombres de PK3 y localizaciones.
2. Reproducir la prioridad de fuentes en el VFS únicamente cuando exista un orden documentado y contrastable.
3. Recuperar modos de error y comportamiento de los handles de archivos antes de implementar escritura/saves.
4. Integrar un sandbox de rutas y permisos para Android y ejecutar pruebas en dispositivo/emulador.
