"""HTTP pro vlastní entity přes privátní unixový socket."""
from http.server import BaseHTTPRequestHandler
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import socketserver
import sys
from uuid import UUID
from urllib.parse import urlsplit

import kniha
import vykop_api
from model import load, unique
from spisy import casova_osa, najdi, prevzate_sanony, zaloz
from zaznamy import Problem, query, read, write


def slozka_spisu(karta, oddil):
    return Path("/opt/polarita-inzenyring-test") / oddil / str(UUID(karta["pozadavek"])) / "current"


def pas_rozvadece(karta, serial, vydani="current"):
    base = slozka_spisu(karta, "pasy").parent / serial / vydani
    # Získat jedno neměnné vydání i během souběžné aktualizace ukazatele current.
    directory = base.resolve()
    info = directory / "prehled.json"
    if info.is_file():
        data = json.loads(info.read_bytes())
        if data["case_id"] == karta["case_id"] and data["vyrobni_cislo"] == serial:
            return directory, data
    return None


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, payload, mime="application/json", tag=None):
        if mime == "application/json":
            payload = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        if tag:
            self.send_header("ETag", f'"{tag}"')
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        pass  # journald přijímá provozní chyby, záznamy obsahují údaje spisu.

    def request_body(self):
        if self.headers.get_content_type() != "application/json":
            raise Problem(415, "Očekáván JSON")
        size = self.headers.get("Content-Length", "")
        if not size.isdigit() or not 0 < int(size) <= 2**20:
            raise Problem(400, "Neplatná délka požadavku")
        return json.loads(self.rfile.read(int(size)), object_pairs_hook=unique)

    def dispatch(self):
        path = urlsplit(self.path).path
        data = self.server.data
        route = "/api/" + data["entity"]
        static = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/spisy": ("spisy.html", "text/html; charset=utf-8"),
                  "/spisy.js": ("spisy.js", "text/javascript; charset=utf-8"),
                  "/formular.js": ("formular.js", "text/javascript; charset=utf-8"),
                  "/openapi.json": ("openapi.json", "application/json; charset=utf-8")}
        if self.command == "GET" and path in static:
            filename, mime = static[path]
            self.reply(200, (self.server.directory / filename).read_bytes(), mime)
            return
        if self.command == "GET" and path == "/zkousky":
            dates = query(data, """SELECT coalesce(json_agg(r ORDER BY platnost_do,spis),'[]') FROM
                (SELECT spis,platnost_do FROM polarita_test_lhutnik.zkousky) r;""")
            lines = "".join(f'<li>{escape(row["spis"])} · <time datetime="{row["platnost_do"]}">'
                            f'{row["platnost_do"][8:]}.{row["platnost_do"][5:7]}.{row["platnost_do"][:4]}</time></li>' for row in dates)
            listing = "<ul>" + lines + "</ul>" if dates else "<p>Dosud nebyla potvrzena žádná zkouška.</p>"
            page = ('<!doctype html><html lang="cs"><meta charset="utf-8"><meta name="viewport" '
                    'content="width=device-width,initial-scale=1"><title>Termíny zkoušek Akademie</title>'
                    '<main><a href="./">Lhůtník</a><h1>Termíny zkoušek Akademie</h1>' + listing + '</main></html>')
            self.reply(200, page.encode(), "text/html; charset=utf-8")
            return
        if self.command == "POST" and path == "/api/spisy":
            self.reply(200, zaloz(data, self.request_body()))
            return
        if self.command == "GET" and path.startswith("/api/pasy/"):
            match = re.fullmatch(r"/api/pasy/([^/]+)/(RZ-[0-9]{4}-[0-9]{5})/(?:([0-9a-f]{64})/)?vyrobni-pas\.pdf", path)
            if not match:
                raise Problem(404, "Neznámý výrobní pas.")
            kod, serial, vydani = match.groups()
            karta = najdi(data, kod)
            cisla = query(data, """SELECT to_json(count(*)) FROM polarita_test_spisy.vyrobni_cisla
                          WHERE case_id=:'kod' AND vyrobni_cislo=:'serial';""", kod=karta["case_id"], serial=serial)
            pas = pas_rozvadece(karta, serial, vydani or "current") if cisla == 1 else None
            if not pas:
                raise Problem(404, "Ve spisu chybí vydání pasu pro tento kus.")
            directory, info = pas
            raw = (directory / "vyrobni-pas.pdf").read_bytes()
            if vydani and sha256((directory / "SHA256SUMS").read_bytes()).hexdigest() != vydani:
                raise Problem(409, "Manifest neodpovídá požadovanému vydání.")
            if sha256(raw).hexdigest() != info["pdf_sha256"]:
                raise Problem(409, "Obsah vydaného PDF se změnil.")
            self.reply(200, raw, "application/pdf")
            return
        if self.command == "GET" and path.startswith("/api/revize/"):
            parts = path.removeprefix("/api/revize/").split("/")
            if len(parts) != 2 or parts[1] != "navrh.pdf":
                raise Problem(404, "Neznámý revizní doklad.")
            file = slozka_spisu(najdi(data, parts[0]), "revize") / "navrh.pdf"
            if not file.is_file():
                raise Problem(404, "Spis nemá návrh revizní zprávy.")
            self.reply(200, file.read_bytes(), "application/pdf")
            return
        if self.command == "GET" and path.startswith("/api/rozpocty/"):
            parts = path.removeprefix("/api/rozpocty/").split("/")
            formats = {"nabidka.xc4": "application/octet-stream",
                       "nabidka.xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
            if len(parts) != 2 or parts[1] not in formats:
                raise Problem(404, "Neznámý formát nabídky.")
            karta = najdi(data, parts[0])
            file = slozka_spisu(karta, "rozpocty") / parts[1]
            if not file.is_file():
                raise Problem(404, "Spis nemá tuto nabídku.")
            self.reply(200, file.read_bytes(), formats[parts[1]])
            return
        if path.startswith("/api/vykopy/") and self.command in ("GET", "POST"):
            post = self.command == "POST"
            self.reply(200, vykop_api.kontrola(data, path.removeprefix("/api/vykopy/"),
                                               self.request_body() if post else None, uvolnit=post))
            return
        if path.startswith("/api/kniha/") and self.command in ("GET", "POST"):
            kod = path.removeprefix("/api/kniha/")
            rows = kniha.prehled(data, kod) if self.command == "GET" else kniha.zaznam(data, kod, self.request_body())
            self.reply(200, rows)
            return
        if self.command == "GET" and path.startswith("/api/sanony/"):
            self.reply(200, prevzate_sanony(data, path.removeprefix("/api/sanony/")))
            return
        if self.command == "GET" and path.startswith("/api/spisy/"):
            parts = path.removeprefix("/api/spisy/").split("/")
            if len(parts) in (2, 3) and parts[1] == "osa":
                self.reply(200, casova_osa(data, parts[0], parts[2] if len(parts) == 3 else None))
            else:
                karta = najdi(data, parts[0] if len(parts) == 1 else "")
                if (slozka_spisu(karta, "rozpocty") / "SHA256SUMS").is_file():
                    karta["ma_rozpocet"] = True
                rozvadece = query(data, """SELECT coalesce(json_agg(r ORDER BY vyrobni_cislo),'[]') FROM
                    (SELECT oznaceni,vyrobni_cislo FROM polarita_test_spisy.vyrobni_cisla
                     WHERE case_id=:'kod') r;""", kod=karta["case_id"])
                if rozvadece:
                    for panel in rozvadece:
                        pas = pas_rozvadece(karta, panel["vyrobni_cislo"])
                        if pas:
                            panel["pas"] = pas[1]
                    karta["rozvadece"] = rozvadece
                prehled = slozka_spisu(karta, "revize") / "prehled.json"
                if prehled.is_file():
                    karta["revizni_navrh"] = json.loads(prehled.read_bytes())
                self.reply(200, karta)
            return
        if self.command == "POST" and path == route:
            row = write(data, self.request_body())
            self.reply(201, row, tag=row["version"])
            return
        if not path.startswith(route + "/"):
            raise Problem(404, "Neznámá cesta")
        key = path[len(route) + 1:]
        if self.command == "GET":
            row = read(data, key)
        elif self.command == "PUT":
            body = self.request_body()
            header = self.headers.get("If-Match")
            if header is None:
                raise Problem(428, "Pro změnu je nutná verze záznamu")
            if not re.fullmatch(r'"[1-9][0-9]{0,18}"', header) or int(header[1:-1]) >= 2**63:
                raise Problem(412, "Očekáván ETag načteného záznamu")
            row = write(data, body, key, int(header[1:-1]))
        else:
            raise Problem(405, "Nepodporovaná metoda")
        self.reply(200, row, tag=row["version"])

    def handle_request(self):
        try:
            self.dispatch()
        except Problem as error:
            self.reply(error.status, {"error": str(error)})
        except (ValueError, UnicodeError, RecursionError):
            self.reply(400, {"error": "Neplatný obsah požadavku"})
        except (OSError, RuntimeError, TimeoutError) as error:
            print(type(error).__name__, file=sys.stderr, flush=True)
            self.reply(503, {"error": "Databáze není dostupná"})

    do_GET = do_PUT = do_POST = handle_request


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True

    def get_request(self):
        conn, address = super().get_request()
        conn.settimeout(20)
        return conn, address


if __name__ == "__main__":
    directory, socket = map(Path, sys.argv[1:])
    data = load(directory / "entity.json")
    if socket.is_socket():
        socket.unlink()
    with Server(str(socket), Handler) as server:
        server.directory = directory
        server.data = data
        server.serve_forever()
