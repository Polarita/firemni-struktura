"""V polarita-hq sestaví návrhy a zpřístupní je ve spisech po potvrzení příloh Decisions."""
import base64
from datetime import date
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from publikace import publikuj

from over_tisk import overit
from priprav import priprav
from spisy_rz import id_spisu, VARIANTY

HERE = Path(__file__).resolve().parent
TEST = HERE.parents[1]
WORK = Path("/srv/polarita/workspace/dukazy/blok-10")
LOGIN = Path("/srv/polarita/data/bootstrap-test/test-login/heslo")


def run(vm, *args, data=None, user=None):
    options = ["--user", user, "--group", user] if user else []
    return subprocess.check_output(["incus","exec","-T",vm,*options,"--",*args], input=data, timeout=360)


def nasad(host):
    board = "paperclip-test"
    db = "postgres-test"
    path = "/etc/polarita-paperclip/revize"
    run(board, "install","-dm0755",path)
    for src in (HERE/"rozhodnuti_rz.py", TEST/"paperclip/board.py", TEST/"akademie/rozhodnuti.py"):
        subprocess.run(["incus","file","push","--mode=0644",str(src),board+path+"/"+src.name+".next"],check=True)
        run(board, "mv","-T",path+"/"+src.name+".next",path+"/"+src.name)
    run("reditelstvi-test", "install","-dm0755","/usr/local/share/polarita-revize-test")
    code = "/opt/polarita-inzenyring-test/rozvadece"
    run(db,"install","-dm0755",code)
    serials = HERE.parent/"rozvadece/cisla.py"
    subprocess.run(["incus","file","push","--mode=0644",str(serials),db+code+"/cisla.py.next"],check=True)
    run(db,"mv","-T",code+"/cisla.py.next",code+"/cisla.py")
    print(run(db,"python3",code+"/cisla.py",*(str(id_spisu(v)) for v in VARIANTY)).decode(),end="",flush=True)
    WORK.mkdir(parents=True,exist_ok=True)
    for variant in VARIANTY:
        uid = str(id_spisu(variant))
        sql = f"SELECT case_id FROM polarita_test_spisy.karty WHERE pozadavek='{uid}'::uuid;"
        case = run(db,"runuser","-u","pol_metadata_read","--","psql","-XAtqw","-v","ON_ERROR_STOP=1","-d","db_erp_lhutnik","-c",sql).decode().strip()
        model = priprav(HERE/"vzor"/(variant+".json"), HERE/"vzor/plan.json", case, date.today())
        if model["stav"] != "navrh-"+variant:
            raise ValueError("Neočekávaný výsledek vzorové revize.")
        encoded = json.dumps(model,ensure_ascii=False,sort_keys=True)
        pdf = run("reditelstvi-test","/usr/local/bin/polarita-typst","compile","--root","/usr/local/share/polarita-revize-test",
                  "--ignore-system-fonts","--creation-timestamp","0","--input","model="+encoded,"-","-",
                  user="65534",data=(HERE/"navrh.typ").read_bytes())
        if not pdf.startswith(b"%PDF-") or len(pdf)<1000:
            raise ValueError("Sazba nevrátila platný návrh.")
        pages = overit(pdf, model)
        digest = hashlib.sha256(pdf).hexdigest()
        packet = {"model":model,"pdf":base64.b64encode(pdf).decode(),"pdf_sha256":digest,"heslo":LOGIN.read_text().strip()}
        response = run(board,"python3",path+"/rozhodnuti_rz.py",host,user="65534",data=json.dumps(packet).encode())
        result = json.loads(response)
        if result["pdf_sha256"]!=digest or result["predani_do_provozu"] is not False or result["stav"]!=model["stav"]:
            raise ValueError("Rozhodnutí nesouhlasí s právě připraveným PDF.")
        base = "/opt/polarita-inzenyring-test/revize/"+uid
        publikuj(run, db, base, {"navrh.pdf":pdf, "posouzeni.json":encoded.encode(), "prehled.json":response}, WORK)
        print(f'{case} · {model["stav"]} · {pages} str. · {digest} · {result["rozhodnuti"]}',flush=True)


if __name__ == "__main__":
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq" or not re.fullmatch(r"[a-z0-9.-]+\.ts\.net",sys.argv[1]):
        raise SystemExit("Instalace patří do polarita-hq TEST.")
    with open("/run/polarita-revize-test.lock","a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        nasad(sys.argv[1])
