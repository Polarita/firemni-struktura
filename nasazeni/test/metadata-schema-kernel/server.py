"""HTTP pro vlastní entity přes privátní unixový socket."""
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import re
import socketserver
import sys
from urllib.parse import urlsplit

import kniha
from model import load, unique
from spisy import casova_osa, najdi, prevzate_sanony, zaloz
from zaznamy import Problem, read, write


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
        if self.command == "POST" and path == "/api/spisy":
            self.reply(200, zaloz(data, self.request_body()))
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
                self.reply(200, najdi(data, parts[0] if len(parts) == 1 else ""))
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
