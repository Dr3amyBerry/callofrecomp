# Fase 4 — eliminación de escrituras arquitectónicas muertas (TECNO CK6n, 2026-10-14)

**Objetivo:** reducir instrucciones ARM64 ejecutadas sin modificar geometría, soldados, efectos, texturas, HUD, resoluciones, visibilidad, colisiones, entradas o guardados. La meta oficial de 60 FPS sostenidos en Camp Toccoa sigue pendiente.

## Hallazgo en código x86 recompilado

El intento anterior de cachear registros dentro de una instrucción x86 no mostró ganancia de FPS. El nuevo análisis **cruza múltiples instrucciones originales** y determina si una escritura a un registro arquitectónico completo es sobrescrita en todas las rutas antes de una lectura o una salida del código recompilado.

- Archivo nuevo: `tools/recomp/register_liveness.py`. Usa conjuntos de bits por byte de registro y un análisis retrospectivo de vida de registros sobre el CFG de cada chunk, incluyendo saltos relativos/directos, caídas a la siguiente instrucción, saltos de entrada, ciclos y rutas de salida al despachador.
- Las salidas de función/chunk y saltos indirectos observan todos los bytes arquitectónicos relevantes. `CALLOTHER` y opcodes desconocidos actúan como barreras de lectura completa. Solo se eliminan operaciones puras de `flag_liveness.PURE`, sin operandos de memoria invitada y con todos los bytes escritos demostrablemente muertos. Las escrituras solapadas y los registros de 80 bits se tratan byte por byte.
- Integración optativa: `tools/recomp/pcode2c.py --prune-hot-register-writes`, **OFF por defecto**. Limitada a CoDSP 1.5, hash SHA-256 del p-code original `36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e`, `separate_spaces` y temporales locales obligatorios.
- Primera región intervenida: cuerpo geométrico original `0x004196F0`, intervalos `[0x004196F0,0x00419779)` y `[0x00419780,0x00419ED6)`, dentro del C generado privado `p0`. **No se modifica `p1` ni `p8`**, que ya contienen parches independientes de x87/FCOM.
- Conteos de auditoría de cuerpos originales, previos al opt-in: **427 COPY potencialmente muertas** en `0x004196F0`, **301** en `0x0041B8F0` y **44** en `0x004D8280`. Solo el primero fue reemitido y compilado; no extrapolar beneficios a los otros dos.

## Verificaciones

- El generado privado experimental `p0` reemplaza **427 escrituras COPY** con sentencias vacías conservando los índices/labels; reduce **17.253 bytes** de C.
- APK A vs APK B: mismo NDK, opción `--hot-x87-transform --x87-normal-f2d`, mismo resto de código, distinta únicamente la unidad privada `p0`; firmas APK v2/v3 válidas.
- Sección `.text` nativa de `libmain.so`: **42.339.840 bytes** en A frente a **42.335.972** en B. Diferencia **−3.868 bytes**. No atribuir esa diferencia a FPS o a un número exacto de instrucciones ejecutadas: son bytes compilados, no perfil dinámico.
- **239 pruebas Python, 4 omitidas; 34/34 CTest** pasadas. Nueva batería `tests/test_register_liveness.py`: prueba CFG, superposiciones de registros, saltos, escrituras de flags y equivalencia de memoria/R/PC desde todos los puntos de entrada de una secuencia sintética, compilada `-O0/-O1/-O2`.
- Seis pares de instrucciones auténticas CoDSP, con ocho escrituras muertas en conjunto, se probaron en un oráculo diferencial ejecutado **en el TECNO ARM64**: 6.000 estados por nivel de compilación, **12.000 comprobaciones `-O1/-O2`**, R completo/PC/RAM idénticos al traductor original. Los archivos C generados son privados/ignorados y **no** constituyen por sí solos una certificación Intel x86 independiente ni prueban los 427 casos.

## Experimento físico controlado A/B/A

APK A reconstruida sin DCE y APK B con DCE solo en p0. La referencia anterior `.local/profiles/tecno_f2d_B_candidate.apk` (con mejora x87 validada) permanece respaldada. El script `.local/profiles/tecno_regcache_run.py` instala con `adb install -r` sin borrar datos, comprueba juego real con PID fijo, captura 55 segundos y usa las **últimas 40 ventanas estables** de ~1 s, en Camp Toccoa, cámara fija, calidad Equilibrado. El p10 es de promedios de ventanas (NO un 1%-low por frame). La temperatura indicada es la batería y no mide temperatura de núcleos individualmente.

| Variante | FPS mediana | FPS p10 ventana | CPU mediana ms/frame | Temperatura |
| --- | ---: | ---: | ---: | --- |
| A1, recompilación base | 25,75 | 19,10 | 37,380 | 45 °C |
| B1, eliminación arquitectónica | 25,70 | 24,40 | 37,475 | 45 °C |
| A2, recompilación base restaurada | 21,90 | 18,80 | 43,470 | 45 °C |

**Veredicto: NO hay aceleración de gameplay demostrada.** A1 y B1 fueron virtualmente iguales en FPS medianos (**−0,05 FPS**) y B consumió **+0,095 ms CPU/frame**. El control A2 sufrió una desaceleración muy grande pese a conservar 45 °C de batería; su valor no se puede usar como prueba causal de una mejora en B. La telemetría térmica Android notificó estado 0 (sin alerta); no se conoce la causa exacta de la variación, y no se inventa una explicación. La métrica p10 de B es mayor que la de A1, pero no se reproduce con una distribución de ventanas comparable en A2.

**Decisión:** dejar el pass OFF, conservar la referencia anterior validada en el TECNO y no atribuir mejoras al ahorro de bytes `.text`. A/B/A demuestra que el entorno se volvió menos estable, no una ganancia clara de la optimización.

Auditoría adicional: junto a las 427 `COPY` arquitectónicas muertas en `0x004196F0`, el análisis de dependencias detectó **77 `COPY` temporales adicionales** que quedarían huérfanas si se propagaran las eliminaciones. No se implementó ni midió esa segunda eliminación; Clang ya puede retirar muchos temporales. No se presenta como ahorro de FPS.

El archivo privado `p0` se restauró byte por byte; el objeto NDK p0 se invalidó y recompiló. **La `libmain.so` restaurada es idéntica a la referencia A** (SHA-256 `9e3a4ebbc2deb670d85a57d46430f0a4f313ded5a95a947f3c7dbc27106a380f`), y los archivos privados p1/p8 permanecen intactos.

## Trazabilidad privada y seguridad

- Referencia A: `.local/profiles/dead_arch_regs/rebuilt_A_reference.apk`, SHA-256 `9010dd0266af4af5e32f987bb849deca78fd19500b1a3c48cfac3681be56bd51`.
- Candidata B: `.local/profiles/dead_arch_regs/dead_writes_candidate_B.apk`, SHA-256 `08a82c2bf3696a193ac84f675265f1e49595a9fab4c6b3924a8237f0cf11b343`.
- Backup del `p0` generado original y hashes de `p1` y `p8` en `.local/profiles/dead_arch_regs/staged_manifest.json`.
- No subir APK, fuentes p-code/PE del juego, assets comerciales, archivos de guardado ni perfiles privados a GitHub.

## Cierre del ensayo e integridad

- APK A nueva: `RC_DCE_A1` y `RC_DCE_A2`, SHA-256 `9010dd0266af4af5e32f987bb849deca78fd19500b1a3c48cfac3681be56bd51`.
- APK B experimental: `RC_DCE_B1`, SHA-256 `08a82c2bf3696a193ac84f675265f1e49595a9fab4c6b3924a8237f0cf11b343`.
- Partida: `autosave/training.svg` sin cambios, SHA-256 `efbc68e54fabc79946dfd3a9d188e5f6ba284b1aad99130bbe2726eb637f64f8` en las tres corridas.
- Todas las métricas por ventana/escena están en `.local/profiles/tecno_live_20261014/RC_DCE_{A1,B1,A2}`, ignorado en Git.
- La APK anterior con x87 ya validada (`.local/profiles/tecno_f2d_B_candidate.apk`) **fue reinstalada con `adb install -r`**. Un `adb pull` posterior verificó el SHA-256 de la APK completa (`efaa575fffb223d47cc824e56f9fe0219c076ff0d55d9a9ed5e2632fe3e7243e`) y de `libmain.so` (`6729aef7de75203ab2970adc9654d6aaf7e1fdef1299ad75ca3f037bc4585fb2`); el autoguardado permaneció idéntico.
- **Resultado válido como ensayo exploratorio, no como mejora de FPS.** La estrategia de rendimiento general y la meta de 60 FPS permanecen pendientes.

## Siguiente etapa

Si el ensayo físico no mejora FPS/CPU, desactivar el pass, restaurar p0 nativo byte a byte y seguir con muestreo Simpleperf correlacionado a bloques ARM64 antes de tocar otras rutas. Si mejora, repetir para confirmar con otra medición y ampliar solo tras mantener equivalencia de registros, RAM, PC, EFLAGS y x87.
