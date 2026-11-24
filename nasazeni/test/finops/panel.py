#!/usr/bin/python3
"""Živé hodnoty FinOps z lokálního socketu PostgreSQL pro stavový řádek."""
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys

BASE = Path("/usr/local/lib/polarita/finops")

def dollars(cents):
    return f"{Decimal(cents)/100:.2f}".replace(".", ",")

def main():
    args = sys.argv[1:]
    if args not in ([],["--json"]):
        raise SystemExit("Použití: polarita-powerline [--json]")
    raw = subprocess.check_output(["psql","-XqAtw","-v","ON_ERROR_STOP=1","-U","pol_finops_read","-d","db_paperclip",
                                   "-h","/run/postgresql","-c","SELECT polarita_finops.stav()"],text=True,timeout=12)
    s = json.loads(raw,parse_float=Decimal)
    if len(s["pozice"])!=20 or s["strop_cent"]!=47000:
        raise RuntimeError("Rozpočet Paperclipu nelze potvrdit")
    if args:
        print(raw.strip())
        return
    line = subprocess.check_output([BASE/"claude-powerline","--basename","--style","minimal","--config",BASE/"powerline.json"],
                                   stdin=subprocess.DEVNULL,text=True,timeout=6).strip()
    warnings = [r["pozice"] for r in s["pozice"] if r["varovani_80"]]
    state = "STOP" if s["globalni_stop"] else ("80 %" if s["varovani_80"] else "v limitu")
    print(f"{line}  Polarita TEST · {s['mesic']} UTC · {dollars(s['cerpano_a_rezervovano_cent'])} / "
          f"{dollars(s['strop_cent'])} USD · {state} · P1 {dollars(sum(r['p1'] for r in s['pozice']))} / "
          f"{dollars(s['rezerva_cent'])} USD" + (" · 80 % kvóty: "+", ".join(warnings) if warnings else ""))

if __name__=="__main__":
    main()
