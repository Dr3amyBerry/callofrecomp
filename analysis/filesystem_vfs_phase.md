# Primera fase del sistema de archivos virtual (VFS) y lectura de PK3

## Implementación existente

El lector C++17 de `src/vfs.cpp` y la interfaz `include/codrecomp/vfs.hpp` permiten montar directorios de solo lectura y archivos PK3 (ZIP32) sin extraer datos al disco. Utilizan zlib para los miembros comprimidos con DEFLATE (método 8), admiten miembros sin compresión (método 0), verifican tamaños y CRC-32 y validan las cabeceras locales frente al directorio central.

El proyecto **no** ha reconstruido aún el filesystem completo del COD1 original. El orden de montajes usado por la librería (el último añadido tiene prioridad) es una política de prueba explícita, no una afirmación sobre la prioridad de paquetes y archivos sueltos del juego.

El lector rechaza rutas absolutas, `..`, rutas con unidad, caracteres de control, escapes por enlaces simbólicos fuera del directorio y miembros ZIP con cabeceras, tamaños o CRC inválidos. Limita a 64 MiB cada lectura descomprimida y a 64 MiB los bytes comprimidos que acepta para un único miembro. No implementa ZIP64, archivos cifrados, escritura ni acceso por streaming.

## Pruebas

`tests/vfs_smoke.cpp` genera archivos sintéticos con miembros almacenados y comprimidos; comprueba lecturas normales, contenido vacío, rutas peligrosas, CRC incorrecto, precedencia explícita y tamaño máximo. Está registrado en CMake/CTest y no requiere archivos del juego.

Se comprobó además con el `main/pakb.pk3` original de 5.087.181 bytes de la instalación proporcionada. El VFS indexó **24 rutas distintas no directorio**, abrió y verificó CRC y tamaño de `ui_mp/createserver.menu` (27.514 bytes) y `ui_mp_x86.dll` (274.432 bytes). Este paquete es contenido de multijugador y se empleó como **prueba real del formato PK3**, no como prueba del orden de carga de la campaña. Ningún archivo original se subió a GitHub.

Ejecutar sin archivos originales:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

Comprobación opcional con un paquete original de tu instalación:

```bash
./build/codrecomp_vfs_smoke /ruta/a/originals/main/pakb.pk3
```

## Modos de apertura observados en `CoDSP.exe`

El despachador en `VA 0x00425FD0` compara el modo con 3; si es mayor usa la ruta de error y, en caso contrario, salta mediante cuatro direcciones de la tabla en `VA 0x004260F0`.

| Modo numérico | Destino | Observación binaria |
|---:|---:|---|
| 0 | `0x00425FF5` | Llama a `0x004226A0` y actualiza estado local del identificador de archivo |
| 1 | `0x00426015` | Llama a `0x00422180` |
| 2 | `0x00426033` | Llama a `0x00422360`, con indicador local `0` |
| 3 | `0x0042602B` | Pone indicador local `1` y pasa a la ruta que llama a `0x00422360` |

Estos cuatro valores **todavía no tienen nombres de modo confirmados**, por lo que deliberadamente no se han fijado en un enum como si fueran equivalentes directos a APIs conocidas. Hace falta verificar también semántica de retornos, errores y handles.

## Adaptador nativo de lectura para el contrato host

Se añadió una implementación independiente `ReadOnlyHostAdapter`
(`include/codrecomp/read_only_host_adapter.hpp` y
`src/read_only_host_adapter.cpp`) que conecta el VFS con las
funciones de `cod_host_services_t`:

- `fs_open`: recibe una ruta lógica y un **modo de lectura configurado
  explícitamente** al construir el adaptador; devuelve un handle opaco
  distinto de cero y, por convención propia, la longitud del archivo.
- `fs_read`: mantiene un cursor por handle, admite lecturas parciales,
  devuelve 0 al alcanzar EOF y -1 en handles o buffers inválidos.
- `fs_close`: invalida el handle y libera el buffer cargado.
- Cada archivo abierto mantiene un buffer independiente; se usan mutexes
  para proteger el mapa de handles y los cursores.

Las funciones de escritura, renombrado, enumeración y comandos de consola
se dejan a `nullptr` **intencionadamente**. No se simula el comportamiento
original sin suficiente evidencia. El adaptador también evita convertir
punteros nativos de 64 bits a palabras x86 de 32 bits.

La prueba `tests/host_adapter_smoke.cpp` ejercita modos incorrectos,
rutas rechazadas, lecturas sucesivas, EOF, archivos vacíos,
handles independientes y cierre/invalidez. Es **una interfaz host
funcional**, pero todavía NO hay puente desde el dispatcher de
`gamex86.dll` ni Android funcional. El número de modo de la prueba
(`77`) es inventado a propósito como convenio de prueba, NO es
un código original del juego.

## Por integrar

1. Identificar nombres y comportamiento de los modos de apertura contra llamadores y rutinas internas.
2. Recuperar prioridad de los PK3 originales, localización y overlays de archivos sueltos.
3. Completar el puente **VM x86 de 32 bits → servicio host** validando punteros/handles; el adaptador de servicio host nativo ya existe.
4. Recuperar el formato real de listas de archivos de `FS_GETFILELIST`.
5. Añadir lectura fragmentada/seek y escritura aislada para configuraciones y guardados.
6. Validar compilación Android NDK y arranque del motor.

La interfaz `include/codrecomp/host_services.h` sigue siendo un **contrato portable**; la librería VFS funciona, pero aún no existe un puente completo al motor ni un juego ejecutable.
