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
    if "--jazyky" in sys.argv:
        (root/"vstup.sh").write_text("#!/bin/sh\ntrue\n")
        (root/"web.astro").write_text("---\nconst hello = 1;\n---\n<p>{hello}</p>")
        (root/"dotaz.sql").write_text("SELECT 1;\n")
        (root/"zdroj.go").write_text("package test\nfunc hodnot() int { return 1 }\n")
        (root/"Ukazka.java").write_text("class Ukazka { int hodnota() { return 1; } }\n")
    subprocess.run([sys.executable, gate, root], check=True)
    if "--jazyky" in sys.argv:
        for name, bad in (("web.astro","---\nconst hello = ;\n---\n<p />"), ("vstup.sh","if then"),("dotaz.sql","SELECT FROM;"),
                          ("zdroj.go","package test }"),("Ukazka.java","class Ukazka { ??? }")):
            source = root/name
            original = source.read_bytes()
            source.write_text(bad)
            result = subprocess.run([sys.executable,gate,root],capture_output=True)
            if result.returncode != 1:
                raise SystemExit("Chybný soubor prošel kontrolou: " + name)
            source.write_bytes(original)
    second.write_text('from prvni import vypocet\n\ndef odpoved(n):\n    return vypocet(n-1) if n else 0\n')
    result = subprocess.run([sys.executable,gate,root],capture_output=True,text=True)
    if result.returncode != 1 or not any("Silný cyklus:" in line and "prvni.py" in line and "druhy.py" in line
                                          for line in result.stderr.splitlines()):
        raise SystemExit("AigisCode nepotvrdil očekávaný cyklus mezi oběma soubory")
    print("Stejná brána přijala acyklický zdroj a odmítla obousměrnou závislost.")
