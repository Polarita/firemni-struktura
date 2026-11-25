"""Nativní fronta Decisions s PDF a diffem technického výroku pro revizního technika."""
import json
import sys
from urllib.parse import urlencode
from uuid import UUID

from board import Board
from rozhodnuti import attachment


def predloz(board, actor, packet):
    model = packet["model"]
    digest = packet["pdf_sha256"]
    company, = [c for c in board.call("GET","/api/companies") if c["name"]=="Polarita s.r.o." and c["budgetMonthlyCents"]==47000]
    cid = str(UUID(company["id"]))
    root = "/api/companies/"+cid
    title = f'{model["spis"]} · Cvičný návrh revizní zprávy · {digest[:16]}'
    description = f'Cvičný projekt {model["projekt"]}. PDF a vyhodnocení měření jsou určeny k odbornému posouzení v TESTu.'
    cases = [i for i in board.call("GET",root+"/issues?"+urlencode({"q":digest[:16]})) if i["title"]==title]
    if not cases:
        cases = [board.call("POST",root+"/issues",dict(title=title,description=description,status="backlog"), (201,))]
    case, = cases
    if case["companyId"] != cid or case["description"] != description or case.get("createdByUserId") != actor:
        raise ValueError("Nesouhlasí identita testovacího spisu v Paperclipu.")
    issue = str(UUID(case["id"]))
    file_id = attachment(board,cid,issue,"navrh-revize.pdf",packet["pdf"],digest)
    after = {"stav":model["stav"], "zavady":model["zavady"], "podpis":model["podpis"], "predani_do_provozu":False}
    after["vyrobni_cislo"] = model["pas"]["vyrobni_cislo"]
    after["pas_sha256"] = model["pas"]["pdf_sha256"]
    after["vydani_pasu"] = model["pas"]["vydani"]
    data = {"test":True,"operace":"revize-navrh","sha256":digest,"spis":model["spis"],"priloha":file_id,
            "pred":{"stav":"mereni-prijato","predani_do_provozu":False},"po":after}
    payload = {"title":title,"summary":"Návrh vyhodnocení naměřených hodnot. Předání do provozu je zablokované.",
               "recommendedAction":"Projděte měření a cvičné podklady. Odborný podpis se připojuje samostatně.",
               "polarita":data}
    proposals = [a for a in board.call("GET",root+"/approvals") if
                 (a["payload"].get("polarita") or {}).get("sha256")==digest and
                 (a["payload"].get("polarita") or {}).get("operace")=="revize-navrh"]
    if not proposals:
        proposals = [board.call("POST",root+"/approvals",{"type":"request_board_approval","issueIds":[issue],"payload":payload},(201,))]
    approval, = proposals
    aid = str(UUID(approval["id"]))
    if (approval["companyId"]!=cid or approval["payload"]!=payload or approval.get("requestedByUserId")!=actor
            or approval["type"]!="request_board_approval" or [i["id"] for i in board.call("GET",f"/api/approvals/{aid}/issues")]!=[issue]):
        raise ValueError("Obsah rozhodnutí nebo vazba na spis nesouhlasí.")
    return {"rozhodnuti": f"https://{board.host}/{company['issuePrefix']}/approvals/{aid}", "priloha":file_id,
            "spis_paperclip":case["identifier"], "pdf_sha256":digest, **after}


if __name__ == "__main__":
    board = Board(sys.argv[1])
    packet = json.load(sys.stdin)
    actor = board.login(packet.pop("heslo"))
    try:
        print(json.dumps(predloz(board, actor, packet), ensure_ascii=False))
    finally:
        board.call("POST", "/api/auth/sign-out", {})
