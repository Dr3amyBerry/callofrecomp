"""Offline GL4ES patch provenance and exact normalization regression tests."""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/recomp/patch_gl4es.py'
UPSTREAM = ROOT / 'build-android-deps/gl4es'


def functions(source):
    return '\n'.join(re.findall(
        r'void (?:getminmax|normalize)_indices_(?:us|ui)\([^\n]+\) \{.*?\n\}',
        source, re.S))


class PatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('patch_gl4es', SCRIPT)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.source = (ROOT / 'tests/fixtures/gl4es_indices.c').read_text()
        if UPSTREAM.is_dir():
            upstream = subprocess.check_output(
                ['git', '-C', str(UPSTREAM), 'show',
                 cls.module.PINNED_REVISION + ':src/gl/array.c'], text=True)
            if functions(cls.source) != functions(upstream):
                raise AssertionError('GL4ES fixture differs from pinned upstream functions')

    def fixture(self, root):
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        subprocess.run(['git', '-C', str(root), 'config', 'core.autocrlf', 'false'], check=True)
        target = root / 'src/gl/array.c'
        target.parent.mkdir(parents=True)
        target.write_text(functions(self.source) + '\n', newline='\n')
        subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture',
                        '-c', 'user.email=fixture@example.invalid',
                        'commit', '-qm', 'Synthetic normalization fixture'], check=True)
        revision = subprocess.check_output(
            ['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        return target, revision

    def test_apply_idempotent_and_reverse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, revision = self.fixture(root)
            original = target.read_bytes()
            with patch.object(self.module, 'PINNED_REVISION', revision):
                self.assertEqual(self.module.apply_patch(root), 'applied')
                self.assertEqual(self.module.apply_patch(root), 'already applied')
            self.assertEqual(target.read_text().count('if (count > 0 && *min == 0) return;'), 2)
            subprocess.run(['git', '-C', str(root), 'apply', '--reverse',
                            str(self.module.PATCH_FILE)], check=True)
            self.assertEqual(target.read_bytes(), original)

    def test_wrong_revision_and_foreign_changes_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, revision = self.fixture(root)
            original = target.read_bytes()
            with self.assertRaises(RuntimeError):
                self.module.apply_patch(root)
            self.assertEqual(target.read_bytes(), original)
            with patch.object(self.module, 'PINNED_REVISION', revision):
                target.write_bytes(original + b'// unrelated edit\n')
                foreign = target.read_bytes()
                with self.assertRaises(RuntimeError):
                    self.module.apply_patch(root)
                self.assertEqual(target.read_bytes(), foreign)

                target.write_bytes(original)
                self.module.apply_patch(root)
                target.write_bytes(target.read_bytes() + b'// unrelated edit\n')
                foreign = target.read_bytes()
                with self.assertRaises(RuntimeError):
                    self.module.apply_patch(root)
                self.assertEqual(target.read_bytes(), foreign)

    def test_windows_line_endings_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, revision = self.fixture(root)
            target.write_bytes(target.read_bytes().replace(b'\n', b'\r\n'))
            with patch.object(self.module, 'PINNED_REVISION', revision):
                self.assertEqual(self.module.apply_patch(root), 'applied')
                self.assertEqual(self.module.apply_patch(root), 'already applied')
            self.assertNotIn(b'\n', target.read_bytes().replace(b'\r\n', b''))

    def test_partial_patch_and_corrupt_patch_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, revision = self.fixture(root)
            original = target.read_bytes()
            first_anchor = b'    getminmax_indices_us(indices, max, min, count);\n'
            partial = original.replace(first_anchor, first_anchor +
                                       b'    if (count > 0 && *min == 0) return;\n')
            with patch.object(self.module, 'PINNED_REVISION', revision):
                target.write_bytes(partial)
                with self.assertRaises(RuntimeError):
                    self.module.apply_patch(root)
                self.assertEqual(target.read_bytes(), partial)
                target.write_bytes(original)
                bad_patch = root/'invalid.patch'
                bad_patch.write_text('invalid patch\n')
                with patch.object(self.module, 'PATCH_FILE', bad_patch):
                    with self.assertRaises(RuntimeError):
                        self.module.apply_patch(root)
                self.assertEqual(target.read_bytes(), original)

    def test_compiled_real_functions_match(self):
        compiler = os.environ.get('RECOMP_TEST_CC') or shutil.which('cc')
        if not compiler:
            self.skipTest('C compiler unavailable; set RECOMP_TEST_CC')
        baseline = functions(self.source)
        optimized = self.module.optimized_source(baseline.encode()).decode()
        baseline = re.sub(r'\b((?:getminmax|normalize)_indices_(?:us|ui))\b',
                          r'base_\1', baseline)
        harness = r'''
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#include <unistd.h>
#include <sys/resource.h>
#endif
typedef unsigned short GLushort;
typedef unsigned int GLuint;
typedef int GLsizei;
'''+baseline+'\n'+optimized+r'''
static uint32_t rng = 12345;
static uint32_t next(void) { rng = rng * 1664525u + 1013904223u; return rng; }
static int readonly_probe(int baseline, int wide) {
    void *page;
#ifdef _WIN32
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    page=VirtualAlloc(NULL,4096,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!page) return 90;
#else
    struct rlimit limit={0,0}; setrlimit(RLIMIT_CORE,&limit);
    long size=sysconf(_SC_PAGESIZE);
    page=mmap(NULL,(size_t)size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if(page==MAP_FAILED) return 90;
#endif
    if(wide) { GLuint *p=page; p[0]=0; p[1]=1; p[2]=65535; }
    else { GLushort *p=page; p[0]=0; p[1]=1; p[2]=65535; }
#ifdef _WIN32
    DWORD previous;
    if(!VirtualProtect(page,4096,PAGE_READONLY,&previous)) return 91;
#else
    if(mprotect(page,(size_t)size,PROT_READ)) return 91;
#endif
    GLsizei min=-1,max=-1;
    if(wide) {
        if(baseline) base_normalize_indices_ui(page,&max,&min,3);
        else normalize_indices_ui(page,&max,&min,3);
    } else {
        if(baseline) base_normalize_indices_us(page,&max,&min,3);
        else normalize_indices_us(page,&max,&min,3);
    }
    return min==0 && max==65535 ? 0 : 92;
}
int main(int argc, char **argv) {
    if(argc==3) return readonly_probe(atoi(argv[1]),atoi(argv[2]));
    for (int trial=0; trial<20000; ++trial) {
        int n=trial%257;
        GLushort a[257], b[257]; GLuint c[257], d[257];
        for(int i=0;i<n;++i) {
            a[i]=b[i]=(GLushort)next(); c[i]=d[i]=next();
            if(trial%4==0) c[i]=d[i]=next()&0x7fffffffu;
            if(trial%4==1) a[i]=b[i]=65535, c[i]=d[i]=0xffffffffu;
            if(trial%4==2) a[i]=b[i]=0, c[i]=d[i]=0;
        }
        if(n && trial%4==0) a[0]=b[0]=0, c[0]=d[0]=0;
        GLsizei amin=-123,amax=-456,bmin=amin,bmax=amax;
        base_normalize_indices_us(a,&amax,&amin,n);
        normalize_indices_us(b,&bmax,&bmin,n);
        if(amin!=bmin || amax!=bmax || memcmp(a,b,n*sizeof *a)) return 1;
        amin=bmin=-123; amax=bmax=-456;
        base_normalize_indices_ui(c,&amax,&amin,n);
        normalize_indices_ui(d,&bmax,&bmin,n);
        if(amin!=bmin || amax!=bmax || memcmp(c,d,n*sizeof *c)) return 2;
    }
    puts("20000 ushort + 20000 uint cases: identical indices/min/max");
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'normalization.c'
            binary = Path(tmp)/('normalization.exe' if os.name=='nt' else 'normalization')
            source.write_text(harness)
            subprocess.run([compiler, '-D_GNU_SOURCE', '-std=c11', '-O2', str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
            # Child processes isolate the intentional baseline write faults.
            # O0 makes the proof independent of optimizer transformations.
            subprocess.run([compiler, '-D_GNU_SOURCE', '-std=c11', '-O0', str(source), '-o', str(binary)], check=True)
            for wide in ('0', '1'):
                subprocess.run([str(binary), '0', wide], check=True)
                failed = subprocess.run([str(binary), '1', wide], capture_output=True)
                if os.name == 'nt':
                    self.assertEqual(failed.returncode & 0xffffffff, 0xc0000005)
                else:
                    import signal
                    self.assertEqual(failed.returncode, -signal.SIGSEGV)


if __name__ == '__main__':
    unittest.main()
