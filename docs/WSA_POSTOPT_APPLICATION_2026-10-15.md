# Aplicación del perfil de la APK optimizada — 2026-10-15

Continúa la [auditoría post-acumulativa](WSA120_OPTIMIZED_APK_CPU_PROFILE_2026-10-15.md)
de `93d8d85`. Se conserva el conjunto de optimizaciones anterior; no se
reactivan CFG14 ni el transform antiguo basado en double.

## P1: eliminar indirecciones del estado guest

El ensamblador exacto del punto muestreado `0x1bbabd8` muestra escrituras MOV
de 32 bits, con cargas repetidas de la dirección de R mediante GOT. Por tanto,
no se reemplazó `memcpy` a ciegas ni se atribuyeron milisegundos a su etiqueta.

Se añadió `--local-guest-state`, opt-in x86_64, y `android/guest_state.map`.
El enlazador hace locales únicamente **R, MEM, U y PC** dentro de libmain.
Conserva los demás símbolos públicos, incluidos JNI y SDL. Las cargas GOT
observadas pasan a LEA de dirección local. No se retiene estado guest oculto
en registros ni se difieren escrituras; no cambia la aritmética, la precisión
x87, la secuencia de accesos guest ni sus puntos de fallo.

Verificación de los ELF reales: se retiran exactamente esos cuatro objetos
de la tabla dinámica; los otros **545 símbolos definidos** conservan nombre,
tipo y binding. Las **28 fuentes generadas** mantienen sus SHA256 originales.
CMake mantiene OFF por defecto el cambio y solo afecta a libmain Android.
No se promete compatibilidad con extensiones externas que interpusieran ese
estado interno; no se encontró tal consumidor en el proyecto.

Reproducción: `build_android.py --abi x86_64 --wsa-cumulative
--native-x87-region RUTA_PE --local-guest-state`, con SDK/NDK/Java locales.

## A/B/A/B físico, siempre con el conjunto acumulativo activo

**A ya incluye x87 nativo y todas las opciones acumulativas previas.** B añade
únicamente el enlace local. Ambas variantes exigen el marcador de ejecución
x87 antes de capturar. Alta, superficie 1280×720, mismo entrenamiento/guardado,
límite120, 45 segundos por corrida, sin compilar ni ejecutar suites en paralelo.

| Corrida | FPS mediana de ventanas | CPU ms/frame mediana | Presentados/s | Presentación p99 ms |
| --- | ---: | ---: | ---: | ---: |
| A1 acumulativa anterior | 66,8 | 14,965 | 63,11 | 32,64 |
| B1 + enlace local | 68,3 | 14,640 | 65,74 | 30,77 |
| A2 acumulativa anterior | 64,7 | 15,460 | 61,24 | 40,00 |
| B2 + enlace local | 68,0 | 14,710 | 65,53 | 26,67 |

Promedio de las medianas: **65,75 → 68,15 FPS (+3,65 %)** y
**15,2125 → 14,675 ms CPU/frame (−3,53 %)**. La mejora es pequeña y se repite
en ambas parejas; las referencias varían. No garantiza ese porcentaje en otras
escenas ni mínimos de 60 FPS. Las cuatro capturas tienen cobertura completa.
Intervalos >100 ms: 1/0/1/0; >50 ms: 2/1/5/0.

**Decisión:** conservar la opción y dejar en WSA la APK normal B, sin contadores
gráficos. Sigue siendo experimental; no alcanza 120 FPS y no mide TECNO.

SHA256 APK A: `a19ea65e30024f7f1f6f55d2be97ba99c854fd1e32e6c151bed6213194da1702`.
SHA256 APK B: `7a86e0776b2ef6abeef355e81c1cb4ba300affb6ebb88513b1b3362704329558`.
Evidencia privada: `.local/profiles/wsa120_20261015/local_guest_state/`,
`LocalStateA1/B1/A2/B2` y `local_state_ab_summary.json`.

## P2: medición gráfica sobre la candidata, sin cachés especulativas

Se compiló otra APK con `--gl-profile --gl-time-profile`, se ejecutó el mismo
guardado y después se restauró la APK normal B y la ausencia original de
`gl_stats`/`gl_time`. No se comparan sus FPS instrumentados con los normales.
El nuevo `diagnostics/analyze_gl_workload.py` agrega ventanas ponderando por
frames, rechaza registros incompletos/negativos y separa contadores de CPU.

Las últimas seis ventanas estables abarcan **1.624 frames**, con estos valores
por frame, visibles en `local_guest_state/gl_summary.json`:

| Contador guest o categoría CPU | Medición |
| --- | ---: |
| DrawElements + DrawRangeElements | 103,44 llamadas |
| Índices solicitados, sumados entre draws | 153.365,49 |
| LockArrays / UnlockArrays | 31,44 / 31,44 |
| Categoría de declaraciones de arrays | 375,32 llamadas; 0,097 ms CPU |
| Draw, dentro de GL4ES/driver llamado por el puente | 3,574 ms CPU del hilo |
| Categoría de estados | 0,124 ms CPU |
| Categoría de texturas/binding | 0,052 ms CPU |
| BindBuffer y payload BufferData/SubData guest | 0 eventos; 0 bytes |
| Subidas de texturas en estas ventanas | 0 |

Los ceros se refieren a las ventanas medidas, no certifican ausencia de VBO
internos del driver/GL4ES ni que todo dato sea reutilizable. Los índices no
son geometría única ni bytes transferidos. El tiempo incluye instrumentación,
es CPU del hilo llamador y **no tiempo GPU**. No se suman etiquetas del perfil
como si fueran costes exclusivos.

El coste CPU observado se concentra en Draw; falta aislar cuánto corresponde
a preparación/transmisión. Esto justifica estudiar el reempaquetado en el intervalo
Lock/Unlock: antes de una caché/VBO hay que demostrar qué spans permanecen
inalterados y cómo se invalidan. No se cambió la geometría ni se habilitaron
los modos GL4ES que habían regresado.

## P3: precisión de la atribución de la frontera x87

La etiqueta `nx87_5061b0_56` también abarca FNSAVE, FXRSTOR64 y el postámbulo,
no solo el último FSTP. En el perfil archivado, entre los PC más muestreados
están FXRSTOR64 (166 muestras) y la escritura que limpia el contexto activo
después de restaurarlo (239). Son posiciones estadísticas y posibles efectos
de ejecución/pipeline, no costes exclusivos atribuibles a cada instrucción.
No se elimina el guardado/restaurado para aparentar un ahorro: debe conservar
el estado host y los metadatos de 64 bits, además del estado guest completo.

## Estado de entrega

Guardados protegidos verificados de nuevo sin cambios. Revisión independiente
del enlace sin bloqueos de corrección/ABI. La APK normal B, con el conjunto
acumulativo y enlace local, queda instalada; los diagnósticos no quedan activos.
Continúan pendientes combate/estabilidad prolongada, recuperación SEH y modo
de pantalla ≥120 Hz. Las conversiones x87 genéricas mantienen las limitaciones
de precisión documentadas: este cambio no las disfraza ni las empeora.
