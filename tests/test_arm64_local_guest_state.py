"""ARM64 port guards and local guest-state ABI audit (no private game inputs)."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.recomp.diagnostics.audit_local_guest_state import (
    parse_dynamic_exports, compare_exports, ExportAuditError,
)

BUILDER=ROOT/"tools/recomp/build_android.py"
OBJ=("OBJECT","GLOBAL","DEFAULT",8)
REG=("OBJECT","GLOBAL","DEFAULT",16)
FNC=("FUNC","GLOBAL","DEFAULT",48)

class LocalGuestStateARM64Tests(unittest.TestCase):
    def test_export_delta_only_exact_four_symbols(self):
        base={k:OBJ for k in ("R","MEM","U","PC")}
        base.update({"JNI_OnLoad":FNC,"Java_org_callofrecomp_GameActivity_nativeInput":FNC,
                     "guest_run":FNC, "SDL_bridge":FNC})
        after={k:v for k,v in base.items() if k not in ("R","MEM","U","PC")}
        result=compare_exports(base,after)
        self.assertEqual(result["status"],"pass")
        self.assertEqual(result["unchanged_other_exports"],4)

    def test_export_delta_rejects_public_abi_changes(self):
        base={k:OBJ for k in ("R","MEM","U","PC")}
        base.update({"JNI_OnLoad":FNC,"guest_run":FNC})
        good={k:v for k,v in base.items() if k not in ("R","MEM","U","PC")}
        for mutated in (
            {**good,"R":OBJ},
            {**good,"guest_run":("FUNC","GLOBAL","HIDDEN",48)},
            {**good,"new_export":FNC},
            {"JNI_OnLoad":FNC},
        ):
            with self.subTest(candidate=mutated):
                self.assertEqual(compare_exports(base,mutated)["status"],"fail")

    def test_export_delta_requires_original_guest_globals(self):
        base={"JNI_OnLoad":FNC}
        res=compare_exports(base,base)
        self.assertEqual(res["status"],"fail")
        self.assertEqual(len(res["invalid_baseline_guest_objects"]),4)

    def test_parse_realistic_readelf_dynamic_symbols(self):
        text=("\nSymbol table '.dynsym' contains 5 entries:\n"
              " Num: Value Size Type Bind Vis Ndx Name\n"
              "  0: 0000000000 0 NOTYPE LOCAL DEFAULT UND\n"
              "  1: 0000000000 0 FUNC GLOBAL DEFAULT UND memcpy@LIBC\n"
              "  2: 000000f2a8 8 OBJECT GLOBAL DEFAULT 22 MEM\n"
              "  3: 0000004300 64 FUNC GLOBAL DEFAULT 13 JNI_OnLoad\n"
              "  4: 000000a210 18 FUNC GLOBAL DEFAULT 13 guest_run\n")
        x=parse_dynamic_exports(text)
        self.assertEqual(x["MEM"],("OBJECT","GLOBAL","DEFAULT",8))
        self.assertEqual(set(x),{"MEM","JNI_OnLoad","guest_run"})

    def test_parser_rejects_repeated_names_and_empty(self):
        lines=("  1: 0000000001 8 OBJECT GLOBAL DEFAULT 22 MEM\n"
               "  2: 0000000002 8 OBJECT GLOBAL DEFAULT 22 MEM\n")
        with self.assertRaisesRegex(ExportAuditError,"Duplicate"):
            parse_dynamic_exports(lines)
        with self.assertRaisesRegex(ExportAuditError,"No defined"):
            parse_dynamic_exports("  1: 0000000001 8 OBJECT GLOBAL DEFAULT UND MEM\n")

    def test_new_flag_is_strictly_arm64(self):
        result=subprocess.run([sys.executable,str(BUILDER),"--abi","x86_64",
                               "--arm64-local-guest-state"],
                              capture_output=True,text=True,timeout=20)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("--arm64-local-guest-state requires --abi arm64-v8a",
                      result.stderr)

    def test_legacy_wsa_flag_stays_x86_only(self):
        result=subprocess.run([sys.executable,str(BUILDER),"--abi","arm64-v8a",
                               "--local-guest-state"],
                              capture_output=True,text=True,timeout=20)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("--local-guest-state requires --abi x86_64",result.stderr)

    def test_precision_shortcut_remains_blocked_with_arm_flag(self):
        result=subprocess.run([sys.executable,str(BUILDER),
                               "--abi","arm64-v8a","--arm64-local-guest-state",
                               "--hot-x87-transform"],capture_output=True,text=True,timeout=20)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("ORIGINAL_X87_PRECISION_UNSAFE",result.stderr)

    def test_arm64_switch_is_off_in_cmake_and_uses_exact_four_symbol_map(self):
        contents=(ROOT/"android/CMakeLists.txt").read_text(encoding="utf8")
        self.assertIn('option(CODRECOMP_ARM64_LOCAL_GUEST_STATE',contents)
        self.assertIn('state requires arm64-v8a',contents)
        self.assertIn('guest_state.map',contents)
        self.assertIn('CODRECOMP_ARM64_LOCAL_GUEST_STATE',contents)
        version=(ROOT/"android/guest_state.map").read_text(encoding="utf8")
        self.assertIn("local: R; MEM; U; PC;",version)
        self.assertIn("global: *;",version)

if __name__=="__main__":unittest.main()
