"""Založí soukromý fork, ověří lokální Git přenosem přes HTTPS a porovná jeho strom."""
import base64
import http.client
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

OWNER = "spravce"
REPO = "polarita-ads-mcp"
DESCRIPTION = "Místní auditovaný reklamní MCP server pro testování."

def create():
    secret = json.load(sys.stdin)
    host = urlsplit(Path("/etc/polarita-gitea/url").read_text().strip()).hostname
    auth = base64.b64encode((secret["admin"]+":"+secret["password"]).encode()).decode()
    def api(method, path, data=None, expected=(200,)):
        c = http.client.HTTPSConnection(host,context=ssl.create_default_context(cafile="/etc/polarita-gitea/git-ca.crt"), timeout=120)
        try:
            c.request(method,"/git/api/v1"+path,json.dumps(data) if data else None,
                      {"Content-Type":"application/json","Authorization":"Basic "+auth,"Sudo":OWNER})
            res = c.getresponse()
            raw = res.read()
            if res.status not in expected:
                raise RuntimeError(f"Gitea {method} {path} vrátila {res.status}")
            return res.status, json.loads(raw)
        finally:
            c.close()
    path = f"/repos/{OWNER}/{REPO}"
    if api("GET","/user")[1]["login"] != OWNER:
        raise RuntimeError("Neočekávaný účet v Gitea")
    status, repo = api("GET",path,expected=(200,404))
    if status == 404:
        api("POST","/user/repos",{"name":REPO,"private":True,"auto_init":False,"default_branch":"main",
            "description":DESCRIPTION},(201,))
        _, repo = api("GET",path)
    if repo["full_name"] != OWNER+"/"+REPO or not repo["private"]:
        raise RuntimeError("Nesouhlasí vlastník nebo viditelnost")
    if repo.get("has_actions") and repo.get("description") == DESCRIPTION:
        api("PATCH",path,{"has_actions":False})
    if api("GET",path)[1].get("has_actions"):
        raise RuntimeError("Fork nemá spouštět cizí workflow")

def publish():
    from fork import build, UPSTREAM
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"git"))
    from pripoj_identitu import ADMIN, INSIDE, admin_password
    with TemporaryDirectory() as temp:
        directory = Path(temp)
        head = build(directory)
        public = subprocess.check_output(INSIDE+["cat","/etc/polarita-gitea/url"],text=True).strip()
        if not re.fullmatch(r"https://[a-z0-9.-]+/git/",public):
            raise RuntimeError("Neočekávaná adresa místní Gitea")
        password = admin_password()
        subprocess.run(["incus","file","push","--mode=0644",__file__,"gitea-test/etc/polarita-gitea/reklama.py"],check=True)
        subprocess.run(INSIDE+["python3","/etc/polarita-gitea/reklama.py"],check=True,
                       input=json.dumps({"admin":ADMIN,"password":password}).encode())
        ca = directory/"ca.crt"
        subprocess.run(["incus","file","pull","gitea-test/etc/polarita-gitea/git-ca.crt",str(ca)],check=True)
        header = base64.b64encode((ADMIN+":"+password).encode()).decode()
        options = {"http."+public+".extraHeader":"Authorization: Basic "+header,"http.sslCAInfo":str(ca),
                   "http.curloptResolve":f"{urlsplit(public).hostname}:443:10.239.32.13","http.followRedirects":"false",
                   "core.hooksPath":"/dev/null"}
        env = {"PATH":"/usr/bin:/bin","HOME":temp,"GIT_TERMINAL_PROMPT":"0","GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_COUNT":str(len(options))}
        for i,(key,value) in enumerate(options.items()):
            env[f"GIT_CONFIG_KEY_{i}"], env[f"GIT_CONFIG_VALUE_{i}"] = key,value
        def git(*args):
            return subprocess.check_output(["git",*args],cwd=directory,env=env,text=True).strip()
        url = public + OWNER+"/"+REPO+".git"
        ref = "refs/heads/main"
        remote = git("ls-remote",url,ref)
        if not remote:
            git("push","--quiet",url,head+":"+ref)
        elif remote.split()[0] != head:
            ref = "refs/heads/test/"+head
            existing = git("ls-remote",url,ref)
            if not existing:
                git("push","--quiet",url,head+":"+ref)
            elif existing.split()[0] != head:
                raise RuntimeError("Větev instalační revize má jiný obsah")
        git("clone","--quiet","--single-branch","--branch",ref.removeprefix("refs/heads/"),url,"overeni")
        if git("-C","overeni","rev-parse","HEAD") != head or git("-C","overeni","rev-parse","HEAD^") != UPSTREAM:
            raise RuntimeError("Stažený fork nebo jeho původ nesouhlasí")
        git("-C","overeni","fsck","--strict")
        print(f"Gitea ověřila soukromý {OWNER}/{REPO}, větev {ref}, revizi {head} a původ {UPSTREAM}.")

if __name__ == "__main__":
    host = socket.gethostname().split(".")[0]
    if host == "gitea-test":
        for attempt in range(3):
            try:
                create()
                break
            except (TimeoutError, http.client.RemoteDisconnected, ConnectionResetError):
                if attempt == 2:
                    raise
    elif host == "polarita-hq" and os.geteuid()==0:
        publish()
    else:
        raise SystemExit("Publikování patří do polarita-hq")
