# CallofRecomp 0.2.4

Dos APK: teléfonos ARM64 y WSA x86_64. Requieren Android 8 o posterior y una
copia compatible propia de Call of Duty 1.5; no incluyen recursos comerciales.
VersionCode 6. Instalar encima conserva los datos; no hace falta desinstalar.

## WSA x86_64

- Conjunto acumulativo de optimizaciones de CPU y región x87 nativa binary80.
- Enlace local de R/MEM/U/PC: menos indirecciones, sin cambiar las instrucciones
  guest ni diferir escrituras.
- Ruta nativa y límite 120 activos por defecto, sin depender de los archivos
  privados usados durante las pruebas. Se respetan los overrides del perfil.
- Diagnósticos CPU/GL desactivados.

Las pruebas anteriores del mismo conjunto en entrenamiento/Alta dieron
68,0–68,3 FPS del motor y 14,64–14,71 ms CPU/frame en las dos B.
**No son 120 FPS sostenidos ni una garantía para otras escenas.** El panel WSA
probado funciona a 75 Hz. [Método y límites](https://github.com/Dr3amyBerry/callofrecomp/blob/v0.2.4/docs/performance/wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md).

## Teléfonos ARM64

- Runtime actualizado, correcciones panorámicas/HUD y conversión normal-f2d
  comprobada con fallback.
- Retirado del APK el transform antiguo double, bloqueado por diferencias de
  precisión frente al x86 original. CFG14 sigue bloqueado.
- Límite público 60 FPS; la región x87 nativa de WSA no se compila para ARM64.

La revalidación de esta build en TECNO sigue pendiente por falta del dispositivo.
No se extrapola la ganancia WSA ni se prometen 60 FPS sostenidos en teléfonos.
Retirar el atajo inseguro puede cambiar el rendimiento frente a builds anteriores.

## Recursos y descargas

La [página pública](https://callofrecomp-packager.mauvezebra128.chatgpt.site)
queda en tres pasos: descargar APK, seleccionar carpeta y crear `.codpack`.
Sin logo, cabecera de marca, eslogan ni tarjetas extra. El empaquetado sigue
siendo local, sin subir los archivos.

- `callofrecomp-arm64.apk`: teléfonos Android ARM64.
- `callofrecomp-x86_64.apk`: WSA x86_64.
- `SHA256SUMS.txt`: hashes de los dos APK.

Copia el `.codpack` al dispositivo, abre la aplicación y pulsa «Importar paquete
.codpack». Al terminar, pulsa «Jugar».

## Verificación y límites

40/40 CTest locales y pruebas CODPACK web aprobados. El builder comprueba firmas,
ABI y alineación de 16 KiB. Las mediciones y oráculos anteriores se conservan en
el [registro de optimizaciones](https://github.com/Dr3amyBerry/callofrecomp/blob/v0.2.4/docs/OPTIMIZATION_LEDGER.md); no se presentan
como pruebas nuevas de cada APK. La campaña completa, escenas complejas y
estabilidad prolongada siguen en validación. No se redujo calidad gráfica.

La APK WSA 0.2.4 se actualizó sin desinstalar, cargó el entrenamiento y ejecutó
la región nativa con límite120 sin overrides privados. Las partidas conservaron
sus hashes. Ambos APK usan el mismo certificado. La web pasó sus pruebas
funcionales; no hubo navegador de previsualización disponible en esta sesión.

### Overrides WSA (avanzado; reiniciar el juego)

`files/profile/native_x87` acepta exactamente un byte `0` o `1`; su ausencia
usa el default de esta APK. `files/profile/frame_limit` acepta `60`, `120`,
`unlimited` u `original` (60). No cambian los relojes de simulación.

Para desactivar la ruta nativa y limitar a 60 desde ADB:

```sh
adb shell "run-as org.callofrecomp sh -c 'printf 0 > files/profile/native_x87'"
adb shell "run-as org.callofrecomp sh -c 'printf 60 > files/profile/frame_limit'"
```
