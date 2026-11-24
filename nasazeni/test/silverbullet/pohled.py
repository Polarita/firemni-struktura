"""Do čtecího prostoru webu vstupují jen schválené Markdown objekty jedné revize Vaultu."""
import fcntl
import os
from pathlib import Path
import tempfile
import subprocess

ROOT=Path("/srv/polarita/vault")
VIEW=Path("/srv/polarita/data/silverbullet-test/overene")

def refresh():
    def git(*args):
        return subprocess.check_output(["runuser","-u","polarita-pamet","--","git","-c",f"safe.directory={ROOT}","-C",ROOT,*args])
    areas=set(Path("/etc/polarita/znalostni-oblasti").read_text().splitlines())
    with (VIEW/".export.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        rev=git("rev-parse","HEAD").decode().strip()
        target=VIEW/rev
        if not target.is_dir():
            with tempfile.TemporaryDirectory(dir=VIEW) as tmp:
                tree=Path(tmp)/"prostor"
                tree.mkdir(mode=0o755)
                for entry in git("ls-tree","-rz",rev).split(b"\0"):
                    if not entry:
                        continue
                    meta,raw=entry.split(b"\t",1)
                    mode,kind,oid=meta.split()
                    name=Path(os.fsdecode(raw))
                    if (mode!=b"100644" or kind!=b"blob" or name.is_absolute() or ".." in name.parts
                            or name.parts[0] not in areas or name.suffix!=".md"):
                        continue
                    f=tree/name
                    f.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
                    f.write_bytes(git("cat-file","blob",oid))
                    f.chmod(0o644)
                if not (tree/"00-Meta/pobocky.md").is_file():
                    raise RuntimeError("Chybí ověřený registr poboček pro zobrazení ve webu")
                tree.rename(target)
        link=VIEW/"current"
        if not link.is_symlink() or link.readlink()!=Path(rev):
            next_link=VIEW/".current-next"
            next_link.unlink(missing_ok=True)
            next_link.symlink_to(rev)
            next_link.replace(link)
        return rev

if __name__=="__main__":
    os.umask(0o022)
    print(refresh())
