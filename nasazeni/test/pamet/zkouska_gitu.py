"""Skutečné commity v dočasném repozitáři pod účtem služby, jen syntetické hodnoty."""
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

HOOKS = "/usr/local/lib/polarita/znalostni-git"


def main():
    if os.geteuid() == 0:
        raise RuntimeError("Zkouška má běžet jako znalostní účet")
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        def git(*args, ok=True):
            result = subprocess.run(["git", *args], cwd=root, capture_output=True)
            if (result.returncode == 0) != ok:
                raise RuntimeError("Znalostní Git vrátil neočekávaný výsledek pro " + args[0])
            return result

        git("init", "-q")
        git("config", "core.hooksPath", HOOKS)
        git("config", "user.name", "Provozní vzorek")
        git("config", "user.email", "znalosti@polarita.test")
        section = root/"07-IT-a-Architektura"
        section.mkdir()
        page = section/"overeni.md"
        clean = "# Ověření\n\nZáznam o obnovení provozu.\n"
        page.write_text(clean)
        git("add", ".")
        git("commit", "-qm", "Čistý provozní vzorek")
        first = git("rev-parse","HEAD").stdout
        fixture = "POLARITA_CI_FIXTURE=" + secrets.token_hex(16)
        for value, reason in [(fixture, "Gitleaks"), ("soukromy.clovek@example.invalid", "e-mail"),
                              ("+420 000 000 000", "telefon"), ("000000/0000", "rodné číslo"),
                              ("datum_narozeni: TEST-DATUM", "osobní karta"), ("heslo: testovaci-hodnota", "přístupový údaj")]:
            page.write_text(value+"\n")
            git("add", ".")
            page.write_text(clean)
            result = git("commit","-qm","Zkouška obsahu indexu",ok=False)
            result2 = git("commit","--no-verify","-qm","Zkouška změny reference",ok=False)
            if any(reason.encode() not in r.stderr or value.encode() in r.stderr for r in (result,result2)):
                raise RuntimeError("Nález nebyl odmítnut očekávanou kontrolou")
            if git("rev-parse","HEAD").stdout != first:
                raise RuntimeError("Neplatný commit změnil historii")
        git("reset", "-q", "HEAD", "--", ".")
        unsafe = section/"vzor.pdf"
        unsafe.write_bytes(b"%PDF-TEST-UNREGISTERED")
        git("add", ".")
        if b"PDF" not in git("commit","-qm","Zkouška původu dokumentu",ok=False).stderr:
            raise RuntimeError("Neověřený PDF vzor neodmítla obsahová kontrola")
        git("reset", "-q", "HEAD", "--", ".")
        disguised = unsafe.rename(section/"vzor.txt")
        git("add", ".")
        if b"PDF" not in git("commit","-qm","Zkouška přípony",ok=False).stderr:
            raise RuntimeError("Přejmenovaný PDF vzor neodmítla kontrola původu")
        git("reset", "-q", "HEAD", "--", ".")
        disguised.unlink()
        # Čistý vrchol nesmí zakrýt závadnou revizi vloženou dříve v téže větvi.
        page.write_text(fixture+"\n")
        git("add", ".")
        bad_tree = git("write-tree").stdout.decode().strip()
        bad = git("commit-tree",bad_tree,"-p","HEAD","-m","Nedostupný syntetický vzorek").stdout.decode().strip()
        clean_tree = git("rev-parse","HEAD^{tree}").stdout.decode().strip()
        tip = git("commit-tree",clean_tree,"-p",bad,"-m","Čistý vrchol").stdout.decode().strip()
        result = git("update-ref","refs/heads/vzorek",tip,ok=False)
        if b"Gitleaks" not in result.stderr or fixture.encode() in result.stderr:
            raise RuntimeError("Kontrola historie nerozpoznala vadnou mezilehlou revizi")
        page.write_text(clean+"Automatická zkouška prošla.\n")
        git("add", ".")
        git("commit", "-qm", "Návazný čistý záznam")
        git("fsck","--strict","--no-dangling")


if __name__ == "__main__":
    main()
