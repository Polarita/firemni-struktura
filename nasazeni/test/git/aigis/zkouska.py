"""Nativní regresní vzorek. Oba stavy mají stejný vstupní bod a žádná síťová volání."""
from pathlib import Path
import subprocess
import sys
import tempfile

gate = Path("/opt/polarita-aigis/kontrola.py")
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)/"src"
    root.mkdir()
    (root/"main.py").write_text('from prvni import vypocet\n\nprint(vypocet(2))\n')
    (root/"prvni.py").write_text('from druhy import odpoved\n\ndef vypocet(n):\n    return odpoved(n-1) if n else 0\n')
    second = root/"druhy.py"
    second.write_text('def odpoved(n):\n    return n + 1\n')
    subprocess.run([sys.executable, gate, root], check=True)
    second.write_text('from prvni import vypocet\n\ndef odpoved(n):\n    return vypocet(n-1) if n else 0\n')
    result = subprocess.run([sys.executable,gate,root],capture_output=True,text=True)
    if result.returncode != 1 or not any("Silný cyklus:" in line and "prvni.py" in line and "druhy.py" in line
                                          for line in result.stderr.splitlines()):
        raise SystemExit("AigisCode nepotvrdil očekávaný cyklus mezi oběma soubory")
    print("Stejná brána přijala acyklický zdroj a odmítla obousměrnou závislost.")
