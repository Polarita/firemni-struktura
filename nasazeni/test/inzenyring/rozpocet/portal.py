"""Porovná obě nabídky stažené přihlášeným správcem s ověřenými soubory daného spisu."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prijem import CASE, prihlasit, pripojeni
from overeni import NeocekavanyStav


def over(origin, password, sums):
    files = {name: digest for digest, name in (line.split() for line in sums.splitlines() if line.strip())}
    if set(files) != {"nabidka.xc4", "nabidka.xlsx"}:
        raise ValueError("Očekávány oba ověřené soubory nabídky.")
    call = pripojeni(origin)
    prihlasit(call, password)
    api = "/lhutnik-test/api/"
    card = json.loads(call("POST", api + "spisy", json.dumps({"pozadavek": str(CASE), "branch_id": 101}).encode(),
                           "application/json"))
    case = card["case_id"]
    if not json.loads(call("GET", api + "spisy/" + case)).get("ma_rozpocet"):
        raise ValueError("Karta spisu neobsahuje nabídku.")
    anonymous = pripojeni(origin)
    for name, checksum in files.items():
        uri = api + "rozpocty/" + case + "/" + name
        try:
            anonymous("GET", uri, status=401)
        except NeocekavanyStav as exc:
            if exc.status != 401:
                raise
        payload = call("GET", uri)
        if hashlib.sha256(payload).hexdigest() != checksum:
            raise ValueError("Stažená nabídka nesouhlasí se zdrojem.")
        print(f"{case} · {name} · {len(payload)} bajtů · SHA-256 {checksum}")


if __name__ == "__main__":
    over(sys.argv[1], sys.stdin.readline().rstrip("\r\n"), sys.stdin.read())
