"""Předá podklady modelové trasy do spisu přes přihlášený portál a jeho karanténu."""
from hashlib import sha256
import json
from pathlib import Path
import sys
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sanony"))
from overeni import pripojeni, prihlasit

CASE = uuid5(NAMESPACE_URL, "polarita.test/inzenyring/DTM/spis")
SAMPLES = Path(__file__).with_name("vzor")


def prijmi(origin, password):
    call = pripojeni(origin)
    prihlasit(call, password)
    route = "/lhutnik-test/api/"
    case = json.loads(call("POST", route + "spisy", json.dumps({"pozadavek": str(CASE),
                           "branch_id": 101}).encode(), "application/json"))["case_id"]
    for name in ("mapa", "vyjadreni"):
        pdf = (SAMPLES / (name + ".pdf")).read_bytes()
        digest = sha256(pdf).hexdigest()
        key = str(uuid5(CASE, digest))
        result = json.loads(call("PUT", f"{route}sanony/{case}/{key}", pdf, "application/pdf"))
        if (result["case_id"], result["priloha"], result["bajtu"]) != (case, key, len(pdf)):
            raise ValueError("Potvrzení příjmu neodpovídá dokumentu trasy.")
        print(f"{case} · {name} · {key} · {result['stav']}", flush=True)


if __name__ == "__main__":
    prijmi(sys.argv[1], sys.stdin.readline().rstrip("\r\n"))
