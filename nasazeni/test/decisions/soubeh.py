"""Dvě relace hradla rozhodnou současně nad shodnou verzí jednoho vzorového spisu."""
from concurrent.futures import ThreadPoolExecutor
import secrets
import subprocess
import uuid


def sql(query, *, required=True):
    result = subprocess.run(
        ["incus", "exec", "-T", "postgres-test", "--", "runuser", "-u", "postgres", "--",
         "psql", "-XqAt", "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=sqlstate", "-d", "db_paperclip"],
        input=query, text=True, capture_output=True, timeout=45,
    )
    if required:
        result.check_returncode()
    return result


def main():
    # Vlastnictví spisu určuje úspěšný INSERT. Cizí případy se nikdy nepoužijí pro zkoušku.
    for _ in range(10):
        case = f"TEST-POL-0000-{1 + secrets.randbelow(99999):05d}"
        if sql(f"INSERT INTO polarita.test_spis(cislo,stav) VALUES ('{case}','rozpracován') "
               "ON CONFLICT DO NOTHING RETURNING cislo").stdout.strip() == case:
            break
    else:
        raise RuntimeError("Nelze přidělit volný vzorový spis")
    proposals = (uuid.uuid4(), uuid.uuid4())
    try:
        sql("BEGIN; SET LOCAL ROLE pol_decisions_proposer;" + "".join(
            f"SELECT polarita.test_navrh('{proposal}','{case}',1,'{state}','URGENT');"
            for proposal, state in zip(proposals, ('ke kontrole', 'uzavřen'))
        ) + "COMMIT;")

        def approve(proposal):
            return sql(f"BEGIN; SET LOCAL ROLE pol_decisions_reviewer; "
                       f"SELECT polarita.test_rozhodni('{proposal}', 'mutation_confirm'); "
                       "SELECT pg_sleep(0.4); COMMIT;", required=False)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(approve, proposals))
        if (sum(r.returncode == 0 for r in results) != 1 or
                sum(r.returncode != 0 and '40001' in r.stderr for r in results) != 1):
            raise RuntimeError("Souběžné potvrzení musí právě jednou odmítnout zastaralou verzi")
        audit = sql(f"SELECT s.verze, count(*) FILTER (WHERE r.akce='mutation_confirm' AND r.po=s.stav), "
                    "count(*) FILTER (WHERE r.akce IS NULL) FROM polarita.test_spis s "
                    "JOIN polarita.test_rozhodnuti r USING(cislo) "
                    f"WHERE s.cislo='{case}' GROUP BY s.verze").stdout.strip()
        if audit != '2|1|1':
            raise RuntimeError("Audit po souběhu nesouhlasí s verzí spisu")
    finally:
        sql(f"BEGIN; DELETE FROM polarita.test_rozhodnuti WHERE cislo='{case}' AND id IN "
            f"('{proposals[0]}', '{proposals[1]}'); DELETE FROM polarita.test_spis WHERE cislo='{case}'; COMMIT;")
    print("Dvě nezávislé relace potvrdily různé návrhy nad stejnou verzí. Pouze jeden změnil spis a zapsal souhlas.")


if __name__ == "__main__":
    main()
