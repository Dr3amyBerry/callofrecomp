# Fase 14C — Oráculo x86 original y dispatcher CFG con fallback (2026-10-15)

**Estado:** integración experimental implementada, **OFF por defecto**; compilación aislada Android ARM64 del dispatcher y el helper verificada. **No se ha instalado APK ni medido CPU/frame o FPS.** La fase de habilitación productiva sigue pendiente.

## 1. Verificación del bloque real de geometría

El nuevo `tools/recomp/diagnostics/verify_geometry_region_original_x86.py` ejecuta con **Unicorn los 29 bytes/instrucciones originales de CoDSP.exe 1.5**, comprobados por Capstone, de `0x0041C017` hasta el salto a la función compartida `0x00523CD9` (se detiene **antes** de ejecutar el epílogo). P-code y mapa Ghidra B están fijados por SHA-256.

**40 casos independientes del x86 original / 40 exitosos**, 8 por escenario. El modelo usa **direcciones guest exactas y 24 MiB de RAM mapeada, sin módulo 64 KiB**. Se comprobaron contra Unicorn dos variantes C compiladas de `pcode2c.Gen` (original A y caché B de cinco campos), byte a byte:

- Los ocho registros generales EAX, ECX, EDX, EBX, ESP, EBP, ESI y EDI.
- Las cinco banderas **CF/PF/ZF/SF/OF** que materializa el traductor (no AF).
- Los **8.192 bytes de R**, todo el espacio de **24 MiB de RAM guest mapeada**, y el **PC final `0x00523CD9`**.
- Escenarios sin alias y con alias en almacenamiento de punteros, celdas de tabla y valores de pila. Hubo **8 lecturas posteriores a escritura** verificadas en cada uno de dos escenarios de alias que cambian datos usados más adelante.

La nueva función **`generate_runtime_region_c`** emite un helper privado compatible con el runtime real: `codsp_cfg14_geom_41c017(void)`. No copia artificialmente RAM ni R, conserva los 16 LOAD y 6 STORE originales, inicia solo en el líder, vuelca los cinco campos R al salir y deja que el dispatcher original ejecute el epílogo. El helper se compiló con **LLVM-MinGW** y como objeto **Android NDK ARM64**; en su forma preparada para runtime volvió a pasar **40/40** pruebas originales x86. Un PC interior `0x0041C01B` fue rechazado sin cambiar estado.

**Control negativo real:** se retiró el volcado de ESP de una DLL privada de prueba y **Unicorn la rechazó**. El helper real no se alteró.

## 2. Seguridad e integración exclusivamente opt-in

- `tools/recomp/runtime/guest.c`: nuevo guard con `CODRECOMP_CFG14_GEOM_REGION`, `PC == 0x0041C017` y módulo CoDSP cargado. Solo si el helper devuelve 1 se continúa al PC `0x00523CD9`; cualquier otro PC usa `dispatch_index_find` y `all_chunks[found].fn()` **sin cambios**.
- `tools/recomp/runtime/cfg_hot_regions.h`: declaración pública del símbolo, sin instrucciones derivadas del juego.
- `tools/recomp/diagnostics/emit_verified_cfg_region.py`: emisor exige PE original, hashes de p-code/mapa y reporte original x86 de >=40 casos con cinco escenarios y alias. Solo escribe a `recomp_out/codsp_cfg14_geom_41c017.c`, **ignorado por Git**, y no sobrescribe archivos con contenido diferente.
- `android/CMakeLists.txt`: opción `CODRECOMP_CFG14_GEOM_REGION`, **OFF**. Si ON exige ABI arm64-v8a, optimización de recompilación 1 y SHA-256 exactos de p-code, mapa y helper; solo añade este C privado y la definición de compilación a `guest.c`.
- `tools/recomp/build_android.py`: flag optativo `--cfg14-geom-region`, no habilitado por defecto, rechaza ABI x86_64 o `--recomp-opt 0`.

**Fingerprint del helper privado emitido, verificado en NDK:**

`dfd2655e497bbf8fa83ad434244f6a33d1afcccca5308bd413c523919cd19899`

No se publicó código privado generado del juego ni se copió código GPL.

## 3. CMake/Ninja real y evidencias

Se crearon dos configuraciones **independientes** de Android NDK:

| Modo | Unidad C privada | Macro en guest.c | Compilación |
| --- | --- | --- | --- |
| **OFF** | No incluida | Ausente | `guest.c` compilado en ARM64, sin referencia al helper |
| **ON** | Una sola | Presente | Objetos `guest.c.o` y `codsp_cfg14_geom_41c017.c.o` compilados en ARM64 |

**llvm-nm** comprobó ausencia completa del símbolo experimental en `guest.c.o` con OFF, y con ON comprobó que `guest.c.o` contiene exactamente una referencia indefinida al helper, resuelta por el símbolo global definido en su objeto C. Esto **no equivale** a enlazar `libmain.so` completo.

El objeto ARM64 del helper contiene **404 B de .text**, 32 cargas y 22 escrituras estáticas. Son datos del helper sin el envoltorio de laboratorio: **no compararlos directamente** con el tamaño de código 976→804 bytes publicado en 14C. No hay medidas dinámicas de ejecución.

Rutas de evidencia privada, fuera de Git:

- `.local/profiles/phase14d_geom_real_x86_40cases/summary.json`
- `.local/profiles/phase14d_runtime_linked_candidate/independent_x86_summary.json`
- `.local/profiles/phase14d_runtime_linked_candidate/compile_summary.json`
- `.local/profiles/phase14d_integrated_esp_mutant_v1/negative_result.txt`
- `.local/builds/phase14d_cfg_off_v3/` y `.local/builds/phase14d_cfg_on_v3/`

**Validación final del repositorio:** 331 pruebas Python ejecutadas, 4 omitidas y 0 fallidas; **35/35 CTest** aprobados tras recompilar el host con el cambio en `guest.c`. Smoke real del CLI `build_android.py` rechazó `--abi x86_64` y `--recomp-opt 0` con el flag experimental. Emisor privado idempotente condicionado a los mismos hashes, y test negativo sin flush ESP correctamente rechazado. El runtime ON solo se compiló como objetos NDK; **no hubo enlace de APK**.

## 4. Reproducción

Los siguientes comandos presuponen acceso legítimo al PE original y al p-code y mapa privados:

```powershell
python tools/recomp/diagnostics/verify_geometry_region_original_x86.py --pe ".local/private/Call of Duty Deluxe Edition/CoDSP.exe" --out .local/profiles/nueva_prueba_x86 --cases 40
python tools/recomp/diagnostics/emit_verified_cfg_region.py --pe ".local/private/Call of Duty Deluxe Edition/CoDSP.exe" --proof .local/profiles/nueva_prueba_x86/summary.json
```

Para una futura construcción de prueba voluntaria, el constructor expone `python tools/recomp/build_android.py --cfg14-geom-region`. El build normal **no utiliza** ese flag y continúa sin enlazar ningún código experimental.

## 5. Bloqueos y próxima validación

1. **No se probó todo el mapa de 4 GiB ni manejo de excepciones.** Si el juego accede a una página no comprometida a mitad de región, un valor cacheado todavía no escrito en R podría alterar el estado visible ante una excepción. Esto debe estudiarse antes de permitir el fast path en juego real.
2. **El epílogo compartido queda original**; falta ejecutar sus dos rutas (cookie coincidente/no coincidente) bajo oráculo independiente con pila, flags y PC finales.
3. Se verificó compilación ARM64 de objetos y emparejamiento de símbolos, **no el enlace completo del .so ni una APK ON, ni gameplay real**.
4. La decisión definitiva sigue dependiendo de una prueba funcional del TECNO con A/B/A de **ms de CPU por fotograma**, sin tocar resolución, shaders, físicas ni guardados.

**Conclusión:** integración guardada y reversible creada, default OFF, original CoDSP x86 igual a helper en los casos ensayados; no se activa para usuarios ni se afirma ningún FPS adicional.
