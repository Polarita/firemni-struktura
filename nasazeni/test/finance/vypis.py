"""Čtecí rozhraní pro místní simulátory bank a UOL v instalaci TEST."""
from decimal import Decimal
from http.client import HTTPConnection
import json

CESTY = {
    "cs": "/cs/vypis",
    "fio": "/fio/vypis",
    "uol": "/uol/sparovane-platby",
}


class CteckaTest:
    def __init__(self, port):
        self.port = port

    def nacti(self, zdroj, metoda="GET"):
        if metoda != "GET":
            raise PermissionError("Finanční konektor TEST povoluje pouze čtení.")
        cesta = CESTY[zdroj]
        spojeni = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            spojeni.request("GET", cesta)
            odpoved = spojeni.getresponse()
            if odpoved.status != 200:
                raise ValueError(f"Zdroj {zdroj} vrátil HTTP {odpoved.status}.")
            return json.loads(odpoved.read())
        finally:
            spojeni.close()


def porovnej(vypisy, uol):
    """Spárovanost přebíráme z UOL až po kontrole banky, pohybu, částky a měny."""
    pohyby = {}
    for banka, zaznamy in vypisy.items():
        for zaznam in zaznamy:
            klic = (banka, zaznam["pohyb"])
            castka = Decimal(zaznam["castka"])
            if klic in pohyby or not castka.is_finite():
                raise ValueError("Nejednoznačný nebo neplatný pohyb na výpisu.")
            pohyby[klic] = (castka, zaznam["mena"])
    vysledek = dict.fromkeys(pohyby)
    for zaznam in uol:
        klic = (zaznam["banka"], zaznam["pohyb"])
        if (pohyby.get(klic) != (Decimal(zaznam["castka"]), zaznam["mena"])
                or vysledek[klic] is not None or not zaznam["doklad"]):
            raise ValueError("Párování UOL nesouhlasí s výpisem.")
        vysledek[klic] = zaznam["doklad"]
    return vysledek
