# Reglas de trabajo (vigentes desde 2026-10-23)

## Objetivo

**Call of Duty recompilado jugable a 60 FPS en teléfonos modestos.** Referencia física: TECNO CK6n (MT6768 / Helio G85, ARM64, Mali-G52). Punto de partida medido: APK 0.2.4 ≈ 22 FPS, ≈ 44 ms CPU/frame. Meta: ≤ 16,7 ms CPU/frame sin bajar calidad. WSA x86_64 (120 FPS) es secundario.

Para llegar no bastan microajustes de un 1 %. La prioridad son **bloques grandes** que cambien el coste estructural de la traducción y del renderer. Los microajustes se conservan como opt-in si son correctos, pero no marcan la agenda.

## Prioridades (en orden)

1. **Medir antes de optimizar.** Perfil simpleperf del TECNO con símbolos y reparto de los 44 ms (código traducido, x87, dispatch, renderer/gl4es, driver). Ninguna línea de trabajo sin un hot spot que la justifique.
2. **Bloques grandes de traducción** (`tools/recomp/pcode2c.py`):
   - promoción de registros guest a locales C dentro de función/región;
   - pila x87 en `double` dentro de función/región, sin ida y vuelta binary80;
   - eliminación global de flags y escrituras muertas;
   - llamadas directas entre funciones conocidas.
3. **Renderer nativo (HLE).** Se permite sustituir la ruta GL1 traducida + gl4es por un renderer GLES3 nativo con batching, siempre que la imagen sea equivalente.
4. Microajustes opt-in.

## Correctitud: equivalencia observable

- La referencia es el **comportamiento observable del juego x86**: lógica, física, IA, guardados, audio e imagen. No se exige bit-exactitud x87 interna. La ruta ARM64 actual ya hace la aritmética x87 en `double` (ver `recomp_rt.h`), así que exigir binary80 exacto solo bloqueaba el trabajo.
- Toda transformación debe pasar:
  - los oráculos diferenciales existentes (Unicorn, `verify_*`) en las funciones afectadas;
  - tests unitarios;
  - una comprobación en juego: misma escena o partida con imagen equivalente (`scene_fingerprint.py`) y sin cambios en partidas ni en lógica.
- Son bloqueo, no «mejora pequeña»: corrupción de saves, crash, divergencia visible de lógica o física, regresión visual.
- `--hot-x87-transform` y CFG14 siguen bloqueados mientras sus divergencias float32 conocidas no se resuelvan. Se pueden reabrir con evidencia nueva.

## Forma de trabajar

- **Todo en `main`.** Nada de subramas ni worktrees. Cada bloque terminado y verificado lleva commit y push a `main`. Si trabajan varios agentes, que toquen archivos distintos y hagan staging solo de lo suyo (nunca `git add -A`, `reset --hard` ni `clean`).
- **Un solo dueño del teléfono.** Solo un agente usa ADB a la vez. El resto trabaja offline sobre el árbol principal, que tiene el C generado privado en `recomp_out/` y puede compilar APKs reales.
- **Medición física:** A/B/A/B con `tools/recomp/diagnostics/stable_frame_gate.py`, misma APK base, escena y calidad. Comprobar el SHA de las partidas antes y después; nunca desinstalar ni borrar datos.
- **Herramientas permitidas:** Ghidra (`tools/ghidra*`, `ghidra_projects/`) para análisis de funciones calientes, simpleperf, Unicorn/Capstone y el PC local para compilar y medir.
- **Comunicación:** hallazgo, evidencia y siguiente acción. Nunca declarar FPS sin captura física comparable.
- **Al cerrar cada bloque:** fila en `docs/OPTIMIZATION_LEDGER.md` con flag, estado (`integrado / opt-in / inconcluso / regresivo / bloqueado`), medida y límites. Si cambia el estado, actualizar `docs/PROJECT_STATUS.md` y `docs/ROADMAP.md`.

## Artefactos privados

- Logs, capturas, perfiles, APKs y scripts de experimento van en una sesión:
  ```
  python tools/local_workspace.py new-run --target tecno|wsa|arm64-offline|shared --slug HIPOTESIS --agent NOMBRE
  ```
  Nada suelto en `.local/` raíz.
- Verificaciones repetibles van a `tools/` con tests, no a scripts clonados. Los scripts históricos archivados no se mueven ni se ejecutan.
- Nunca subir a Git binarios comerciales, C generado, partidas ni APKs.

## Lectura mínima al empezar

`AGENTS.md` → `docs/PROJECT_STATUS.md` (sección «Objetivo vigente») → `docs/ROADMAP.md` → últimas filas de `docs/OPTIMIZATION_LEDGER.md`. Los informes fechados y `docs/history/` solo se leen cuando hay una hipótesis concreta.
