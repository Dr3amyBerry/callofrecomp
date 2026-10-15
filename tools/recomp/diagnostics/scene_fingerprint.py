#!/usr/bin/env python3
"""Small read-only scene-comparability fingerprint for Android gameplay captures.

One PNG per stage is enough for a coarse check that the A/B camera view and
rendered workload do not obviously differ. Measures central scene appearance,
excluding most HUD/borders. It is NOT a guarantee of identical game state,
camera coordinates, draw calls, GPU work or full functional equivalence.

Use identical physical orientation, graphics configuration, UI scaling, game
scene and save. Reject missing/unreadable PNGs rather than inventing a match.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

# Pillow is deliberately imported lazily: ordinary FPS log analysis should
# continue working on hosts that do not install image dependencies.


def _fingerprint(raw: bytes) -> dict:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as err:
        raise RuntimeError("Pillow required for PNG visual comparison") from err
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Expected a PNG screenshot")
    try:
        with Image.open(BytesIO(raw)) as input_image:
            if input_image.format != "PNG":
                raise ValueError("Not a PNG image")
            if input_image.width < 200 or input_image.height < 100:
                raise ValueError("Screenshot resolution too small")
            image = input_image.convert("RGB")
    except (OSError, UnidentifiedImageError, ValueError) as err:
        raise ValueError("Unreadable PNG screenshot") from err
    width,height=image.size
    # Scene-dominant center avoids navigation and large HUD edges. The crop
    # is defined in fractions to remain orientation-scale independent.
    crop=(int(width*.18),int(height*.20),int(width*.82),int(height*.78))
    scene=image.crop(crop)
    from PIL import Image
    gray=list(scene.convert("L").resize((32,18),resample=Image.Resampling.BILINEAR).getdata())
    # Coarse visible geometry fingerprint, 576 grayscale samples.
    # Maintain exact sample array in PRIVATE run reports; don't publish images.
    return {
        "size":[width,height],
        "crop":list(crop),
        "gray_32x18":gray,
        "sha256_png":sha256(raw).hexdigest(),
        "mean_luma":round(sum(gray)/len(gray),3),
        "algorithm":"center_gray_32x18_v1",
    }


def compare_scene(reference:dict, current:dict, *,max_mean_difference_pct:float=12.0)->dict:
    if not 0 < max_mean_difference_pct <= 100:
        raise ValueError("Invalid visual threshold")
    if reference.get("algorithm")!="center_gray_32x18_v1" or current.get("algorithm")!=reference.get("algorithm"):
        raise ValueError("Unknown scene algorithm")
    if reference.get("size")!=current.get("size"):
        return {"comparable":False,"reasons":["resolution_or_orientation_mismatch"]}
    a=reference.get("gray_32x18")
    b=current.get("gray_32x18")
    if not isinstance(a,list) or not isinstance(b,list) or len(a)!=576 or len(b)!=576:
        raise ValueError("Invalid fingerprint array")
    if not all(isinstance(x,int) and 0<=x<=255 for x in a+b):
        raise ValueError("Invalid fingerprint pixels")
    difference=100.0*sum(abs(x-y) for x,y in zip(a,b))/(576*255)
    return {
        "comparable":difference<=max_mean_difference_pct,
        "reasons":[] if difference<=max_mean_difference_pct else ["scene_visual_difference"],
        "mean_difference_pct":round(difference,4),
        "allowed_difference_pct":max_mean_difference_pct,
        "note":"Coarse visual check only; not proof of identical 3D camera/state",
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reference",type=Path,required=True)
    parser.add_argument("--capture",type=Path,required=True)
    parser.add_argument("--max-difference-pct",type=float,default=12.0)
    parser.add_argument("--out",type=Path,help="private JSON destination (create-only)")
    args=parser.parse_args(argv)
    try:
        ref=_fingerprint(args.reference.read_bytes())
        current=_fingerprint(args.capture.read_bytes())
        result=compare_scene(ref,current,max_mean_difference_pct=args.max_difference_pct)
        result.update({
          "reference_png_sha256":ref["sha256_png"],
          "candidate_png_sha256":current["sha256_png"],
          "resolution":current["size"],
          "algorithm":current["algorithm"],
        })
        output=json.dumps(result,indent=2)+"\n"
        if args.out:
            with args.out.open("x",encoding="utf8") as f:f.write(output)
        print(output,end="")
        return 0 if result["comparable"] else 1
    except (OSError,ValueError,RuntimeError) as err:
        parser.exit(2,"SCENE_FINGERPRINT_ERROR: "+str(err)+"\n")


if __name__=="__main__":
    raise SystemExit(main())
