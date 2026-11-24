"""Vytvoří soukromý testovací repozitář v účtu ověřeném přes Keycloak."""
import base64
from http.client import HTTPSConnection
import json
import re
from pathlib import Path
import socket
import ssl
import subprocess
import sys
from urllib.parse import urlsplit

REPO = "firemni-struktura-test"
OWNER = "spravce"


def configure():
    config = json.load(sys.stdin)
    host = urlsplit(Path("/etc/polarita-gitea/url").read_text().strip()).hostname
    ctx = ssl.create_default_context(cafile="/etc/polarita-gitea/git-ca.crt")
    auth = base64.b64encode((config["admin"] + ":" + config["password"]).encode()).decode()
    def api(method, path, data=None, expected=(200,)):
        c = HTTPSConnection(host, port=443, context=ctx, timeout=20)
        try:
            c.request(method, "/git/api/v1"+path, body=json.dumps(data).encode() if data is not None else None,
                      headers={"Authorization":"Basic "+auth,"Content-Type":"application/json","Sudo":OWNER})
            res = c.getresponse()
            raw = res.read()
            if res.status not in expected:
                raise RuntimeError(f"Gitea {method} {path} vrátila HTTP {res.status}")
            return res.status, json.loads(raw) if raw else None
        finally:
            c.close()
    _, user = api("GET","/user")
    if user["login"] != OWNER or user["email"] != "spravce@polarita.test":
        raise RuntimeError("Nepotvrzená identita vlastníka testovacího repozitáře")
    path = f"/repos/{OWNER}/{REPO}"
    status, repo = api("GET",path,expected=(200,404))
    if status == 404:
        _, repo = api("POST","/user/repos",{"name":REPO,"private":True,"auto_init":False,
                         "default_branch":"main","description":"Ověřování instalace ředitelství v režimu TEST."},(201,))
    if not repo["private"] or repo["full_name"] != f"{OWNER}/{REPO}":
        raise RuntimeError("Nesouhlasí vlastník nebo viditelnost repozitáře")
    if not repo.get("has_actions"):
        api("PATCH",path,{"has_actions":True})
    _, repo = api("GET",path)
    if not repo.get("has_actions") or not repo["private"]:
        raise RuntimeError("Gitea nepotvrdila soukromý repozitář s Actions")
    candidate = config.get("kandidat")
    if candidate and candidate["branch"] != "main":
        branch = candidate["branch"]
        if branch != "instalace/" + candidate["tree"] or not re.fullmatch(r"instalace/[0-9a-f]{40}", branch):
            raise ValueError("Neplatná větev instalační zkoušky")
        page = 1
        while True:
            _, pulls = api("GET", path + f"/pulls?state=open&limit=50&page={page}")
            found = next((pr for pr in pulls if pr["head"]["ref"] == branch and pr["base"]["ref"] == "main"
                          and pr["head"]["repo"]["id"] == repo["id"]), None)
            if found or len(pulls) < 50:
                break
            page += 1
        if not found:
            _, found = api("POST", path + "/pulls", {"base": "main", "head": branch,
                           "title": "Ověření testovací instalace " + candidate["tree"][:12]}, (201,))
        if found["head"]["sha"] != candidate["commit"]:
            raise RuntimeError("Požadavek na začlenění míří na jinou revizi")
        print(f"Gitea přijala instalační revizi do ověření v požadavku č. {found['number']}.")
    if config.get("ochrana"):
        for rule in ("main","release/**"):
            _, rules = api("GET",path+"/branch_protections")
            matches = [r for r in rules if r.get("rule_name") == rule]
            policy = {"rule_name":rule, "enable_push":False, "required_approvals":1, "block_on_rejected_reviews":True,
                      "protected_file_patterns":".gitea/workflows/**", "enable_status_check":True,
                      "status_check_contexts":["kontrola-navrhu / kontrola (pull_request)"]}
            if not matches:
                api("POST",path+"/branch_protections",policy,(200,201))
            _, rules = api("GET",path+"/branch_protections")
            if not any(all(r.get(k)==v for k,v in policy.items()) for r in rules):
                raise RuntimeError("Gitea nepotvrdila ochranu větve "+rule)
        print("Gitea vyžaduje pro main a release/** kontrolu změny a výsledek CI. Přímý zápis je uzavřen.")
    if config.get("opakuj"):
        _, runs = api("GET", path+"/actions/runs?limit=1")
        if not runs.get("workflow_runs"):
            raise RuntimeError("Chybí první zkouška CI")
        run = runs["workflow_runs"][0]
        if run["conclusion"] == "failure":
            api("POST", path+"/actions/runs/"+str(run["id"])+"/rerun", expected=(201,202,204))
            print("Gitea přijala opakování nezdařeného běhu CI.")
    print("Gitea potvrdila soukromý repozitář správce a zapnuté Actions.")


def main():
    if socket.gethostname().split(".")[0] == "gitea-test":
        configure()
        return
    if socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Úloha patří do testovací VM")
    from pripoj_identitu import ADMIN, INSIDE, admin_password
    source = str(Path(__file__).resolve())
    subprocess.run(["incus","file","push","--mode=0644",source,"gitea-test/etc/polarita-gitea/"],check=True)
    candidate = None
    if "--kandidat" in sys.argv:
        candidate = json.loads(Path(sys.argv[sys.argv.index("--kandidat")+1]).read_text())
    subprocess.run(INSIDE + ["python3","/etc/polarita-gitea/repozitar.py"],
                   input=json.dumps({"admin":ADMIN,"password":admin_password(),"kandidat":candidate,"opakuj":"--opakuj-ci" in sys.argv,"ochrana":"--ochrana" in sys.argv}).encode(),check=True)


if __name__ == "__main__":
    main()
