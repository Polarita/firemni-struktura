"""Posouzení aktivní trasy ze spisu. Klient podává pouze název trasy a otisk otevřené revize."""
import json
import re

from spisy import najdi
from vykop import vyhodnot
from zaznamy import Problem, query


def kontrola(data, kod, body=None, *, uvolnit=False):
    case_id = najdi(data, kod)["case_id"]
    states = query(data, "SELECT coalesce(json_agg(v),'[]') FROM polarita_test_spisy.vykopy(:'kod') v;", kod=case_id)
    if uvolnit and (not isinstance(body, dict) or body.keys() != {"trasa", "revize"}
                    or not isinstance(body["revize"], str) or not re.fullmatch(r"[a-f0-9]{64}", body["revize"])):
        raise Problem(400, "Zadejte trasu a revizi právě otevřeného projektu.")
    result = []
    for state in states:
        if uvolnit and state["trasa"] != body["trasa"]:
            continue
        reasons = vyhodnot(state)
        row = {"trasa": state["trasa"], "revize": state["revize"], "den": state["den"], "duvody": reasons,
               "stav": "FAIL_CLOSED" if reasons else "pripraveno-test"}
        if uvolnit:
            if state["revize"] != body["revize"]:
                raise Problem(409, "Revize se změnila. Znovu otevřete spis.")
            if reasons:
                raise Problem(409, "FAIL_CLOSED · " + " ".join(reasons))
            saved = query(data, "SELECT to_json(polarita_test_spisy.uloz_vykop(:'kod',:'trasa',:'stav'::jsonb));",
                          kod=case_id, trasa=state["trasa"], stav=json.dumps(state))
            if not saved:
                raise Problem(409, "Změnily se podklady výkopu. Zopakujte kontrolu.")
            row["stav"] = "uvolneno-test"
            return row
        result.append(row)
    if uvolnit:
        raise Problem(409, "FAIL_CLOSED · Ve spisu chybí projekt uvedené trasy.")
    return result
