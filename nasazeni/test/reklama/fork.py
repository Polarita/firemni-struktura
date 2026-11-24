"""Vytvoří reprodukovatelný commit nad ověřeným původním repozitářem."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

UPSTREAM = "207c78119124761554c58cd1b92a4b107f085a11"
SOURCE = Path(__file__).resolve().parent

def build(directory):
    def git(*args, **kwargs):
        return subprocess.check_output(["git","-c","core.hooksPath=/dev/null",*args],cwd=directory,text=True,**kwargs).strip()
    git("init","-q","-b","main")
    git("fetch","-q","--no-tags","https://github.com/Draivix/aidvertaiser.git",UPSTREAM)
    if git("rev-parse","FETCH_HEAD") != UPSTREAM or 'license = "MIT"' not in git("show",UPSTREAM+":pyproject.toml"):
        raise RuntimeError("Nesouhlasí původ nebo licence předlohy.")
    # Původní plná historie je v rodiči. Do distribuovaného TEST stromu vstupují pouze schválené soubory.
    for name in ("server.py","zkouska.py","sdk.lock","README.md"):
        shutil.copyfile(SOURCE/name,directory/name)
    git("add","--","server.py","zkouska.py","sdk.lock","README.md")
    env = {**os.environ,"GIT_AUTHOR_NAME":"Polarita TEST","GIT_COMMITTER_NAME":"Polarita TEST",
           "GIT_AUTHOR_EMAIL":"instalace@polarita.test","GIT_COMMITTER_EMAIL":"instalace@polarita.test",
           "GIT_AUTHOR_DATE":git("show","-s","--format=%cI",UPSTREAM),"GIT_COMMITTER_DATE":git("show","-s","--format=%cI",UPSTREAM)}
    head = git("commit-tree",git("write-tree"),"-p",UPSTREAM,"-m","Omezený místní reklamní server TEST",env=env)
    git("update-ref","refs/heads/main",head)
    return head

if __name__ == "__main__":
    print(build(Path(sys.argv[1]).resolve(strict=True)))
