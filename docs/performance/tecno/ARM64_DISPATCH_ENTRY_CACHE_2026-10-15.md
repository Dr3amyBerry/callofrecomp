# ARM64: cache local de entrada completa de dispatch

**Estado: CANDIDATA EXPERIMENTAL, opt-in y OFF por defecto.** APK ARM64 compilada y equivalencia del lookup/callback ensayada en AArch64. Sin ejecucion nueva del juego, ADB, WSA ni nuevos FPS. No acredita fidelidad integral o aceleracion del TECNO.

## Implementacion y motivo

`--arm64-dispatch-entry-cache` conserva rango y callback del ultimo chunk dentro de cada `guest_run`. Evita volver a leer la tabla cuando PC sigue dentro del mismo rango. Una identidad de indice y su generacion invalidan la entrada tras reconstruir la tabla. El contrato exige reconstruir el indice ante cambios de rangos o callbacks; el cargador existente lo hace. No se difiere estado guest, flags ni memoria.

Es una alternativa al cache antiguo de indice, no una combinacion: el builder rechaza `--dispatch-last-cache` junto a esta bandera y rechaza ABI distinta de `arm64-v8a`. CMake tambien protege esas condiciones. Las rutas de profiling y de error posteriores al callback permanecen iguales.

La [evidencia previa de dispatch](CPU_PHASE5_OFFLINE_DISPATCH_CACHE_2026-10-14.md) atribuia aproximadamente 1,13-1,18 % de muestras del proceso al lookup. Son muestras historicas, no tiempo exclusivo ni prediccion de ganancia. La tasa real de aciertos de esta candidata sigue pendiente.

## Evidencia AArch64 reproducible

`tools/recomp/diagnostics/verify_arm64_dispatch.py` compila el smoke C existente con NDK 30, target Android AArch64 y O1, y lo ejecuta en Unicorn. Comprueba limites, huecos, direcciones altas, callback exacto y sus efectos, reemplazo de callback con rebuild, identidad/generacion, hints independientes y reduccion del numero de chunks. Los hints independientes no prueban recursion real de `guest_run` ni recarga desde un callback del juego.

Ademas ejecuta 512 callbacks por patron, con semilla `0x4038015` y 403 chunks sinteticos. Se comprueban indices y numero de callbacks contra la referencia. Conteos dinamicos de instrucciones / bytes leidos de la tabla:

| Patron | Referencia | Cache indice anterior | Cache entrada |
| --- | ---: | ---: | ---: |
| Mismo chunk | 18.482 / 9.796 | 14.881 / 8.192 | 13.866 / 24 |
| Rachas de 8 | 16.853 / 9.072 | 15.997 / 8.792 | 15.360 / 1.644 |
| Alternancia de 2 | 17.069 / 9.168 | 23.466 / 12.236 | 25.517 / 13.264 |
| Aleatorio 403 | 16.763 / 9.032 | 23.111 / 12.056 | 25.150 / 13.080 |

Hay ahorro con localidad y regresion con fallos frecuentes. No son ciclos, tiempos del telefono ni FPS; por eso se conserva desactivada hasta medir el juego.

## APK real e integridad

A y B usan normal-f2d y fuentes generadas normales; outlining x87, ICF y enlace local estan OFF. Solo se recompila `guest.c.o` entre variantes. Las 28 fuentes generadas conservan SHA. Las 490 exportaciones conservan nombre/tipo/binding/visibilidad; solo cambia el tamano de `guest_run`, de 1.152 a 1.336 bytes (288 a 334 instrucciones estaticas). El mayor cuerpo completo no contradice el ahorro dinamico en aciertos. El prologo reserva 96 bytes de pila en A y 128 en B; conserva los mismos registros callee-saved x19-x30. Los 32 bytes adicionales reflejan almacenamiento local adicional, no una ganancia. El coste dinamico de spills/reloads y la latencia real siguen pendientes de medicion.

Los APK conservan entradas, assets, DEX y dependencias; solo difieren `lib/arm64-v8a/libmain.so` y firmas META-INF. Firma v2/v3 y alineacion comprobadas por el empaquetador. Al terminar se restauro la configuracion OFF, el ELF y APK A por SHA.

| Artefacto privado | SHA256 |
| --- | --- |
| `dispatch-A.apk` | `c736228eb454d17a4b798391007793aa434c5e9341b8ec64e811106c5d5f5daa` |
| `dispatch-B.apk` | `d7e7f1bf776715ada651cc97b3e8c5e3e8d6cb596f9099da222efe30cfd9e99f` |
| `dispatch-A.so` sin strip | `36961343775ec5c8b61e4defd818add9b21c046e4c0d8d5ba762b2fde7db5205` |
| `dispatch-B.so` sin strip | `b7426405d90976b2dfb3d6227088cb4be2a0d39fd2247e5d76e158ed8eefb48e` |

Sesion privada: `.local/profiles/runs/tecno/2026-10-15/arm64-dispatch-bounds/20261015T223820Z-10768-00`. Evidencia final: `raw/aarch64-final/result.json`, `reports/guest-run-comparison.json`, `reports/integrity.json`, `reports/objects-A.json`, `logs/` y `builds/`. Los primeros intentos de enlace del harness fallaron por direccion de texto incompatible con la base ELF; se corrigio a `0x400000`. Esos intentos no cuentan como pruebas aprobadas.

## Siguiente comprobacion

Validacion local: 40/40 CTest; suite Python de 492 pruebas aprobada con cinco omitidas, usando `RECOMP_TEST_CC` explicito. Revision independiente sin bloqueos nuevos de correctitud; se corrigio el comentario del smoke para no atribuirle cobertura de recursion real. Verificador privado sin errores (permanece el aviso historico de sintaxis de `phase14d_fix_cmake_winpaths.py`, no ejecutado).

Reproduccion sin telefono:

```powershell
python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d --arm64-dispatch-entry-cache --jobs 3
python tools/recomp/diagnostics/verify_arm64_dispatch.py --llvm-bin RUTA_NDK_LLVM_BIN --out RUTA_SESION_PRIVADA/raw/aarch64-nuevo
```

Omitir `--arm64-dispatch-entry-cache` restaura la referencia en el builder. No combinar con otras candidatas hasta obtener su A/B independiente.

Usar el procedimiento A/B/A/B y las guardas de [estabilidad](TECNO_STABILITY_GATE_2026-10-15.md), con estas dos APK y misma escena/calidad/partida cuando vuelva el dispositivo y se autorice. Medir tasa de aciertos y coste total antes de acumular esta bandera. Si hay regresion repetida, mantenerla fuera de la candidata activa. La siguiente familia offline vuelve al coste de estado/memoria de los chunks calientes; esta cache por si sola no resuelve 60 FPS.
