"""Scene visual fingerprint: basic camera comparability, not exact game state."""
from io import BytesIO
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.recomp.diagnostics.scene_fingerprint import _fingerprint,compare_scene


class SceneFingerprintTests(unittest.TestCase):
    @staticmethod
    def png(*,shift=0,width=800,height=450,white=False)->bytes:
        from PIL import Image,ImageDraw
        im=Image.new("RGB",(width,height),("white" if white else "#222222"))
        d=ImageDraw.Draw(im)
        if not white:
            d.rectangle([width*.22+shift,height*.30,width*.70+shift,height*.72],fill="#b8a675")
            d.rectangle([width*.38+shift,height*.42,width*.52+shift,height*.66],fill="#332211")
        buf=BytesIO()
        im.save(buf,format="PNG")
        return buf.getvalue()

    def test_identical_scene_is_comparable(self):
        a=_fingerprint(self.png())
        b=_fingerprint(self.png())
        self.assertEqual(a["sha256_png"],b["sha256_png"])
        r=compare_scene(a,b)
        self.assertTrue(r["comparable"])
        self.assertEqual(r["mean_difference_pct"],0)

    def test_mismatch_major_camera_view_rejected(self):
        a=_fingerprint(self.png())
        b=_fingerprint(self.png(white=True))
        r=compare_scene(a,b)
        self.assertFalse(r["comparable"])
        self.assertIn("scene_visual_difference",r["reasons"])

    def test_small_animated_shift_tolerated(self):
        a=_fingerprint(self.png())
        b=_fingerprint(self.png(shift=4))
        self.assertTrue(compare_scene(a,b)["comparable"])

    def test_wrong_resolution_rejected(self):
        a=_fingerprint(self.png())
        b=_fingerprint(self.png(width=1024,height=450))
        self.assertFalse(compare_scene(a,b)["comparable"])
        self.assertIn("resolution_or_orientation_mismatch",
                      compare_scene(a,b)["reasons"])

    def test_unknown_or_invalid_fingerprint_fails_closed(self):
        a=_fingerprint(self.png())
        with self.assertRaises(ValueError):
            compare_scene(a,{"algorithm":"bad"})
        with self.assertRaises(ValueError):
            compare_scene(a,{**a,"gray_32x18":[0]})
        with self.assertRaises(ValueError):
            compare_scene(a,a,max_mean_difference_pct=0)

    def test_png_validation(self):
        with self.assertRaises(ValueError):
            _fingerprint(b"not an image")
        with self.assertRaises(ValueError):
            _fingerprint(b"\x89PNG\r\n\x1a\ntruncated")
        with self.assertRaises(ValueError):
            _fingerprint(self.png(width=100,height=50))


if __name__=="__main__":
    unittest.main()
