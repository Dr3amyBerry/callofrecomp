# WSA: estado x87 y oráculo nativo x86

Fecha: 2026-10-15. Continúa el [componente binary80](superpowers/plans/2026-10-15-wsa-native-binary80.md).
Código: `d68e164`; [CI 38737576358 aprobado](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38737576358).
**Fuera de la APK. No demuestra mejora de FPS.** El juego conserva su referencia
de ~18 ms CPU/frame; todavía no se alcanzan 120 FPS.

## Componente desarrollado

`tools/recomp/runtime/x87_native_state.h` representa el entorno FNSAVE/FRSTOR
de 108 bytes. Importa/exporta los campos Ghidra medidos: CW, SW, tag completo,
FOP, FDP, FIP y los ocho slots binary80. Conserva padding y registros ajenos.
Los selectores CS/DS deben suministrarse explícitamente: no se inventa una
correspondencia con R que no se haya demostrado. El adaptador no garantiza que
el lowering previo haya mantenido correctamente esos campos.

Una prueba nativa de ida/vuelta importa y exporta el entorno sin ejecutar
instrucciones guest. Mantiene el tag físico completo, los slots lógicos y TOP;
no convierte valores a double ni usa el tag abreviado de FXSAVE como estado
guest. Controles inválidos o con excepciones sin máscara se rechazan sin tocar
la salida. No se conectó a pcode2c, `recomp_rt.h`, builder ni al juego.

## Oráculo independiente de la FPU

La herramienta privada compiló un proceso Windows i686 y ejecutó en la CPU las
**58 instrucciones originales verificadas** de `0x005061B0` hasta RET. PE
verificado por SHA-256; Capstone confirmó límites y ausencia de saltos/CALL
internos. La memoria de código pasa de RW a RX antes de ejecutarse. No se
publican bytes propietarios, EXE, DLL ni perfiles.

Se comparó contra la misma secuencia x87 con punteros host en x86_64, importando
y exportando el entorno completo en una sola región asm. **1.596 casos**, 12
combinaciones de precisión/redondeo, TOP variable, flags previos y tags vacíos,
llenos o mixtos, incluidos desbordamientos de pila con excepciones enmascaradas.
Entradas finitas de cancelación/midpoint y aleatorias, además de casos dirigidos
NaN, sNaN, infinitos, ceros, subnormales y extremos float32.

| Comparación con original nativo x86 | RAM | CW | SW | Tags | Ocho slots binary80 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Windows x86_64 | 0 | 0 | 0 | 0 | 0 |
| NDK x86_64 ejecutado en WSA | 0 | 0 | 0 | 0 | 0 |

Las cifras son **casos con diferencias**, no FPS. Esto complementa Unicorn,
que en la prueba anterior no reflejó flags observados en CPU. **FIP, FDP, FOP
y selectores quedan excluidos** de esta comparación: las direcciones y las
codificaciones de operandos cambian en el host. Los buffers son válidos y
disjuntos; no valida alias, fallos de memoria ni excepciones sin máscara.

## Correcciones de aislamiento host

La revisión pidió formato explícito `FXSAVE64/FXRSTOR64` para conservar el
formato de punteros host de 64 bits. Se aplicó también al componente matemático
anterior y se amplió su captura de comprobación. Las pruebas incluyen punteros
centinela superiores a 4 GiB; no se afirma que todos los procesadores expongan
esos campos de la misma manera.

El nuevo test con una excepción host inválida pendiente y sin máscara reprodujo
una **excepción numérica** durante FRSTOR. Corregido guardando primero el host,
ejecutando **FNINIT no waiting** antes de importar el guest y restaurando el host
al terminar. El helper no debe disparar una excepción ajena al guest. Las pruebas
comprueban que los CW/SW pendientes originales siguen presentes al devolver.
Todo permanece en un único bloque asm para evitar intercalado del compilador.
También se rechaza CW con bit reservado 6 a cero.

## Coste y validación

Ensayo final WSA, sin CTest/compilación simultáneos: diez rondas alternadas de
300.000 transformaciones, un input finito fijo. Generado p-code O2: mediana
**441,349 ns**; región x87 con importación/exportación FPU e aislamiento host:
**210,508 ns** (~2,10× en este ensayo). No incluye empaquetar/desempaquetar R,
guardas de memoria ni recuperación de fallos. Frecuencias/térmica sin controlar.
No convertirlo en ahorro por frame ni extrapolarlo al resto del motor.

Test nuevo: fallo inicial por componente ausente, luego verde. Tags mixtos con
los ocho TOP, preservación de bytes ajenos, rechazo e importación/exportación
en el mismo buffer. Ambos componentes matemático/estado aprobados con avisos
estrictos en Windows y WSA, **O0/O2/O3 (12 ejecuciones)**. Regresión final:
**37/37 CTest**, 68,37 s. Revisión final sin hallazgos tras correcciones.

## Próxima integración

La continuación descrita abajo ya contrasta metadatos, alias y captura de
fallos para esta región. Falta conectar la región generada y su mapa de PC al
runtime real, materializar R desde la señal antes de reportar el fallo y probar
el retorno virtual por la pila, incluidos sus fallos. La reanudación de una
falta de página y las excepciones guest sin máscara no están certificadas.
Medir el coste completo de ese contrato. Una ruta que solo pase buffers válidos
no satisface la misión. Después se requiere APK y A/B/A/B con Alta y la misma
partida, además de las escenas exigentes y validación prolongada pendientes.
El bloqueo del helper double y el de CFG14 siguen vigentes.

Evidencia privada bajo `.local/profiles/wsa120_20261015/`:
`full_fpu_native_v2/{summary,wsa_summary}.json`, `full_fpu_cost_v2/summary.json`,
`native_{math_matrix_v2,state_matrix_v1}/summary.json` y
`native_state_all_ctest.log`. Scripts: `audit_native_full_fpu.py`,
`run_full_fpu_wsa.py`, `benchmark_full_fpu.py`, `run_state_validation.py`.

## Continuación: metadatos, alias y fallos reales

Código `b0256db`; [CI 38741645925 aprobado](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38741645925).

Se añadieron dos operaciones al adaptador público, todavía fuera del juego:

- `x87_native_state_set_memory_metadata`: PC, dirección efectiva, opcode de
  11 bits y selectores guest explícitos para instrucciones x87 de memoria
  que actualizan esos campos. Solo después de completar la instrucción;
  no sirve para FLDCW/FNSTCW/FRSTOR ni operaciones exclusivamente de registro.
  Opcode fuera de rango: rechazo sin cambios. Conserva el resto del estado.
- `x87_native_state_read_fxsave64_arithmetic`: lee CW/SW y los ocho slots de
  un FXSAVE64/contexto de señal válido; reconstruye el tag físico completo
  desde TOP, FTW abreviado y bits binary80. Conserva metadatos para que el
  llamador los reubique por separado. Prueba independiente contra FNSAVE:
  ocho TOP × tres patrones con ceros, normales, subnormales, pseudo-denormales,
  unnormals, Inf, NaN y slots vacíos. Se conserva también el dato residual vacío.

**Alias/metadatos:** 1.596 vectores × 14 distribuciones = **22.344 casos**,
con solapamientos de matriz/posición/dirección/salidas, salidas entre sí y
punteros sin alineación. Se comparó toda la RAM de 128 bytes del caso, CW/SW,
tags, ocho slots y FIP/FDP/FOP/CS/DS: **cero diferencias**, tanto Windows x64
como WSA frente al original nativo i686. El original verificó sus metadatos
host observados antes de reubicarlos; el candidato usa el helper público.
Selectores guest suministrados explícitamente; bytes reservados excluidos.

**Faltas reales de página:** se ejecutó un prefijo válido y se protegió la
página justo antes de cada una de las **45 instrucciones x87 con memoria**,
usando single-step. 12 controles de precisión/redondeo: **540 pares** de
capturas Windows x86/WSA. Se verificó por separado que los **1.080 registros**
capturados señalan exactamente la instrucción elegida. PC de fallo, RAM,
metadatos y estado FPU: **cero diferencias**. WSA usa el decodificador público
de FXSAVE64, no una copia distinta del algoritmo.

Windows entrega su CONTEXT al handler de acceso inválido; WSA entrega el
ucontext de SIGSEGV. Los procesos de prueba guardan la captura y terminan;
**no reanudan el acceso fallido**. Esta prueba usa operandos en páginas
disjuntas, sin accesos partidos entre páginas y con excepciones enmascaradas;
no cubre el RET ni demuestra aún la recuperación dentro del runtime del juego.
No se instaló APK nueva ni se tocaron partidas o ajustes gráficos.

Rojo previo a cada API ausente y verde posterior. Matriz final de estado y
metadatos Windows/WSA O0/O2/O3: **6/6 ejecuciones** con avisos estrictos.
Revisión pública sin hallazgos bloqueantes; mejorada la prueba para cambiar
ambos selectores en vez de escribir los valores que ya tenía el estado.
La revisión no auditó los scripts propietarios privados.
Regresión final tras ambas APIs: **37/37 CTest**, 68,05 s.

Evidencia adicional privada: `alias_metadata_v1/summary.json`,
`page_fault_native_v3/summary.json` (originales y validación de objetivo),
`page_fault_native_v4/summary.json` (WSA con decodificador público),
`native_metadata_matrix_v2/summary.json`. Scripts:
`audit_alias_metadata.py`, `audit_real_page_faults.py`, `verify_fault_targets.py`.
