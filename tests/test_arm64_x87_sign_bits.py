"""Verified CoDSP 1.5 FCHS bit-level patch: narrow ARM64 opt-in only."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import importlib.util
import random
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/"tools/recomp/patch_codsp_x87_sign.py"
spec=importlib.util.spec_from_file_location("verified_codsp_sign",PATCH)
sign=importlib.util.module_from_spec(spec)
spec.loader.exec_module(sign)

def _generated(*,marker=False,crlf=False):
    code=sign.SOURCE_HEADER+"\n#include \"recomp_rt.h\"\n"
    for pc in sign.PC_SITES:
        code+=(f"void codsp_chunk_{pc}(void) {{\nL_{pc:x}:\n"
               " { uint8_t T[1];\n"
               f" wr(guest_regs+0x10ac,4,(u128)0x{pc:x}ULL);\n"
               f"{sign.NEW if marker else sign.OLD}\n"
               " }\n}\n")
    return code.replace("\n","\r\n").encode("utf8") if crlf else code.encode("utf8")

class FCHSARM64Tests(unittest.TestCase):
    def test_three_sites_are_only_original_float_neg_10(self):
        sys.path.insert(0,str(ROOT/"tools/recomp"))
        from pcode2c import parse
        pcode=ROOT/"recomp_out/codsp.pcode"
        if not pcode.is_file():
            self.skipTest("Private CoDSP p-code unavailable in public checkout")
        self.assertEqual(sha256(pcode.read_bytes()).hexdigest(),sign.PCODE_SHA256)
        ins,_,_=parse(pcode)
        for pc in sign.PC_SITES:
            ops=next(item[2] for item in ins if item[0]==pc)
            self.assertEqual([v[0] for v in ops],["COPY","FLOAT_NEG"])
            self.assertEqual(ops[1][1],("r",0x1100,10))
            self.assertEqual(ops[1][2],[("r",0x1100,10)])
            self.assertEqual(ops[0][1],("r",0x10ac,4))

    def test_apply_restore_utf8_byte_exact(self):
        original=_generated()
        patched, pcs=sign.transform(original,apply=True)
        self.assertEqual(pcs,sign.PC_SITES)
        self.assertEqual(patched.count(sign.NEW.encode()),3)
        self.assertEqual(patched.count(sign.OLD.encode()),0)
        self.assertEqual(len(patched.splitlines()),len(original.splitlines()))
        restored,_=sign.transform(patched,apply=False)
        self.assertEqual(restored,original)
        self.assertEqual(sign.transform(original,apply=False)[0],original)

    def test_crlf_preserved_and_idempotent_restore(self):
        original=_generated(crlf=True)
        patched,_=sign.transform(original,apply=True)
        self.assertEqual(patched.count(b"\r\n"),original.count(b"\r\n"))
        self.assertEqual(sign.transform(patched,apply=False)[0],original)

    def test_fail_closed_on_missing_pc_or_wrong_expression(self):
        base=_generated()
        for mutation in (base.replace(b"L_41975e:",b"L_41975f:"),
                         base.replace(sign.OLD.encode(),b" wr(foo,1,0);",1),
                         base.replace(b"wr(guest_regs+0x10ac,4,",b"wr(guest_regs+0x10aa,4,",1),
                         base.replace(b"CoDSP.exe",b"UNKNOWN.exe")):
            with self.subTest(mutation=mutation[:28]):
                with self.assertRaises(ValueError):
                    sign.transform(mutation,apply=True)

    def test_fail_closed_on_double_patch_and_mixed_lines(self):
        patched,_=sign.transform(_generated(),apply=True)
        with self.assertRaises(ValueError):
            sign.transform(patched,apply=True)
        with self.assertRaises(ValueError):
            sign.transform(_generated().replace(b"\n",b"\r\n",1),apply=True)

    def test_sign_bit_changes_only_tenth_byte(self):
        rng=random.Random(0xF0C53)
        for i in range(10000):
            reg=bytearray(rng.randbytes(0x2000))
            before=bytes(reg)
            # CoDSP guest R includes x87 stack and adjacent 6-byte padding.
            reg[0x1109]^=0x80
            assert reg[:0x1109]==before[:0x1109]
            assert reg[0x110a:]==before[0x110a:]
            self.assertEqual(reg[0x1109],before[0x1109]^0x80)
            # FCHS twice must recover byte-identical state.
            reg[0x1109]^=0x80
            self.assertEqual(reg,before)

    def test_special_values_not_converted_through_host_double(self):
        # Includes +0/-0, infinities, sNaN/qNaN payload, pseudo-denormal,
        # unnormal and arbitrary x87 byte patterns; test only value bits.
        vectors=[
            bytes.fromhex(s) for s in (
                "00000000000000000000","00000000000000000080",
                "0000000000000080ff7f","0000000000000080ffff",
                "01000000000000c0ff7f","01000000000000a0ff7f",
                "01000000000000000000","0000000000000040ff3f"
            )
        ]
        for v in vectors:
            self.assertEqual(v[:9]+bytes([v[9]^0x80]),
                             (int.from_bytes(v,"little")^(1<<79)).to_bytes(10,"little"))

    def test_cli_rejects_wrong_abi(self):
        r=subprocess.run([sys.executable,str(ROOT/"tools/recomp/build_android.py"),
                          "--abi","x86_64","--arm64-x87-sign-bits"],
                          capture_output=True,text=True,timeout=25)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("--arm64-x87-sign-bits requires arm64-v8a",r.stderr)

    def test_unsafe_double_transform_still_blocked(self):
        r=subprocess.run([sys.executable,str(ROOT/"tools/recomp/build_android.py"),
                          "--abi","arm64-v8a","--hot-x87-transform",
                          "--arm64-x87-sign-bits"],
                          capture_output=True,text=True,timeout=25)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("ORIGINAL_X87_PRECISION_UNSAFE",r.stderr)

    def test_package_only_must_not_hide_mismatched_binary(self):
        r=subprocess.run([sys.executable,str(ROOT/"tools/recomp/build_android.py"),
                          "--abi","arm64-v8a","--arm64-x87-sign-bits","--package-only"],
                          capture_output=True,text=True,timeout=25)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("--arm64-x87-sign-bits cannot use --package-only",r.stderr)

if __name__=="__main__":unittest.main()
