"""Generated GL wrappers must retain context-dependent byte-offset semantics."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/recomp/gen_gl.py'
# Minimal synthetic Khronos registry, never a shipped game asset.
COMMANDS = {
    'glBindBufferARB': [('GLenum', 'target'), ('GLuint', 'buffer')],
    'glDeleteBuffersARB': [('GLsizei', 'n'), ('GLuint *', 'buffers')],
    'glDrawElements': [('GLenum', 'mode'), ('GLsizei', 'count'),
                       ('GLenum', 'type'), ('void *', 'indices')],
    'glVertexPointer': [('GLint', 'size'), ('GLenum', 'type'),
                        ('GLsizei', 'stride'), ('void *', 'pointer')],
    'glTexImage2D': [('GLenum', 'target'), ('GLint', 'level'),
                     ('GLint', 'internalformat'), ('GLsizei', 'width'),
                     ('GLsizei', 'height'), ('GLint', 'border'), ('GLenum', 'format'),
                     ('GLenum', 'type'), ('void *', 'pixels')],
    'glBufferDataARB': [('GLenum', 'target'), ('GLsizeiptr', 'size'),
                        ('void *', 'data'), ('GLenum', 'usage')],
}

def xml_source():
    body=[]
    for name, params in COMMANDS.items():
        args = ''.join(
            '<param>' + ('<ptype>' + kind.replace('*','').strip() + '</ptype> *'
                        if '*' in kind else '<ptype>' + kind + '</ptype> ')
            + '<name>' + arg + '</name></param>'
            for kind,arg in params)
        body.append('<command><proto><ptype>void</ptype> <name>'+name+'</name></proto>'+args+'</command>')
    return '<registry><commands>' + ''.join(body) + '</commands></registry>'

class GLGenerationTest(unittest.TestCase):
    def test_generated_wrappers_preserve_buffer_offsets_and_profile_hooks(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); xml=root/'gl.xml'; names=root/'names.txt'; dst=root/'out.c'
            xml.write_text(xml_source())
            names.write_text('\n'.join(COMMANDS))
            subprocess.run([sys.executable,str(SCRIPT),str(xml),str(names),'-o',str(dst)],
                           check=True, capture_output=True)
            s=dst.read_text()
            self.assertIn('gl_bridge_arg(&gl_bindings, GL_BRIDGE_ELEMENT_ARRAY_BUFFER, MEM, ARG(esp, 3))',s)
            self.assertIn('gl_bridge_arg(&gl_bindings, GL_BRIDGE_ARRAY_BUFFER, MEM, ARG(esp, 3))',s)
            self.assertIn('p_glTexImage2D((int)',s)
            self.assertIn('GP(ARG(esp, 8))',s) # texture pixels stay memory pointers
            self.assertIn('gl_bridge_delete_many(&gl_bindings',s)
            self.assertIn('gl_bridge_reset(&gl_bindings);',s)
            self.assertIn('GL_PERF(GL_PERF_DRAW_ELEMENTS',s)
            self.assertIn('GL_PERF(GL_PERF_TEX_IMAGE',s)
            self.assertIn('gl_perf_enabled = getenv("CODRECOMP_GL_STATS") != NULL;',s)

if __name__ == '__main__':
    unittest.main()
