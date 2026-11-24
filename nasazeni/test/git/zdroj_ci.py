"""Importuje sledované soubory návrhu do prázdného TEST repozitáře a vytvoří dva nezávislé klony."""
import base64
import fcntl
import os
from pathlib import Path
import pwd
import shutil
import secrets
import socket
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from pripoj_identitu import ADMIN, INSIDE, admin_password
from repozitar import OWNER, REPO


def main():
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Import patří do testovací VM")
    os.umask(0o077)
    archive = Path(sys.argv[1]).resolve(strict=True)
    workspace = Path("/srv/polarita/workspace")
    public = subprocess.check_output(INSIDE+["cat","/etc/polarita-gitea/url"],text=True).strip()
    host = urlsplit(public).hostname
    url = f"{public}{OWNER}/{REPO}.git"
    with (workspace/".git-test-instalace").open("a") as lock, TemporaryDirectory(dir=workspace) as staging:
        fcntl.flock(lock,fcntl.LOCK_EX)
        tmp = Path(staging)
        ca = tmp/"ca.crt"
        subprocess.run(["incus","file","pull","gitea-test/etc/polarita-gitea/git-ca.crt",str(ca)],check=True)
        basic = base64.b64encode((ADMIN+":"+admin_password()).encode()).decode()
        options = {"http."+public+".extraHeader":"Authorization: Basic "+basic,
                   "http.curloptResolve":f"{host}:443:10.239.32.13","http.sslCAInfo":str(ca),
                   "http.followRedirects":"false","core.hooksPath":"/dev/null"}
        env = {"PATH":"/usr/bin:/bin", "HOME":str(tmp), "GIT_TERMINAL_PROMPT":"0","GIT_CONFIG_NOSYSTEM":"1",
               "GIT_CONFIG_COUNT":str(len(options))}
        for index,(key,value) in enumerate(options.items()):
            env[f"GIT_CONFIG_KEY_{index}"] = key
            env[f"GIT_CONFIG_VALUE_{index}"] = value
        def git(*args, directory=tmp):
            return subprocess.check_output(["git",*args],cwd=directory,env=env,text=True).strip()
        head = git("ls-remote",url,"refs/heads/main")
        if "--zkouska-skenu" in sys.argv:
            sample = tmp/"zkouska"
            git("clone","-q","--no-local",url,str(sample))
            branch = "refs/heads/zkouska-detektoru-"+secrets.token_hex(8)
            (sample/"kontrola.txt").write_text("Kontrola příjmu souboru v TEST.\n")
            git("add","kontrola.txt",directory=sample)
            git("-c","user.name=Polarita TEST","-c","user.email=instalace@polarita.test","commit","-qm","Čistý kontrolní vzorek",directory=sample)
            clean = git("rev-parse","HEAD",directory=sample)
            git("push","--quiet",url,"HEAD:"+branch,directory=sample)
            if git("ls-remote",url,branch).split()[0] != clean:
                raise RuntimeError("Čistý kontrolní vzorek nebyl přijat")
            git("push","--quiet","--force-with-lease="+branch+":"+clean,url,":"+branch,directory=sample)
            (sample/"kontrola.txt").write_text("POLARITA_CI_FIXTURE="+secrets.token_hex(16)+"\n")
            git("add","kontrola.txt",directory=sample)
            git("-c","user.name=Polarita TEST","-c","user.email=instalace@polarita.test","commit","-qm","Neškodný vzorek detektoru",directory=sample)
            push = subprocess.run(["git","push",url,"HEAD:"+branch],cwd=sample,env=env,capture_output=True,text=True)
            if not push.returncode or "gitleaks nepovolil" not in push.stderr or git("ls-remote",url,branch):
                raise RuntimeError("Serverová brána nepotvrdila odmítnutí testovacího vzorku")
            print("Gitea prostřednictvím gitleaks odmítla push s neškodnou kontrolní hodnotou. Větev nevznikla.")
            return
        if not head:
            src = tmp/"zdroj"
            src.mkdir()
            with tarfile.open(archive,"r:gz") as tar:
                tar.extractall(src,filter="data")
            workflow = src/".gitea/workflows/kontrola.yml"
            workflow.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(src/"balicky/ci-gitea-actions-priklad.yml",workflow)
            git("init","-q","-b","main",directory=src)
            git("add","--all",directory=src)
            git("-c","user.name=Polarita TEST","-c","user.email=instalace@polarita.test","commit","-qm",
                "Výchozí návrh ředitelství a ověřovací workflow",directory=src)
            git("push","--quiet",url,"HEAD:refs/heads/main",directory=src)
            head = git("ls-remote",url,"refs/heads/main")
        if not head:
            raise RuntimeError("Gitea nemá větev main")
        for name in ("worker","judge"):
            account = "pol-git-"+name
            if subprocess.run(["id","-u",account],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
                subprocess.run(["useradd","--system","--user-group","--no-create-home","--shell","/usr/sbin/nologin",account],check=True)
            owner = pwd.getpwnam(account)
            target = workspace/("wt-"+name)
            if not target.exists():
                clone = tmp/("wt-"+name)
                git("clone","-q","--no-local",url,str(clone))
                if git("rev-parse","HEAD",directory=clone) != head.split()[0]:
                    raise RuntimeError("Klon neodpovídá zdrojové větvi")
                for path in [clone,*clone.rglob("*")]:
                    os.chown(path,owner.pw_uid,owner.pw_gid,follow_symlinks=False)
                clone.chmod(0o700)
                clone.rename(target)
            # Pracovní účet nemusí procházet jiná firemní data ve workspace.
            parent = Path("/var/lib/polarita-git-test")
            parent.mkdir(mode=0o711,exist_ok=True)
            parent.chmod(0o711)
            mount = parent / target.name
            mount.mkdir(mode=0o700,exist_ok=True)
            unit = subprocess.check_output(["systemd-escape","--path","--suffix=mount",str(mount)],text=True).strip()
            content = (f"[Unit]\nDescription=Samostatný klon {name} pro TEST\nRequiresMountsFor={target}\n"
                       f"[Mount]\nWhat={target}\nWhere={mount}\nType=none\nOptions=bind,nodev,nosuid\n"
                       "[Install]\nWantedBy=multi-user.target\n")
            unit_path = Path("/etc/systemd/system") / unit
            if not unit_path.exists() or unit_path.read_text() != content:
                unit_path.write_text(content)
                unit_path.chmod(0o644)
                subprocess.run(["systemctl","daemon-reload"],check=True)
            subprocess.run(["systemctl","enable","--now",unit],check=True)
            if not os.path.samefile(mount,target):
                raise RuntimeError("Nesouhlasí soukromý pohled na klon")
            check = subprocess.check_output(["runuser","-u",account,"--","git","-C",str(mount),
                                              "rev-parse","--absolute-git-dir"],text=True).strip()
            if check != str(mount/".git") or not (target/".git").is_dir():
                raise RuntimeError("Klon používá nesamostatnou databázi Gitu")
        for name,other in (("worker","judge"),("judge","worker")):
            if subprocess.run(["runuser","-u","pol-git-"+name,"--","test","-r",f"/var/lib/polarita-git-test/wt-{other}/.git/config"]).returncode != 1:
                raise RuntimeError("Chybné oddělení klonů")
        if os.path.samefile(workspace/"wt-judge/.git",workspace/"wt-worker/.git"):
            raise RuntimeError("Klony sdílejí databázi Gitu")
        print("Gitea uchovává návrh a workflow ve větvi main. Worker a judge mají samostatné soukromé klony.")


if __name__ == "__main__":
    main()
