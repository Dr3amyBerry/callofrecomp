"""Run synthetic DLL lifecycle and prove stale native chunks cannot dispatch."""
from pathlib import Path
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix='codrecomp-lifecycle-') as directory:
    fixture = Path(directory) / 'lifecycle.dll'
    subprocess.run([sys.argv[1], str(fixture)], check=True, timeout=20)
    stale = subprocess.run([sys.argv[1], str(fixture), 'stale-call'],
                           capture_output=True, text=True, timeout=20)
    assert stale.returncode == 5, (stale.returncode, stale.stdout, stale.stderr)
    output = stale.stdout + stale.stderr
    assert 'no recompiled code at this address' in output, output
    assert 'unloaded chunk still dispatched' not in output
