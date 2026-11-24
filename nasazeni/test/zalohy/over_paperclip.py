"""Porovná obnovené řídicí pozice, vazby a výsledek Stage 1 s daty z téhož snapshotu."""
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess


def query(sql):
    result = subprocess.run(
        ["runuser", "-u", "postgres", "--", "psql", "-XqAt", "-v", "ON_ERROR_STOP=1",
         "-U", "obnova_test", "-d", "db_paperclip"],
        input=sql, text=True, capture_output=True, check=True,
    )
    return result.stdout.splitlines()


def verify(root):
    data = root / "paperclip"
    if not data.exists() and query("SELECT to_regclass('public.agents') IS NULL") == ["t"]:
        return  # Snímek ze starší verze bez Paperclipu.
    plan = json.loads((data / "pozice.json").read_bytes())
    company = (plan["company"], plan["budget_cents"])
    rows = query("""
        SELECT json_build_array(c.name, c.budget_monthly_cents, a.metadata->>'polaritaId',
            a.name, parent.metadata->>'polaritaId', a.budget_monthly_cents)
        FROM agents a JOIN companies c ON c.id=a.company_id
        LEFT JOIN agents parent ON parent.id=a.reports_to AND parent.company_id=a.company_id
        WHERE a.metadata->>'polaritaId' IS NOT NULL
    """)
    actual = [tuple(json.loads(row)) for row in rows]
    expected = []
    for item in plan["agents"]:
        if hashlib.sha256(item["prompt"].encode()).hexdigest() != item["prompt_sha256"]:
            raise RuntimeError("Nesouhlasí otisk instrukce pozice " + item["id"])
        parent = None if item["reports_to"] == "1001" else item["reports_to"]
        expected.append((*company, item["id"], f'{item["name"]} (ai {item["id"]})', parent, item["operating_cents"]))
    if len(expected) != 20 or sorted(row for row in actual if row[:2] == company) != sorted(expected):
        raise RuntimeError("Obnovené vedení, vztahy nebo rozpočty Paperclipu neodpovídají kartám")
    eval_root = (data / "data/eval").resolve(strict=True)
    last = (eval_root / "posledni-stage1").resolve(strict=True)
    if last.parent != eval_root or not re.fullmatch(r"stage1\.[a-zA-Z0-9]{8}", last.name):
        raise RuntimeError("Neplatný odkaz na obnovený výsledek Stage 1")
    report, = last.glob("*.json")
    result = json.loads(report.read_bytes())
    if (result["mode"], result["suite"], result["evidence"], result["passed"], result["total"],
        result["failed"], result["verdict"]) != ("dry-run", "base", "REFERENCE_POLICY", 20, 20, 0, "VERIFIED_PASS"):
        raise RuntimeError("Obnovený výsledek Stage 1 nesouhlasí")
    print("Obnova Paperclipu ověřila organizační strom, rozpočty dvaceti pozic a výsledek Stage 1.")


if __name__ == "__main__":
    if (not re.fullmatch(r"restic-obnova-[a-f0-9]{12}", socket.gethostname().split(".")[0])
            or {path.name for path in Path("/sys/class/net").iterdir()} != {"lo"}):
        raise SystemExit("Kontrola vyžaduje izolovanou obnovu")
    verify(Path("/var/tmp/obnova-polarita"))
