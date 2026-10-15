# ARM64: candidatas y procedimiento A/B/A/B preparado

**Estado: preparacion offline comprobada; ninguna ejecucion nueva en telefono.** Las candidatas permanecen opt-in. No hay FPS nuevos, ADB, WSA ni capturas nuevas en este bloque. CI del bloque de shifts `1a231f7`: [38822856272 aprobado](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38822856272).

## Candidatas conservadas

| Cambio | Codigo | Evidencia y limite |
| --- | --- | --- |
| Safe ICF ARM64 y copias x87 | `89b4524` | [Informe](ARM64_SAFE_ICF_2026-10-15.md): -13.620 bytes de texto; oraculo AArch64 de 12.000 llamadas. A/B incorpora outlining en ambas; no confundir su efecto con ICF. |
| Cache de entrada de dispatch | `180c21a` | [Informe](ARM64_DISPATCH_ENTRY_CACHE_2026-10-15.md): menos instrucciones con localidad y mas con fallos. Tasa real de aciertos pendiente. |
| Shifts derechos estrechos | `1a231f7` | [Informe](ARM64_NARROW_RIGHT_SHIFT_2026-10-15.md): 8.192 casos por variante, cambios mixtos por chunk y texto neto -16 bytes. Sin ganancia de FPS demostrada. |

Cada informe conserva los SHA de sus APK/ELF, fuentes, comandos, ensamblador y reversion. Los APK permanecen privados; no se publican recursos del juego ni partidas. El [enlace local ARM64](ARM64_WSA_LOCAL_STATE_BINARY80_2026-10-15.md) sigue por separado como inconcluso, sin nueva medicion. No acumular porcentajes ni activar el transform double bloqueado.

## Procedimiento existente convertido en herramienta

`tools/recomp/diagnostics/android_abab.py` extrae la navegacion y los marcadores de los scripts privados `run_abab.py` y `measure.py` de `fixed-scene-x87-abab-retry/20261015T215445Z-17424-00`. Esos originales quedan intactos. Se reutilizan `stable_frame_gate.py`, `scene_fingerprint.py`, `android_perf_environment.py`, `analyze_frame_stats.py` y `local_capture.py`; no se crea otro analizador de FPS ni de imagenes.

Dos operaciones separadas:

```powershell
# Offline: no inicia procesos ni busca dispositivos.
python tools/recomp/diagnostics/android_abab.py prepare --run RUTA_SESION_TECNO --baseline A.apk --candidate B.apk --restore APK_INICIAL.apk --protected-files PARTIDAS.json --scene-reference ESCENA_CONOCIDA.png --serial SERIAL --reference-fps FPS_REFERENCIA

# Solo cuando vuelva el telefono y se autorice medir:
python tools/recomp/diagnostics/android_abab.py run --plan RUTA_SESION_TECNO/reports/abab-plan.json
```

Crear primero la sesion con `tools/local_workspace.py new-run --target tecno`. `prepare` comprueba ELF AArch64 y manifest identico entre A/B/restauracion, fija SHA de APK/escena/partidas y de las seis herramientas usadas. Cambiar un input o una herramienta exige preparar otra sesion. La APK de restauracion puede ser distinta de A; debe coincidir exactamente con la instalacion inicial de `org.callofrecomp`, comprobada antes de modificar el dispositivo. El manifest identico evita instalar otro paquete/version cuando esa identidad inicial se cumple. No certifica la matematica interna de APK arbitrarias: usar candidatas con su evidencia de correccion.

`run` exige TECNO CK6n ARM64 y usuario Android 0, serial explicito, bateria/temperatura legibles y condiciones razonables. Reutiliza las coordenadas del perfil de checkpoint, sin descubrimiento por fotos. Si cambia la interfaz o no aparecen los marcadores, aborta. Verifica SHA de partidas antes/despues de cada pasada; no escribe configuracion ni guardados.

Espera gameplay estable por logs y toma **una imagen privada por pasada** para compararla automaticamente con la referencia historica. No pide al agente que vea las cuatro imagenes. Captura 55 segundos de log nuevo, comprueba PID/continuidad y aplica las guardas de 40 ventanas y repetibilidad A/B/A/B. La referencia externa de FPS solo se aplica a A; no impone a B un techo arbitrario de FPS. Telemetria y captura de imagen quedan fuera de la ventana medida. Una comparacion central gruesa no acredita todos los objetos 3D, combate, partidas complejas o estabilidad prolongada.

## Recuperacion de instalaciones

Se sustituyo la instalacion opaca del script antiguo por sesiones con ID: transferencia temporal y SHA, `install-create -r`, `install-write`, `install-commit`. Se registra el ID antes de enviar contenido/commit. Ante timeout o interrupcion se recoge el cliente local, se solicita abandonar la sesion y se espera su registro **historico con estado final no nulo** antes de permitir otra instalacion. Una sesion activa, `mDestroyed` o su ausencia no bastan.

La comprobacion sigue el [dump de Package Installer de AOSP](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android13-release/services/core/java/com/android/server/pm/PackageInstallerService.java) y el [ciclo de finalizacion/abandono](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android13-release/services/core/java/com/android/server/pm/PackageInstallerSession.java). El selector limitado [dumpsys package installs](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android13-release/services/core/java/com/android/server/pm/DumpHelper.java) evita recopilar el inventario completo de aplicaciones.

Si no puede demostrar el estado terminal, registra `critical_restore_failure`, no inicia otra instalacion y no afirma haber restaurado. En el camino normal y en errores recuperables reinstala la APK inicial sin desinstalar/borrar datos y verifica SHA y partidas. Una terminacion forzada del proceso o una desconexion persistente pueden impedir el `finally`: los informes por ID permiten auditar lo pendiente, pero no equivalen a recuperacion automatica ya realizada. El formato real del firmware TECNO sigue pendiente de comprobacion; se rechaza si no se reconoce.

## Planes reales preparados, sin ejecutar

Todos usan la imagen **B1 de la 0.2.4 segura** del [corte fisico](TECNO_RELEASE024_ABAB_2026-10-15.md), 2400x1080, SHA `9f0cb014bab057ec17468c601c0b8131ddd43fe9e4bd067f4e16af3e9aafa929`. La referencia temporal es 21,675 FPS de [R3/R4](TECNO_STABILITY_GATE_2026-10-15.md). Es una precondicion historica que el futuro preflight puede rechazar, no evidencia de estado actual del telefono. La restauracion fijada es la APK publica segura `fb8647c34dfe8fd269c0902f34edcc4c0844b18c6aa13ff6006232678da25f70`.

Bajo `.local/profiles/runs/tecno/2026-10-15/`, cada ruta termina en `reports/abab-plan.json`:

- ICF: `prepared-safe-icf-abab/20261015T233641Z-18248-00/`.
- Dispatch: `prepared-dispatch-entry-abab/20261015T233641Z-18248-00/`.
- Shifts: `prepared-narrow-right-shift-abab/20261015T233641Z-18248-00/`.

Indice con SHA completos: `reusable-abab-procedure/20261015T232109Z-24664-00/reports/prepared-plan-index.json`. La preparacion y carga de esos tres planes se ejecutaron con `subprocess.run` y `Popen` bloqueados por dobles que fallarian si fueran llamados. No se ejecutaron las pasadas ni se contacto el dispositivo.

## Verificacion del bloque

23 pruebas offline cubren preparacion, ABI/manifests, hashes, conservacion de evidencia, orden, referencia A anomala, navegacion con una imagen, partidas, temperatura desconocida, restauracion inicial, fallo parcial, timeout remoto pendiente y rechazo de restauracion sin estado terminal. Una revision independiente detecto y verifico la correccion del antiguo riesgo de instalaciones concurrentes. Son pruebas con dobles, no validacion fisica del firmware.

Regresion: 517 pruebas Python aprobadas con cinco omitidas. Los 39 CTest restantes aprobaron a la primera; `static_analysis_python` detecto un import del test dependiente del directorio de trabajo. Se corrigio su ruta y la repeticion de ese CTest aprobo (35,99 s). Auditor privado sin errores; conserva el aviso de sintaxis historico de `phase14d_fix_cmake_winpaths.py`, que no se ejecuto. Ningun enlace local roto.

El resultado A/B/A/B conserva el veredicto del auditor: una senal pequena positiva se mantiene como no confirmada; no convierte dos pares en prueba estadistica ni en 60 FPS sostenidos. La siguiente medicion requiere estos mismos APK/ELF y calidad/escena/partidas equivalentes.
