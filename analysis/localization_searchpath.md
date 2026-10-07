# Call of Duty 1.5 SP — localización y nodos de búsqueda

**Origen:** binario `CoDSP.exe` (SHA-256 `c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47`). Este análisis procede de los bytes del ejecutable original, no de suposiciones de id Tech 3. La herramienta verifica cinco ventanas de instrucciones mediante hashes SHA-256 y valida una tabla estática.

## Tabla de idiomas recuperada

La tabla comienza en **VA `0x00564B08`**. Tiene **14 registros de 8 bytes**, con puntero a cadena en el primer DWORD y segundo DWORD cero en el archivo analizado. Las cadenas se encuentran en `.rdata`.

| Índice | Nombre literal |
|---:|---|
| 0 | `english` |
| 1 | `french` |
| 2 | `german` |
| 3 | `italian` |
| 4 | `spanish` |
| 5 | `british` |
| 6 | `russian` |
| 7 | `polish` |
| 8 | `korean` |
| 9 | `taiwanese` |
| 10 | `japanese` |
| 11 | `chinese` |
| 12 | `thai` |
| 13 | `leet` |

**`spanish=4`** está comprobado. `leet=13` es una entrada interna real de la tabla, aunque no debe confundirse con un idioma instalado. La tabla representa nombres reconocidos por el motor; **no implica que esta instalación tenga paquetes de los 14 idiomas**.

## Estructura de un nodo de búsqueda (20 bytes, PE32)

| Desplazamiento | Significado respaldado |
|---:|---|
| `+0x00` | puntero al siguiente nodo |
| `+0x04` | puntero al objeto del paquete PK3 (para nodo de paquete) |
| `+0x08` | puntero a la información de directorio (para nodo suelto) |
| `+0x0C` | **indicador de contenido localizado**, antes llamado provisionalmente `class_flag` |
| `+0x10` | **índice de idioma** asociado al nodo |

**Correlación binaria:** el constructor de paquetes escribe `[esi+0x0C]` en **VA `0x00424D3C`**, y `[esi+0x10]` en `0x00424D3F`. La detección del prefijo `localized_` está en el tramo `0x00424BA1–0x00424BC7`; reconoce la condición localizada y consulta los 14 nombres mediante la tabla en `0x00564B08`. El constructor de directorios guarda los mismos campos en `0x00425081` y `0x00425084`. La ruta que compara un directorio existente con los nuevos flags e índices en `0x00424F25–0x00424F79` utiliza mensajes que distinguen explícitamente **localized / non-localized** y advierten si un directorio localizado cambia de idioma.

En la variante SP también se observan las constantes `localized_`, `sp_`, `mp_` y `zz_`. **No hay todavía una prueba completa de cómo se combinan estos prefijos al seleccionar cada paquete**, especialmente para MP/UO; las etiquetas de nombre generadas por la herramienta son *candidatas*, no montajes afirmados.

## Efecto en la prioridad de carga

La función ya modelada en `SearchpathOrder` (**VA `0x004248B0`**) recibe el mismo campo `+0x0C`. Ahora hay evidencia independiente de que corresponde a localización:

- Nodo **no localizado** (`+0x0C=0`): se inserta en cabeza.
- Nodo **localizado** (`+0x0C!=0`): se inserta después de la cabeza y de sus sucesores inmediatos no localizados, según el algoritmo observado.

Esto diferencia a las fuentes localizadas de las generales, pero **no basta para reconstruir la prioridad final completa**: faltan todas las llamadas de inicialización, el selector de idioma activo, el orden de descubrimiento de PK3/directorios y el comportamiento de las búsquedas que filtran por idioma.

Por seguridad, **la VFS todavía no utiliza esta política como sustitución automática** de su priorización provisional: el código actual de montaje no representa todavía el contexto real de idioma y los prefijos SP/MP.

## Inventario verificado de Drive / main

Paquetes españoles instalados: `localized_spanish_pak0.pk3`, `localized_spanish_pak1.pk3`, `localized_spanish_pak2.pk3`, `localized_spanish_pak3.pk3`, `localized_spanish_pak4.pk3`, `localized_spanish_pak5.pk3` (**6**).

Paquetes generales observados: `pak0.pk3` a `pak6.pk3`, `pak8.pk3`, `pak9.pk3`, `paka.pk3`, `pakb.pk3` (**11**). No aparece `pak7.pk3` en el listado consultado. La ausencia de un paquete no demuestra que sea requerido.

Comprobación adicional del archivo local `localized_spanish_pak4.pk3`: contiene los menús `ui_mp/spanish/createserver.menu` y `ui_mp/spanish/joinserver.menu`. El segundo archivo `pakb.pk3` contiene una versión no localizada de `ui_mp/createserver.menu`. Esto **confirma la coexistencia de variantes de menú**, pero no prueba que el motor prefiera una sobre otra en toda situación; el directorio del recurso también interviene.

## Reproducción

```bash
python tools/searchpath_localization_probe.py originals/CoDSP.exe \
  --pk3-name localized_spanish_pak4.pk3 \
  --pk3-name pakb.pk3 \
  --json analysis/local/searchpath_localization.json

python -m unittest discover -s tests -p "test_*.py" -v
```

Requisitos: Python 3.11+; el parser PE interno no tiene dependencias externas. `CODRECOMP_ORIGINALS=originals` activa pruebas opcionales contra el ejecutable original; los originales nunca se incorporan al repositorio.

## Filtro por idioma activo confirmado en las búsquedas

En dos ramas de búsqueda real dentro de `CoDSP.exe` se repite el mismo control:

1. **VA `0x004226E7`**: consulta el indicador `[nodo+0x0C]`. Cuando es cero, no exige coincidencia de idioma. Si está localizado, carga el DWORD de `[(*0x014DBA84)+0x20]` y omite el nodo cuando es distinto de cero. De lo contrario, compara `[nodo+0x10]` con `[(*0x014BD624)+0x20]` y también omite los índices distintos. La rama que omite el nodo avanza al siguiente elemento.
2. **VA `0x00422848`**: reproduce el mismo control en otra ruta de acceso a archivos.

Ambas ventanas se validan ahora con hashes SHA-256 (`0x004226E7`, 41 bytes; `0x00422848`, 46 bytes). Las dos variables globales son punteros a estructuras con un valor en `+0x20`; **todavía no se conoce con seguridad su nombre, quién configura la primera bandera ni la política de fallbacks**.

Se añadió `SearchpathOrder::eligible(active_language_index, reject_localized)` como un **modelo separado** que conserva el orden existente y descarta fuentes localizadas que fallan ese filtro. Por ejemplo, cuando el idioma activo es `spanish=4`, puede conservar fuentes generales más fuentes con índice 4, omitiendo fuentes localizadas con índice 0 (inglés). Con la bandera de rechazo activa, omite todas las fuentes localizadas. Esto representa las condiciones binarias observadas; **no determina todavía la prioridad final entre PK3, directorios y distintos niveles de parches**.

La función no está integrada en `Vfs` porque falta la inicialización completa del orden y del estado del idioma. `tests/searchpath_locale_filter_smoke.cpp` comprueba el comportamiento mixto sin distribuir archivos propietarios.

## Pendientes concretos

1. Rastrear completamente las funciones de descubrimiento `0x004248F0` y `0x00424E10`, incluidas sus banderas de gamedir.
2. **Filtro de las dos rutas principales recuperado**. Determinar dónde se inicializan y actualizan los globals de idioma activo y rechazo de archivos localizados, y confirmar las demás rutas de búsqueda.
3. Recuperar precedencia exacta entre `sp_`, `mp_`, `zz_`, paquetes generales y directorios sueltos en el arranque SP.
4. Solo entonces conectar `SearchpathOrder` al VFS con tests de colisión, overlays y diferentes idiomas.
