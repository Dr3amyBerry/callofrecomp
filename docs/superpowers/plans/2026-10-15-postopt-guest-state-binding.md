# Aplicar auditoría post-acumulativa: enlace del estado guest

Solicitud: aplicar el perfil publicado en `93d8d85` sin retirar las mejoras
acumulativas, perder fidelidad ni rebajar calidad. Ejecución local en main,
autorizada por el usuario; no crear otra copia del enorme árbol privado.

## Candidata delimitada y evidencia

El PC muestreado `0x1bbabd8` del ELF `23df3b5f...` es un MOV de 32 bits,
no una llamada a memcpy. Antes/después aparecen cargas GOT de `R`. Los cuatro
objetos `R`, `MEM`, `U`, `PC` son GLOBAL DEFAULT en la tabla dinámica y se usan
dentro de libmain; el host ya integra todos los módulos recompilados allí.

Probar un version script que haga locales únicamente esos cuatro objetos,
manteniendo globales el resto de símbolos. No reemplazar rd/wr ni modificar
precisión, orden de memoria, guardas, estado observable o código generado.
Opción experimental OFF, preset acumulativo conservado. Deshacer el enlace
si la comprobación ABI o la medición falla.

## Pasos y evidencia requerida

1. Test primero: contrato de mapa y opción; fixture ELF propio comprueba que
   los cuatro objetos dejan de exportarse y los entry points públicos siguen.
2. Añadir mapa, CMake y argumento del builder. Solo reenlazar, sin regenerar
   las particiones ni cambiar sus SHA256. Verificar exports y ensamblador del
   ELF real; conservar ambos APK/ELF.
3. Compilar candidato acumulativo + enlace local y medir A/B/A/B WSA sobre
   el APK acumulativo anterior (~67 FPS), Alta/límite120/misma partida.
   Exigir región nativa activa en ambas variantes y guardados idénticos.
4. Revisión independiente, registrar resultado y CI. Si mejora no se repite,
   conservar como ensayo OFF, mantener APK previo activo y seguir P2/P3.

P2 (reutilización de geometría) queda condicionado a medir atributos/índices
y validar invalidación; el perfil no autoriza una caché especulativa. P3 no
puede sustituir FXSAVE64/FXRSTOR64 perdiendo metadatos host de 64 bits.

## Registro

- Inicio: perfil existente reutilizado; revisión nativa dirigida completada.
- Test del mapa observado fallar por ausencia de archivo y después pasar.
  Opción OFF y x86_64 aplicada en CLI/CMake. Build NDK correcto.
- ELF real: se retiran exactamente R/MEM/U/PC de la tabla dinámica, otros
  545 exports definidos preservados y 28 SHA256 generados sin cambios.
  MOV de indirección GOT convertido en LEA; escrituras guest conservadas.
- Revisión independiente sin bloqueo; añadió cobertura de wiring CLI/CMake.
  A/B/A/B en ejecución. No se compila durante sus capturas.
- A/B/A/B completado: CPU/frame menor en ambas parejas; se conserva enlace
  local en APK WSA. [Resultados y alcance](../../performance/wsa/WSA_POSTOPT_APPLICATION_2026-10-15.md).
- P2 ejecutado con contadores/timers existentes y analizador ponderado nuevo;
  restaurados APK normal y marcadores ausentes. Sin cachés no verificadas.
- P3: desambiguadas muestras del símbolo final vs restauración/postámbulo.
