# Benchmark por etapas: WSA actual → superficie Vulkan → juego final

**Fecha:** 2026-10-14. **Dispositivo:** Windows Subsystem for Android (WSA), x86_64, Android 13. **Teléfono TECNO:** no disponible; NO se utilizó. **Juego:** Call of Duty 1.5 recompilado, entrenamiento Camp Toccoa, perfil Equilibrado, misma cámara y partida guardada.

**Meta del usuario:** comprobar si un backend Vulkan produce una mejora importante, idealmente de ~50 a 120 FPS. **Resultado todavía NO confirmado:** NO existe un renderizador Vulkan de CallofRecomp en esta revisión; una superficie Vulkan por sí sola **no** equivale a renderizar el juego.

## Condiciones que condicionan los FPS

- La ruta del juego actual es OpenGL clásico → puente generado → GL4ES → GLES2 → EGL Microsoft. Conservada en producción.
- `tools/recomp/runtime/frame_pacing.h` limita explícitamente a **60 FPS** por un temporizador de host. No se puede observar 120 FPS *del juego* sin desactivar ese límite de forma controlada en ambas variantes.
- `adb shell dumpsys display` informa para WSA una única modalidad **1600×900 a 75 Hz**. El experimento Vulkan de presentación usa **FIFO**; `VK_PRESENT_MODE_IMMEDIATE_KHR` **no aparece entre los modos ofrecidos**. La presentación FIFO se estabiliza en ~75 Hz aunque el motor Vulkan pueda preparar frames con menor latencia.
- **WSA no permite trasladar resultados a una Mali ARM64 real.** Las pruebas locales son útiles para el rendimiento x86_64 y compatibilidad, no para afirmar que el teléfono llegará a 60 o 120 FPS.

## Tabla de las tres etapas

| Etapa | Trabajo real | FPS principal | p10 de ventanas de ~1 segundo | CPU/frame | Resultado |
| --- | --- | ---: | ---: | ---: | --- |
| **1. A1:** OpenGL/GL4ES antes del experimento | **Juego completo** en Camp Toccoa, 60 ventanas estables | **55,20** mediana | **53,60 FPS** | **17,14 ms** | Referencia válida |
| **2. Vulkan FIFO:** prueba independiente | **Solo limpieza a color sólido**, superficie y swapchain Vulkan 1280×720, 17,01 s/1.276 frames | **75,014** promedio | **74,922 FPS** | **1,902 ms** | Presentación nativa funcional, **no es FPS del juego** |
| **2 repetición:** se solicita modo inmediato | **Misma limpieza**, 17,001 s/1.276 frames, cae a FIFO porque IMMEDIATE no está disponible | **75,055** promedio | **74,895 FPS** | **1,693 ms** | Repite ~75 Hz; no prueba mejora del motor |
| **Control A2:** OpenGL/GL4ES después de Vulkan | **Mismo juego** y escena, otras 60 ventanas | **55,05** mediana | **51,80 FPS** | **17,315 ms** | La referencia se mantiene (~−0,15 FPS, ruido entre corridas) |
| **Diagnóstico B:** mismo juego GL4ES sin host cap 60 FPS | Misma partida, flag experimental x86_64, 60 ventanas | **57,20** mediana | **56,10 FPS** | **17,47 ms** | Pacing 0 ms; NO Vulkan |
| **Control A3:** APK GL4ES original restaurada | Mismo juego/cámara/Equilibrado, 60 ventanas tras B | **55,30** mediana | **54,60 FPS** | **17,27 ms** | Regresa a la referencia original |
| **3. Final:** CallofRecomp realmente dibujando toda la escena con Vulkan | Debe incluir geometría, materiales, HUD, profundidad, texturas, simulación, colisiones y controles | **NO MEDIDO** | — | — | **Backend aún no implementado** |

**Los FPS de la prueba Vulkan no se pueden comparar directamente con A1 ni A2.** Solo representan lo que el compositor de WSA puede presentar con un color sólido y la API Vulkan. A1/A2/A3 y B sí ejecutan la misma escena del juego; B cambia solo el limitador de 60 FPS y **mantiene GL4ES**.

**Resultado A2/B/A3:** 55,05 → **57,20** → 55,30 FPS (diferencia B de +1,90 a +2,15 FPS respecto a los controles), mientras la CPU/frame **17,315 → 17,47 → 17,27 ms** no disminuyó. Es una mejora de presentación limitada por eliminar el retardo del host, **no de eficiencia del renderizador Vulkan ni de cálculo del motor**. Ni siquiera sin el límite la misma escena llega a 60 FPS medianos en WSA, mucho menos a 120. El límite de pantalla 75 Hz con FIFO seguiría aplicando aunque el trabajo del motor se acelerase más.

## Lo que se implementó de verdad

- `tools/recomp/diagnostics/wsa_vk_surface_bench.c`: aplicación `NativeActivity` de Android independiente del juego, crea `VkAndroidSurfaceKHR`, selecciona cola gráfica con soporte de presentación, `VkSwapchainKHR`, imágenes, render pass (clear), framebuffers, comandos, semáforos y fences, ejecuta `vkQueuePresentKHR`, imprime estadísticas a logcat y libera recursos. **No tiene shaders de juego ni puente GL heredado.**
- `tools/recomp/diagnostics/build_wsa_vk_bench.py`: construye APK **x86_64** independiente firmada en la carpeta privada `.local/profiles/wsa_vulkan_ab`; no modifica ni contiene PK3, DLL o saves del juego. Dos perfiles: FIFO e intento IMMEDIATE (con fallback FIFO).
- `tools/recomp/diagnostics/summarize_wsa_vk_surface.py`: analiza `VK_WINDOW` y `VK_RESULT` y marca explícitamente el contenido como **NO comparable con FPS del juego**.
- `tools/recomp/diagnostics/capture_wsa_game_frames.py`: registra nuevas ventanas reales del juego, controla escena/carga y rechaza usar accidentalmente la FPS del menú.
- `--wsa-uncap-bench`: **flag experimental OFF por defecto y restringido a x86_64** que elimina solo el retardo artificial de 60 FPS, sin cambiar renderer, calidad ni lógica. No se recomienda para releases ni teléfonos. La comparación de esta variante debe declararse como diagnóstico de margen de CPU, NO como optimización Vulkan.
- Tests de parser, no confusión de cargas de trabajo, seguridad del flag y compilación Android.

## Evidencia y reproducibilidad

Archivos generados, APKs del experimento y logs de juego bajo `.local/profiles/wsa_vulkan_ab/`, ignorados por Git. No publicar recursos de Call of Duty ni guardados.

La biblioteca `lib/x86_64/libmain.so` instalada originalmente en WSA fue comprobada **idéntica por SHA-256** a la APK `recomp_out/callofrecomp-x86_64-debug.apk` del repositorio: `403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde`.

La ventana de FPS es un resumen de ~1 segundo; «p10» es percentil 10 de **ventanas** y no percentil de frames individuales. Los `thread_cpu_ms_per_frame` de la prueba Vulkan miden un **hilo que limpia a color sólido**; no incluyen el coste de lógica de Call of Duty.

### Repetir benchmarks

```powershell
# 1. Entra previamente en la misma partida/vista fija de Camp Toccoa.
python tools/recomp/diagnostics/capture_wsa_game_frames.py --serial 127.0.0.1:58526 --seconds 75 --last 60 --out .local/profiles/wsa_vulkan_ab/game_A_new

# 2. Superficie Vulkan aislada (nunca sustituye al juego).
python tools/recomp/diagnostics/build_wsa_vk_bench.py --present fifo
adb -s 127.0.0.1:58526 install -r .local/profiles/wsa_vulkan_ab/fifo/wsa-vulkan-fifo.apk
adb -s 127.0.0.1:58526 shell am start -n org.rigorcore.vkswapbench/android.app.NativeActivity
# Tras >=20 s:
adb -s 127.0.0.1:58526 logcat -d -s RigorVkSurface:I > .local/profiles/wsa_vulkan_ab/fifo/new-run.log
python tools/recomp/diagnostics/summarize_wsa_vk_surface.py --log .local/profiles/wsa_vulkan_ab/fifo/new-run.log

# 3. DIAGNÓSTICO solo si interesa medir margen del propio juego sin su cap:
python tools/recomp/build_android.py --abi x86_64 --jobs 3 --wsa-uncap-bench
# Respaldar antes, no reemplazar la APK estable sin plan de restauración.
```

## Criterio estricto para declarar mejora final

Una validación del renderer Vulkan del juego solo es válida cuando:
1. El APK B **renderiza de verdad la misma escena y todos sus efectos** mediante el backend Vulkan, sin omitir trabajo. HUD, FOV, texturas, niebla, estado depth/stencil y guardados deben coincidir.
2. La variante A (GL4ES) y la B (Vulkan) tienen la **misma política de frame cap, presentación y calidad**. En WSA 75 Hz FIFO, no se pueden afirmar 120 frames **presentados** usando esa única modalidad.
3. Se comparan al menos 60 ventanas A/B/A, idealmente A/B/A/B/A, FPS medianos, p10, CPU/frame, swap, capturas visuales y estado de la simulación. No confundir un `vkQueuePresentKHR` exitoso con un frame completo.
4. La ganancia supera la variación de A1/A2. Repetir finalmente en hardware ARM64 cuando el teléfono vuelva.

**Estrategia oficial:** conserva las tres fases y contador **0/5**. Una prueba de superficie, su repetición y el diagnóstico sin limitador no son «fallos» de una optimización Vulkan funcional; son controles de laboratorio. [Estrategia vigente](PERFORMANCE_STRATEGY_CURRENT.md).

## Verificación de cierre tras la interrupción del chat

Se recuperaron los resultados ya terminados de B1 y A3 desde sus JSON y tareas existentes, **sin repetir los benchmarks**. La compilación diagnóstica x86_64 había terminado y el flag se había devuelto a `CODRECOMP_WSA_UNCAP_BENCH:BOOL=OFF` en `build-android-native-x86_64/CMakeCache.txt`. Se detectó que la APK regenerada con el flag OFF ya no era idéntica byte a byte al backup de A1; por tanto se reinstaló en WSA la **APK exacta** `.local/profiles/wsa_vulkan_ab/reference_A_gl4es_x86.apk` con `adb install -r` (sin borrar los datos).

La restauración final se verificó extrayendo `lib/x86_64/libmain.so` de la APK realmente instalada, y su SHA-256 coincidió **byte a byte** con la referencia A1: `403a5bc304b3ec36b43b04a8322c31a212727a8a8ff254e47b70afec2d960cde` (60.680.384 bytes). `PASS`. **No se ejecutó un nuevo benchmark** durante esta verificación. La prueba B1 y el control A3 conservan sus datos originales; el TECNO no se utilizó.

Las pruebas unitarias específicas del trabajo anterior pasaron (7 pruebas WSA de extracción/parsing y 2 pruebas del flag de build). No se repitieron al retomar. La prueba final del juego renderizado en Vulkan no existe todavía, por lo que **no se atribuye ninguna mejora de FPS a Vulkan**.

**Estado:** WSA Vulkan WSI demostrado y métricas guardadas. **No se ha creado un renderizador Vulkan de CallofRecomp** y por ello el tercer número de «CallofRecomp Vulkan completo» queda correctamente **PENDIENTE**.
