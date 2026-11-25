"""Importuje kontrolovanou testovací metodiku, zafixovanou trasu a vyjádření do již založeného spisu."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import socket
import subprocess
from uuid import UUID


def uloz(src, case):
    if socket.gethostname().split(".")[0] != "postgres-test":
        raise RuntimeError("Zápis do registru vyžaduje databázovou instanci TEST.")
    raw = (src / "trasa.json").read_bytes()
    rev = sha256(raw).hexdigest()
    route = json.loads(raw)
    docs = json.loads((src / "doklady.json").read_bytes())
    policy = json.loads((src / "metodika.json").read_bytes())
    if (docs["revize"] != rev or any(s["revize"] != rev for s in docs["vyjadreni"].values())
            or set(docs["vyjadreni"]) != set(route["spravci"]) or policy["ucel"] != "simulace"):
        raise ValueError("Zdroje neodpovídají revizi trasy nebo zkušební metodice.")
    args = {"case": str(case), "rev": rev, "route": route["oznaceni"], "key": policy["kod"],
            "project": json.dumps(route), "docs": json.dumps(docs), "policy": json.dumps(policy)}
    sql = """
BEGIN;
SET LOCAL ROLE pol_metadata_ddl;
INSERT INTO polarita_test_spisy.vykop_metodika(kod,telo) VALUES(:'key',:'policy'::jsonb)
    ON CONFLICT (kod) DO NOTHING;
SELECT (telo=:'policy'::jsonb) AS shoda FROM polarita_test_spisy.vykop_metodika WHERE kod=:'key' FOR SHARE
\\gset
\\if :shoda
INSERT INTO polarita_test_spisy.vykop_trasa(spis,trasa,revize,metodika,projekt,doklady)
    VALUES (:'case'::uuid,:'route',:'rev',:'key',:'project'::jsonb,:'docs'::jsonb)
    ON CONFLICT (spis,trasa) DO UPDATE SET revize=EXCLUDED.revize,metodika=EXCLUDED.metodika,
        projekt=EXCLUDED.projekt,doklady=EXCLUDED.doklady;
COMMIT;
\\else
DO $$ BEGIN RAISE EXCEPTION 'Obsah již evidované verze metodiky se liší'; END $$;
\\endif
"""
    cmd = ["runuser", "-u", "postgres", "--", "psql", "-Xqw", "-v", "ON_ERROR_STOP=1", "-d", "db_erp_lhutnik"]
    for key, val in args.items():
        cmd += ["-v", key + "=" + val]
    subprocess.run(cmd, input=sql, text=True, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slozka", type=Path)
    parser.add_argument("spis", type=UUID)
    args = parser.parse_args()
    uloz(args.slozka, args.spis)
