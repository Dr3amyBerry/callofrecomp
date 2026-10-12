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
    (overlay / "temp.svg").write_bytes(b"new autosave content")
    (overlay / "autosave.svg").write_bytes(b"old")
    subprocess.run([sys.argv[1], str(install), str(overlay)], check=True)
    assert (overlay / "autosave.svg").read_bytes() == b"new autosave content"
    assert not (overlay / "temp.svg").exists()
