"""Ověřuje běžné CLI se skutečnými identitami, trvalým Gitem a databází."""
import json
import subprocess

def call(role,*args,body=b"",success=True):
    p = subprocess.run(["runuser","-u","pol-vault-"+role,"--","/usr/local/bin/agent_vault",*args],
                       input=body,capture_output=True,timeout=240)
    if (p.returncode==0)!=success:
        # Reálný obsah požadavku ani dokumentů se nedostává do protokolu.
        raise RuntimeError(f"Operace {args[0]} role {role} skončila kódem {p.returncode}")
    return json.loads(p.stdout) if success else None

def main():
    pages = call("11001","get-context")["stranky"]
    charters = [f"02-Oddeleni-a-Procesy/utvar-{n}.md" for n in range(11,19)]
    if not set(charters+["00-Meta/pobocky.md","08-Deniky-a-Predavky/sablona-predavky.md"]).issubset(pages):
        raise RuntimeError("Neúplné organizační podklady")
    if "CZ-101" not in call("11001","get-context","00-Meta/pobocky.md")["text"]:
        raise RuntimeError("Chybí pražská centrála")
    for path in ("test-login/heslo","../data/bootstrap-test","00-Meta/../../.git/config"):
        call("11001","get-context",path,success=False)
    before=call("11001","get-context")["revize"]
    for kind in ("log","adr"):
        call("11001",kind,"zkouska-stinu",body=b"TEST",success=False)
    call("17005","log","zkouska-osobnich-udaju",body=b"fixture@example.invalid",success=False)
    if call("11001","get-context")["revize"]!=before:
        raise RuntimeError("Zamítnutý zápis změnil historii")
    for kind,body in (("log","Ověření předání provozní služby ve zkušebním prostředí."),
                      ("adr","Sémantické vyhledávání běží místně nad revizí znalostního Gitu.")):
        saved = call("17005",kind,"predani-instalace",body=body.encode())
        again = call("17005",kind,"predani-instalace",body=body.encode())
        if saved!=again or body not in call("11001","get-context",saved["cesta"])["text"]:
            raise RuntimeError("Předávka nebo rozhodnutí nejsou trvalé a opakovatelné.")
    matches = call("11001","search","Kdo obstarává materiál a řídí zásoby internetového obchodu?","--limit","3")
    if charters[2] not in [r["cesta"] for r in matches["vysledky"]] or any(not -1<=r["shoda"]<=1 for r in matches["vysledky"]):
        raise RuntimeError("Český sémantický dotaz nenašel odpovědné obchodní oddělení")
    print("Agent CEO v SHADOW přečetl pobočku CZ-101 a osm útvarů. Zápisy CEO, cizí cesta a syntetický osobní údaj byly odmítnuty.")
    print("Role 17005 uložila předávku a ADR do Gitu. Opakování zachovalo revizi a účet CEO oba výsledky přečetl.")
    print("Místní model E5 a pgvector nalezly útvar 13 v prvních třech odpovědích na český dotaz. Revize znalostí "+matches["revize"]+".")

if __name__=="__main__":
    main()
