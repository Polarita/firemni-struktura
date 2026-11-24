"""Založí kanonický strom v Paperclipu a porovná každou uloženou instrukci přes jeho API."""
import hashlib
import json
from pathlib import Path
import sys
from board import Board


def main():
    board = Board(sys.argv[1])
    board.login(sys.stdin.readline().rstrip("\r\n"))
    target = json.loads(Path("/etc/polarita-paperclip/pozice.json").read_bytes())
    description = "Testovací ředitelství Polarity · " + target["branch"]
    companies = [c for c in board.call("GET", "/api/companies") if c["name"] == target["company"]]
    if not companies:
        company = board.call("POST", "/api/companies", {
            "name": target["company"], "description": description, "budgetMonthlyCents": target["budget_cents"],
        }, allowed=(201,))
    else:
        company, = companies
    if company["description"] != description or company["budgetMonthlyCents"] != target["budget_cents"]:
        raise RuntimeError("Firma stejného jména má odlišnou identitu nebo rozpočet")
    path = "/api/companies/" + company["id"]
    rows = board.call("GET", path + "/agents")
    managed = {}
    names = set()
    for agent in rows:
        names.add(agent["name"])
        code = (agent.get("metadata") or {}).get("polaritaId")
        if code:
            if code in managed:
                raise RuntimeError("Duplicitní identita v Paperclipu " + code)
            managed[code] = agent
    restore_approval = company["requireBoardApprovalForNewAgents"]
    if restore_approval:
        board.call("PATCH", path, {"requireBoardApprovalForNewAgents": False})
    try:
        for item in target["agents"]:
            code = item["id"]
            name = f'{item["name"]} (ai {code})'
            manager = None if item["reports_to"] == "1001" else managed[item["reports_to"]]["id"]
            attributes = {
                "name": name, "role": "ceo" if item["sysid"] == "ceo" else "general",
                "title": item["sysid"], "reportsTo": manager, "budgetMonthlyCents": item["operating_cents"],
                "adapterType": "codex_local",
                "metadata": {"polaritaId": code, "polaritaSysid": item["sysid"], "zulipChannel": item["channel"],
                             "nominalCents": item["nominal_cents"], "reserveCents": item["reserve_cents"]},
            }
            if code not in managed:
                if name in names:
                    raise RuntimeError("Shoda jména s nespravovaným účtem " + code)
                managed[code] = board.call("POST", path + "/agents", {
                    **attributes, "instructionsBundle": {"entryFile": "AGENTS.md", "files": {"AGENTS.md": item["prompt"]}},
                    "runtimeConfig": {"heartbeat": {"enabled": False}},
                }, allowed=(201,))
            agent_path = "/api/agents/" + managed[code]["id"]
            saved = board.call("GET", agent_path)
            if any(saved.get(key) != value for key, value in attributes.items()):
                raise RuntimeError("Organizační údaje se rozcházejí u účtu " + code)
            instruction_path = agent_path + "/instructions-bundle/file"
            detail = board.call("GET", instruction_path + "?path=AGENTS.md")
            if hashlib.sha256(detail["content"].encode()).hexdigest() != item["prompt_sha256"]:
                # Aktualizace nové verze karty probíhá podporovaným API s ochranou souběžných revizí.
                update = {"path": "AGENTS.md", "content": item["prompt"]}
                if detail.get("revisionId"):
                    update["baseRevisionId"] = detail["revisionId"]
                board.call("PUT", instruction_path, update, allowed=(200, 201))
                detail = board.call("GET", instruction_path + "?path=AGENTS.md")
            if hashlib.sha256(detail["content"].encode()).hexdigest() != item["prompt_sha256"]:
                raise RuntimeError("Uložený systémový prompt nesouhlasí s kartou " + code)
    finally:
        if restore_approval:
            board.call("PATCH", path, {"requireBoardApprovalForNewAgents": True})
    if len(managed) != 20:
        raise RuntimeError("Počet registrovaných ai pozic neodpovídá")
    print("Paperclip potvrdil firmu, strom 20 pozic, samostatné měsíční kvóty a shodný obsah všech 20 systémových promptů.")


if __name__ == "__main__":
    main()
