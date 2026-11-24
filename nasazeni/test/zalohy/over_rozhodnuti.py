"""Ověření schvalovací fronty a služebního účtu nad izolovaně obnovenou databází."""
import json
from pathlib import Path
import re
import socket
import subprocess


def sql(query):
    return subprocess.check_output(
        ["runuser", "-u", "postgres", "--", "psql", "-XqAtw", "-v", "ON_ERROR_STOP=1",
         "-U", "obnova_test", "-d", "db_paperclip"], input=query, text=True).splitlines()


def over(data):
    marker = data / "rozhodnuti.json"
    if sql("SELECT to_regclass('polarita.test_vazba') IS NULL") == ["t"] and not marker.exists():
        return
    # Nevyřízený nativní hlas se může dostat do zálohy před následujícím spuštěním časovače.
    # Převzetí se vyzkouší v izolované transakci; původní obnovené hodnoty zachová ROLLBACK.
    rows = sql("""
        BEGIN;
        SET LOCAL ROLE pol_decisions_bridge;
        SELECT polarita.test_prevez();
        RESET ROLE;
        SELECT json_build_object('spis',s.cislo,'approval',a.id,'company',a.company_id,'spravce',v.spravce,
                'obsah',a.payload,'stav',s.stav,'verze',s.verze,'vysledek',v.vysledek,'hlas',a.status,
                'puvod',a.type='request_board_approval' AND v.obsah=a.payload AND v.company=a.company_id
                      AND v.spravce=a.requested_by_user_id AND a.requested_by_agent_id IS NULL
                      AND u.email='spravce@polarita.test' AND (a.status='pending' OR v.spravce=a.decided_by_user_id),
                'pred',z.pred,'po',z.po,'verze_pred',z.verze_pred)
            FROM polarita.test_spis s JOIN polarita.test_rozhodnuti z USING(cislo)
            JOIN polarita.test_vazba v ON v.navrh=z.id JOIN public.approvals a ON a.id=v.approval
            JOIN public."user" u ON u.id=v.spravce
            WHERE s.cislo IN ('TEST-POL-0000-00011','TEST-POL-0000-00012','TEST-POL-0000-00013')
            ORDER BY s.cislo;
        ROLLBACK;
    """)
    receipts = [json.loads(r) for r in rows if r]
    if len(receipts) != 3:
        raise RuntimeError("Obnovená fronta neobsahuje tři samostatné vzory")
    expected = (("approved",), ("rejected",), ("pending", "approved", "rejected", "revision_requested"))
    states = {"approved": ("potvrzeno", "ke kontrole", 2), "rejected": ("zamitnuto", "rozpracován", 1),
              "pending": (None, "rozpracován", 1), "revision_requested": (None, "rozpracován", 1)}
    for row, allowed in zip(receipts, expected):
        if (row['hlas'] not in allowed or not row['puvod'] or
                (row['pred'], row['po'], row['verze_pred']) != ('rozpracován', 'ke kontrole', 1) or
                (row['vysledek'], row['stav'], row['verze']) != states[row['hlas']]):
            raise RuntimeError("Nativní hlas, diff nebo obnovený stav spisu se liší")
    if marker.exists():
        expected_manifest = json.loads(marker.read_text())
        if [{k:r[k] for k in ('approval','company','spravce','obsah')} for r in receipts] != expected_manifest:
            raise RuntimeError("Nativní žádosti a jejich původ se liší od soupisu v záloze")
    print("Obnovený Paperclip i Decisions potvrzují oba hlasy, jejich původ, přesný diff a verze tří vzorových spisů.")


def over_finops(data):
    marker = data / "finops.json"
    if not marker.is_file():
        return  # Starší souborová záloha ještě neukládala doklad rozpočtového vzoru.
    expected = json.loads(marker.read_bytes())
    rows = sql("""
        SELECT jsonb_build_object('hlas',a.id,'rozsah',a.rozsah)
        FROM polarita_finops.uvolneni u JOIN polarita_finops.hlasovani a ON a.id=u.hlas
        JOIN polarita_finops.navrhy n ON n.id=u.navrh AND n.ukol=u.ukol AND n.prijemce=u.pozice
        WHERE a.rozsah = jsonb_build_object('navrh',n.id,'rezim','TEST','mesic',to_char(n.mesic,'YYYY-MM'),
            'pozice',u.pozice,'ukol',u.ukol,'centy',u.centy) AND n.mesic=u.mesic AND n.centy=u.centy;
    """)
    if expected not in [json.loads(row) for row in rows]:
        raise RuntimeError("Obnova FinOps ztratila vazbu návrhu, souhlasu nebo technického uvolnění")
    states=sql("BEGIN; SET LOCAL ROLE pol_finops_read; SELECT polarita_finops.stav(); ROLLBACK;")
    state=json.loads(states[0])
    if (len(state['pozice']),state['strop_cent'],sum(r['kvota'] for r in state['pozice']),state['rezerva_cent'])!=(20,47000,39950,7050):
        raise RuntimeError("Obnovené kvóty nebo souhrnný limit Paperclipu nesouhlasí")
    print("Obnovený rozpočet ověřil dvacet kvót a věcně svázaný doklad P1.")

if __name__ == "__main__":
    if not re.fullmatch(r"(restic-obnova-[a-f0-9]{12}|obnova-pg-[a-f0-9]{10})",socket.gethostname().split(".")[0]) or {
            p.name for p in Path("/sys/class/net").iterdir()} != {"lo"}:
        raise SystemExit("Ověření vyžaduje izolovanou obnovu")
    data = Path("/var/tmp/obnova-polarita/paperclip")
    over(data)
    over_finops(data)
