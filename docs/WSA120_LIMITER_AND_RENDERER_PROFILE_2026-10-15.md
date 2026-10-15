# WSA 120 FPS: control reversible y perfil del renderer

Fecha: 2026-10-15. Continuación de [la línea base](WSA120_BASELINE_2026-10-15.md).
Código: control de límites `5132112`; bloqueo de precisión `5ebe4cd`.
**120 FPS reales no alcanzados.** Se implementó una configuración necesaria
para investigar el objetivo, sin afirmar que sea una optimización de CPU.

## Cambio implementado y pruebas

`files/profile/frame_limit` selecciona `original`, `60`, `120` o `unlimited`.
SDL_main lee una vez el archivo y coordina `com_maxfps` y el pacing del host.
Sin archivo conserva el launcher y los diagnósticos previos; entrada inválida
conserva 60. No se cambian relojes, precisión matemática ni ajustes gráficos.
Documentación de uso: [FRAME_PACING](FRAME_PACING.md).

Pruebas C: 120 Hz fraccional, cero/unlimited, stalls, relojes extremos y
configuración inválida/NUL; rojo previo y verde posterior. Ejecutable nativo
de esas pruebas aprobado en WSA. Revisión independiente corrigió el caso
de ausencia de archivo; segunda revisión sin hallazgos. APK completa enlazada,
firmada v2/v3, alineada e instalada conservando datos. Ningún fast path x87 o
CFG14 se habilitó. No se ha certificado todavía física/audio a >60 FPS reales.

## Comparación física con Alta

Misma APK x86_64, autoguardado, cámara sin entradas durante medición, GL4ES,
ventana/superficie nativa 1280×720, perfil Alta (texturas/LOD sin reducción,
luces, sombras, detalle y sol activados). Cada corrida contiene 45 ventanas
del motor y ~45 s de timestamps simultáneos SurfaceFlinger. No se compara
causalmente contra la referencia Equilibrado de otra APK.

| Corrida / límite | FPS motor mediana | CPU ms/frame mediana | Presentaciones/s | Presentación p95/p99 ms |
| --- | ---: | ---: | ---: | ---: |
| High_original_A1 | 52.20 | 19.01 | 51.06 | 31.75 / 35.28 |
| High_120_B1 | 53.80 | 18.60 | 52.07 | 31.58 / 40.00 |
| High_original_A2 | 54.10 | 18.06 | 52.82 | 31.21 / 32.94 |
| High_120_B2_retry | 55.10 | 18.15 | 53.14 | 31.33 / 33.31 |
| High_unlimited_C1 | 56.60 | 17.65 | 55.16 | 31.30 / 33.36 |
| High_60_A3 | 54.40 | 17.89 | 53.04 | 31.47 / 32.60 |

Todas las capturas aceptadas conservaron hashes de partidas y tuvieron
cobertura completa del buffer de presentación. La primera B2 se **rechazó**
por permanecer en briefing; no se le atribuyen FPS. Se corrigió la navegación
para esperar ventanas nuevas después de inicialización y briefing, no las
ventanas de carga acumuladas. A1 y A2 necesitaron intervención de navegación
antes de la captura. Estas incidencias limitan el protocolo y deben eliminarse
en ensayos prolongados; no ocurrieron durante las mediciones aceptadas.

La variación de controles original/60 va de 19,01 a 17,89 ms CPU/frame. Las
dos B están dentro de ese rango. La retirada del pacing produjo espera cero,
pero **no demuestra reducción causal del trabajo CPU**. El resultado C es una
única pasada posterior, susceptible a calentamiento de cachés, scheduler y
actividad del mapa. No declarar éxito ni sumar estas diferencias a futuras
ganancias. La comparación no controló frecuencias/térmica de Windows.

Las medianas de FPS/CPU siguen siendo estadísticas de ventanas; p95/p99 son
intervalos individuales de presentación. No son tiempo GPU ni prueba de
contenidos visuales únicos. El modo virtual 75 Hz fue constante: impide 120
presentaciones visibles/s bajo esta configuración, aunque se retiren topes.

## Perfil exacto y selección de cuello de botella

Perfil High A1 posterior a su benchmark, sin compilación simultánea:
**3.992 muestras**, ninguna perdida; Build ID del ELF verificado
`b53d4c7271a20e236af0f97ab5b07478684d4fe9`. Se comprobaron los hashes de
todas las fuentes generadas antes de resolver líneas; ELF sin strip preservado.
3.941 muestras pertenecen al hilo SDL del motor. `libmain.so`: **3.109/3.992**.

| Etiqueta DWARF elegida dentro de libmain | Muestras |
| --- | ---: |
| memcpy inline | 1.132 |
| f2d | 965 |
| d2f | 418 |
| Otras / rd / mask / popc / sx | 594 |

Son familias anotadas por el compilador, **no coste exclusivo de cada
microoperación ni recuentos de llamadas**. Dentro de copias libc resueltas,
81 muestras tuvieron `glUtilsPackPointerData` como primer caller fuera de libc.
No asumir que todas las copias del proceso sean gráficos.

El cuerpo Ghidra original `0x005061B0` reunió **717/3.992 muestras (~17,96 %)**:
transformación de posición y dirección en el renderer, 58 instrucciones x86.
Le siguen geometría `0x0041B8F0` (101), visibilidad `0x004D94C0` (72), geometría
`0x004196F0` (67), estado `0x0047BD40` (62), `0x0041CD60`/`0x004D8280` (61)
e índices `0x0042B0A0` (53). Etiquetas aproximadas, sin tiempos exclusivos.

## Bloqueo nuevo: fast path de transformaciones

Se ejecutaron las **58 instrucciones originales**, hasta su RET real en
`0x00506245`, mediante Unicorn x86 con CW `0x037f` y pila x87 vacía. PE 1.5
verificado por SHA-256; Capstone confirmó límites, ausencia de saltos/CALL y
RET. El helper público actual se compiló en DLL host con contracción FP OFF.

En **20/23 casos** difirió la salida float32 de posición frente al original;
GPR y PC coincidieron. Diez diferencias usan entradas entre 0 y 1, no solo
magnitudes extremas. Ejemplo matemático sintético de los términos de una fila:
`1 + 2^-24 + 2^-54`: x87 extended da al almacenar float32
**1,0000001192092896**, mientras el helper double da **1,0**. Otros diez
casos muestran cancelación `2^n + 1 - 2^n`, n=53..62: original 1, helper 0.

Esto prueba una incompatibilidad de precisión del helper; **no** prueba que
esos valores se hayan visto en el gameplay medido ni valida el traductor
genérico, que también usa double. No se verificó aquí todo R/RAM, FPU ni
fallos. La igualdad anterior contra p-code no era equivalencia independiente.

`--hot-x87-transform` y `CODRECOMP_HOT_X87_FASTPATH=ON` ahora rechazan con
`ORIGINAL_X87_PRECISION_UNSAFE`. El helper queda como evidencia histórica y
tests, sin integración nueva. CLI probado en ambas ABI; configuración NDK
real ON rechazada por ese motivo y OFF aprobada. CFG14 mantiene su bloqueo.

## Siguiente optimización

Investigar una ruta **binary80 nativa o exacta** para el trabajo transversal
de conversión/materialización y el cuerpo del renderer que domina el perfil.
Primero comprobar formato/precisión del compilador x86_64 y contratos CW/SW,
TOP/tag, alias y fallos; no reutilizar la matemática double del helper bloqueado.
La consulta real al NDK r30 (`--target=x86_64-linux-android26 -dM -E`)
confirmó `__LDBL_MANT_DIG__=113`, `__SIZEOF_LONG_DOUBLE__=16`: **long double
es binary128, no binary80**. No basta sustituir el tipo C; la próxima prueba
debe usar formato binary80 explícito y redondeo/estado x87 comprobables.
Una sola función de ~18 % tampoco basta por sí sola para llegar a 8,33 ms.
Solo integrar con oráculo original, pruebas de estado y A/B/A/B completo.
Tiempo GPU, escenas complejas y estabilidad prolongada siguen pendientes.

Datos crudos y scripts de conducción permanecen privados bajo
`.local/profiles/wsa120_20261015/`; no se publican PE, APK, p-code ni trazas.

## Verificación final del bloque

### Continuación: prototipo x87 nativo aislado

Se compiló y ejecutó la secuencia aritmética original, con el mismo orden de
operandos, usando instrucciones x87 explícitas y punteros host. No usa
`long double` ni el helper double bloqueado. Corpus: 23 casos de cancelación/
midpoint anteriores y 100 casos finitos pseudoaleatorios (semilla 5061,
exponentes -60..60), repetidos en las 12 combinaciones de precisión x87
24/53/64 bits y los cuatro modos de redondeo: **1.476 casos**.

- Windows nativo frente al original x86 en Unicorn: **0 diferencias de
  salida** en los seis float32 de cada caso. Esto cubre aritmética en memoria
  válida con pila inicial vacía; no equivale a equivalencia arquitectónica.
- **1.412 diferencias de status word**: Unicorn devolvió cero; el host dio
  `0x0020` (1.114 casos) o `0x0220` (298). Los bits de precisión/redondeo
  impiden usar ese oráculo por sí solo para validar el estado FPU completo.
- El mismo prototipo compilado con NDK r30 y ejecutado en el dispositivo
  verificado `windows_x86_64`: **0 diferencias de salida y status word frente
  al host Windows** en los 1.476 casos.
- Cada caso WSA dejó dos valores centinela en la pila x87 y CW no predeterminado
  antes del helper. FXSAVE/FXRSTOR: **0 fallos de restauración** en los primeros
  32 bytes del entorno (incluido MXCSR) y los 10 bytes de cada registro x87.
  No se compararon los registros XMM ni se probaron señales/context switches.

Los resultados prueban viabilidad aritmética, no una mejora de FPS. El prototipo
es privado y aislado: no cambió la APK, las partidas ni el runtime. No cubre
NaN/Inf, entradas subnormales dirigidas, pila inicial llena, alias, accesos
inválidos, excepciones sin máscara o metadatos guest FIP/FDP. Restaurar la FPU
host tampoco implementa el estado x87 virtual del invitado. Antes de integrar,
resolver ese contrato y su materialización binary80, además del coste real de
guardar/restaurar el entorno. Los bloqueos existentes permanecen activos.

Evidencia privada: `native_x87_probe_v3/summary.json`, `android_result.json`
y scripts `probe_native_x87.py` / `run_android_x87_probe.py`, bajo la carpeta
local de esta sesión. No se publican instrucciones originales ni binarios.

**Componente desarrollado después:** [binary80 nativo y contrato pendiente](superpowers/plans/2026-10-15-wsa-native-binary80.md).
Cuatro operaciones con estado de operación explícito, aisladas del runtime
guest; pruebas host/WSA O0/O2/O3 aprobadas. El ensayo privado alternado de la
transformación dio 435,083 ns generados y 135,617 ns nativos aislados de mediana.
No incluye exportación de estado guest en la candidata y solo usa un input
finito: no convertir esta relación en FPS ni considerarla una optimización
integrada. Los ~18 ms/frame medidos en juego siguen siendo la referencia.

Host: **386 tests Python, 4 omitidos, 35/35 CTest**. La CI detectó después
un selector antiguo ligado al texto de un comentario CMake; se reprodujo y
se cambió por límites de opciones, conservando todas sus aserciones.
Código final `234065c`: [CI 38732364851 aprobado](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38732364851).
El capturador previo también tuvo CI aprobada. Límite normal restaurado,
override privado retirado y hashes finales de partidas sin cambios.
