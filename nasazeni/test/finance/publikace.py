"""Připraví export z vydaných čísel a uloží zkontrolované bajty v jedné transakci."""
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

from lxml import etree
from isdoc import davka, sestav

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/"registry"))
sys.path.insert(0, str(HERE.parent/"inzenyring"/"revize"))
from spisy_rz import id_spisu
from vzorove_doklady import doklady


def sql(statement, **values):
    cmd = ["incus","exec","-T","postgres-test","--","runuser","-u","postgres","--","psql","-XqAtw",
           "-v","ON_ERROR_STOP=1","-d","db_erp_lhutnik"]
    for k,v in values.items():
        cmd.extend(["-v", k+"="+v])
    result = subprocess.run(cmd, input=statement, text=True, capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError("PostgreSQL odmítl účetní export. " + result.stderr.strip()[:1200])
    return result.stdout.strip()


def zverejni(schema, out):
    if socket.gethostname().split(".")[0] != "polarita-hq":
        raise ValueError("Účetní export patří do VM ředitelství.")
    pravidla = etree.XMLSchema(etree.parse(str(schema),etree.XMLParser(no_network=True,resolve_entities=False)))
    vzory = json.loads((HERE.parent/"registry"/"vzory.json").read_bytes())
    zdroje = {(r["spis"],r["druh"]):r for r in doklady(vzory)}
    polozky = json.loads((HERE/"polozky-test.json").read_bytes())
    faktury = []
    transakce = ["BEGIN;", "SET LOCAL ROLE pol_registr_ddl;"]
    values = {}
    for i,(varianta,podklad) in enumerate(sorted(polozky.items())):
        uid = str(id_spisu(varianta))
        f, u = zdroje[uid,"FAK"], zdroje[uid,"ORG-UOL"]
        radky = sql("""SET ROLE pol_metadata_read; SELECT k.case_id,d.druh,d.cislo,d.podklad_sha256
                    FROM polarita_test_spisy.karty k JOIN polarita_registr_test.prehled_dokladu d USING(case_id)
                    WHERE k.pozadavek=:'spis' AND d.podklad_sha256 IN (:'f',:'u');""",
                    spis=uid,f=f["otisk"],u=u["otisk"]).splitlines()
        registry = {d:(k,c,h) for k,d,c,h in (r.split("|") for r in radky)}
        if len(radky)!=2 or registry["FAK"][2]!=f["otisk"] or registry["ORG-UOL"][2]!=u["otisk"]:
            raise ValueError("Chybí jednoznačná dvojice dokladů odpovídající podkladům.")
        spis, faktura, _ = registry["FAK"]
        _, predavka, _ = registry["ORG-UOL"]
        raw = sestav(faktura, f["klic"], spis, podklad)
        pravidla.assertValid(etree.fromstring(raw))
        row = {"spis":spis,"faktura":faktura,"predavka":predavka,"xml":raw}
        faktury.append(row)
        param = {"fid":f["klic"],"uid":u["klic"],"karta":uid,"fh":f["otisk"],"uh":u["otisk"],
                 "fc":faktura,"uc":predavka,"ceny":json.dumps(podklad,ensure_ascii=False),
                 "xml":raw.hex(),"uol":davka([row]).hex()}
        values.update({k+str(i):v for k,v in param.items()})
        # Hodnoty používají citované proměnné psql. Do SQL se vkládá pouze pořadí místního vzoru.
        transakce.append(f"""
WITH vstup AS (
 SELECT f.pozadavek AS faktura,u.pozadavek AS predavka FROM polarita_registr_test.doklad f
 JOIN polarita_registr_test.doklad u ON u.spis=f.spis
 WHERE f.spis=:'karta{i}' AND f.druh='FAK' AND u.druh='ORG-UOL'
 AND f.pozadavek=:'fid{i}' AND u.pozadavek=:'uid{i}' AND f.cislo=:'fc{i}' AND u.cislo=:'uc{i}'
 AND f.podklad_sha256=:'fh{i}' AND u.podklad_sha256=:'uh{i}')
INSERT INTO polarita_registr_test.isdoc(faktura,predavka,podklad,soubor,predavka_xml)
SELECT faktura,predavka,:'ceny{i}'::jsonb,decode(:'xml{i}','hex'),decode(:'uol{i}','hex') FROM vstup
ON CONFLICT(faktura) DO NOTHING;
SELECT EXISTS(SELECT FROM polarita_registr_test.isdoc WHERE faktura=:'fid{i}' AND predavka=:'uid{i}'
 AND podklad=:'ceny{i}'::jsonb AND soubor=decode(:'xml{i}','hex') AND predavka_xml=decode(:'uol{i}','hex')) AS shoda
\\gset
\\if :shoda
\\else
DO $$ BEGIN RAISE EXCEPTION 'Nesouhlasí identita nebo dříve vydaný obsah faktury'; END $$;
\\endif""")
    obsah = davka(faktury)
    digest = sha256(obsah).hexdigest()
    transakce.extend(["INSERT INTO polarita_registr_test.davka_isdoc(obsah) VALUES(decode(:'davka','hex')) ON CONFLICT DO NOTHING;",
                      "SELECT encode(obsah,'hex') FROM polarita_registr_test.davka_isdoc WHERE sha256=:'otisk';","COMMIT;"])
    raw = bytes.fromhex(sql("\n".join(transakce),**values,davka=obsah.hex(),otisk=digest))
    if raw != obsah:
        raise ValueError("Odlišný obsah při zpětném čtení účetní dávky.")
    out.mkdir(parents=True,exist_ok=True,mode=0o700)
    target = out/(digest+".xml")
    with tempfile.NamedTemporaryFile(dir=out,delete=False) as f:
        tmp = Path(f.name)
        try:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
            try:
                os.link(tmp,target)
            except FileExistsError:
                pass
            if target.is_symlink() or target.read_bytes() != raw:
                raise ValueError("Archivní soubor dávky má odlišný obsah.")
        finally:
            tmp.unlink()
    for d in faktury:
        print(d["spis"],d["faktura"],d["predavka"],sha256(d["xml"]).hexdigest())
    print("Dávka",digest,"· dokladů",len(faktury),"·",target)


if __name__ == "__main__":
    zverejni(Path(sys.argv[1]),Path(sys.argv[2]))
