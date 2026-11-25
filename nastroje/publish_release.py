"""Dokončí vydání z GitHub Actions i po výpadku při vytváření nebo nahrávání příloh."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True, timeout=180)


def najdi(repo, tag):
    # Seznam včetně konceptů vytvořených týmž účtem, i po výpadku odpovědi na zápis.
    pages = json.loads(gh("api", "--paginate", "--slurp", f"repos/{repo}/releases?per_page=100"))
    hits = [r for page in pages for r in page if r["tag_name"] == tag]
    if len(hits) > 1:
        raise ValueError("Jeden tag odpovídá více vydáním.")
    return hits[0] if hits else None


def prilohy(repo, vydani):
    pages = json.loads(gh("api", "--paginate", "--slurp",
                          f"repos/{repo}/releases/{vydani['id']}/assets?per_page=100"))
    return {a["name"]:a["digest"] if a["state"] == "uploaded" else None for page in pages for a in page}


def dokonci(repo, tag, directory, expected):
    r = najdi(repo, tag)
    if r is None:
        gh("release","create",tag,"--draft","--verify-tag","--title",tag,"--generate-notes","--repo",repo)
        r = najdi(repo, tag)
    if not r:
        raise RuntimeError("GitHub zatím nevrátil vytvořený koncept.")
    actual = prilohy(repo, r)
    if not r["draft"]:
        if actual != expected:
            raise ValueError("Veřejné přílohy neodpovídají sestavení.")
        return
    if set(actual) - set(expected):
        raise ValueError("Koncept obsahuje přílohu mimo sestavení.")
    if r["author"]["login"] != "github-actions[bot]":
        raise ValueError("Koncept vytvořil jiný vydavatel.")
    soubory = [str(directory/name) for name,h in expected.items() if actual.get(name) != h]
    if soubory:
        gh("release","upload",tag,*soubory,"--clobber","--repo",repo)
    if prilohy(repo, r) != expected:
        raise RuntimeError("GitHub dosud nepotvrdil všechny kontrolní součty konceptu.")
    gh("release","edit",tag,"--draft=false","--repo",repo)
    hotovo = najdi(repo,tag)
    if not hotovo or hotovo["draft"] or hotovo["id"] != r["id"] or prilohy(repo,hotovo) != expected:
        raise RuntimeError("GitHub dosud nepotvrdil zveřejnění všech příloh.")


def main():
    repo, tag = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_REF_NAME"]
    directory = Path(sys.argv[1])
    expected = {}
    for p in directory.iterdir():
        if not p.is_file() or p.is_symlink():
            raise ValueError("Neočekávaná položka ve výstupu sestavení.")
        with p.open("rb") as f:
            expected[p.name] = "sha256:"+hashlib.file_digest(f,"sha256").hexdigest()
    if "SHA256SUMS" not in expected or len(expected) < 2:
        raise ValueError("Chybí sestavené soubory nebo jejich manifest.")
    for pokus in range(5):
        try:
            dokonci(repo,tag,directory,expected)
            print(f"GitHub potvrdil {len(expected)} příloh vydání {tag}.",flush=True)
            return
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired,RuntimeError) as exc:
            if pokus == 4:
                raise
            print(f"Publikace se zopakuje po kontrole stavu na GitHubu ({type(exc).__name__}).",flush=True)
            time.sleep(10*(pokus+1))


if __name__ == "__main__":
    main()
