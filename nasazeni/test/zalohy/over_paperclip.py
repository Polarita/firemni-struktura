"""Porovná obnovené řídicí pozice, vazby a výsledek Stage 1 s daty z téhož snapshotu."""
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
from uuid import UUID


def query(sql):
    result = subprocess.run(
        ["runuser", "-u", "postgres", "--", "psql", "-XqAt", "-v", "ON_ERROR_STOP=1",
         "-U", "obnova_test", "-d", "db_paperclip"],
        input=sql, text=True, capture_output=True, check=True,
    )
    return result.stdout.splitlines()


def over_zdroj(repozitar, plan):
    source = plan["zdroj_gitea"]
    commit, tree = source["commit"], source["tree"]
    if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (commit, tree)):
        raise ValueError("Chybí jednoznačná revize zdrojových pravidel")
    git = ["git", "--git-dir=" + str(repozitar)]
    if subprocess.check_output(git + ["rev-parse", commit + "^{tree}"], text=True).strip() != tree:
        raise RuntimeError("Obnovená Gitea neobsahuje strom instrukcí")
    def blob(path):
        return subprocess.check_output(git + ["cat-file", "blob", f"{commit}:{path}"])

    canon = json.loads(blob("nastroje/kanon.json"))
    files = subprocess.check_output(git + ["ls-tree", "-r", "--name-only", tree, "--",
                                          "agenti-a-prompty", "oddeleni"], text=True).splitlines()
    shared = blob("agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md")
    expected = {}
    for item in canon["agents"]:
        code = item["id"]
        charter, = (name for name in files if name.startswith("oddeleni/" + item["department"] + "-"))
        card, = (name for name in files if name.startswith("agenti-a-prompty/" + code + "-"))
        expected[code] = hashlib.sha256(b"\n\n".join((shared, blob(charter), blob(card)))).hexdigest()
    actual = {agent["id"]: agent["prompt_sha256"] for agent in plan["agents"]}
    if len(expected) != 20 or expected != actual:
        raise RuntimeError("Instrukce rolí se liší od úplných souborů obnovené Gitey")
    print("Obnovená Gitea potvrdila revizi a úplné znění pravidel pro všech dvacet pozic Paperclipu.")


def verify(root):
    data = root / "paperclip"
    if not data.exists() and query("SELECT to_regclass('public.agents') IS NULL") == ["t"]:
        return  # Snímek ze starší verze bez Paperclipu.
    plan = json.loads((data / "pozice.json").read_bytes())
    if "zdroj_gitea" in plan:
        over_zdroj(root / "gitea/spravce/firemni-struktura-test.git", plan)
    company = (plan["company"], plan["budget_cents"])
    rows = query("""
        SELECT json_build_array(c.name, c.budget_monthly_cents, a.metadata->>'polaritaId',
            a.name, parent.metadata->>'polaritaId', a.budget_monthly_cents,
            c.id, a.id, a.adapter_config->>'instructionsFilePath')
        FROM agents a JOIN companies c ON c.id=a.company_id
        LEFT JOIN agents parent ON parent.id=a.reports_to AND parent.company_id=a.company_id
        WHERE a.metadata->>'polaritaId' IS NOT NULL
    """)
    actual = []
    files = (data / "data").resolve(strict=True)
    for row in rows:
        name, budget, code, agent_name, parent, allocation, company_id, agent_id, filename = json.loads(row)
        if (name, budget) != company:
            continue
        relative = (Path("instances/default/companies") / str(UUID(company_id))
                    / "agents" / str(UUID(agent_id)) / "instructions/AGENTS.md")
        if filename != str(Path("/var/lib/paperclip") / relative):
            raise RuntimeError("Obnovená pozice má jinou cestu instrukce " + code)
        instruction = files / relative
        if instruction.resolve(strict=True) != instruction:
            raise RuntimeError("Obnovená instrukce vede na jinou cestu " + code)
        digest = hashlib.sha256(instruction.read_bytes()).hexdigest()
        actual.append((name, budget, code, agent_name, parent, allocation, digest))
    expected = []
    for item in plan["agents"]:
        if hashlib.sha256(item["prompt"].encode()).hexdigest() != item["prompt_sha256"]:
            raise RuntimeError("Nesouhlasí otisk instrukce pozice " + item["id"])
        parent = None if item["reports_to"] == "1001" else item["reports_to"]
        expected.append((*company, item["id"], f'{item["name"]} (ai {item["id"]})', parent, item["operating_cents"], item["prompt_sha256"]))
    if len(expected) != 20 or sorted(actual) != sorted(expected):
        raise RuntimeError("Obnovené vedení, instrukce, vztahy nebo rozpočty Paperclipu neodpovídají kartám")
    eval_root = (data / "data/eval").resolve(strict=True)
    last = (eval_root / "posledni-stage1").resolve(strict=True)
    if last.parent != eval_root or not re.fullmatch(r"stage1\.[a-zA-Z0-9]{8}", last.name):
        raise RuntimeError("Neplatný odkaz na obnovený výsledek Stage 1")
    report, = last.glob("*.json")
    result = json.loads(report.read_bytes())
    if (result["mode"], result["suite"], result["evidence"], result["passed"], result["total"],
        result["failed"], result["verdict"]) != ("dry-run", "base", "REFERENCE_POLICY", 20, 20, 0, "VERIFIED_PASS"):
        raise RuntimeError("Obnovený výsledek Stage 1 nesouhlasí")
    print("Obnova Paperclipu ověřila organizační strom, instrukce i rozpočty dvaceti pozic a výsledek Stage 1.")


if __name__ == "__main__":
    if (not re.fullmatch(r"restic-obnova-[a-f0-9]{12}", socket.gethostname().split(".")[0])
            or {path.name for path in Path("/sys/class/net").iterdir()} != {"lo"}):
        raise SystemExit("Kontrola vyžaduje izolovanou obnovu")
    verify(Path("/var/tmp/obnova-polarita"))
