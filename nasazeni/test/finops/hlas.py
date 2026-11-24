"""Hlasování správce TEST nad jediným zřetelně označeným vzorem, bez spuštění agenta."""
import json
import sys
from uuid import UUID

sys.path.insert(0, "/etc/polarita-paperclip")
from board import Board

def main():
    fqdn, raw = sys.argv[1:]
    scope = json.loads(raw)
    for key in ("navrh","ukol"):
        UUID(scope[key])
    if scope["rezim"]!="TEST" or scope["pozice"]!="16002" or scope["centy"]!=1:
        raise ValueError("Neplatný zkušební návrh")
    board = Board(fqdn)
    user = board.login(sys.stdin.readline().rstrip("\r\n"))
    try:
        company, = [c for c in board.call("GET","/api/companies") if c["name"]=="Polarita s.r.o." and c["budgetMonthlyCents"]==47000]
        path = "/api/companies/"+company["id"]+"/approvals"
        payload = {"title":"Zkouška rezervy P1 · "+scope["mesic"],
                   "summary":"Před změnou má tento zkušební úkol uvolněno 0,00 USD. Po potvrzení může technická role uvolnit 0,01 USD pro pozici 16002.",
                   "recommendedAction":"Automatická zkouška ověří potvrzení a pročte jeho rozsah. Model se nespouští.",
                   "polaritaFinOps":scope}
        rows = [a for a in board.call("GET",path) if (a.get("payload") or {}).get("polaritaFinOps",{}).get("navrh")==scope["navrh"]]
        if not rows:
            rows = [board.call("POST",path,{"type":"request_board_approval","payload":payload},allowed=(201,))]
        a, = rows
        if (a["payload"]!=payload or a["type"]!="request_board_approval" or a["companyId"]!=company["id"]
            or a.get("requestedByUserId")!=user or a.get("requestedByAgentId") is not None):
            raise RuntimeError("Nesouhlasí původ zkušebního hlasování")
        aid = str(UUID(a["id"]))
        if a["status"]=="pending":
            board.call("POST","/api/approvals/"+aid+"/approve",{"decisionNote":"Automatická zkouška potvrzení jednoho centu v TEST."})
        a=board.call("GET","/api/approvals/"+aid)
        if a["status"]!="approved" or a.get("decidedByUserId")!=user or a["payload"]!=payload:
            raise RuntimeError("FinOps nemá požadované hlasování správce TEST")
        print(aid)
    finally:
        board.call("POST","/api/auth/sign-out",{})

if __name__=="__main__":
    main()
