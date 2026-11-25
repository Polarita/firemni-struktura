"""Stabilní identifikátory a otisky prvotních dokladových podkladů TEST."""
from hashlib import sha256
import json
from uuid import uuid5

from spisy_rz import id_spisu


def doklady(vzory):
    rows = []
    for varianta,polozky in vzory.items():
        spis = id_spisu(varianta)
        if set(polozky) != {"FAK","ORG-UOL","VYD"}:
            raise ValueError("Chybí vzor účetní nebo skladové řady.")
        for druh,popis in polozky.items():
            source = json.dumps({"spis":str(spis),"druh":druh,"popis":popis,"rezim":"TEST"},
                                sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
            rows.append({"spis":str(spis),"druh":druh,"klic":str(uuid5(spis,"registr-test/"+druh)),
                         "otisk":sha256(source).hexdigest()})
    return rows
