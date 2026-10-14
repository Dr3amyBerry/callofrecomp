"""Safety and provenance checks for the standalone ARM64 hot-function audit.

The fixtures are synthetic p-code, not commercial CoD instructions.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools/recomp/diagnostics"))
from audit_hot_function import (
    AuditError, function_metadata, varnode, scan_pcode, op_metrics, audit
)

ENTRY=0x401000

def fixture_map():
    return {
        "functions":[{
            "entry_va":"0x00401000",
            "entry_in_translation":True,
            "body_uniquely_owned_instruction_count":3,
        }],
        "ghidra_body_ranges":[
            {"entry_va":"0x00401000","start_va":"0x00401000",
             "end_va_inclusive":"0x00401004"},
            {"entry_va":"0x00401000","start_va":"0x00401008",
             "end_va_inclusive":"0x0040100a"},
        ],
        "chunks":[{"index":3,"body_ambiguous_instructions":0,
                   "function_entries_in_chunk":["0x00401000","0x00401200"],
                   "body_function_instruction_counts":[
                       {"entry_va":"0x00401000","instruction_count":3}
                   ]}],
    }

CODE="""U 20 floating_synth
I 4198400 2
P INT_ADD r:10:4 r:10:4 c:2:4
P COPY r:0:4 r:10:4
I 4198402 3
P LOAD u:100:4 c:1:4 r:0:4
P STORE - c:1:4 r:4:4 u:100:4
I 4198408 3
P CBRANCH - m:401000:4 r:206:1
P RETURN - c:0:4 r:10:4
I 4198500 1
P COPY r:10:4 c:0:4
"""


class FunctionAuditTests(unittest.TestCase):
    def test_metadata_uses_disjoint_body_and_counts(self):
        ranges,n,chunks=function_metadata(fixture_map(),ENTRY)
        self.assertEqual((ranges,n,chunks),([(0x401000,0x401004),
                                              (0x401008,0x40100a)],3,1))

    def test_reject_ambiguous_shared_chunk(self):
        data=fixture_map()
        data["chunks"][0]["body_ambiguous_instructions"]=1
        with self.assertRaisesRegex(AuditError,"Ambiguous"):
            function_metadata(data,ENTRY)

    def test_reject_overlapping_ranges(self):
        data=fixture_map()
        data["ghidra_body_ranges"][1]["start_va"]="0x00401004"
        with self.assertRaisesRegex(AuditError,"overlap"):
            function_metadata(data,ENTRY)

    def test_reject_entry_not_translated(self):
        data=fixture_map()
        data["functions"][0]["entry_in_translation"]=False
        with self.assertRaisesRegex(AuditError,"not covered"):
            function_metadata(data,ENTRY)

    def test_reject_inconsistent_map_count(self):
        data=fixture_map()
        data["functions"][0]["body_uniquely_owned_instruction_count"]=2
        with self.assertRaisesRegex(AuditError,"contradicts"):
            function_metadata(data,ENTRY)

    def test_decode_spaces_and_widths(self):
        self.assertEqual(varnode("r:20b:1"),("r",0x20b,1))
        self.assertEqual(varnode("u:1100:10"),("u",0x1100,10))
        self.assertIsNone(varnode("-"))
        with self.assertRaises(AuditError):
            varnode("u:100:0")
        with self.assertRaises(AuditError):
            varnode("unknown:100:4")

    def test_stream_only_function_body_and_reject_missing(self):
        with TemporaryDirectory() as tmp:
            f=Path(tmp)/"synthetic.pcode"
            f.write_text(CODE,encoding="utf8")
            instructions=scan_pcode(f,[(0x401000,0x401004),(0x401008,0x40100a)])
            self.assertEqual([i["pc"] for i in instructions],
                             [0x401000,0x401002,0x401008])
            with self.assertRaisesRegex(AuditError,"missing"):
                scan_pcode(f,[(0x500000,0x500004)])

    def test_aggregate_not_instructions_or_source_text(self):
        with TemporaryDirectory() as tmp:
            f=Path(tmp)/"synthetic.pcode"
            f.write_text(CODE,encoding="utf8")
            instructions=scan_pcode(f,[(0x401000,0x401004),(0x401008,0x40100a)])
            samples={
                "samples":8,
                "top":[
                    {"native_pc":"0x100","guest_pc":"0x401000","weight":3},
                    {"native_pc":"0x104","guest_pc":"0x401002","weight":2},
                    {"native_pc":"0x108","guest_pc":"0x555555","weight":3}
                ],
            }
            result=audit(fixture_map(),instructions,samples,ENTRY)
            self.assertEqual(result["original_instructions"],3)
            self.assertEqual(result["samples_in_top_native_sites_only"],5)
            self.assertEqual(result["operation_categories"]["guest_loads"],1)
            self.assertEqual(result["operation_categories"]["guest_stores"],1)
            self.assertEqual(result["operation_categories"]["indirect_exits"],1)
            self.assertTrue(result["chunk_entry_risks"][0]["multiple_entries"])
            self.assertNotIn("INT_ADD r:10:4",str(result))
            self.assertIn("NO safe register-cache patch",result["decision"])

    def test_duplicate_native_site_rejected(self):
        with TemporaryDirectory() as tmp:
            f=Path(tmp)/"synthetic.pcode"
            f.write_text(CODE,encoding="utf8")
            instructions=scan_pcode(f,[(0x401000,0x401004),(0x401008,0x40100a)])
            duplicates={
                "top":[
                    {"native_pc":"0x100","guest_pc":"0x401000","weight":1},
                    {"native_pc":"0x100","guest_pc":"0x401002","weight":1}
                ],
            }
            with self.assertRaisesRegex(AuditError,"Repeated"):
                audit(fixture_map(),instructions,duplicates,ENTRY)


if __name__=="__main__":
    unittest.main()
