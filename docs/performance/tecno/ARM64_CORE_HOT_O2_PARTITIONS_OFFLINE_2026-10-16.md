# ARM64 — `core-hot-o2` particionado y auditoría offline (2026-10-16)

**Plataforma:** TECNO ARM64 (estudio offline en Windows/NDK; **sin ADB ni teléfono** en esta fase). Rama `main`. **Estado:** opción experimental, desactivada por defecto; ninguna ganancia nueva de FPS atribuida a estas APK.

## Referencia física anterior (historia recuperada y verificada)

El ensayo con `--core-hot-o2` para `p0,p1,p4`, A/B/A/B físico previo, terminó y su informe privado declara `completed_abab`, `restored: true`. La tarea remota quedó `interrupted` por pérdida de conexión **después de escribir** los resultados. Ruta privada:

`.local/profiles/runs/tecno/2026-10-16/core-hot-o2-physical-ab/20261016T035527Z-18940-00/reports/abab-result.json`

| Pasada | Mediana FPS (40 ventanas) | CPU ms/frame | Estabilidad |
| --- | ---: | ---: | --- |
| A1 | 21,30 | 45,220 | Aprobada |
| B1 `p0,p1,p4` | 21,85 | 44,040 | Aprobada |
| A2 | 21,80 | 44,025 | Aprobada |
| B2 `p0,p1,p4` | 21,90 | 43,890 | Aprobada |

Se observa +2,5822 % y +0,4587 % de FPS en las dos parejas; la media de medianas B frente a A es +1,51 %, pero la propia referencia A cambió +2,35 % entre A1 y A2. **Señal positiva, no causalidad ni significación estadística confirmadas.** Comparación de escena gruesa solamente; no sustituye revisión funcional, juego completo ni guardados. La restauración figura en el runner, pero sin conexión ADB nueva **no hay verificación independiente posterior del hash instalado**.

## Nuevo control selectivo, sin alterar el default

Se extiende el flag experimental existente `--core-hot-o2` con `--core-hot-o2-parts p0,p1,p4`. Si el argumento de subconjunto se omite, conserva **exactamente los tres originales**. Solo acepta IDs distintos entre `p0,p1,p4`, rechaza espacios, duplicados, vacíos y `p8`. Mantiene requisitos ARM64, `RECOMP_OPTIMIZATION=1`, SHA p-code CoDSP 1.5, fallback a `-O1` para las otras particiones y `-ffp-contract=off` en las seleccionadas. CMake directo valida también la lista; los builds ordinarios siguen OFF.

Las variantes privadas se compilaron y firmaron con el mismo SDK/NDK, recursos y modo base `--x87-normal-f2d`, sin tocar el código C generado. Comandos específicos:

```text
python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d --core-hot-o2 --core-hot-o2-parts p1 --jobs 2
python tools/recomp/build_android.py --abi arm64-v8a --recomp-opt 1 --x87-normal-f2d --core-hot-o2 --core-hot-o2-parts p0,p1 --jobs 2
```

**Comparación offline del ELF ARM64** con la referencia original exacta y la candidata completa física (sección `.text` medida por `llvm-size`):

| Conjunto compilado a `-O2` | Bytes de `.text` | Delta contra A | APK SHA-256 |
| --- | ---: | ---: | --- |
| A original (`-O1` hot) | 42.340.100 | 0 | `9ba61260ba04394db600f5d5feebc4a2df2a7f38948049fa8eb0e5fb7e217455` |
| `p0,p1,p4` (físico previo) | 42.455.872 | +115.772 | `c0152087c592bf48a144239e1c52b2058b4b21222648df2dba8bc2d3a24d9503` |
| **`p1`** (nuevo) | **42.338.448** | **−1.652** | `de7fc44e57ead10c1b3e0ce84e94ae5426d351bbe45bcaed327caa714b2748a6` |
| `p0,p1` (nuevo) | 42.386.908 | +46.808 | `346c3df37fdd8510899b6305fe6dfa95c1a03d0d2778e1090550c2c2c46f24de` |

Todas las candidatas conservan **490 exportaciones ARM64 con tipo idéntico a A**; las únicas entradas ZIP diferentes son `lib/arm64-v8a/libmain.so` y firma `META-INF/`. En Ninja real, `p1` aislado termina en `-O2 -ffp-contract=off`; `p0/p4/p8/p10` quedan `-O1`, sin `-ffast-math`. Con `p0,p1`, solo `p0/p1` terminan en `-O2`.

Auditoría con `tools/recomp/diagnostics/audit_arm64_native_symbols.py`: en los 18 símbolos reales de chunks de `p1` hay **−21 instrucciones ARM64 estáticas (−84 B)** en total, con disminuciones grandes en algunos chunks y aumentos en otros. **Un histograma de ensamblador y un tamaño menor no demuestran menos ciclos dinámicos o FPS.**

Evidencia **privada e inmutable** dentro de `.local/profiles/runs/tecno/2026-10-16/arm64-hot-o2-offline-partition-audit/20261016T110511Z-4712-00/`:
- `reports/part_p1_comparison.json`, `reports/part_p0_p1_comparison.json`, `reports/p1_native_chunk_audit.json`
- `builds/core_o2_p1.apk`, `builds/core_o2_p1_unstripped.so`, `builds/core_o2_p0_p1.apk`, `builds/core_o2_p0_p1_unstripped.so`
- `scripts/audit_o2_partition.py` (análisis experimental privado; no duplicar herramienta pública)

## Decisión y próxima validación

**Conservar el perfil `p1` OFF, como candidato de menor tamaño**, además del perfil completo que mostró señal física débil. No convertir `p1` en el default, no sumar porcentajes ni declarar aumento de FPS. Cuando vuelva a estar disponible el TECNO: comparar **A contra `p1`** y, en estudio diferente, A contra `p0,p1,p4`, cada uno con identidad de APK/ELF, checkpoint, escena, gráficos, temperatura y guardados, e inspeccionar divergencias x86, x87 binary80, flags, excepciones y crash paths. Si `p1` es regresiva mantenerla solo como opción experimental.

## Verificación técnica de la implementación

- Pruebas de argumentos y política: **14/14** en `test_build_android_profiles.py`, **2/2** en `test_core_hot_o2_policy.py`.
- Suite Python completa: **536 tests (6 omitidos, 0 fallidos)**.
- CTest de reconstrucción host: **40/40**.
- Compilaciones Android NDK reales: APKs firmadas para `p1` y `p0,p1`, sin instalar.
- Auditoría ELF por `llvm-size`/`llvm-nm` y CMake/Ninja real: **490 símbolos**, recursos ZIP comparados, `-O2` aplicado únicamente a los subconjuntos exigidos.
- `git diff --check` correcto; `tools/verify_local_artifacts.py --save` sin errores (advertencia preexistente: un script histórico sin ejecutar tiene sintaxis inválida). Verificados 200 scripts, 33 capturas, 7 builds archivados y ningún archivo privado rastreado por Git.
- Catálogo: **135 documentos** sin enlaces rotos. CI de GitHub se confirmará tras el push.
