#!/bin/bash
# Ověřený nástroj pro uzamčené instalace Pythonu ve firemní VM.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 && $(uname -m) == x86_64 ]]
cache=/var/cache/polarita-uv
install -dm0700 "$cache"
exec 8>"$cache/.priprava"
flock 8
url=https://files.pythonhosted.org/packages/3d/aa/26d64642d808de4a652579ef950d7cd2d37f080a8babf9c67c6b75fc4c3f/uv-0.13.9-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
sum=d7f459fe4fd247d830351c75686d3996ace3c6f3f728eb0e85a30b7ada0cef19
wheel=$cache/uv-0.13.9.whl
if ! echo "$sum  $wheel" | sha256sum --status -c - 2>/dev/null; then
    curl --fail --retry 3 --max-time 120 --proto '=https' -LsS "$url" -o "$wheel.part"
    echo "$sum  $wheel.part" | sha256sum --status -c -
    mv -T "$wheel.part" "$wheel"
fi
python3 - "$wheel" "$cache/uv-0.13.9" <<'PY'
from zipfile import ZipFile
from pathlib import Path
import os,sys,tempfile
target=Path(sys.argv[2])
with ZipFile(sys.argv[1]) as z:
    data=z.read(next(n for n in z.namelist() if n.endswith("/scripts/uv")))
if not target.exists() or target.read_bytes()!=data:
    with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as out:
        out.write(data)
        os.fchmod(out.fileno(),0o700)
    os.replace(out.name,target)
print(target)
PY
