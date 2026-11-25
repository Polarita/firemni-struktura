"""Zkontroluje skutečné uvolnění ve spisu přes ředitelství, včetně opakovaného požadavku."""
from hashlib import sha256
import json
import sys
import time
from urllib.error import URLError
from uuid import uuid5

from prijem import CASE, SAMPLES, pripojeni, prihlasit
from overeni import NeocekavanyStav


def over(origin, password):
    call = pripojeni(origin)
    def request(*args):
        try:
            return json.loads(call(*args))
        except NeocekavanyStav as exc:
            if exc.status != 401:
                raise
        prihlasit(call, password)
        return json.loads(call(*args))

    api = "/lhutnik-test/api/"
    def spis(key):
        return request("POST",api+"spisy",json.dumps({"pozadavek":str(key),"branch_id":101}).encode(),
                       "application/json")["case_id"]
    prihlasit(call, password)
    case = spis(CASE)
    other = spis(uuid5(CASE, "bez-projektu"))
    data = {"trasa":"R-TEST-01","revize":sha256((SAMPLES/"trasa.json").read_bytes()).hexdigest()}
    payload = json.dumps(data).encode()
    post = ("application/json", 409)
    if "FAIL_CLOSED" not in request("POST",api+"vykopy/"+other,payload,*post)["error"]:
        raise RuntimeError("Spis bez trasy nezablokoval uvolnění.")
    path = api+"vykopy/"+case
    denied = False
    deadline = time.monotonic() + 10800
    while time.monotonic() < deadline:
        try:
            [row] = request("GET",path)
            if row["trasa"] != data["trasa"] or row["revize"] != data["revize"]:
                raise RuntimeError("Spis vrátil jinou revizi trasy.")
            if row["stav"] in ("pripraveno-test", "uvolneno-test"):
                break
            if not denied:
                try:
                    err = request("POST",path,payload,*post)["error"]
                except NeocekavanyStav as exc:
                    if exc.status == 200:  # archiv se mohl uzavřít mezi čtením a zápisem
                        continue
                    raise
                if "FAIL_CLOSED" not in err:
                    raise RuntimeError("Před dokončením archivu musí být výkop blokován.")
                print(f"{case} · systém odmítl uvolnění. {err}", flush=True)
                denied = True
        except NeocekavanyStav as exc:
            if exc.status not in (502,503,504):
                raise
        except (TimeoutError,ConnectionError,URLError):
            pass
        time.sleep(15)
    else:
        raise TimeoutError("Spis neprokázal úplné archivované podklady pro výkop.")
    stale = json.dumps({**data,"revize":"0"*64}).encode()
    request("POST",path,stale,*post)
    for attempt in range(2):
        saved = request("POST",path,payload,"application/json")
        if saved["stav"] != "uvolneno-test" or saved["duvody"] or saved["revize"] != row["revize"]:
            raise RuntimeError("Ředitelství nepotvrdilo aktuální technické uvolnění.")
    [reopened] = request("GET",path)
    if reopened != saved:
        raise RuntimeError("Po znovuotevření spisu se změnil stav právě uvolněné trasy.")
    print(f"{case} · Trasa {row['trasa']} prošla zkouškou krytí, křížení a souběhu. "
          f"Oba dokumenty jsou ve spisu. Cizí spis a zastaralá revize byly odmítnuty.", flush=True)


if __name__ == "__main__":
    over(sys.argv[1], sys.stdin.readline().rstrip("\r\n"))
