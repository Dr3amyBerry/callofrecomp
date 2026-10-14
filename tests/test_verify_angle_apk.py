"""Synthetic verification gates: no device, APK installation or networking."""
from __future__ import annotations
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/recomp/diagnostics"))
from verify_angle_apk import (elf_x86_64_header, inspect_archive,
                              inspect, parse_aapt_badging, parse_apksigner_result)


def stub_elf(arch: int = 62, bits: int = 2) -> bytes:
    return b"\x7fELF" + bytes((bits, 1)) + b"\0" * 12 + arch.to_bytes(2, "little")


def archive(path: Path, abi: str = "x86_64", gles: bool = True,
            arch: int = 62) -> None:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("AndroidManifest.xml", b"synthetic")
        z.writestr(f"lib/{abi}/libEGL_angle.so", stub_elf(arch))
        if gles:
            z.writestr(f"lib/{abi}/libGLESv2_angle.so", stub_elf(arch))


class VerifyAngleApkTests(unittest.TestCase):
    def test_elf_machine_x86_64_only(self):
        self.assertTrue(elf_x86_64_header(stub_elf()))
        self.assertFalse(elf_x86_64_header(stub_elf(183)))
        self.assertFalse(elf_x86_64_header(stub_elf(bits=1)))
        self.assertFalse(elf_x86_64_header(b"not-an-elf"))
    def test_zip_has_expected_abi_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.apk"
            archive(p)
            result = inspect_archive(p)
            self.assertTrue(result["native_elf_headers_valid_x86_64"])
            self.assertEqual(result["native_abis"], ["x86_64"])
            self.assertEqual(len(result["sha256"]), 64)
    def test_missing_gles2_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.apk"
            archive(p, gles=False)
            self.assertFalse(inspect_archive(p)["native_elf_headers_valid_x86_64"])
    def test_wrong_abi_and_wrong_machine_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.apk"
            archive(p, abi="arm64-v8a")
            self.assertFalse(inspect_archive(p)["native_elf_headers_valid_x86_64"])
            archive(p, arch=183)
            self.assertFalse(inspect_archive(p)["native_elf_headers_valid_x86_64"])
    def test_aapt_package_name(self):
        self.assertEqual(parse_aapt_badging("package: name='org.chromium.angle' versionCode='1'"),
                         "org.chromium.angle")
        self.assertIsNone(parse_aapt_badging("garbage"))
    def test_apksigner_requires_verified_scheme_and_exit_code(self):
        s = "Verifies\nVerified using v1 scheme (JAR signing): false\nVerified using v2 scheme (APK Signature Scheme v2): true\n"
        self.assertTrue(parse_apksigner_result(0, s))
        self.assertFalse(parse_apksigner_result(1, s))
        self.assertFalse(parse_apksigner_result(0, "Verifies\nVerified using v2 scheme: false\n"))
    def test_no_android_tools_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.apk"
            archive(p)
            self.assertFalse(inspect(p, None, None)["ready_for_isolated_trial"])
    def test_positive_gate_needs_package_and_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.apk"
            archive(p)
            with patch("verify_angle_apk.verify_with_android_tools",
                       return_value={"package_name":"org.chromium.angle",
                                     "apk_signature_verified":True}):
                result = inspect(p, "aapt", "apksigner")
                self.assertTrue(result["ready_for_isolated_trial"])
                self.assertFalse(result["angle_vulkan_executed"])
                bad = inspect(p, "aapt", "apksigner", "0"*64)
                self.assertFalse(bad["ready_for_isolated_trial"])
    def test_bad_zip_fails_without_guess(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.apk"
            p.write_bytes(b"not an apk")
            with self.assertRaises(zipfile.BadZipFile):
                inspect_archive(p)


if __name__ == "__main__":
    unittest.main()
