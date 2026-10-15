# TECNO CK6n ARM64 — A/B/A/B de x87 normal f2d y descarte de geometry -O2 (2026-10-14)

**Veredicto:** mejora de rendimiento real y repetida en Camp Toccoa, aunque pequena respecto a la meta de 60 FPS. `--hot-x87-transform --x87-normal-f2d` es la variante de mejor resultado del ensayo. `-O2` en CoDSP p1 no produjo mejora y NO debe habilitarse. Esta evaluacion corresponde al telefono ARM64 fisico, **no WSA**.

## Entorno y comparabilidad

- Dispositivo: TECNO CK6n, Android 14 ARM64, escena 3D del spawn de Camp Toccoa a calidad **Equilibrado**, misma partida/autoguardado y vista estacionaria. No se altero la calidad, resolucion, HUD ni renderer GL4ES.
- Procedimiento: captura fresca de 55 segundos de juego por corrida; ultimas **40 ventanas** de ~1 s despues de estabilizar carga y CPU, mismo metodo en todos los ensayos. Rechazo de capturas de menu/carga y comprobacion de PID. El p10 es de **FPS promedio por ventana**, no percentil de frametimes individuales.
- APK A: copia exacta de la instalacion inicial, respaldada de forma privada. `libmain.so` SHA-256 `1c952f27d2b5d21dbc81e99a4bdd830caeba1eb0bd0a2ba10f3aee48578dc325`.
- APK B: `--hot-x87-transform --x87-normal-f2d`, respaldada como `.local/profiles/tecno_f2d_B_candidate.apk`. SHA-256 APK `efaa575fffb223d47cc824e56f9fe0219c076ff0d55d9a9ed5e2632fe3e7243e`; `libmain.so` SHA-256 `6729aef7de75203ab2970adc9654d6aaf7e1fdef1299ad75ca3f037bc4585fb2`.
- Temperatura orientativa: valor de `dumpsys battery temperature` dividido entre 10. No equivale a un perfil termico completo. Los NPC, frecuencias y condiciones termicas pueden variar.

| Corrida | Codigo | Ventanas | FPS mediana | FPS p10 ventanas | CPU ms/frame mediana | Swap ms | Temp inicial→final |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| A1 | A referencia x87 | 40 | **24,90** | 24,30 | 38,685 | 2,025 | 41→42 °C |
| B1 | B x87 + normal-f2d | 40 | **25,70** | 25,30 | 37,365 | 1,940 | 42→43 °C |
| A2 | A reinstalada | 40 | **25,00** | 24,40 | 38,455 | 2,080 | 43→43 °C |
| B2 | B reinstalada | 40 | **25,85** | 25,10 | 37,175 | 1,955 | 44→44 °C |

Media de dos referencias: **24,95 FPS**, **38,570 ms CPU/frame**. Media de dos B: **25,775 FPS**, **37,270 ms CPU/frame**. Ganancia media: **+0,825 FPS (+3,31 %)** y **1,300 ms menos CPU/frame (-3,37 %)**. Los p10 mejoraron de 24,35 a 25,20 FPS promedio por ventana. A1/A2 variaron solo 0,10 FPS, mientras B1/B2 coincidieron cerca de 25,8 FPS y fueron tomadas a mayor temperatura. Esto supera el ruido A observado en estas sesiones, sin asegurar igual beneficio en otras escenas/telefonos.

Los cinco experimentos previos de conversion, junto al smoke ARM64 con ~1,2 millones de representaciones binary80 y el microbenchmark, siguen documentados en [ARM64_X87_NORMAL_F2D_2026-10-14.md](ARM64_X87_NORMAL_F2D_2026-10-14.md). La equivalencia de ese smoke es con el runtime recompilado actual, **no** una certificacion de todos los estados Intel x86 originales.

## Ensayo C posterior — `-O2` geometria CoDSP p1

- Hipotesis: los cuerpos calientes `0x0041B8F0` y `0x004196F0` en `p1` podrian beneficiarse de `-O2` con `-ffp-contract=off`, manteniendo el resto `-O1`.
- Se introdujo temporalmente un flag optativo `--geometry-o2`; se verifico en el comando **real** de Clang que `-O2` seguia a `-O1` solo en `p1`. APK ARM64 compilada y firmada V2/V3; **231 pruebas Python (4 omitidas), 34/34 CTest** correctas.
- C1, 40 ventanas de gameplay: **25,90 FPS mediana, 19,90 FPS p10, 37,180 ms CPU/frame**, temperatura 44→45 °C. Comparado con B2 (**25,85 / 25,10 / 37,175**), no hay ganancia de FPS ni CPU y los FPS bajos observados son peores.
- La diferencia de p10 puede estar afectada por calor/NPC: no afirmar causalidad del compilador sin repeticion adicional. Sin beneficio mediano/C PU, la opcion no merece activarse. **Se revirtio el cambio al constructor y CMake**; el APK C se conserva de forma privada como `.local/profiles/tecno_live_20261014/geometry_O2_C_candidate.apk`.

## Estado final y seguridad

- El telefono quedo con la **APK B exacta** reinstalada mediante `adb install -r`; un `adb pull` posterior probo identidad tanto del **APK completo** como de `libmain.so` por SHA-256, sin depender de la mera respuesta `Success`.
- Autoguardado `autosave/training.svg`: hash inicial y final identicos, `efbc68e54fabc79946dfd3a9d188e5f6ba284b1aad99130bbe2726eb637f64f8`; no se borraron recursos, configuraciones ni partidas. B y A estan respaldadas privadamente.
- Registros y reportes por corrida bajo `.local/profiles/tecno_live_20261014/{A1,B1,A2,B2,C1}/`, excluidos de Git. No subir APK, save, binarios generados o datos comerciales.
- El codigo de `CODRECOMP_X87_NORMAL_F2D` continua optativo, OFF en compilaciones normales, activable junto a `--hot-x87-transform` para el perfil ARM64 evaluado. La mejora se confirma solo en el spawn, no en campana completa ni en una validacion x86 independiente.
- La meta **60 FPS sostenidos continua sin cumplirse**: B usa unos **37,27 ms CPU/frame** contra presupuesto total de ~**16,67 ms/frame**. No es correcto extrapolar un microbenchmark al FPS.
- Politica: resultado B exitoso y reproducido en TECNO para el spawn; **contador de fracasos validos permanece 0/5**. C fue un A/B exploratorio adicional sin un nuevo A/B/A, no se registra como intento valido fallido.

## Proximo objetivo con mas impacto potencial

No insistir en ANGLE/Zink, VBO ni cambiar `-O2` de otras particiones sin perfil nuevo. El perfil nativo muestra costes distribuidos en geometria `0x0041B8F0`, `0x004196F0`, estructuras `0x0047BD40` y familia de visibilidad `0x004Dxxxx`. Priorizar una **reduccion estructural del trabajo del recompilador** que pueda ahorrar varios ms/frame (incluida fusion segura de subbloques y registros virtuales), con oraculo independiente de flags, x87, RAM, PC y aliasing, revision del ARM64 generado y A/B/A/B/A en TECNO. Una unica rutina de ~1 ms no cierra la brecha de ~20,6 ms restante.
