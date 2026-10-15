"""Synthetic tests for overlap-aware inline CPU sample classification."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools/recomp/diagnostics"))
from inline_profile_overlap import summarize

class InlineProfileOverlapTests(unittest.TestCase):
    def test_overlapping_tags_do_not_double_count_leaf(self):
        result=summarize([
            {"samples":3,"guest_pc":0x470000,"frames":["memcpy","rd","f2d","outer"]},
            {"samples":2,"guest_pc":0x470010,"frames":["rd","outer"]},
            {"samples":4,"guest_pc":0x470020,"frames":["other","wr"]},
            {"samples":1,"guest_pc":0x470030,"frames":["outer"]},
        ])
        self.assertEqual(result["resolved_samples"],10)
        self.assertEqual(result["inclusive_inline_samples"]["memcpy"],3)
        self.assertEqual(result["inclusive_inline_samples"]["rd"],5)
        self.assertEqual(result["inclusive_inline_samples"]["wr"],4)
        self.assertEqual(result["innermost_named_inline_frame_samples"]["memcpy"],3)
        self.assertEqual(result["innermost_named_inline_frame_samples"]["rd"],2)
        self.assertEqual(result["innermost_named_inline_frame_samples"]["wr"],4)
        self.assertEqual(result["innermost_named_inline_frame_samples"]["other"],1)
        self.assertEqual(result["pairwise_overlaps"]["f2d+memcpy"],3)
        self.assertEqual(result["pairwise_overlaps"]["memcpy+rd"],3)
        self.assertEqual(result["top_guest_pc_by_innermost_frame"]["memcpy"],[["0x470000",3]])

    def test_sum_and_duplicated_frame_names(self):
        result=summarize([{"samples":6,"guest_pc":0x11,"frames":["rd","rd","memcpy"]}])
        self.assertEqual(result["resolved_samples"],6)
        self.assertEqual(result["inclusive_inline_samples"]["rd"],6)
        self.assertEqual(result["pairwise_overlaps"]["memcpy+rd"],6)

    def test_empty_and_invalid(self):
        self.assertEqual(summarize([])["resolved_samples"],0)
        for row in (
            {"samples":0,"guest_pc":1,"frames":[]},
            {"samples":1,"guest_pc":-1,"frames":[]},
            {"samples":1,"guest_pc":1,"frames":"rd"},
            {"samples":1,"guest_pc":1,"frames":[None]},
        ):
            with self.assertRaises(ValueError):
                summarize([row])

if __name__=="__main__":
    unittest.main()
