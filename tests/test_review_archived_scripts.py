"""Functional classification tests for SHA-guarded historical scripts.

Entirely synthetic fixture archive; no legacy tool is executed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from tools import review_archived_scripts as roles


class First200RoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/".local/catalog").mkdir(parents=True)
        self.manifests=[]
        for batch in (1,2):
            name=(".local/catalog/archived_legacy_scripts_2026-10-15.json"
                  if batch==1 else
                  ".local/catalog/archived_legacy_scripts_2026-10-15_batch02.json")
            self.manifests.append(self.root/name)
        self.entries=[[],[]]
        for index in range(200):
            batch=index//100
            filename=f"phase14_synthetic_{index}.py"
            dest=f".local/profiles/history/scripts/cfg-phase14/{filename}"
            old=f".local/profiles/{filename}"
            p=self.root/dest
            p.parent.mkdir(parents=True,exist_ok=True)
            src=f"# synthetic scenario\nprint({index})\n".encode("utf-8")
            p.write_bytes(src)
            self.entries[batch].append({
                "old":old,"new":dest,"sha256":hashlib.sha256(src).hexdigest(),
                "bytes":len(src),
            })
        self.save_manifests()

    def save_manifests(self):
        for i,p in enumerate(self.manifests):
            p.write_text(json.dumps({"moves":self.entries[i]}),encoding="utf-8")

    def get(self):
        return roles.archive_entries(root=self.root,manifests=tuple(self.manifests))

    def test_both_manifests_review_every_sha(self):
        result=self.get()
        self.assertEqual(len(result),200)
        self.assertEqual({r["batch"] for r in result},{1,2})
        self.assertEqual(len({r["name"] for r in result}),200)

    def test_modified_historical_bytes_refuse_classification(self):
        p=self.root/self.entries[0][0]["new"]
        p.write_bytes(b"different")
        with self.assertRaisesRegex(roles.ReviewError,"SHA/size"):
            self.get()

    def test_duplicate_input_in_two_manifests_fails(self):
        self.entries[1][0]["new"]=self.entries[0][0]["new"]
        self.save_manifests()
        with self.assertRaisesRegex(roles.ReviewError,"Duplicate"):
            self.get()

    def test_project_mutation_is_oneoff(self):
        r=dict(name="phase14e_add_doc.py",path=".local/profiles/history/scripts/a.py",
               batch=1,sha256="a",source='from pathlib import Path\nPath("docs/STATUS.md").write_text("new")\n')
        x=roles.classify(r)
        self.assertEqual(x["role"],"one_off_edit")
        self.assertTrue(x["likely_source_edit"])

    def test_literal_string_replace_is_not_file_write(self):
        r=dict(name="phase14e_report.py",path=".local/profiles/history/scripts/b.py",
               batch=1,sha256="b",
               source='from pathlib import Path\ns=Path("docs/STATUS.md").read_text()\nprint(s.replace("a","b"))\n')
        x=roles.classify(r)
        self.assertEqual(x["role"],"pinned_experiment")
        self.assertFalse(x["writes"])

    def test_pinned_probe_remains_study(self):
        r=dict(name="phase14e_probe.py",path=".local/profiles/history/scripts/c.py",
               batch=1,sha256="c",
               source='import subprocess\nsubprocess.run(["echo","hello"],check=True)\n')
        x=roles.classify(r)
        self.assertEqual(x["role"],"pinned_experiment")
        self.assertTrue(x["has_subprocess"])

    def test_promoted_capability_points_to_canonical_tool(self):
        r=dict(name="phase15_compare_capture_hashes.py",
               path=".local/profiles/history/scripts/d.py",batch=2,
               sha256="22e303b6b49505cdf5330dcc43dd509c4368d8c2474346a7e16ff6ebcdfb9fda",
               source='import hashlib\nfrom pathlib import Path\n'
                      'print(hashlib.sha256(Path("a.perf.data").read_bytes()).hexdigest())\n')
        x=roles.classify(r)
        self.assertEqual(x["role"],"reusable_capability")
        self.assertEqual(x["canonical"],"tools/recomp/diagnostics/profile_evidence.py")

    def test_filename_alone_never_grants_reusable_status(self):
        r=dict(name="phase15_compare_capture_hashes.py",
               path=".local/profiles/history/scripts/d.py",batch=2,sha256="changed",
               source='import hashlib\nprint("not pinned")\n')
        result=roles.classify(r)
        self.assertNotEqual(result["role"],"reusable_capability")

    def test_deterministic_document_contains_complete_catalog(self):
        all_rows=[roles.classify(x) for x in self.get()]
        text=roles.markdown(all_rows)
        self.assertEqual(text.count("(L1)"),100)
        self.assertEqual(text.count("(L2)"),100)
        self.assertIn("200 scripts reales",text)
        self.assertIn("No se ejecutó ningún script",text)


if __name__=="__main__":
    unittest.main()
