"""Porovnání stavů stanic TEST na síťovém vstupu ředitelství."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"sanony"))
sys.path.insert(0,str(HERE.parent/"revize"))
from overeni import prihlasit, pripojeni
from spisy_rz import id_spisu


def over(origin, password):
    api = "/lhutnik-test/api/"
    call = pripojeni(origin)
    prihlasit(call,password)
    for variant,name,state in (("kladny","EV-TEST-01","Available"),("zaporny","EV-TEST-02","Faulted")):
        body = json.dumps({"pozadavek":str(id_spisu(variant)),"branch_id":101}).encode()
        case = json.loads(call("POST",api+"spisy",body,"application/json"))["case_id"]
        result = json.loads(call("GET",api+"ocpp/"+case))
        if result != [{"stanice":name,"evse":1,"konektor":1,"stav":state,
                       "cas":"2026-11-25T08:12:00.000000+00:00","pocet":2}]:
            raise ValueError("Počet, příslušnost nebo pořadí hlášení OCPP nesouhlasí.")
        print(case, name, state, "· dvě původní hlášení přes OCPP-J", flush=True)


if __name__ == "__main__":
    over(sys.argv[1],sys.stdin.readline().rstrip("\r\n"))
