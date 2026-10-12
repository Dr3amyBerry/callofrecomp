"""Run the real C runtime against a synthetic file and writable overlay."""
import pathlib
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix="codrecomp-files-") as tmp:
    root = pathlib.Path(tmp)
    install, overlay = root / "install", root / "overlay"
    install.mkdir()
    overlay.mkdir()
    (install / "fixture.pk3").write_bytes(b"PK\x03\x04")
    subprocess.run([sys.argv[1], str(install), str(overlay)], check=True)
