"""Phase14C/D guarded CFG original-x86 evidence and build policy tests (synthetic)."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from cfg_region_lab import CFGError,Region,generate_region_c,generate_runtime_region_c
from diagnostics.emit_verified_cfg_region import validate_proof
from diagnostics.verify_x86_prefix_oracle import OracleError

PE_SHA="p"*64
PCODE_SHA="c"*64
MAP_SHA="m"*64

def proof():
    return {
        "schema":"phase14c-real-original-x86-exact-RAM-oracle-v1",
        "source_sha256":PE_SHA,
        "pcode_sha256":PCODE_SHA,
        "map_sha256":MAP_SHA,
        "original_start_pc":"0x0041c017",
        "original_exit_pc":"0x00523cd9",
        "original_x86_instructions":29,
        "memory_model":"EXACT guest 32-bit addresses, 24 MiB mapped; no modulo",
        "all_passed":True,
        "cases":40,
        "tested_scenarios":{str(i):{
            "cases":8,
            "guest_pc_and_GPR_and_5_EFLAGS_and_full_R_and_full_RAM_matched":True,
            "read_after_write_alias_cases":8 if i in (1,4) else 0,
        } for i in range(5)},
    }


class OriginalX86EvidenceGate(unittest.TestCase):
    def test_proof_requires_all_five_verified_memory_scenarios(self):
        validate_proof(proof(),PE_SHA,PCODE_SHA,MAP_SHA)
        p=proof()
        del p["tested_scenarios"]["4"]
        with self.assertRaises(OracleError):
            validate_proof(p,PE_SHA,PCODE_SHA,MAP_SHA)

    def test_reject_wrong_hash_version_status_and_case_counts(self):
        mutations=[
            ("source_sha256","0"*64),("pcode_sha256","0"*64),
            ("map_sha256","0"*64),("original_start_pc","0x0041c01b"),
            ("original_exit_pc","0x0041c07f"),("all_passed",False),
            ("cases",39),("original_x86_instructions",28),
            ("memory_model","folded 64KiB")
        ]
        for key,value in mutations:
            with self.subTest(key=key):
                p=proof();p[key]=value
                with self.assertRaises(OracleError):
                    validate_proof(p,PE_SHA,PCODE_SHA,MAP_SHA)

    def test_reject_alias_coverage_and_incomplete_state(self):
        p=proof()
        p["tested_scenarios"]["1"]["read_after_write_alias_cases"]=0
        p["tested_scenarios"]["4"]["read_after_write_alias_cases"]=0
        with self.assertRaisesRegex(OracleError,"alias"):
            validate_proof(p,PE_SHA,PCODE_SHA,MAP_SHA)
        p=proof()
        p["tested_scenarios"]["2"]["guest_pc_and_GPR_and_5_EFLAGS_and_full_R_and_full_RAM_matched"]=False
        with self.assertRaises(OracleError):
            validate_proof(p,PE_SHA,PCODE_SHA,MAP_SHA)
        p=proof();p["tested_scenarios"]["0"]["cases"]=7
        with self.assertRaises(OracleError):
            validate_proof(p,PE_SHA,PCODE_SHA,MAP_SHA)


class RuntimeABITest(unittest.TestCase):
    def test_unpinned_region_cannot_emit_runtime_helper(self):
        for region in (Region(0x004196F0,0x0041c017,()),
                       Region(0x0041B8F0,0x0041c017,())):
            with self.subTest(region=region),self.assertRaises(CFGError):
                generate_runtime_region_c(region)

    def test_lab_memory_models_and_entry_policies_are_explicit(self):
        from test_cfg_region_lab import sample
        from cfg_region_lab import select_block
        original,mapping=sample()
        region=select_block(original,mapping,0x1000,0x1000)
        exact,_=generate_region_c(region,cache_count=1,
            memory_model="exact",entry_policy="start_only")
        folded,_=generate_region_c(region,cache_count=1,
            memory_model="folded64k",entry_policy="all_entries")
        self.assertIn("#define G(a) (MEM + (uint32_t)(a))",exact)
        self.assertNotIn("% UINT32_C",exact)
        self.assertIn("% UINT32_C(65520)",folded)
        self.assertNotIn("case 0x1001u:",exact)
        self.assertIn("case 0x1001u:",folded)
        with self.assertRaises(CFGError):
            generate_region_c(region,memory_model="unknown")

    def test_builder_denies_unsafe_cfg14_even_on_supported_abi(self):
        import subprocess
        import sys
        cmd=[sys.executable,str(ROOT/"tools/recomp/build_android.py"),
             "--cfg14-geom-region","--abi","arm64-v8a","--recomp-opt","1"]
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,2)
        self.assertIn("BLOCKED",result.stderr)
        self.assertIn("page-fault",result.stderr)

    def test_normal_android_build_remains_off_with_original_fallback(self):
        cmake=(ROOT/"android/CMakeLists.txt").read_text(encoding="utf-8")
        guest=(ROOT/"tools/recomp/runtime/guest.c").read_text(encoding="utf-8")
        builder=(ROOT/"tools/recomp/build_android.py").read_text(encoding="utf-8")
        self.assertIn("option(CODRECOMP_CFG14_GEOM_REGION",cmake)
        self.assertIn('0x0041C017 CFG region, OFF" OFF)',cmake)
        self.assertIn("dfd2655e497bbf8fa83ad434244f6a33d1afcccca5308bd413c523919cd19899",cmake)
        self.assertIn("file(SHA256",cmake)
        self.assertIn("cfg14_source_hash",cmake)
        # Phase14D proves the optimization cannot recover correct guest
        # state at 15/18 mid-block page faults; direct CMake ON must refuse.
        self.assertIn("CFG14 FAULT_STATE_UNSAFE",cmake)
        self.assertIn("PC == UINT32_C(0x0041c017)",guest)
        self.assertIn("module_loaded_at(UINT32_C(0x00400000))",guest)
        self.assertIn("codsp_cfg14_geom_41c017()",guest)
        self.assertIn("all_chunks[found].fn();",guest)
        self.assertIn('parser.add_argument("--cfg14-geom-region"',builder)
        self.assertIn('args.cfg14_geom_region and args.abi != "arm64-v8a"',builder)
        self.assertIn('args.cfg14_geom_region and args.recomp_opt != "1"',builder)


if __name__=="__main__":
    unittest.main()
