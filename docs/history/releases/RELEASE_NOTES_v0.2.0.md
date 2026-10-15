CallofRecomp 0.2.0 — versión de prueba

APK pública **sin archivos del juego**. Necesitas tu instalación propia y compatible de Call of Duty para PC, versión 1.5.

## Instalar

1. Descarga `callofrecomp-arm64.apk` para un teléfono Android ARM64. `callofrecomp-x86_64-wsa.apk` es para WSA x86_64.
2. Abre [el empaquetador web](https://dr3amyberry.github.io/callofrecomp/) en Chrome o Edge en tu PC.
3. Selecciona la carpeta del juego, crea el archivo `.codpack` y cópialo al teléfono.
4. En CallofRecomp, pulsa **Importar paquete .codpack**. Al terminar, pulsa **Jugar**.

Los archivos se procesan localmente en el navegador. También sigue disponible la importación directa de una carpeta. Las partidas se guardan por separado.

## Incluye

- Importación de paquetes por bloques, CRC32 y validación SHA-256 de los cuatro binarios compatibles.
- Menús originales y controles RetroTouch que se pueden ocultar.
- Pantalla panorámica sin estirar 4:3; tope de 60 FPS.
- Perfiles Ligero, Equilibrado y Alta; comienza en Ligero en teléfonos modestos.
- README actualizado y web pública para preparar la instalación.

## Requisitos y validación

Android 8 o superior, procesador de 64 bits y OpenGL ES 2.0. El mínimo de RAM y los 60 FPS sostenidos en teléfonos reales siguen pendientes de medir. La campaña completa **no está verificada como completable**.

Comprobaciones automáticas: 15 pruebas CTest del host, pruebas Java del lanzador e intercambio JavaScript ↔ Java del paquete. Ambas APK tienen firmas v2/v3 y alineación de 16 KiB verificadas. Son compilaciones de desarrollo firmadas con una clave local. Las comprobaciones visuales y las pruebas de juego en ARM64 físico siguen pendientes de validación.

`SHA256SUMS.txt` contiene los hashes de las APK. No se incluye el APK privado preimportado.
