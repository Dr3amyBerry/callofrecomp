#!/usr/bin/env python3
"""Audit the first two archived 100-script batches by actual Python source.

Classifies non-destructively, verifies SHA256, and records the code evidence.
These roles describe intent, not proof a historical one-off can run today.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/".local/catalog"
MANIFESTS=(CAT/"archived_legacy_scripts_2026-10-15.json",
           CAT/"archived_legacy_scripts_2026-10-15_batch02.json")
JSON_REPORT=CAT/"archived_script_roles_first200.json"
MD_REPORT=ROOT/"docs/history/ARCHIVED_SCRIPT_ROLES_FIRST200.md"

# Manually evaluated reusable *capabilities*, not reusable old scripts.
# Capabilities were reviewed against the exact original bytes, not only names.
CANONICAL={
 "phase15_compare_capture_hashes.py":("hash","Files and fingerprints",
   "22e303b6b49505cdf5330dcc43dd509c4368d8c2474346a7e16ff6ebcdfb9fda"),
 "phase15_inventory_existing_perf.py":("inventory","Bounded profile discovery",
   "8cbc8be863084a6ebda79b79e304232e5d2eb7e4ab90cda7902258ca6ce09af7"),
 "phase15_two_session_check.py":("metadata","Session identity and metadata",
   "200a828d01983ad0d5224b9322a6309a92b9459c841d1c7cb10e602224fb228e"),
}
EDIT_CALLS={"write_text","write_bytes","write","writelines","rename",
            "unlink","rmtree","copyfile","copy2"}
SOURCE_RE=re.compile(
 r"(?:docs[/\\][A-Za-z0-9_.-]+|tests[/\\][A-Za-z0-9_.-]+|"
 r"tools[/\\]recomp[/\\][A-Za-z0-9_./\\-]+|android[/\\]CMakeLists\.txt|"
 r"CMakeLists\.txt|PROGRESS\.md|AGENTS\.md|"
 r"\.local[/\\]profiles[/\\][A-Za-z0-9_.-]+\.py)",re.I)

class ReviewError(ValueError):
 pass


def archive_entries(root:Path=ROOT,manifests=MANIFESTS):
 rows=[]
 old_paths=set()
 new_paths=set()
 for batch,manifest in enumerate(manifests,1):
  items=json.loads(manifest.read_text(encoding="utf8"))["moves"]
  if len(items)!=100:raise ReviewError("Expected 100 archived scripts per manifest")
  for item in items:
   old,new=item["old"],item["new"]
   if old in old_paths or new in new_paths:
    raise ReviewError("Duplicate script in archive manifests")
   old_paths.add(old);new_paths.add(new)
   if not new.startswith(".local/profiles/history/scripts/"):
    raise ReviewError("Unrecognized archive path")
   p=(root/new).resolve()
   if not p.is_relative_to(root.resolve()) or not p.is_file() or p.is_symlink():
    raise ReviewError("Missing or unsafe archived file: "+new)
   raw=p.read_bytes()
   if len(raw)!=item["bytes"] or hashlib.sha256(raw).hexdigest()!=item["sha256"]:
    raise ReviewError("Archived SHA/size changed: "+new)
   rows.append(dict(batch=batch,name=p.name,old=old,path=new,sha256=item["sha256"],
                    source=raw.decode("utf-8-sig")))
 if len(rows)!=200:raise ReviewError("Expected exactly 200 scripts")
 return rows


def classify(row):
 src=row["source"]
 tree=ast.parse(src,filename=row["name"])
 calls=set()
 constants=[]
 for n in ast.walk(tree):
  if isinstance(n,ast.Call):
   if isinstance(n.func,ast.Attribute):calls.add(n.func.attr)
   elif isinstance(n.func,ast.Name):calls.add(n.func.id)
  if isinstance(n,ast.Constant) and isinstance(n.value,str):
   constants.append(n.value)
 doc=(ast.get_docstring(tree) or "").strip().splitlines()
 source_refs=sorted(set(SOURCE_RE.findall("\n".join(constants))))
 may_write=bool(EDIT_CALLS&calls)
 repo_edit=may_write and bool(source_refs)
 uses_process="subprocess" in src or "os.system" in src
 if row["name"] in CANONICAL and row["sha256"] == CANONICAL[row["name"]][2]:
  role="reusable_capability"
  detail="Generalized into profile_evidence.py "+CANONICAL[row["name"]][0]
  action="Use permanent CLI; preserve pinned original"
 elif repo_edit:
  role="one_off_edit"
  detail="Mutates source/docs/tests (static paths/call evidence)"
  action="Preserve only; never rerun blindly"
 else:
  role="pinned_experiment"
  detail=("Runs a pinned offline experiment/probe" if uses_process else
          "Writes study evidence/fixtures" if may_write else
          "Reads/verifies pinned experiment inputs")
  action="Preserve with matching experiment and evidence"
 return dict(batch=row["batch"],name=row["name"],path=row["path"],
             sha256=row["sha256"],lines=len(src.splitlines()),role=role,
             reason=detail,action=action,doc=(doc[0][:180] if doc else ""),
             source_refs=source_refs[:8],calls=sorted(calls)[:55],
             writes=may_write,likely_source_edit=repo_edit,
             has_subprocess=uses_process,
             requires_pinned_context=role!="reusable_capability",
             canonical=("tools/recomp/diagnostics/profile_evidence.py"
                        if role=="reusable_capability" else None),
             historical_executed=False)


def markdown(rows):
 c=Counter(row["role"] for row in rows)
 parts=[
 "# Clasificación funcional de los primeros 200 scripts históricos",
 "",
 "Auditoría estática de **200 scripts reales**, comparados con sus dos"
 " manifiestos SHA256. No se ejecutó ningún script legado ni se"
 " modificó o eliminó su archivo original. Esta clasificación es"
 " una decisión de mantenimiento, no una garantía de compatibilidad de ejecución.",
 "",
 "| Categoría | Cantidad | Tratamiento |",
 "|---|---:|---|",
 f"| Patrón aprovechado en herramienta permanente | {c['reusable_capability']} | Extraer funcionalidad generalizable; conservar originales |",
 f"| Editor puntual | {c['one_off_edit']} | No reejecutar sobre fuentes actuales; mantener como historial |",
 f"| Experimento/inspección de entradas fijadas | {c['pinned_experiment']} | Conservar con evidencia, oráculo y configuración |",
 "",
 "## Herramienta canónica resultante",
 "",
 "`tools/recomp/diagnostics/profile_evidence.py` cubre tres capacidades"
 " antes codificadas con rutas fijas de sesiones TECNO:",
 "",
 "- `inventory --root .local/profiles`: inventario acotado de perfiles sin recorrer enlaces de terceros.",
 "- `hash --root .local/profiles --files RUTA1 RUTA2`: huellas SHA256 de entradas explícitas.",
 "- `hash ... --output runs/.../metrics/sha.json`: guarda manifiesto sin sobrescribir en una sesión existente.",
 "- `verify --root .local/profiles --manifest runs/.../metrics/sha.json`: detecta evidencia alterada.",
 "- `metadata --root .local/profiles --files A.json B.json --require-same-build`: lee campos acotados y comprueba Build ID; no estima FPS.",
 "",
 "**Ninguno de los tres archivos antiguos se vuelve a ejecutar como una utilidad general.**"
 " El patrón se reimplementó con CLI, rutas de entrada, pruebas y validación."
 " Las verificaciones x86/CFG/x87 específicas continúan sujetas al"
 " oráculo original o a las herramientas y tests canónicos del repositorio.",
 "",
 "## Reglas para las otras IAs",
 "",
 "- Scripts que modifican textos, código o pruebas una vez: escribir el cambio,"
 " revisar diff, hacer tests y conservar solo evidencia útil; no crear un editor reusable por párrafo.",
 "- Scripts experimentales: fijar entradas, versión y resultados; no ejecutar"
 " un experimento viejo suponiendo que la ABI, el perfil o el Build ID siguen iguales.",
 "- Para verificaciones nuevas, buscar primero en `tools/`."
 " Si falta una capacidad repetida, crear una utilidad parametrizada con pruebas"
 " y rechazo seguro de entradas, no versiones `v2` y `final` de scripts temporales.",
 "- Los dos archivos históricos de 100 deben conservarse íntegros."
 " Esta catalogación no autoriza borrar, fusionar ni mover scripts nuevos.",
 "",
 "## Inventario completo, clasificado por código",
 "",
 "Las pistas de edición se derivan de llamadas AST de escritura y literales"
 " de rutas (revisión estática). Los demás scripts se guardan como estudios"
 " de escenario; algunas verificaciones podrían promocionarse en"
 " una auditoría futura, pero ninguna se declara portátil sin refactor y tests.",
 "",
 ]
 labels=(("reusable_capability","Funciones extraídas para reutilización"),
         ("one_off_edit","Parches y ediciones puntuales"),
         ("pinned_experiment","Experimentos y verificaciones contextuales"))
 for role,title in labels:
  parts.extend([f"### {title} ({c[role]})","",
                "| Archivo (lote) | Qué hace / evidencia | Acción |",
                "|---|---|---|"])
  for row in rows:
   if row["role"]!=role:continue
   purpose=(row["doc"] or row["reason"]).replace("|","/").replace("`","'")
   purpose=purpose[:125]
   action=("CLI permanente" if role=="reusable_capability" else
           "No reejecutar" if role=="one_off_edit" else "Historial de experimento")
   parts.append(f"| `{row['name']}` (L{row['batch']}) | {purpose} | {action} |")
  parts.append("")
 parts.extend([
 "## Reproducibilidad",
 "",
 "- Generar/revisar: `python tools/review_archived_scripts.py --check`;"
 " solo en caso de cambios deliberados en el catálogo: `--write`.",
 "- Evidencia detallada privada con SHA256, invocaciones y referencias:"
 " `.local/catalog/archived_script_roles_first200.json`.",
 "- Manifiestos inmutables:"
 " `.local/catalog/archived_legacy_scripts_2026-10-15.json`"
 " y `.local/catalog/archived_legacy_scripts_2026-10-15_batch02.json`.",
 ])
 return "\n".join(parts)+"\n"


def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__)
 group=parser.add_mutually_exclusive_group()
 group.add_argument("--check",action="store_true")
 group.add_argument("--write",action="store_true")
 args=parser.parse_args(argv)
 try:
  rows=[classify(row) for row in archive_entries()]
  md=markdown(rows)
  if args.check:
   if not MD_REPORT.is_file() or MD_REPORT.read_text(encoding="utf-8")!=md:
    raise ReviewError("Markdown catalog is outdated; regenerate intentionally")
  if args.write:
   MD_REPORT.parent.mkdir(parents=True,exist_ok=True)
   MD_REPORT.write_text(md,encoding="utf-8",newline="\n")
   JSON_REPORT.parent.mkdir(parents=True,exist_ok=True)
   JSON_REPORT.write_text(json.dumps(dict(schema=1,
     generated_utc=datetime.now(timezone.utc).isoformat(),entries=rows),
     ensure_ascii=False,indent=2),encoding="utf-8")
  print(json.dumps(dict(count=len(rows),
    sha256_verified=len(rows),roles=dict(Counter(row["role"] for row in rows)),
    mode="check" if args.check else "write" if args.write else "preview")))
  return 0
 except (ReviewError,ValueError,OSError,UnicodeError,SyntaxError,KeyError) as err:
  print("ARCHIVE_REVIEW_ERROR:",err,file=sys.stderr)
  return 2


if __name__=="__main__":
 raise SystemExit(main())
