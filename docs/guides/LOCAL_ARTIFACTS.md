# Organización privada y reutilización de scripts (ChatGPT + RigorCore Dev MCP)

**Vigente desde 2026-10-15.** Obligatorio para cualquier agente que use el plugin RigorCore Dev, otros MCP o scripts locales de CallofRecomp. Objetivos independientes: **120 FPS WSA** y **60 FPS TECNO ARM64, vigente aunque el dispositivo esté temporalmente ausente**.

## Antes de escribir o ejecutar

1. Leer `AGENTS.md`, `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md` y `docs/OPTIMIZATION_LEDGER.md`. **Comprobar el estado Git y tareas en curso**, pues otras IAs pueden trabajar a la vez.
2. Antes de crear un script, buscar la operación por concepto, no solo por nombre:
   - `python tools/local_workspace.py find capture --kind script --limit 12`
   - `python tools/local_workspace.py find x87 --kind script --limit 20`
   - `python tools/local_workspace.py find "frame stats" --kind script --limit 12`
   - Actualizar el índice si aparecen scripts nuevos: `python tools/local_workspace.py refresh`.
3. Preferir **herramientas versionadas y probadas** en `tools/`, `tools/recomp/` y `tools/recomp/diagnostics/` sobre experimentos sueltos de `.local/profiles/`. Revisar parámetros, plataforma, equivalencia y fecha. No ejecutar como "actual" un script de fase antigua sin cotejar su ELF/flags.
4. Si algo existe pero necesita una variación, **añadir un argumento/configuración y pruebas a la herramienta canónica** cuando sea seguro. Evitar `script_v2.py`, `script_final.py` y múltiples copias con rutas A/B escritas dentro. No reescribir el script histórico para reutilizarlo.
5. No suponer que los scripts parecidos son intercambiables: una semilla, A/B, checkpoint, CW, Build ID, ABI o región x86 diferentes **pueden ser esenciales**. Nada de deduplicación automática por nombre o parecido textual.

## Dónde escribir a partir de ahora

Crear **una sesión por hipótesis/ejecución**:

`python tools/local_workspace.py new-run --target wsa --slug gl-buffer-reuse --agent chatgpt-mcp`

La herramienta devuelve una ruta única, por ejemplo:

`.local/profiles/runs/wsa/2026-10-15/gl-buffer-reuse/20261015T180000Z-1234-00/`

A partir de esa ruta **todos** los archivos de la sesión van dentro de estas subcarpetas:

| Subcarpeta | Guardar aquí |
| --- | --- |
| `captures/` | PNG/JPG originales, capturas WSA/TECNO/Windows y comparaciones visuales |
| `logs/` | `adb logcat`, compilación, ejecución, simpleperf textual, errores |
| `metrics/` | Estadísticas FPS/CPU/GPU, A/B/A/B, JSON/CSV, timestamps |
| `scripts/` | Solo scripts experimentales **específicos** de esa sesión; no clones de helpers existentes |
| `builds/` | APK/ELF/objetos de comparación privados identificados por hash; builds activas compartidas continúan en `.local/builds/` |
| `reports/` | Hipótesis, método, resultados, límites, `SHA256`, decisiones y pasos siguientes |
| `raw/` | Perfdata, dumps y trazas binarias sin procesar |
| `session.json` | Metadatos creados automáticamente: plataforma, estudio, agente, hora y commit al empezar |

**Capturas:** para obtener una imagen que **persista en disco**, usar el capturador reutilizable (o un script equivalente que tome `--run`):

`python tools/local_capture.py android --run RUTA_DE_SESION --serial SERIAL_ADB --name training-a1`

`python tools/local_capture.py windows --run RUTA_DE_SESION --name scene-reference`

`--serial` se obtiene de `adb devices` o del MCP **en esa sesión**; nunca reutilizar uno antiguo sin verificar. Una captura devuelta visualmente por `android_screenshot` o `take_screenshot` mediante el MCP **no demuestra que exista un PNG guardado**. Si debe conservarse, crear la sesión y escribir el archivo con un método que confirme ruta y bytes. No volcar PNG/base64 ni decenas de capturas repetidas en el chat.

## Trabajo simultáneo: contrato de no interferencia

- **No mover, renombrar, sobrescribir, limpiar, deduplicar ni borrar** directorios de estudios que otro agente pueda estar utilizando. Las rutas antiguas en la raíz de `.local/profiles/` quedan como **legado en su sitio** hasta que el trabajo esté cerrado y las referencias verificadas. No asumir que una fecha vieja vuelve obsoleto un perfil TECNO.
- Crear sesiones **únicas** (`new-run`, creación exclusiva, sin sobreescritura). Si un agente vuelve a trabajar sobre una evidencia anterior, enlazar su ruta/ID en el nuevo `reports/`, no modificar los raw anteriores.
- No ejecutar `git add -A`, `git reset --hard`, `git clean`, cambios de rama, reinstalación APK ni cierres de procesos si otra IA trabaja; hacer staging por archivos propios y comprobar el estado justo antes del commit. **No apropiarse de cambios ajenos**.
- Antes de mover un artefacto legado: verificar referencias en scripts/documentos, recencia, tamaño/hash, destinatario libre y posibilidad de restauración. Documentar `old → new` en un manifiesto privado. Si hay riesgo o sesión activa, **catalogar y no mover**.
- No volver a compilar ni repetir A/B si el objetivo era solo catalogar documentación. Para FPS físicos conservar perfil gráfico, escena, ABI y Build ID; no inferir resultados TECNO de capturas WSA.

## Investigación anterior y directorios protegidos

- `.local/profiles/wsa120_20261015/`: estudio WSA **vigente para reproducción**; no reorganizar sus rutas internas mientras existan scripts/reportes que las referencien.
- `.local/profiles/tecno_live_20261014/` y `tecno_phase8_20261014/`: evidencia ARM64 **válida históricamente**, no medición de la build acumulativa más nueva.
- `.local/profiles/history/`: archivos legados que ya pasaron controles de referencias/hashes, con manifiesto en `.local/catalog/`.
- `.local/catalog/profiles_index.json`: índice **privado, de metadatos**; `find` lo consulta sin abrir el contenido de miles de binarios.
- `.local/catalog/script_similarity_2026-10-15.json`: auditoría AST y similitud de scripts; **candidatos** a consolidación, no autorización para borrarlos.
- `.local/private`, `.local/builds`, `recomp_out`, `build-*` y junctions: fuentes privadas, cachés, APK y artefactos activos; excluir de búsquedas generales.

## Promoción de un script a herramienta común

Solo si el comportamiento está bien definido, probarlo con entradas sintéticas **y** hay suficiente repetición: crear/modificar una herramienta pública bajo `tools/` y pruebas en `tests/`. Enlazar desde este documento y el registro; dejar los scripts originales como **historia reproducible**, sin sustituirlos sin consentimiento. Ejemplo: `tools/local_capture.py` centraliza guardado de capturas con `--serial` y `--run`, mientras antiguos scripts TECNO que imprimen base64 quedan como antecedentes y no como receta nueva.

**Señal de final de sesión:** registrar en `reports/` el propósito, fuentes, IDs, comando ejecutado, resultado de pruebas, archivos generados y qué quedó pendiente. Evitar declarar que una captura/medición existe si no se verificó el archivo.

## Segunda tanda verificada — 2026-10-15

Se archivaron **100 scripts Python más** (64 CFG14 y 36 fases CPU), sumando **200 scripts históricos** y dejando **353 sueltos**. La primera tanda y la segunda tienen manifiestos SHA256 independientes; no se borran ni se sobrescriben.

El preflight nuevo, `tools/audit_private_script_refs.py`, revisa referencias desde herramientas, documentos, perfiles activos y los 100 scripts ya archivados. En esta tanda examinó **453 scripts y 1.560 fuentes**, identificando **145 candidatos** antes de elegir 100; excluye referencias textuales, imports locales, rutas relativas a `__file__`, sintaxis inválida y archivos recientes. Omite catálogos JSON al computar consumidores para evitar falsos positivos.

```powershell
python tools/audit_private_script_refs.py --batch-id 2 --write
python tools/organize_legacy_scripts.py --batch-id 2 --batch-size 100
# Este paso ya fue ejecutado. NO repetirlo si existe el manifiesto:
python tools/organize_legacy_scripts.py --batch-id 2 --batch-size 100 --apply
python tools/local_workspace.py refresh
python tools/verify_local_artifacts.py --save
# Para restaurar únicamente el segundo lote:
python tools/organize_legacy_scripts.py --batch-id 2 --restore
```

Manifiestos privados: `.local/catalog/archived_legacy_scripts_2026-10-15.json` (tanda 1) y `.local/catalog/archived_legacy_scripts_2026-10-15_batch02.json` (tanda 2). El verificador revisa ambos y sus **200 SHA256**. Para otra tanda, elegir otro ID y generar un nuevo preflight. Un análisis estático no garantiza descubrir rutas dinámicas.

## Primera tanda verificada (2026-10-15)

**Resultado real y reversible:** se archivaron **100 scripts Python antiguos** de la raíz de perfiles sin ejecutar ninguno. Procedimiento: preflight de 580 scripts privados → análisis de dependencias en docs/tools/tests/perfiles y carpetas anidadas → exclusión de `__file__` e importaciones locales → lote con SHA256 y sin escritura reciente → movimiento con manifiesto → verificador completo. Quedaron **453 scripts Python sueltos** en vez de 553; el historial se organiza así:

| Ruta privada | Historial |
| --- | --- |
| `.local/profiles/history/scripts/cfg-phase14/` | 57 scripts de experimentos CFG14 |
| `.local/profiles/history/scripts/cpu-phases/` | 34 scripts de fases CPU anteriores |
| `.local/profiles/history/scripts/oneoff-edits/` | 7 parches puntuales históricos |
| `.local/profiles/history/scripts/tecno/` | 2 scripts de screenshots TECNO con serial fijo, reemplazados operativamente por `tools/local_capture.py` |

**Restauración:** `python tools/organize_legacy_scripts.py --restore` verifica hash y que el destino anterior esté libre antes de cada retorno. No ejecutar una segunda tanda usando el mismo manifiesto. El primer archivo está en `.local/catalog/archived_legacy_scripts_2026-10-15.json` (privado, no subido a Git).

**Verificación repetible desde la raíz del repositorio:**

```powershell
python tools/local_workspace.py refresh
python tools/verify_local_artifacts.py --save
python tools/refresh_doc_catalog.py --check-only
python -m unittest discover -s tests
ctest --test-dir build --output-on-failure
```

El verificador guarda `.local/catalog/verification_report.json` y controla tamaños/SHA archivados, índice, carpetas por sesión y privacidad de Git. Preflight inicial de **580 scripts**: **579 válidos**. La verificación extendida de carpetas WSA/TECNO y catálogo inspecciona **626 scripts: 625 AST válidos y uno histórico con sintaxis inválida**, `.local/profiles/phase14d_fix_cmake_winpaths.py`. Se conserva sin ejecutarlo ni alterarlo. Un error en un script viejo no implica que la APK o el motor fallen. **Suite comprobada:** 412 pruebas Python (6 omitidas) y 38/38 CTest tras corregir los imports de tres tests nuevos. La auditoría no se equipara a una compilación/medición nueva en un dispositivo.

**Límite:** un análisis estático no garantiza descubrir rutas construidas dinámicamente. No mover arbitrariamente los 353 scripts ahora restantes; tratar cada tanda como una operación reversible con evidencias.
