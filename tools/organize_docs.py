#!/usr/bin/env python3
"""Organización conservadora de la documentación: previsualizar primero, --apply después."""
from pathlib import Path
from collections import defaultdict
from urllib.parse import unquote
import argparse, os, re, json, subprocess, shutil, hashlib

ROOT = Path(__file__).resolve().parents[1]
KEEP = {'INDEX.md', 'PROJECT_STATUS.md','ROADMAP.md','PERFORMANCE_STRATEGY_CURRENT.md','OPTIMIZATION_LEDGER.md','WORKSPACE.md','TECNO_REVALIDATION.md'}
GUIDES = {'ANALYSIS_TOOLS.md','ANDROID_BUILD.md','ANDROID_PERFORMANCE.md','AUDIO_BRIDGE.md','CAMPAIGN_VERIFICATION.md','FRAME_PACING.md','LEGACY_FS_BRIDGE.md','MANUAL_PLAYTEST.md','PACKAGE_FORMAT.md','RECOMP_CLOCKS.md','RECOMP_MEMORY.md','REFERENCE_SOURCES.md','SYMBOL_LEDGER.md'}

def category(name):
    if name in KEEP: return None
    if name in GUIDES: return 'guides'
    if name.startswith('RELEASE_NOTES_'): return 'history/releases'
    if name.startswith('PROJECT_STATUS_CHECKPOINT') or name == 'PERFORMANCE_DEEP_DIVE_2026-10-13.md': return 'history/checkpoints'
    if name.startswith(('ANGLE_','MESA_','WSA_VULKAN_','WSA_GL_','GL_VK_','RENDER_TRANSLATION_','HUD_')): return 'performance/graphics'
    if name.startswith('PHASE14'): return 'performance/cfg'
    if name.startswith('WSA'): return 'performance/wsa'
    if name.startswith(('TECNO_','ARM64_','CPU_PHASE','PHASE15','PERFORMANCE_STRATEGY_RUN')): return 'performance/tecno'
    if name.startswith(('FUNCTION_LEVEL_','CODSP_')): return 'performance/cpu'
    raise ValueError('Unclassified documentation: '+name)

def tracked_files():
    out=subprocess.run(['git','ls-files','-z'],cwd=ROOT,check=True,stdout=subprocess.PIPE).stdout
    return [x.decode('utf-8') for x in out.split(b'\0') if x]

def is_native(target):
    return bool(re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',target)) or target.startswith(('//','/'))

MD_LINK = re.compile(r'(?<!!)(\[[^\]]+\]\()([^)]+)(\))')

def check_links(documents):
    bad=[]
    for path,txt in documents.items():
        for m in MD_LINK.finditer(txt):
            dest=m.group(2).split('#',1)[0].split('?',1)[0].strip().strip('<>')
            if not dest or is_native(dest): continue
            found=(ROOT / path).parent / unquote(dest)
            if not found.exists():bad.append([path,dest])
    return bad

def create_mapping():
    mapping={}
    for p in (ROOT/'docs').glob('*.md'):
        group=category(p.name)
        if group: mapping['docs/'+p.name]='docs/'+group+'/'+p.name
    if not (ROOT/'docs/history/PROGRESS_LOG.md').exists():
        mapping['PROGRESS.md']='docs/history/PROGRESS_LOG.md'
    return mapping

def convert_text(old,new,content,mapping):
    def change(m):
        raw=m.group(2)
        if is_native(raw):return m.group(0)
        path,hashmark,frag=raw.partition('#')
        query=''
        if '?' in path:
            path,query=path.split('?',1);query='?'+query
        if not path:return m.group(0)
        left=path.strip('<>')
        absolute=os.path.normpath(os.path.join(os.path.dirname(old),unquote(left))).replace('\\','/')
        target=mapping.get(absolute,absolute)
        if target==absolute and old==new:return m.group(0)
        rel=os.path.relpath(ROOT/target,ROOT/Path(new).parent).replace('\\','/')
        return m.group(1)+rel+query+(hashmark+frag if hashmark else '')+m.group(3)
    content=MD_LINK.sub(change,content)
    # Explicit repo-root paths outside Markdown links (docs/... in code or backticks).
    for oldpath,newpath in sorted(mapping.items(),key=lambda item:-len(item[0])):
        if oldpath.startswith('docs/'):
            content=content.replace(oldpath,newpath)
    return content

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()
    mapping=create_mapping()
    versions=tracked_files()
    paths=set(versions)|{'docs/OPTIMIZATION_LEDGER.md'}
    originals={}
    for name in paths:
        p=ROOT/name
        if not p.is_file() or p.suffix.lower() not in {'.md','.py','.yml','.yaml','.json','.ps1','.sh','.xml','.txt','.mjs','.js','.cmake'}:continue
        try:originals[name]=p.read_text(encoding='utf-8')
        except UnicodeError:continue
    before=check_links({p:s for p,s in originals.items() if p.endswith('.md')})
    if before:
        print('WARNING existing broken links:',len(before),before[:12])
    result={}
    for path,data in originals.items():
        new=mapping.get(path,path)
        newtext=convert_text(path,new,data,mapping)
        if path!=new or newtext!=data:result[path]=(new,newtext)
    report={'moving_files':mapping,'updated_text_files':len(result),'existing_broken_links':before[:30],'mode':'apply' if args.apply else 'dry-run'}
    manifest=ROOT/'.local/catalog/docs_reorganization_manifest_2026-10-15.json'
    manifest.parent.mkdir(parents=True,exist_ok=True)
    manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if not args.apply:
        print(json.dumps({'mode':'DRY','moves':len(mapping),'text_files_updated':len(result),'old_broken_links':len(before),'counts_by_destination':{k:len([x for x in mapping.values() if x.startswith('docs/'+k+'/')]) for k in ['guides','performance/wsa','performance/tecno','performance/cpu','performance/cfg','performance/graphics','history/checkpoints','history/releases']}},indent=2))
        return
    # Retain original file bytes under private .local before modifying any tracked path.
    backup=ROOT/'.local/catalog/pre_migration_text'
    for name in result:
        src=ROOT/name;dst=backup/name
        dst.parent.mkdir(parents=True,exist_ok=True)
        if not dst.exists():shutil.copy2(src,dst)
    for old,new in mapping.items():
        a,b=ROOT/old,ROOT/new
        if b.exists():raise RuntimeError('Destination already exists: '+new)
        b.parent.mkdir(parents=True,exist_ok=True)
    for old,new in mapping.items():
        (ROOT/old).rename(ROOT/new)
    for old,(new,data) in result.items():
        (ROOT/new).write_text(data,encoding='utf-8',newline='\n')
    pointer='''# Progreso y continuidad\n\nLa documentación operativa actual está en [estado](docs/PROJECT_STATUS.md), [roadmap](docs/ROADMAP.md), [registro de optimizaciones](docs/OPTIMIZATION_LEDGER.md) y [objetivo TECNO vigente](docs/TECNO_REVALIDATION.md).\n\nLa bitácora histórica completa, sin recortar experimentos, está en [PROGRESS_LOG](docs/history/PROGRESS_LOG.md). Los hitos pasados no sustituyen al estado vigente.\n'''
    (ROOT/'PROGRESS.md').write_text(pointer,encoding='utf-8',newline='\n')
    print(json.dumps({'mode':'APPLIED','moved':len(mapping),'rewritten':len(result),'backup':str(backup)},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
