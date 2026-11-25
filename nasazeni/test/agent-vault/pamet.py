"""Zpřístupňuje jen verzované Markdown stránky schváleného znalostního stromu."""
import fcntl
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

ROOT = Path("/srv/polarita/vault")
HOOKS = Path("/usr/local/lib/polarita/znalostni-git")

def git(directory, *args):
    return subprocess.check_output(["git","-c",f"safe.directory={directory}","-C",directory,*args],
                                   stdin=subprocess.DEVNULL)

def snapshot(*, doklady=False, head=None):
    head = head or git(ROOT,"rev-parse","--verify","HEAD^{commit}").decode().strip()
    areas = set(Path("/etc/polarita/znalostni-oblasti").read_text().splitlines())
    entries = {}
    for item in git(ROOT,"ls-tree","-rz",head).split(b"\0"):
        if item:
            meta, name = item.split(b"\t",1)
            mode,kind,oid = meta.split()
            path = PurePosixPath(os.fsdecode(name))
            if mode == b"100644" and kind == b"blob" and len(path.parts)>1 and path.parts[0] in areas and (path.suffix == ".md"
                    or (doklady and path.parts[0] == "07-IT-a-Architektura")):
                entries[path.as_posix()] = oid.decode()
    return head, entries

def read(oid):
    return git(ROOT,"cat-file","blob",oid).decode("utf-8")

def save(pages, message, *, update_seed=False, doklady=False):
    # Soukromý klon zachytí zamítnuté zápisy mimo živý Vault i jeho databázi objektů.
    with (ROOT/".git"/"agent-vault.lock").open("a") as lock, tempfile.TemporaryDirectory() as tmp:
        fcntl.flock(lock,fcntl.LOCK_EX)
        head, known = snapshot(doklady=doklady)
        base = Path(tmp)/"navrh"
        git(ROOT,"clone","--quiet","--no-local","--single-branch","--branch","main",str(ROOT),str(base))
        if git(base,"rev-parse","HEAD").decode().strip() != head:
            raise ValueError("Znalostní větev se změnila. Zopakuj požadavek.")
        git(base,"config","core.hooksPath",str(HOOKS))
        git(base,"config","user.name","Správa znalostí TEST")
        git(base,"config","user.email","znalosti@polarita.test")
        hash_type = git(base, "rev-parse", "--show-object-format").decode().strip()
        changed = []
        for name, content in pages.items():
            raw = content if isinstance(content, bytes) else content.encode("utf-8")
            if name in known:
                oid = hashlib.new(hash_type, f"blob {len(raw)}\0".encode() + raw).hexdigest()
                if known[name] == oid:
                    continue
                if not (update_seed or doklady):
                    raise ValueError("Identifikátor již patří jinému záznamu.")
                last = git(base,"log","-1","--format=%ae%x00%s",head,"--",name).decode().rstrip("\n")
                if last != "znalosti@polarita.test\0"+message:
                    if doklady:
                        raise ValueError("Starší soubor nevytvořila přejímka instalačních dokladů.")
                    continue
            target = base/name
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open("wb" if name in known else "xb") as f:
                f.write(raw)
            changed.append(name)
        if not changed:
            return head
        git(base,"add","--",*changed)
        git(base,"commit","-qm",message)
        commit = git(base,"rev-parse","HEAD").decode().strip()
        if git(ROOT,"symbolic-ref","--short","HEAD").strip() != b"main":
            raise ValueError("Vault používá jinou pracovní větev.")
        git(ROOT,"fetch","--quiet","--no-tags",str(base),"refs/heads/main")
        git(ROOT,"merge","--quiet","--ff-only",commit)
        return commit

def record(kind, key, body):
    if not re.fullmatch("[a-z0-9][a-z0-9-]{0,63}",key) or not body.strip() or len(body.encode())>32768:
        raise ValueError("Zadej neprázdný záznam do 32 KiB a identifikátor z malých písmen, číslic a pomlček.")
    section, title = {"log":("08-Deniky-a-Predavky","Předávka"),"adr":("07-IT-a-Architektura","Rozhodnutí ADR")}[kind]
    role = os.environ["POLARITA_VAULT_ACTOR"]
    if not re.fullmatch(r"instalace|1[1-8]\d{3}",role) or role == "11001":
        raise ValueError("Role nemá oprávnění pro zápis do Vaultu.")
    name = f"{section}/{kind}-{role}-{key}.md"
    content = f"# {title} {key}\n\nRole {role}\n\n{body.strip()}\n"
    return {"revize":save({name:content},title+" role "+role),"cesta":name}
