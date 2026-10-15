"""Synthetic tests for SHA-pinned, reversible CoDSP p4 x87 call-site patch.

No original PE/p-code, generated game instructions, APKs or private trace data.
"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp"))
import patch_codsp_p4_f2d_selective as p4


SOURCE = (
    '#include "recomp_rt.h"\n'
    'void mock_chunk(void) {\n'
    'L_475d80:\n'
    ' { f2d(rd(R+0x1100,10),10); f2d(rd(R+0x1110,10),10);'
    ' f2d(rd(R+0x1120,8),8); }\n'
    'L_475eaa:\n'
    ' { f2d(rd(R+0x1130,10),10); }\n'
    'L_475ebd:\n'
    ' { f2d(rd(R+0x1140,10),10); }\n'
    'L_47bd6d:\n'
    ' { f2d(rd(R+0x1140,10),10); }\n'
    'L_47bd71:\n'
    ' { f2d(rd(R+0x1150,10),10); }\n'
    'L_5070aa:\n'
    ' { f2d(rd(R+0x1160,10),10); }\n'
    '}\n'
)


class P4SelectiveTests(unittest.TestCase):
    def test_guest_range_exact_and_reversible(self):
        candidate, n, labels = p4.patch_text(SOURCE, True)
        self.assertEqual((n, labels), (4, 3))
        self.assertEqual(candidate.count('codsp_x87_normal_f2d('), 4)
        self.assertIn('L_475ebd:\n { f2d(rd(R+0x1140,10),10); }', candidate)
        self.assertIn('L_47bd6d:\n { f2d(rd(R+0x1140,10),10); }', candidate)
        self.assertIn('L_5070aa:\n { f2d(rd(R+0x1160,10),10); }', candidate)
        self.assertIn('f2d(rd(R+0x1120,8),8)', candidate)
        self.assertIn('#undef f2d', candidate)
        self.assertIn('#error "Patched CoDSP p4 requires', candidate)
        restored, inverse, labels = p4.patch_text(candidate, False)
        self.assertEqual(inverse, n)
        self.assertEqual(restored.encode(), SOURCE.encode())

    def test_no_rewrite_of_non_x87_calls(self):
        source = SOURCE.replace('f2d(rd(R+0x1110,10),10)', 'f2d((u128)1,10)')
        result, n, labels = p4.patch_text(source, True)
        self.assertEqual(n, 3)
        self.assertIn('f2d((u128)1,10)', result)

    def test_crlf_byte_reversal(self):
        windows = SOURCE.replace('\n', '\r\n')
        modified, n, _ = p4.patch_text(windows, True)
        self.assertIn('#undef f2d\r\n', modified)
        restored, _, _ = p4.patch_text(modified, False)
        self.assertEqual(restored.encode(), windows.encode())

    def test_duplicate_pc_or_missing_header_fail_closed(self):
        with self.assertRaises(ValueError):
            p4.patch_text(SOURCE + 'L_475d80:\n { f2d(rd(R,10),10); }\n', True)
        with self.assertRaises(ValueError):
            p4.patch_text(SOURCE.replace('#include "recomp_rt.h"', '#include "wrong.h"'), True)

    def test_profiled_pc_set_exact_and_reversible(self):
        # One historically observed PC and an adjacent eligible-but-not-
        # observed guest PC: only the first may receive the fast conversion.
        import codsp_p4_profiled_pcs
        self.assertEqual(len(codsp_p4_profiled_pcs.PROFILED_GUEST_PCS), 124)
        picked = min(codsp_p4_profiled_pcs.PROFILED_GUEST_PCS)
        unpicked = 0x475d80
        self.assertNotIn(unpicked, codsp_p4_profiled_pcs.PROFILED_GUEST_PCS)
        source = (
            '#include "recomp_rt.h"\n'
            f'L_{picked:x}:\n f2d(rd(R+0x1100,10),10);\n'
            f'L_{unpicked:x}:\n f2d(rd(R+0x1110,10),10);\n')
        fast, number, labels = p4.patch_text(source, True, profiled=True)
        self.assertEqual((number, labels), (1, 1))
        self.assertIn('CODRECOMP_X87_NORMAL_F2D_P4_PROFILED', fast)
        self.assertIn('codsp_x87_normal_f2d(rd(R+0x1100,10),10)', fast)
        self.assertIn('f2d(rd(R+0x1110,10),10)', fast)
        restored, removed, touched = p4.patch_text(fast, False, profiled=True)
        self.assertEqual((removed, touched), (1, 1))
        self.assertEqual(restored, source)
        with self.assertRaises(ValueError):
            p4.patch_text(fast, False, profiled=False)

    def test_profiled_mutate_hash_idempotence_and_rejects_other_mode(self):
        import codsp_p4_profiled_pcs
        pc = min(codsp_p4_profiled_pcs.PROFILED_GUEST_PCS)
        source = '#include "recomp_rt.h"\nL_%x:\n f2d(rd(R,10),10);\n' % pc
        fast, n, _ = p4.patch_text(source, True, profiled=True)
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'private.c'
            pcfile = Path(directory) / 'private.pcode'
            file.write_bytes(source.encode())
            pcfile.write_bytes(b'synthetic')
            with mock.patch.object(p4, 'ORIGINAL_SHA256', p4.digest(source.encode())), \
                 mock.patch.object(p4, 'PROFILED_PATCHED_SHA256', p4.digest(fast.encode())), \
                 mock.patch.object(p4, 'PROFILED_EXPECTED_REPLACEMENTS', n), \
                 mock.patch.object(p4, 'PCODE_SHA256', p4.digest(b'synthetic')):
                p4.mutate(file, pcfile, apply=True, profiled=True)
                self.assertEqual(file.read_bytes(), fast.encode())
                p4.mutate(file, pcfile, apply=True, profiled=True)
                with self.assertRaises(ValueError):
                    p4.mutate(file, pcfile, apply=False, profiled=False)
                p4.mutate(file, pcfile, apply=False, profiled=True)
                self.assertEqual(file.read_bytes(), source.encode())

    def test_mutate_enforces_hashes_idempotence_and_atomic_restore(self):
        original = SOURCE.encode('utf-8')
        candidate, n, _ = p4.patch_text(SOURCE, True)
        with tempfile.TemporaryDirectory() as directory:
            src = Path(directory) / 'original.c'
            pcode = Path(directory) / 'guest.pcode'
            src.write_bytes(original)
            pcode.write_bytes(b'not real game pcode')
            with mock.patch.object(p4, 'ORIGINAL_SHA256', p4.digest(original)), \
                 mock.patch.object(p4, 'PATCHED_SHA256', p4.digest(candidate.encode())), \
                 mock.patch.object(p4, 'PCODE_SHA256', p4.digest(pcode.read_bytes())), \
                 mock.patch.object(p4, 'EXPECTED_REPLACEMENTS', n):
                p4.mutate(src, pcode, apply=True)
                self.assertEqual(src.read_bytes(), candidate.encode())
                p4.mutate(src, pcode, apply=True)  # No-op if already patched
                p4.mutate(src, pcode, apply=False)
                self.assertEqual(src.read_bytes(), original)
                p4.mutate(src, pcode, apply=False)  # No-op if restored
                src.write_bytes(original + b'UNEXPECTED')
                with self.assertRaises(ValueError):
                    p4.mutate(src, pcode, apply=True)
                self.assertEqual(src.read_bytes(), original + b'UNEXPECTED')
                pcode.write_bytes(b'corrupt')
                with self.assertRaises(ValueError):
                    p4.mutate(src, pcode, apply=False)
                self.assertFalse(src.with_name(src.name+'.selective.tmp').exists())


if __name__ == '__main__':
    unittest.main()
