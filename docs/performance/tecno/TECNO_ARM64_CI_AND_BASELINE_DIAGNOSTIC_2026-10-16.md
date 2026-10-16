# TECNO ARM64 — restauración de CI y evidencia del calentamiento anómalo (16-10-2026)

## Antecedentes verificados

- Los controles R3/R4 de la APK 0.2.4 fueron 21,70/21,65 FPS; el A/B/A/B FCHS registró una referencia repetida de 22,10 FPS. El programa de prueba reutilizable existe y no debe reemplazarse.
- Otros ensayos físicos registraron aproximadamente 17 FPS que posteriormente volvían a 22 FPS **sin cambiar la APK durante la sesión**. El experimento FLD32 del commit `e31ae56` se detuvo en A1 antes de obtener imagen y telemetría detallada.
- El ensayo FCHS y el FLD32 baseline recompilado tienen idéntico SHA-256 de `libmain.so`: `f81d228c73f4125e6d87a9f33d109a11f76e50a9054d20dba6cc1370a5956c8e`. No atribuir la anomalía a FLD32 ni a diferencias de firma de APK.

## Cambios de ingeniería

1. Los tests `test_arm64_x87_sign_bits.py` y `test_arm64_x87_fld32_normal.py` comprueban los orígenes comerciales **cuando están presentes en el puesto de desarrollo**; en un checkout público sin `recomp_out/codsp.pcode` o `codsp_recomp_p10.c` omiten **solo** las verificaciones que dependen de esas fuentes. Los tests con fixtures sintéticos, fallos esperados, ABI y transformaciones reversibles siguen ejecutándose en CI. Archivos incorrectos presentes fallan por su SHA; nunca incorporar binarios privados a Git.
2. `tools/recomp/diagnostics/android_abab.py` captura **una sola evidencia adicional únicamente cuando falla el calentamiento**: gate de 20 ventanas, los últimos 24 KiB del log posterior a `CL_InitCGame`, snapshot de batería/HAL/relojes y PNG más huella de la escena contra la referencia anclada. Se almacena dentro de la **sesión privada nueva** (`logs/A1-warmup-rejected.log`, `metrics/A1-warmup-rejected.json`, `captures/a1-warmup-rejected.png`). Fallos parciales de captura aparecen como campos `*_error`; no se consideran resultados válidos.
3. Se conserva el umbral externo de referencia 21,675 FPS (tolerancia 7 %, solo A), el control de estabilidad, la identidad y el hash de la APK, los guardados, la misma calidad y la restauración con Package Installer. El código experimental de FLD32 permanece **OFF** por defecto.

## Criterios para continuar

Primero: verificar GitHub Actions `tools-ci` en la revisión con estos cambios. Segundo: preparar **una sesión nueva** con los APK A/B FLD32 y la referencia privada existente, porque los planes anteriores fijan por SHA la versión antigua del corredor. Tercero: en el TECNO CK6n conectado, ejecutar `android_abab.py run` solamente con la APK 0.2.4 y los hashes de partida previos comprobados. Si A1 vuelve a ~17 FPS, detener antes de B, comparar la imagen y el entorno de la anomalía y diagnosticar la causa; no atribuir ningún FPS a FLD32. Si las cuatro pasadas son repetibles, contrastar FPS y CPU/frame, sin extrapolar el ahorro estático de tres instrucciones a 60 FPS.

**Límites:** las huellas visuales son gruesas y el HAL solo es una instantánea; ni una cámara parecida ni `thermal_status=0` demuestran carga 3D o frecuencia igual. El análisis offline FLD32 no certifica todo el modelo x87 original ni todas las escenas.

## Validación local tras el cambio

- `python -m unittest discover -s tests`: **535 pruebas ejecutadas, 6 omitidas, ninguna fallida**.
- `ctest --test-dir .local/builds/build --output-on-failure`: **40/40 CTest** aprobadas.
- `tests/test_android_abab.py`: **24/24**; el nuevo caso de rechazo registra evidencia, confirma cero instalaciones de B y restauración de la APK.
- Verificador privado: **200/200** scripts, **33/33** imágenes, **7/7** builds, cero rutas privadas rastreadas por Git.
- Catálogo de documentos: 134 documentos verificados, sin enlaces locales rotos. `git diff --check` correcto.

Estos resultados prueban el tooling, **no** la ganancia de FPS de FLD32. El workflow público debe confirmarse por separado después del push.

## Resultado físico adicional — sesión de diagnóstico 2026-10-16 UTC

- **Commit del tooling:** `517910ec4957ad7d2b8c1e31cd8cac04ca40112d`. GitHub Actions `tools-ci` [38846701351](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38846701351) aprobó el conjunto público, incluidos los CTest en Linux.
- **Sesión privada nueva:** `.local/profiles/runs/tecno/2026-10-16/arm64-fld32-warmup-diagnostic/20261016T033904Z-8868-00/`. Plan `reports/abab-plan.json`, originales comerciales fuera de Git, captura `captures/a1-warmup-rejected.png`, `metrics/A1-warmup-rejected.json` y `logs/A1-warmup-rejected.log`.
- **A1 detenida ANTES de B** al alcanzar 20 ventanas: **17,10 FPS**, **56,16 ms CPU/frame**, FPS p10 de ventanas **16,10**, desviación externa **−21,1073 %** frente a 21,675. La serie es temporalmente estable (deriva de extremos **−1,1628 %**, mitades **+1,1799 %**), pero corresponde a un estado de carga **no comparable**. No hay FPS medidos de la APK B.
- **Evidencia simultánea:** batería 35 °C/100 % USB, HAL CPU/GPU **51,3 °C**, skin **40 °C**, `thermal_status=0`, relojes observados de núcleos 6/7 a 2,0/1,9 GHz. Son instantáneas y no descartan cambio de planificación, contención, GPU ni el trabajo dinámico real del guion.
- **Imagen anclada:** huella de escena central aceptada con **0,3091 %** de diferencia; una comparación visual directa entre PNG privados muestra un mensaje temporal de HUD/objetivo en la referencia que no está presente en el rechazo. Esto **no demuestra** por sí solo que la cámara, IA o geometría difieran: no confundir una notificación con una causa de 13 ms CPU/frame.
- **Restauración:** `reports/abab-result.json` registra `status=failed`, `restored=true`, `completed_stages=[]`. Segunda verificación ADB confirmó APK instalada SHA-256 `fb8647c34dfe8fd269c0902f34edcc4c0844b18c6aa13ff6006232678da25f70`, partida SHA-256 `efbc68e54fabc79946dfd3a9d188e5f6ba284b1aad99130bbe2726eb637f64f8`. El repositorio sigue limpio, no cambió código del motor.

### Próximo experimento fundamentado

**No lanzar reiteradamente FLD32 contra una A1 inconsistente.** Prioridad: comparar la misma APK 0.2.4 en estados ~17 y ~22 FPS con controles de proceso/hilos, frecuencias temporales, ejecución del guion y perfil Simpleperf asociado al ELF exacto; separar tiempo de ejecución CPU de la espera/scheduler y usar capturas/estados de escena equivalentes. Solo entonces repetir A/B/A/B, exigir repetibilidad de A y conservar cualquier beneficio válido de FLD32 como opt-in hasta contar con evidencia. Mantener calidad Equilibrado y partidas iguales.
