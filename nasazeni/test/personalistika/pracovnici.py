"""Vyhodnotí vzorové nástupy z balíčku S2. Na výstup propustí jen výsledek a otisk podkladu."""
import hashlib
import json
from pathlib import Path
import sys
import uuid

S2 = Path(__file__).resolve().parents[3] / "balicky/S2-eval-suite"
sys.path.insert(0, str(S2))
from reference_policy import decide


def vyhodnot(scenare):
    vysledky = []
    for scenar in scenare:
        udalost = scenar["event"]
        if udalost["type"] != "worker_release":
            continue
        kod = scenar["id"]
        skutecnost = decide(udalost)
        predloha = scenar["expected"]
        akce = set(skutecnost["actions"])
        if (skutecnost["decision"] != predloha["decision"]
                or skutecnost["reason_code"] != predloha["reason_code"]
                or not set(predloha["required_actions"]) <= akce
                or not akce.isdisjoint(predloha["forbidden_actions"])):
            raise ValueError(f"Výsledek nástupu se liší od předlohy {kod}")
        podklad = json.dumps(udalost, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        # Každý scénář má vlastní pseudonym v testovacím přehledu, i když sdílí identitu ze vzoru.
        osoba = uuid.uuid5(uuid.NAMESPACE_URL, f"urn:polarita:test:personalistika:{kod}")
        vysledky.append({"scenar": kod, "person_no": str(osoba), "rozhodnuti": skutecnost["decision"],
                         "duvod": skutecnost["reason_code"], "otisk": hashlib.sha256(podklad).hexdigest()})
    duvody = {r["duvod"] for r in vysledky}
    povinne = {"WORKER_ELIGIBLE", "JMHZ_NOT_REGISTERED", "QUALIFICATION_INVALID",
               "MEDICAL_EXPIRED", "ELIGIBILITY_NOT_CONFIRMED", "SUB_INSURANCE_INVALID"}
    if not povinne <= duvody:
        raise ValueError("Chybí kladné nebo záporné scénáře nástupu pracovníka.")
    return vysledky


if __name__ == "__main__":
    soubor = S2 / "eval_suite_polarita_extended.json"
    print(json.dumps(vyhodnot(json.loads(soubor.read_bytes())["scenarios"]), ensure_ascii=False))
