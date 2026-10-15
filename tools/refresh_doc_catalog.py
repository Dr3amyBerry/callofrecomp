#!/usr/bin/env python3
"""Generate a small link catalog and validate local Markdown links without reading builds."""
from pathlib import Path
from collections import defaultdict
import argparse, os, re, json, subprocess

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CATALOG = DOCS / "history" / "DOCUMENT_CATALOG.md"
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
ORDER = [
 ("docs","Documentos operativos"),
 ("docs/guides","Guías técnicas"),
 ("docs/performance/wsa","WSA x86_64 — 120 FPS"),
 ("docs/performance/tecno","TECNO ARM64 — 60 FPS vigente"),
 ("docs/performance/cpu","CPU general"),
 ("docs/performance/cfg","Investigación y bloqueos CFG"),
 ("docs/performance/graphics","Renderer / gráficos"),
 ("docs/history","Historial y releases"),
 ("docs/archive","Estrategias anteriores"),
 ("docs/superpowers","Planes técnicos"),
]

def title(path):
    for line in path.read_text(encoding="utf-8",errors="replace").splitlines()[:8]:
        if line.startswith("# "):return line[2:].strip().replace("|","-")
    return path.stem

def generate():
    md=sorted(x for x in DOCS.rglob("*.md") if x!=CATALOG)
    groups=defaultdict(list)
    for p in md:
        rel=p.relative_to(ROOT).as_posix()
        group="docs/"+p.relative_to(DOCS).parts[0] if p.parent!=DOCS else "docs"
        if group.startswith("docs/superpowers"):group="docs/superpowers"
        groups[group].append(p)
    lines=["# Catálogo completo de documentación",
        "",
        "**Propósito:** localizar informes sin recorrer builds, perfiles privados ni repos externos. **No confundir archivos históricos con prioridades actuales.**",
        "",
        "[Ruta de lectura corta](../INDEX.md) · [estado](../PROJECT_STATUS.md) · [objetivo TECNO vigente](../TECNO_REVALIDATION.md)",
        ""]
    for folder,label in ORDER:
        group=groups.pop(folder,[])
        if not group:continue
        lines.extend(["## "+label,""])
        for p in group:
            link=os.path.relpath(p,CATALOG.parent).replace("\\","/")
            lines.append("- ["+p.name+"]("+link+") — "+title(p))
        lines.append("")
    for folder,extra in sorted(groups.items()):
        lines.extend(["## "+folder,""])
        for p in extra:
            link=os.path.relpath(p,CATALOG.parent).replace("\\","/")
            lines.append("- ["+p.name+"]("+link+") — "+title(p))
        lines.append("")
    CATALOG.write_text("\n".join(lines),encoding="utf-8",newline="\n")
    return len(md)

def tracked_markdowns():
    listing=subprocess.run(["git","ls-files","--cached","--others","--exclude-standard","-z"],cwd=ROOT,check=True,stdout=subprocess.PIPE).stdout
    paths=set()
    for raw in listing.split(b"\0"):
        if not raw:continue
        p=ROOT/raw.decode("utf-8")
        if p.is_file() and p.suffix.lower()==".md":paths.add(p)
    return sorted(paths)

def verify():
    missing=[]
    markdowns=tracked_markdowns()
    for p in markdowns:
        for m in LINK.finditer(p.read_text(encoding="utf-8",errors="replace")):
            dest=m.group(1).split("#",1)[0].split("?",1)[0].strip().strip("<>")
            if not dest or dest.startswith(("/","//")) or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:",dest):continue
            dest=dest.replace("%20"," ")
            if not (p.parent/dest).exists():missing.append([p.relative_to(ROOT).as_posix(),dest])
    return {"documents_checked":len(markdowns),"broken_links":missing}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--check-only",action="store_true")
    args=parser.parse_args()
    count=0 if args.check_only else generate()
    result=verify()
    print(json.dumps({"catalog_entries":count,**result},ensure_ascii=False,indent=2))
    raise SystemExit(1 if result["broken_links"] else 0)

if __name__=="__main__":
    main()
