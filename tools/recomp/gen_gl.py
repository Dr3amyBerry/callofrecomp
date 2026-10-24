#!/usr/bin/env python3
"""Generate runtime/gl_thunks.c: guest (32-bit stdcall) -> host OpenGL wrappers.

Input: Khronos gl.xml and a list of GL function names the engine looks up.
Each wrapper reads its arguments from the guest stack, converts guest
pointers to host pointers and float/double bit patterns to values, and calls
the host GL entry point resolved at context creation.
"""
from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

PTR_INT = {'GLsizeiptr', 'GLintptr', 'GLsizeiptrARB', 'GLintptrARB'}

# When a buffer is bound, GL interprets these arguments as byte offsets.
# The rest of the pointer arguments (textures, matrices, glBufferData, etc.)
# always refer to guest memory and must not use this conversion.
ARRAY_POINTER_SLOTS = {
    'glColorPointer': 3, 'glEdgeFlagPointer': 1, 'glIndexPointer': 2,
    'glInterleavedArrays': 2, 'glNormalPointer': 2, 'glTexCoordPointer': 3,
    'glVertexAttribPointerARB': 5, 'glVertexPointer': 3,
}
ELEMENT_POINTER_SLOTS = {
    'glDrawElements': 3, 'glDrawRangeElements': 5, 'glDrawRangeElementsEXT': 5,
}

# Each event is recorded only in diagnostic builds after a successful GL call.
# The reported counts are guest/bridge calls, not GLES draw submissions.
PERF_EVENTS = {
    'glDrawArrays': ('GL_PERF_DRAW_ARRAYS', 2),
    'glDrawElements': ('GL_PERF_DRAW_ELEMENTS', 1),
    'glDrawRangeElements': ('GL_PERF_DRAW_RANGE', 3),
    'glDrawRangeElementsEXT': ('GL_PERF_DRAW_RANGE', 3),
    'glBindTexture': ('GL_PERF_BIND_TEXTURE', None),
    'glTexImage2D': ('GL_PERF_TEX_IMAGE', None),
    'glTexSubImage2D': ('GL_PERF_TEX_SUBIMAGE', None),
    'glBindBufferARB': ('GL_PERF_BIND_BUFFER', None),
    'glBufferDataARB': ('GL_PERF_BUFFER_DATA', 1),
    'glBufferSubDataARB': ('GL_PERF_BUFFER_SUBDATA', 2),
    'glLockArraysEXT': ('GL_PERF_LOCK_ARRAYS', None),
    'glUnlockArraysEXT': ('GL_PERF_UNLOCK_ARRAYS', None),
    'glActiveTexture': ('GL_PERF_ACTIVE_TEXTURE', None),
    'glActiveTextureARB': ('GL_PERF_ACTIVE_TEXTURE', None),
}


# These are CPU-time measurements of guest GL calls into GL4ES + GLES; they
# do not measure GPU execution or time spent within guest renderer chunks.
TIME_EVENTS = {
    **{name: "GL_TIME_DRAW" for name in (
        "glDrawElements", "glDrawRangeElements", "glDrawRangeElementsEXT", "glDrawArrays")},
    **{name: "GL_TIME_TEXTURE_BIND" for name in (
        "glBindTexture", "glActiveTexture", "glActiveTextureARB")},
    **{name: "GL_TIME_TEXTURE_UPLOAD" for name in (
        "glTexImage2D", "glTexSubImage2D", "glCompressedTexImage2DARB", "glCompressedTexSubImage2DARB")},
    **{name: "GL_TIME_ARRAY_POINTER" for name in (
        "glVertexPointer", "glNormalPointer", "glColorPointer", "glTexCoordPointer",
        "glInterleavedArrays", "glVertexAttribPointerARB")},
    **{name: "GL_TIME_ARRAY_LOCK" for name in ("glLockArraysEXT", "glUnlockArraysEXT")},
    **{name: "GL_TIME_RENDER_STATE" for name in (
        "glEnable", "glDisable", "glBlendFunc", "glDepthMask", "glDepthFunc",
        "glAlphaFunc", "glTexEnvi", "glTexEnvf", "glTexEnvfv", "glTexParameteri",
        "glMatrixMode", "glLoadIdentity", "glLoadMatrixf", "glMultMatrixf",
        "glCullFace", "glShadeModel", "glScissor", "glViewport")},
    **{name: "GL_TIME_BUFFER" for name in (
        "glBindBufferARB", "glBufferDataARB", "glBufferSubDataARB")},
}

# Opt-in redundant-state filter (CODRECOMP_GL_STATE_FILTER, OFF by default).
# Only calls that are idempotent in GL4ES are dropped; see gl_state_filter.h.
# Value = (filter op, number of guest stack arguments passed to the filter).
STATE_FILTER_OPS = {
    'glEnable': ('GL_SF_OP_ENABLE', 1),
    'glDisable': ('GL_SF_OP_DISABLE', 1),
    'glEnableClientState': ('GL_SF_OP_CLIENT_ENABLE', 1),
    'glDisableClientState': ('GL_SF_OP_CLIENT_DISABLE', 1),
    'glBindTexture': ('GL_SF_OP_BIND_TEXTURE', 2),
    'glActiveTexture': ('GL_SF_OP_ACTIVE_TEXTURE', 1),
    'glActiveTextureARB': ('GL_SF_OP_ACTIVE_TEXTURE', 1),
    'glClientActiveTexture': ('GL_SF_OP_CLIENT_ACTIVE_TEXTURE', 1),
    'glClientActiveTextureARB': ('GL_SF_OP_CLIENT_ACTIVE_TEXTURE', 1),
    'glDepthMask': ('GL_SF_OP_DEPTH_MASK', 1),
    'glDepthFunc': ('GL_SF_OP_DEPTH_FUNC', 1),
    'glBlendFunc': ('GL_SF_OP_BLEND_FUNC', 2),
    'glCullFace': ('GL_SF_OP_CULL_FACE', 1),
}
# Calls that can change filtered state behind the filter's back, or make GL4ES
# record instead of execute. They are always forwarded.
STATE_FILTER_EVENTS = {
    'glBegin': 'GL_SF_EV_BEGIN', 'glEnd': 'GL_SF_EV_END',
    'glNewList': 'GL_SF_EV_LIST_BEGIN', 'glEndList': 'GL_SF_EV_LIST_END',
    'glCallList': 'GL_SF_EV_INVALIDATE_ALL', 'glCallLists': 'GL_SF_EV_INVALIDATE_ALL',
    'glPopAttrib': 'GL_SF_EV_INVALIDATE_ALL', 'glPopClientAttrib': 'GL_SF_EV_INVALIDATE_ALL',
    'glDeleteTextures': 'GL_SF_EV_INVALIDATE_ALL',
    'glInterleavedArrays': 'GL_SF_EV_INVALIDATE_CLIENT',
    'glEnableVertexAttribArrayARB': 'GL_SF_EV_INVALIDATE_CLIENT',
    'glDisableVertexAttribArrayARB': 'GL_SF_EV_INVALIDATE_CLIENT',
}

# A separate, OFF-by-default instrumentation build measures inclusive thread
# CPU time inside GL4ES/driver entry points. Timing is never enabled by only
# adding a marker to the normal APK.
TIME_IMPL = r'''
#ifdef CODRECOMP_GL_TIMING
#include "gl_call_timing.h"
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
static gl_time_counters gl_time_window;
static int gl_time_enabled;
static uint64_t gl_time_start_ms;
static uint64_t gl_thread_ns(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &ts)) return 0;
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}
#define GL_TIME_START() (gl_time_enabled ? gl_thread_ns() : 0)
#define GL_TIME_END(kind, start) do { if (gl_time_enabled) {     uint64_t stop = gl_thread_ns();     gl_time_record(&gl_time_window, kind, stop >= (start) ? stop - (start) : 0); } } while (0)
void gl_time_frame(uint64_t now_ms) {
    if (!gl_time_enabled) return;
    gl_time_window.frames++;
    if (!gl_time_start_ms) { gl_time_start_ms = now_ms; return; }
    if (now_ms - gl_time_start_ms < 5000) return;
    const gl_time_counters *s = &gl_time_window;
    printf("gl cpu: frames=%llu draw_calls=%llu draw_us=%llu tex_bind_calls=%llu tex_bind_us=%llu tex_upload_calls=%llu tex_upload_us=%llu array_calls=%llu array_us=%llu lock_calls=%llu lock_us=%llu state_calls=%llu state_us=%llu buffer_calls=%llu buffer_us=%llu\n",
      (unsigned long long)s->frames,
      (unsigned long long)s->events[GL_TIME_DRAW].count, (unsigned long long)(s->events[GL_TIME_DRAW].cpu_ns / 1000),
      (unsigned long long)s->events[GL_TIME_TEXTURE_BIND].count, (unsigned long long)(s->events[GL_TIME_TEXTURE_BIND].cpu_ns / 1000),
      (unsigned long long)s->events[GL_TIME_TEXTURE_UPLOAD].count, (unsigned long long)(s->events[GL_TIME_TEXTURE_UPLOAD].cpu_ns / 1000),
      (unsigned long long)s->events[GL_TIME_ARRAY_POINTER].count, (unsigned long long)(s->events[GL_TIME_ARRAY_POINTER].cpu_ns / 1000),
      (unsigned long long)s->events[GL_TIME_ARRAY_LOCK].count, (unsigned long long)(s->events[GL_TIME_ARRAY_LOCK].cpu_ns / 1000),
      (unsigned long long)s->events[GL_TIME_RENDER_STATE].count, (unsigned long long)(s->events[GL_TIME_RENDER_STATE].cpu_ns / 1000),
      (unsigned long long)s->events[GL_TIME_BUFFER].count, (unsigned long long)(s->events[GL_TIME_BUFFER].cpu_ns / 1000));
    fflush(stdout);
    gl_time_reset(&gl_time_window);
    gl_time_start_ms = now_ms;
}
#else
#define GL_TIME_START() (0ULL)
#define GL_TIME_END(kind, start) ((void)0)
#endif
'''


# Opt-in observer for GL->Vulkan state translation research. These typed
# operations are added at GENERATION time, after forwarding to GL4ES, and
# must never suppress or replace the original OpenGL host call.
# The observer is deliberately fail-closed for states the prototype cannot
# yet translate. It does not make Vulkan the game's renderer.
VK_CAPTURE = {
    'glEnable': ('GLVK_OP_ENABLE', 'ARG(esp, 0)', '0', '0', 'NULL'),
    'glDisable': ('GLVK_OP_DISABLE', 'ARG(esp, 0)', '0', '0', 'NULL'),
    'glDepthFunc': ('GLVK_OP_DEPTH_FUNC', 'ARG(esp, 0)', '0', '0', 'NULL'),
    'glDepthMask': ('GLVK_OP_DEPTH_MASK', 'ARG(esp, 0)', '0', '0', 'NULL'),
    'glBlendFunc': ('GLVK_OP_BLEND_FUNC', 'ARG(esp, 0)', 'ARG(esp, 1)', '0', 'NULL'),
    'glStencilFunc': ('GLVK_OP_STENCIL_FUNC', 'ARG(esp, 0)', 'ARG(esp, 1)',
                      'ARG(esp, 2)', 'NULL'),
    'glStencilOp': ('GLVK_OP_STENCIL_OP', 'ARG(esp, 0)', 'ARG(esp, 1)',
                    'ARG(esp, 2)', 'NULL'),
    'glStencilMask': ('GLVK_OP_STENCIL_MASK', 'ARG(esp, 0)', '0', '0', 'NULL'),
    'glCullFace': ('GLVK_OP_CULL_FACE', 'ARG(esp, 0)', '0', '0', 'NULL'),
    'glFrontFace': ('GLVK_OP_FRONT_FACE', 'ARG(esp, 0)', '0', '0', 'NULL'),
    'glAlphaFunc': ('GLVK_OP_ALPHA_FUNC', 'ARG(esp, 0)', 'ARG(esp, 1)', '0', 'NULL'),
    'glTexEnvi': ('GLVK_OP_TEX_ENV_I', 'ARG(esp, 0)', 'ARG(esp, 1)', 'ARG(esp, 2)', 'NULL'),
    'glTexEnvf': ('GLVK_OP_TEX_ENV_F', 'ARG(esp, 0)', 'ARG(esp, 1)', 'ARG(esp, 2)', 'NULL'),
    'glTexEnviv': ('GLVK_OP_TEX_ENV_IV', 'ARG(esp, 0)', 'ARG(esp, 1)', '0', 'GP(ARG(esp, 2))'),
    'glTexEnvfv': ('GLVK_OP_TEX_ENV_FV', 'ARG(esp, 0)', 'ARG(esp, 1)', '0', 'GP(ARG(esp, 2))'),
    'glActiveTexture': ('GLVK_OP_ACTIVE_TEXTURE', 'ARG(esp, 0)', '0', '0', 'NULL'),
    'glActiveTextureARB': ('GLVK_OP_ACTIVE_TEXTURE', 'ARG(esp, 0)', '0', '0', 'NULL'),
    'glBindTexture': ('GLVK_OP_BIND_TEXTURE', 'ARG(esp, 0)', 'ARG(esp, 1)', '0', 'NULL'),
    'glMatrixMode': ('GLVK_OP_MATRIX_MODE', 'ARG(esp, 0)', '0', '0', 'NULL'),
    'glLoadIdentity': ('GLVK_OP_LOAD_IDENTITY', '0', '0', '0', 'NULL'),
    'glLoadMatrixf': ('GLVK_OP_LOAD_MATRIX_F', '0', '0', '0', 'GP(ARG(esp, 0))'),
    'glMultMatrixf': ('GLVK_OP_MULT_MATRIX_F', '0', '0', '0', 'GP(ARG(esp, 0))'),
    'glLoadMatrixd': ('GLVK_OP_LOAD_MATRIX_D', '0', '0', '0', 'GP(ARG(esp, 0))'),
    'glMultMatrixd': ('GLVK_OP_MULT_MATRIX_D', '0', '0', '0', 'GP(ARG(esp, 0))'),
    'glPushMatrix': ('GLVK_OP_PUSH_MATRIX', '0', '0', '0', 'NULL'),
    'glPopMatrix': ('GLVK_OP_POP_MATRIX', '0', '0', '0', 'NULL'),
}

# Unsupported legacy changes must be VISIBLE in the diagnostic output.
# Observing these does not permit assuming equivalent shaders or texture
# samplers in the Vulkan prototype.
# Each argument is decoded exactly like the forwarded host GL call. Double
# values occupy TWO x86 guest stack slots; float values one.
VK_MATRIX_CALLS = {
    'glTranslatef': ('GLVK_OP_TRANSLATE', 'f', 3),
    'glTranslated': ('GLVK_OP_TRANSLATE', 'd', 3),
    'glScalef': ('GLVK_OP_SCALE', 'f', 3),
    'glScaled': ('GLVK_OP_SCALE', 'd', 3),
    'glRotatef': ('GLVK_OP_ROTATE', 'f', 4),
    'glRotated': ('GLVK_OP_ROTATE', 'd', 4),
    'glFrustum': ('GLVK_OP_FRUSTUM', 'd', 6),
    'glOrtho': ('GLVK_OP_ORTHO', 'd', 6),
}

VK_UNSUPPORTED = {
    'glTexParameteri', 'glTexParameterf', 'glTexParameterfv', 'glTexParameteriv',
    'glTexImage2D', 'glTexSubImage2D',
    'glLightfv', 'glLightf', 'glMaterialfv', 'glMaterialf',
    'glFogf', 'glFogfv', 'glFogi', 'glFogiv',
    'glShadeModel', 'glPolygonMode',
    'glViewport', 'glScissor', 'glDepthRange', 'glColorMaterial',
    'glTexGeni', 'glTexGenf', 'glTexGenfv',
    'glVertexPointer', 'glTexCoordPointer', 'glColorPointer',
    'glNormalPointer', 'glInterleavedArrays',
    'glBindBufferARB', 'glBufferDataARB', 'glBufferSubDataARB',
    'glClipPlane', 'glTexGeniv', 'glTexGend', 'glTexGendv',
}

def vk_legacy_category(name: str) -> str:
    if name.startswith(('glTexEnv', 'glTexGen', 'glTexParameter')):
        return 'GLVK_LEGACY_TEXTURE_STATE'
    if name.startswith(('glTexImage', 'glTexSubImage')):
        return 'GLVK_LEGACY_TEXTURE_UPLOAD'
    if name.startswith(('glTranslate', 'glRotate', 'glScale', 'glFrustum', 'glOrtho')):
        return 'GLVK_LEGACY_MATRIX_TRANSFORM'
    if name in {'glVertexPointer', 'glTexCoordPointer', 'glColorPointer',
                'glNormalPointer', 'glInterleavedArrays'}:
        return 'GLVK_LEGACY_VERTEX_INPUT'
    if name.startswith(('glLight', 'glFog', 'glMaterial')):
        return 'GLVK_LEGACY_LIGHTING_FOG'
    if name.startswith(('glBindBuffer', 'glBufferData', 'glBufferSubData')):
        return 'GLVK_LEGACY_BUFFER'
    return 'GLVK_LEGACY_OTHER'


VK_OBSERVER_IMPL = r"""
#ifdef CODRECOMP_GL_VK_STATE_CAPTURE
#include "gl_vk_state.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static gl_vk_state gl_vk_observer;
static int gl_vk_observer_enabled;
static uint64_t gl_vk_window_start;
#define GL_VK_OBSERVE(op,a,b,c,ptr) do { if (gl_vk_observer_enabled) \
    (void)gl_vk_state_apply(&gl_vk_observer,(op),(a),(b),(c),(ptr)); } while(0)
void gl_vk_capture_frame(uint64_t now_ms) {
    if(!gl_vk_observer_enabled)return;
    if(!gl_vk_window_start){gl_vk_window_start=now_ms;return;}
    if(now_ms-gl_vk_window_start<5000)return;
    const gl_vk_state *s=&gl_vk_observer;
    printf("gl vkstate: tracked=%llu unsupported=%llu mask=0x%x state_ready=%d "
           "mvproj_hash=%08x depth=%u blend=%u stencil=%u alpha=%u "
           "tex0=%u tex1=%u matrix_push=%llu matrix_pop=%llu "
           "legacy_tex=%llu legacy_upload=%llu legacy_matrix=%llu "
           "legacy_vertex=%llu legacy_light=%llu legacy_buffer=%llu legacy_other=%llu\n",
           (unsigned long long)s->supported_calls,
           (unsigned long long)s->unsupported_calls,
           s->unsupported_flags,gl_vk_state_pipeline_ready(s),
           gl_vk_state_matrix_digest(s),
           s->enabled_depth,s->enabled_blend,s->enabled_stencil,s->enabled_alpha,
           s->texture[0].bound_2d,s->texture[1].bound_2d,
           (unsigned long long)s->matrix_pushes,
           (unsigned long long)s->matrix_pops,
           (unsigned long long)s->legacy_categories[GLVK_LEGACY_TEXTURE_STATE],
           (unsigned long long)s->legacy_categories[GLVK_LEGACY_TEXTURE_UPLOAD],
           (unsigned long long)s->legacy_categories[GLVK_LEGACY_MATRIX_TRANSFORM],
           (unsigned long long)s->legacy_categories[GLVK_LEGACY_VERTEX_INPUT],
           (unsigned long long)s->legacy_categories[GLVK_LEGACY_LIGHTING_FOG],
           (unsigned long long)s->legacy_categories[GLVK_LEGACY_BUFFER],
           (unsigned long long)s->legacy_categories[GLVK_LEGACY_OTHER]);
    fflush(stdout);
    gl_vk_window_start=now_ms;
}
#else
#define GL_VK_OBSERVE(op,a,b,c,ptr) ((void)0)
#endif
"""


def classify(param) -> tuple[str, str]:
    """Return argument kind and its native C type."""
    text = ''.join(param.itertext())
    ptype = param.find('ptype')
    t = ptype.text if ptype is not None else 'void'
    if text.count('*') == 2:
        return 'pp', 'void **'
    if '*' in text:
        return 'p', 'void *'
    if t in ('GLdouble', 'GLclampd'):
        return 'd', 'double'
    if t in ('GLfloat', 'GLclampf'):
        return 'f', 'float'
    if t in ('GLint64', 'GLuint64', 'GLint64EXT', 'GLuint64EXT'):
        return 'q', 'long long'
    if t in PTR_INT:
        return 'z', 'intptr_t'
    return 'i', 'int'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('gl_xml', type=Path)
    ap.add_argument('names', type=Path)
    ap.add_argument('-o', '--out', type=Path, required=True)
    args = ap.parse_args()

    root = ET.parse(args.gl_xml).getroot()
    cmds = {c.find('proto').find('name').text: c for c in root.find('commands').findall('command')}
    names = sorted({n.strip() for n in args.names.read_text().split() if n.startswith('gl') and n.strip() in cmds})

    out = ['// Generated by tools/recomp/gen_gl.py from Khronos gl.xml. Do not edit.',
           '#include "gl_thunks.h"', '#include "gl_buffer_pointers.h"', '',
           'static gl_bridge_buffers gl_bindings;', '',
           '#ifdef CODRECOMP_GL_STATE_FILTER',
           '#include "gl_state_filter.h"',
           'static gl_state_filter gl_sf;',
           '#define GL_SF_SKIP(op, a, b) do { if (gl_sf_redundant(&gl_sf, op, a, b)) return 0; } while (0)',
           '#define GL_SF_EVENT(ev) gl_sf_event_apply(&gl_sf, ev)',
           '#else',
           '#define GL_SF_SKIP(op, a, b) ((void)0)',
           '#define GL_SF_EVENT(ev) ((void)0)',
           '#endif', '',
           '#ifdef CODRECOMP_GL_PROFILING',
           '#include "gl_perf_metrics.h"', '#include <stdio.h>', '#include <stdlib.h>',
           'static gl_perf_counters gl_perf_window;',
           'static int gl_perf_enabled;',
           'static uint64_t gl_perf_start_ms;',
           '#define GL_PERF(kind, amount) do { if (gl_perf_enabled) gl_perf_record(&gl_perf_window, kind, amount); } while (0)',
           'void gl_perf_frame(uint64_t now_ms) {',
           '    if (!gl_perf_enabled) return;',
           '    gl_perf_record(&gl_perf_window, GL_PERF_FRAME, 0);',
           '    if (!gl_perf_start_ms) { gl_perf_start_ms = now_ms; return; }',
           '    if (now_ms - gl_perf_start_ms < 5000) return;',
           '    const gl_perf_counters *s = &gl_perf_window;',
           '    printf("gl profile: frames=%llu arrays=%llu elements=%llu ranges=%llu array_verts=%llu indices=%llu tex_bind=%llu tex_image=%llu tex_sub=%llu buf_bind=%llu buf_data_bytes=%llu buf_sub_bytes=%llu lock=%llu unlock=%llu active_tex=%llu\\n",',
           '      (unsigned long long)s->frames, (unsigned long long)s->draw_arrays,',
           '      (unsigned long long)s->draw_elements, (unsigned long long)s->draw_ranges,',
           '      (unsigned long long)s->array_vertices, (unsigned long long)s->index_count,',
           '      (unsigned long long)s->bind_texture, (unsigned long long)s->tex_image,',
           '      (unsigned long long)s->tex_subimage, (unsigned long long)s->bind_buffer,',
           '      (unsigned long long)s->bytes_buffer_data, (unsigned long long)s->bytes_buffer_subdata,',
           '      (unsigned long long)s->lock_arrays, (unsigned long long)s->unlock_arrays,',
           '      (unsigned long long)s->active_texture);',
           '    fflush(stdout);',
           '    gl_perf_reset(&gl_perf_window); gl_perf_start_ms = now_ms;',
           '}',
           '#else',
           '#define GL_PERF(kind, amount) ((void)0)',
           '#endif', '']
    out.extend(TIME_IMPL.strip().splitlines())
    out.append('')
    out.extend(VK_OBSERVER_IMPL.strip().splitlines())
    out.append('')
    table = []
    for n in names:
        c = cmds[n]
        proto = c.find('proto')
        ret = ''.join(proto.itertext()).replace(n, '').strip()
        params = [classify(p) for p in c.findall('param')]
        ret_kind = 'void' if ret == 'void' else ('ptr' if '*' in ret else 'int')
        host_ret = {'void': 'void', 'ptr': 'const void *', 'int': 'unsigned int'}[ret_kind]
        proto_args = ', '.join(t for _, t in params) or 'void'
        out.append(f'typedef {host_ret} (GLAPI_CALL *pfn_{n})({proto_args});')
        out.append(f'static pfn_{n} p_{n};')
        call, slot, pointer_outputs = [], 0, []
        for kind, _ in params:
            if kind == 'pp':
                call.append(f'&pointer_{slot}')
                pointer_outputs.append(slot)
            elif kind == 'p':
                if ARRAY_POINTER_SLOTS.get(n) == slot:
                    call.append(f'gl_bridge_arg(&gl_bindings, GL_BRIDGE_ARRAY_BUFFER, MEM, ARG(esp, {slot}))')
                elif ELEMENT_POINTER_SLOTS.get(n) == slot:
                    call.append(f'gl_bridge_arg(&gl_bindings, GL_BRIDGE_ELEMENT_ARRAY_BUFFER, MEM, ARG(esp, {slot}))')
                else:
                    call.append(f'GP(ARG(esp, {slot}))')
            elif kind == 'f':
                call.append(f'F32(ARG(esp, {slot}))')
            elif kind == 'd':
                call.append(f'F64(esp, {slot})')
                slot += 1
            elif kind == 'q':
                call.append(f'(long long)rd(G(esp + 4 + 4 * {slot}), 8)')
                slot += 1
            elif kind == 'z':
                call.append(f'(intptr_t)(int32_t)ARG(esp, {slot})')
            else:
                call.append(f'(int)ARG(esp, {slot})')
            slot += 1
        invoke = f'p_{n}({", ".join(call)})'
        body = f'    if (!p_{n}) gl_missing("{n}");\n'
        if n in STATE_FILTER_OPS:
            op, count = STATE_FILTER_OPS[n]
            second = 'ARG(esp, 1)' if count > 1 else '0'
            body += f'    GL_SF_SKIP({op}, ARG(esp, 0), {second});\n'
        if n in STATE_FILTER_EVENTS:
            body += f'    GL_SF_EVENT({STATE_FILTER_EVENTS[n]});\n'
        body += ''.join(f'    void *pointer_{s} = NULL;\n' for s in pointer_outputs)
        if n == 'glGetString':
            body += f'    return gl_guest_string((unsigned int)ARG(esp, 0), {invoke});'
        elif ret_kind == 'void':
            if n in TIME_EVENTS:
                body += '    const uint64_t gl_start_ns = GL_TIME_START();\n'
            body += f'    {invoke};\n'
            if n in TIME_EVENTS:
                body += f'    GL_TIME_END({TIME_EVENTS[n]}, gl_start_ns);\n'
            if n in VK_MATRIX_CALLS:
                op, kind, count = VK_MATRIX_CALLS[n]
                arguments = [
                    (f'(double)F32(ARG(esp, {i}))' if kind == 'f' else
                     f'F64(esp, {i * 2})')
                    for i in range(count)
                ]
                # Wrap compound literal in parentheses so the comma-separated
                # initializer stays a single C macro argument.
                arguments.extend(['0.0'] * (6 - count))
                vector = '((const double[6]){' + ', '.join(arguments) + '})'
                body += f'    GL_VK_OBSERVE({op}, 0, 0, 0, {vector});\n'
            elif n in VK_CAPTURE or n in VK_UNSUPPORTED:
                if n in VK_CAPTURE:
                    op, a, b, c, ptr = VK_CAPTURE[n]
                else:
                    op, a, b, c, ptr = ('GLVK_OP_UNSUPPORTED_STATE',
                                         vk_legacy_category(n), '0', '0', 'NULL')
                body += f'    GL_VK_OBSERVE({op}, {a}, {b}, {c}, {ptr});\n'
            if n in PERF_EVENTS:
                event, idx = PERF_EVENTS[n]
                size = (f'((int32_t)ARG(esp, {idx}) > 0 ? ARG(esp, {idx}) : 0)'
                        if idx is not None else '0')
                body += f'    GL_PERF({event}, {size});\n'
            if n == 'glBindBufferARB':
                body += '    gl_bridge_bind(&gl_bindings, ARG(esp, 0), ARG(esp, 1));\n'
            if n == 'glDeleteBuffersARB':
                body += ('    gl_bridge_delete_many(&gl_bindings, (int)ARG(esp, 0), '
                         '(const uint32_t *)GP(ARG(esp, 1)));\n')
            body += ''.join(f'    gl_guest_pointer(ARG(esp, {s}), pointer_{s});\n' for s in pointer_outputs)
            body += '    return 0;'
        elif ret_kind == 'ptr':
            body += f'    gl_missing("{n} (pointer result)");\n    return 0;'
        else:
            body += f'    return {invoke};'
        out.append(f'static uint32_t t_{n}(uint32_t esp) {{\n    (void)esp;\n{body}\n}}')
        out.append('')
        table.append((n, slot * 4))

    out.append('const thunk_def gl_thunks[] = {')
    out.extend(f'    {{"opengl32.dll", "{n}", t_{n}, {pop}}},' for n, pop in table)
    out.append('    {0, 0, 0, 0},')
    out.append('};')
    out.append('')
    out.append('void gl_load(void *(*getproc)(const char *)) {')
    out.append('    gl_bridge_reset(&gl_bindings);')
    out.append('    GL_SF_EVENT(GL_SF_EV_RESET);')
    out.extend(['#ifdef CODRECOMP_GL_PROFILING',
                '    gl_perf_enabled = getenv("CODRECOMP_GL_STATS") != NULL;',
                '    gl_perf_start_ms = 0;',
                '    gl_perf_reset(&gl_perf_window);',
                '#endif'])
    out.extend(['#ifdef CODRECOMP_GL_VK_STATE_CAPTURE',
                '    const char *vk_capture_env = getenv("CODRECOMP_GL_VK_CAPTURE");',
                '    gl_vk_observer_enabled = !vk_capture_env || strcmp(vk_capture_env, "0") != 0;',
                '    gl_vk_window_start = 0;',
                '    gl_vk_state_reset(&gl_vk_observer);',
                '#endif'])
    out.extend(['#ifdef CODRECOMP_GL_TIMING',
                '    gl_time_enabled = getenv("CODRECOMP_GL_TIME") != NULL;',
                '    gl_time_start_ms = 0;',
                '    gl_time_reset(&gl_time_window);',
                '#endif'])
    out.extend(f'    p_{n} = (pfn_{n})getproc("{n}");' for n, _ in table)
    out.append('}')
    args.out.write_text('\n'.join(out) + '\n', newline='\n')
    print(f'{len(table)} GL wrappers -> {args.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
