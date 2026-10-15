## Menos trabajo de CPU y APK ARM64 más pequeño

- El código recompilado aprovecha la separación entre registros y RAM para reducir accesos redundantes.
- El análisis de flags omite cálculos sobrescritos antes de usarse, conservando ramas, bucles y el estado visible al salir del bloque.
- División y resto con signo usan operaciones nativas para operandos de hasta 64 bits, con tratamiento explícito del desbordamiento MIN/-1.
- La reserva de memoria agrupa páginas consecutivas nuevas en una llamada al sistema.
- La capa gráfica omite normalizaciones de índices que no cambian sus valores en los caminos donde se aplican.
- Se corrigió el sesgo del muestreo de CPU. El diagnóstico está desactivado en los APK normales.
- Conserva pantalla completa horizontal y el límite de 60 FPS.

Versión Android **0.2.3**, código **5**. El APK ARM64 ocupa aproximadamente **50,2 MB**. Las 19 pruebas automatizadas y el CI del código pasaron. Los benchmarks aislados mejoraron, pero **no certifican los FPS del juego**: la zona del alambrado del entrenamiento y la campaña completa siguen pendientes de comprobación por el usuario.

### Descargas

- `callofrecomp-arm64.apk`: teléfonos Android ARM64; requiere Android 8.0 o posterior y una instalación compatible propia de Call of Duty 1.5.
- `SHA256SUMS.txt`: hash del APK.

Este release publica únicamente la nueva build ARM64. La build anterior de WSA x86_64 está en [v0.2.2](https://github.com/Dr3amyBerry/callofrecomp/releases/tag/v0.2.2).

**No incluye los archivos comerciales del juego ni el APK privado con recursos.** Prepara tu instalación con el [empaquetador web](https://callofrecomp-packager.mauvezebra128.chatgpt.site) e importa el archivo `.codpack` en la aplicación.
