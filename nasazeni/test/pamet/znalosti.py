"""Založí provozní znalosti ve firemní VM, oprávnění a první revizi."""
import grp
import os
from pathlib import Path
import pwd
import subprocess

ROOT = Path("/srv/polarita/vault")
SERVICE = "polarita-pamet"
DOCS = {
    "00-Meta": "Při změně postupu uveď účel, odpovědnou roli, stav ověření a odkaz na schválený podklad.",
    "01-Vize-a-Strategie": "U rozhodnutí zaznamenej očekávaný přínos, období a způsob vyhodnocení.",
    "02-Oddeleni-a-Procesy": "Pro každý proces popiš vstup, výstup a odpovědnou roli oddělení.",
    "03-Normy-a-Metodiky": "U metodiky eviduj zdroj, platnost a datum posledního ověření.",
    "04-Pravo-a-Smlouvy": "Sem patří obecné postupy. Podepsané listiny uchovávej v řízeném právním archivu.",
    "05-Obchod-a-Ceniky": "Ceník označ verzí, jednotkou, měnou a obdobím účinnosti.",
    "06-Spisy-Zakazek": "Na oprávněný spis odkazuj interním číslem zakázky. Zákaznické podklady uchovávej v řízeném systému.",
    "07-IT-a-Architektura": "Popiš účel služby, její závislosti a ověřený postup obnovy. Přístupové údaje patří do trezoru.",
    "08-Deniky-a-Predavky": "Při předání zaznamenej stav práce, otevřené úkoly a další odpovědnou roli.",
    "09-Lide-a-BOZP": "Sem patří anonymní metodiky rolí a školení. Osobní spisy spravuje oprávněná personální role.",
}


def run(*args):
    return subprocess.check_output(args, stdin=subprocess.DEVNULL, text=True).strip()


def git(*args):
    return run("runuser", "-u", SERVICE, "--", "git", "-c", f"safe.directory={ROOT}", "-C", ROOT, *args)


def main():
    if run("hostname", "-s") != "polarita-hq" or run("findmnt", "-no", "SOURCE", "--mountpoint", ROOT) != "polarita_zfs/vault":
        raise SystemExit("Chybí znalostní dataset na polarita-hq")
    if not all((ROOT / name).is_symlink() for name in ("test-login", "openbao-test", "keycloak-test")):
        raise SystemExit("Nejprve odděl soukromý bootstrap")
    try:
        account = pwd.getpwnam(SERVICE)
    except KeyError:
        run("useradd", "--system", "--user-group", "--no-create-home", "--home-dir", "/nonexistent",
            "--shell", "/usr/sbin/nologin", SERVICE)
        account = pwd.getpwnam(SERVICE)
    gid = grp.getgrnam(SERVICE).gr_gid
    run("setfacl", "-m", f"u:{SERVICE}:--x", ROOT.parent)
    os.chown(ROOT, 0, gid)
    ROOT.chmod(0o750)
    gitdir = ROOT / ".git"
    gitdir.mkdir(mode=0o700, exist_ok=True)
    os.chown(gitdir, account.pw_uid, gid)
    if not (gitdir / "HEAD").exists():
        git("init", "--quiet", "--initial-branch=main")
    hooks = Path("/usr/local/lib/polarita/znalostni-git")
    run("install", "-d", "-m", "0755", hooks)
    source = Path(__file__).parent
    run("install", "-m", "0644", source.parent/"git/gitleaks.toml", hooks/"gitleaks.toml")
    for script in ("kontrola.py", "zkouska_gitu.py"):
        run("install", "-m", "0644", source/script, hooks/script)
    for hook in ("pre-commit", "reference-transaction"):
        run("install", "-m", "0755", source/hook, hooks/hook)
    areas_file = Path("/etc/polarita/znalostni-oblasti")
    areas_file.write_text("\n".join(DOCS) + "\n")
    areas_file.chmod(0o644)
    for key, value in (("core.hooksPath", str(hooks)), ("user.name", "Správa znalostí TEST"), ("user.email", "znalosti@polarita.test"),
                       ("receive.denyDeletes", "true"), ("receive.denyNonFastForwards", "true")):
        git("config", key, value)
    allow = "/*\n!/.gitignore\n" + "".join(f"!/{name}/\n" for name in DOCS)
    ignore = ROOT / ".gitignore"
    ignore.write_text(allow)
    ignore.chmod(0o644)
    initial = [".gitignore"]
    for name, instructions in DOCS.items():
        area = ROOT / name
        area.mkdir(mode=0o750, exist_ok=True)
        if area.is_symlink():
            raise RuntimeError("Oblast znalostí musí být samostatný adresář")
        os.chown(area, account.pw_uid, gid, follow_symlinks=False)
        page = area / "README.md"
        try:
            fd = os.open(page, os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY, 0o640)
        except FileExistsError:
            if page.is_symlink() or not page.is_file():
                raise RuntimeError("Úvod oblasti musí být běžný soubor")
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                os.fchown(stream.fileno(), account.pw_uid, gid)
                stream.write(f"# {name}\n\n{instructions}\n")
        initial.append(str(page.relative_to(ROOT)))
    branches = git("branch", "--format=%(refname)")
    if not branches:
        git("add", "--", *initial)
        if set(git("ls-files").splitlines()) != set(initial):
            raise RuntimeError("Počáteční index obsahuje jiné soubory")
        git("commit", "--quiet", "-m", "Založení deseti oblastí firemních znalostí")
    files = git("ls-files", "-z").strip("\x00").split("\x00")
    if not set(initial).issubset(files) or any(p != ".gitignore" and p.split("/")[0] not in DOCS for p in files):
        raise RuntimeError("Znalostní repozitář obsahuje cizí cestu")
    for name in ("test-login", "openbao-test", "keycloak-test"):
        git("check-ignore", "--quiet", name)
        if subprocess.run(["runuser", "-u", SERVICE, "--", "test", "-r", ROOT/name]).returncode != 1:
            raise RuntimeError("Znalostní účet získal přístup k soukromým datům")
    subprocess.run(["runuser", "-u", SERVICE, "--", "env", "GIT_CONFIG_COUNT=1",
                    "GIT_CONFIG_KEY_0=safe.directory", f"GIT_CONFIG_VALUE_0={ROOT}",
                    "python3", hooks/"kontrola.py", "--historie"], cwd=ROOT, check=True)
    run("runuser", "-u", SERVICE, "--", "python3", hooks/"zkouska_gitu.py")
    print("Znalostní Git ověřil historii a odmítl zkušební tajemství, osobní údaje a neověřený PDF soubor.")
    git("fsck", "--strict")
    print("Git ověřil úplnost historie.", len(DOCS), "oblastí znalostí. Soukromé instalační adresáře jsou pro účet znalostí nepřístupné.")
    print("Revize znalostí", git("rev-parse", "HEAD"))


if __name__ == "__main__":
    main()
