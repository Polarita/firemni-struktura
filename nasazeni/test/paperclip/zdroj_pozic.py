"""Načte vstupy Paperclipu z konkrétní revize soukromé Gitey ověřené instalačním CI."""
import json
import re
import subprocess
import tarfile


def nacti(marker, dest):
    rev = json.loads(marker.read_bytes())
    commit, tree, branch = (rev[k] for k in ("commit", "tree", "branch"))
    if (not all(re.fullmatch("[0-9a-f]{40}", value) for value in (commit, tree))
            or branch not in ("main", "instalace/" + tree)):
        raise ValueError("Neplatná revize instalačního CI")
    git = ["incus", "exec", "-T", "gitea-test", "--", "runuser", "-u", "gitea-test", "--",
           "git", "--git-dir=/var/lib/gitea/git/spravce/firemni-struktura-test.git"]
    refs = subprocess.check_output(git + ["rev-parse", "refs/heads/" + branch, commit + "^{tree}"], text=True)
    if refs.splitlines() != [commit, tree]:
        raise ValueError("Větev nebo strom Gitey se od ověření změnily")
    inputs = ["nastroje/kanon.json", "agenti-a-prompty", "oddeleni"]
    with subprocess.Popen(git + ["archive", commit, "--", *inputs], stdout=subprocess.PIPE) as proc:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as archive:
            for member in archive:
                if member.isdir():
                    continue
                if (not member.isfile() or member.size > 1024 * 1024 or
                        not re.fullmatch(r"(agenti-a-prompty|oddeleni)/[\w-]+\.md|nastroje/kanon\.json", member.name)):
                    raise ValueError("Neočekávaný soubor pravidel Gitey")
                file = dest / member.name
                file.parent.mkdir(parents=True, exist_ok=True)
                with file.open("xb") as out:
                    out.write(archive.extractfile(member).read())
        proc.stdout.read()  # Git může za koncem TAR poslat zarovnávací bloky.
        if proc.wait():
            raise RuntimeError("Gitea nedokončila export instrukcí")
    return {"commit": commit, "tree": tree, "branch": branch}
