"""Integrační zkouška místního HTTP výpisu ČS, Fio a přehledu spárovanosti UOL."""
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from threading import Thread

from vypis import CESTY, CteckaTest, porovnej


def over():
    vzor = json.loads(Path(__file__).with_name("vypis-TEST.json").read_bytes())
    odpovedi = {cesta: json.dumps(vzor[zdroj]).encode() for zdroj, cesta in CESTY.items()}
    dotazy = []

    class Zdroj(BaseHTTPRequestHandler):
        def do_GET(self):
            dotazy.append(("GET", self.path))
            if self.path not in odpovedi:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(odpovedi[self.path])

        def zakaz_zapisu(self):
            dotazy.append((self.command, self.path))
            self.send_response(405)
            self.send_header("Allow", "GET")
            self.end_headers()

        do_POST = do_PUT = do_PATCH = do_DELETE = zakaz_zapisu

        def log_message(self, *args):
            pass

    with HTTPServer(("127.0.0.1", 0), Zdroj) as server:
        vlakno = Thread(target=server.serve_forever)
        vlakno.start()
        try:
            ctecka = CteckaTest(server.server_port)
            vypisy = {banka: ctecka.nacti(banka) for banka in ("cs", "fio")}
            uol = ctecka.nacti("uol")
            ocekavane = {("cs", "TEST-001"): "TEST-PAUSAL-A", ("cs", "TEST-002"): None,
                         ("fio", "TEST-001"): "TEST-PAUSAL-B"}
            if porovnej(vypisy, uol) != ocekavane:
                raise ValueError("Výsledek neodpovídá předloze.")
            for zdroj in CESTY:
                for metoda in ("POST", "PUT", "PATCH", "DELETE"):
                    try:
                        ctecka.nacti(zdroj, metoda)
                    except PermissionError:
                        continue
                    raise RuntimeError("Čtečka umožnila zápis.")
            if dotazy != [("GET", cesta) for cesta in CESTY.values()]:
                raise RuntimeError("Čtečka odeslala nečekaný požadavek.")
            for cesta in CESTY.values():
                spojeni = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    spojeni.request("POST", cesta)
                    odpoved = spojeni.getresponse()
                    if odpoved.status != 405 or odpoved.getheader("Allow") != "GET":
                        raise RuntimeError("Zdroj přijal pokus o zápis.")
                finally:
                    spojeni.close()
            for chyba in ({"castka": "1840.11"}, {"mena": "EUR"}, {"pohyb": "chybi"}):
                try:
                    porovnej(vypisy, [uol[0] | chyba])
                except ValueError:
                    continue
                raise RuntimeError("Neshoda výpisu a párování UOL prošla kontrolou.")
        finally:
            server.shutdown()
            vlakno.join()
    print("Místní ČS, Fio a UOL TEST. Tři pohyby, dvě párování podle UOL a jeden nepřiřazený pohyb.")
    print("Čtečka provedla pouze tři GET. Simulátory zamítly přímý POST. Neshody částky, měny a pohybu zachyceny.")


if __name__ == "__main__":
    over()
