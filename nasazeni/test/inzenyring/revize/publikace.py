"""Atomické vydání ověřené sady souborů do databázového kontejneru TEST."""
import hashlib
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


WORK = Path("/srv/polarita/workspace/dukazy/blok-10")


def run(vm, *args, data=None, user=None):
    options = ["--user", user, "--group", user] if user else []
    return subprocess.check_output(["incus","exec","-T",vm,*options,"--",*args], input=data, timeout=360)


def publikuj(run, db, base, files, work):
    run(db, "install", "-dm0755", base)
    with TemporaryDirectory(dir=work) as tmp:
        for name,raw in files.items():
            (Path(tmp)/name).write_bytes(raw)
        sums = "".join(hashlib.sha256(raw).hexdigest()+"  "+name+"\n" for name,raw in files.items())
        (Path(tmp)/"SHA256SUMS").write_text(sums)
        rev = hashlib.sha256(sums.encode()).hexdigest()
        tar = subprocess.check_output(["tar","-C",tmp,"--mode=0644","-cf","-",*files,"SHA256SUMS"])
        run(db,"bash","-ec",'''cd "$1"
if ! test -d "$2"; then
    stage=$(mktemp -d .priprava-XXXXXXXX)
    trap 'rm -rf -- "$stage"' EXIT
    tar -xf - -C "$stage"
    (cd "$stage" && sha256sum --status -c SHA256SUMS)
    chmod 0755 "$stage"
    mv -T "$stage" "$2"
fi
(cd "$2" && sha256sum --status -c SHA256SUMS)
ln -sfn "$2" .current.next
mv -Tf .current.next current''',"--",base,rev,data=tar)
