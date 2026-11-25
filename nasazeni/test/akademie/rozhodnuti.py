"""Přiloží oba doklady k testovacímu spisu a prověří jeho potvrzení v Decisions."""
import base64
import hashlib
import json
import re
import secrets
import sys
from urllib.parse import urlencode
from uuid import UUID

from board import Board


def attachment(board, company, case, name, encoded, digest):
    pdf = base64.b64decode(encoded, validate=True)
    if not pdf.startswith(b"%PDF-") or hashlib.sha256(pdf).hexdigest() != digest:
        raise ValueError("Předaná příloha neodpovídá archivnímu dokladu.")
    matches = [a for a in board.call("GET", f"/api/issues/{case}/attachments") if a["originalFilename"] == name]
    if not matches:
        boundary = secrets.token_hex(24)
        header = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
                  'Content-Type: application/pdf\r\n\r\n').encode()
        body = header + pdf + f"\r\n--{boundary}--\r\n".encode()
        raw = board.request("POST", f"/api/companies/{company}/issues/{case}/attachments", body,
                            "multipart/form-data; boundary=" + boundary, (201,))
        matches.append(json.loads(raw))
    item, = matches
    path = f"/api/attachments/{UUID(item['id'])}/content"
    if item["contentPath"] != path or item["contentType"] != "application/pdf" or board.request("GET", path) != pdf:
        raise RuntimeError("Paperclip vrátil jinou přílohu než archiv.")
    return str(UUID(item["id"]))


def drive(board, actor, data):
    record = data["zaznam"]
    issue = record["vydani"]
    if (record["rezim"] != "TEST" or record["osoba"] != "test-akademie-a" or record["procent"] != 100
            or len(set(record["komise"])) != 3 or not all(re.fullmatch(r"[0-9a-f]{64}", s)
            for s in (issue, record["protokol_sha256"], record["osvedceni_sha256"]))):
        raise ValueError("Neočekávané podklady cvičného rozhodnutí.")
    company, = [c for c in board.call("GET", "/api/companies") if c["name"] == "Polarita s.r.o." and c["budgetMonthlyCents"] == 47000]
    cid = str(UUID(company["id"]))
    root = f"/api/companies/{cid}"
    title = "Cvičná zkouška Akademie TEST · " + issue[:16]
    description = f"Instalační zkouška tříčlenné komise. Vydání Moodle {issue}. Účastník TEST A."
    cases = [c for c in board.call("GET", root + "/issues?" + urlencode({"q": issue[:16]})) if c["title"] == title]
    if not cases:
        cases.append(board.call("POST", root + "/issues", {"title": title, "description": description, "status": "backlog"}, (201,)))
    case, = cases
    if case["companyId"] != cid or case["description"] != description or case.get("createdByUserId") != actor:
        raise RuntimeError("Existující spis neodpovídá instalaci Akademie.")
    case_id = str(UUID(case["id"]))
    files = {}
    for kind, digest in (("osvedceni", record["osvedceni_sha256"]), ("protokol", record["protokol_sha256"])):
        files[kind] = attachment(board, cid, case_id, kind + "-test.pdf", data[kind], digest)
    payload = {
        "title": title, "summary": "Osvědčení a zapečetěný protokol odpovídají výsledku Offline Quiz. Oba PDF doklady jsou v přílohách spisu.",
        "recommendedAction": "Potvrdit cvičný protokol a předat datum další zkoušky do Lhůtníku.",
        "polarita": {"test": True, "operace": "akademie-komise", "vydani": issue, "spis": case_id,
                     "prilohy": files, "platnost_do": record["platnost_do"]},
    }
    approvals = [a for a in board.call("GET", root + "/approvals") if
                 (a["payload"].get("polarita") or {}).get("vydani") == issue]
    if not approvals:
        approvals.append(board.call("POST", root + "/approvals", {"type": "request_board_approval",
                             "issueIds": [case_id], "payload": payload}, (201,)))
    approval, = approvals
    aid = str(UUID(approval["id"]))
    path = "/api/approvals/" + aid
    if (approval["companyId"] != cid or approval["payload"] != payload or approval["type"] != "request_board_approval"
            or approval.get("requestedByUserId") != actor or [i["id"] for i in board.call("GET", path + "/issues")] != [case_id]):
        raise RuntimeError("Rozhodnutí nemá očekávaný obsah nebo vazbu na cvičný spis.")
    if approval["status"] == "pending":
        board.call("POST", path + "/approve", {"decisionNote": "Automatická zkouška předání protokolu fiktivní komise v režimu TEST."})
    final = board.call("GET", path)
    if final["status"] != "approved" or final.get("decidedByUserId") != actor:
        raise RuntimeError("Cvičné rozhodnutí nebylo potvrzeno účtem správce.")
    return {"rezim": "TEST", "spis": case_id, "identifier": case["identifier"], "approval": aid,
            "vydani": issue, "stav": final["status"], "prilohy": files, "url": f"https://{board.host}/{company['issuePrefix']}/approvals/{aid}"}


if __name__ == "__main__":
    board = Board(sys.argv[1])
    data = json.load(sys.stdin)
    actor = board.login(data.pop("heslo"))
    try:
        print(json.dumps(drive(board, actor, data)))
    finally:
        board.call("POST", "/api/auth/sign-out", {})
