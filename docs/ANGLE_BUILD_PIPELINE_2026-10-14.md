# ANGLE: compilación Linux reproducible y aislada (2026-10-14)

**Estado:** infraestructura de compilación preparada, NO resultado de compilación. Continúa el bloqueo de no tener un Linux local en el equipo Windows; aún no se ha generado ni instalado un APK ANGLE. No se ha medido el juego con ANGLE ni se ha modificado la APK estable.

## Propósito

Evitar instalar una distribución Linux o herramientas Chromium en Windows/WSA hasta tener evidencia. El script `tools/recomp/diagnostics/build_angle_android_linux.sh` obtiene **ANGLE upstream oficial** mediante gclient, lo fija exactamente a `43140711d13063716fd32a15de829885d0bce469`, sincroniza las dependencias Android de ese commit, compila `angle_apks` y genera un SHA-256 y un manifiesto de procedencia. Rechaza trabajar en una carpeta ajena o con otro commit. El target es **Android x86_64**, no ARM64.

## Ejecución

- Opción aislada con Linux propio (requiere espacio libre considerable y herramientas/dependencias apt):
  `ANGLE_INSTALL_BUILD_DEPS=1 bash tools/recomp/diagnostics/build_angle_android_linux.sh /ruta/temporal/angle-android-work`
- Opción GitHub Actions **manual**, sin ejecutar automáticamente con commits: pestaña Actions → *ANGLE Android x86_64 manual experiment* → *Run workflow*. El workflow solo se activa por `workflow_dispatch`, sin acceso a secretos ni paquetes del juego, con un timeout de 240 minutos y artefactos de 7 días. La capacidad de disco de los runners estándar y el tiempo de build no se han demostrado suficientes; podría fallar por recursos. No se ha activado este workflow.
- Salida esperada: `angle/out/Android/apks/AngleLibraries.apk` con `AngleLibraries.apk.sha256` y `ANGLE_PROVENANCE.txt`. No se descarga un APK aleatorio ni se trata un checksum autogenerado como firma del fabricante.

## Verificación independiente del artefacto

Descargar el artifact únicamente de la ejecución verificada y comparar el checksum contra `AngleLibraries.apk.sha256` y `ANGLE_PROVENANCE.txt`. Con las herramientas de Android SDK Build-Tools, ejecutar:

```text
python tools/recomp/diagnostics/verify_angle_apk.py RUTA/AngleLibraries.apk --aapt RUTA/aapt --apksigner RUTA/apksigner --expected-sha256 SHA256_DEL_ARTIFACTO --json-out .local/profiles/angle-research/angle-apk-verification.json
```

El comando es de **solo lectura**. Devuelve código 0 únicamente si encuentra `org.chromium.angle`, firma Android válida, librerías EGL/GLESv2 x86_64 con cabeceras ELF correctas y checksum coincidente cuando se facilita. Es un filtro estructural, no demuestra que el código sea seguro, que la firma sea de Google o que ANGLE ejecute Vulkan. Sin `aapt`/`apksigner`, rechaza aprobar la APK.

## Condiciones obligatorias antes de tocar WSA

1. Verificar el resultado completo del workflow, commit upstream pinneado y la identidad de la APK; inspeccionar el manifiesto para `org.chromium.angle`, las bibliotecas `lib/x86_64/` EGL+GLESv2 y la firma Android. **Un SHA local únicamente demuestra integridad de archivo, no que Google haya firmado el paquete**.
2. Conservar el paquete y la configuración existente: guardar todos los valores `angle_*`; rechazar perfiles inconsistentes. Instalar la APK comprobada en la WSA únicamente cuando se haya decidido ejecutar el ensayo.
3. Seleccionar `org.callofrecomp` exclusivamente; verificar en Logcat `GraphicsEnvironment` y `ANGLE Renderer (Vulkan...)` atribuibles al proceso. Un valor en `settings` no demuestra ejecución de Vulkan.
4. Comparar imagen, HUD, controles, audio y una escena idéntica de Camp Toccoa. Medir A/B/A de **CallofRecomp**, no del prototipo gráfico ni de la pantalla de inicio; restaurar settings originales y APK estable.
5. No extrapolar resultados de WSA/AMD x86_64 al TECNO/Mali ARM64. El contador oficial de experimentos válidos en TECNO permanece **0/5**.

## Referencias primarias

- https://chromium.googlesource.com/angle/angle/+/43140711d13063716fd32a15de829885d0bce469/doc/DevSetupAndroid.md
- https://chromium.googlesource.com/angle/angle/+/43140711d13063716fd32a15de829885d0bce469/doc/DevSetup.md
- https://github.com/google/angle/releases (sin binarios publicados)
