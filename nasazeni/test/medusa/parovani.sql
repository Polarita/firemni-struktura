-- Jeden příjem nákupní položky může spojit několik dodacích a fakturačních řádků.
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.wms.parovani.ddl',0));
DO $roles$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['pol_wms_objednavky','pol_wms_faktury'] LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname=role_name) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN',role_name);
        END IF;
        IF EXISTS (SELECT FROM pg_roles WHERE rolname=role_name AND
            (rolcanlogin OR rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls))
        THEN RAISE EXCEPTION 'Neočekávaná oprávnění role %',role_name; END IF;
    END LOOP;
END $roles$;
GRANT USAGE ON SCHEMA wms TO pol_wms_objednavky,pol_wms_faktury;
SET LOCAL ROLE pol_wms_ddl;
CREATE TABLE IF NOT EXISTS wms.nakupni_doklady (
    id uuid PRIMARY KEY,
    druh text NOT NULL CHECK (druh IN ('objednavka','prijemka','faktura')),
    subjekt text NOT NULL CHECK (length(btrim(subjekt)) BETWEEN 1 AND 160),
    dodavatel text NOT NULL CHECK (length(btrim(dodavatel)) BETWEEN 1 AND 160),
    cislo text NOT NULL CHECK (length(btrim(cislo)) BETWEEN 1 AND 120),
    radek integer NOT NULL CHECK (radek>0),
    polozka_objednavky uuid REFERENCES wms.nakupni_doklady,
    cil text NOT NULL CHECK (cil ~ '^(POL-[0-9]{4}-[0-9]{5}|VAN-[0-9]{3}-[0-9]{2})$'),
    varianta text NOT NULL CHECK (length(btrim(varianta)) BETWEEN 1 AND 120),
    jednotka text NOT NULL CHECK (length(btrim(jednotka)) BETWEEN 1 AND 16),
    mnozstvi numeric NOT NULL CHECK (mnozstvi>0 AND mnozstvi<1e15),
    cerpano numeric NOT NULL DEFAULT 0 CHECK (cerpano>=0 AND cerpano<=mnozstvi AND (druh='objednavka' OR cerpano=0)),
    mena text CHECK (mena ~ '^[A-Z]{3}$'),
    cena_bez_phe numeric CHECK (cena_bez_phe>=0 AND cena_bez_phe<1e15),
    phe_za_jednotku numeric CHECK (phe_za_jednotku>=0 AND phe_za_jednotku<1e15),
    sklad text REFERENCES wms.sklady,
    otisk_sha256 text NOT NULL CHECK (otisk_sha256 ~ '^[0-9a-f]{64}$'),
    UNIQUE(druh,subjekt,dodavatel,cislo,radek),
    CHECK ((druh='objednavka') = (polozka_objednavky IS NULL)),
    CHECK ((druh='prijemka' AND sklad IS NOT NULL AND mena IS NULL AND cena_bez_phe IS NULL AND phe_za_jednotku IS NULL)
        OR (druh<>'prijemka' AND sklad IS NULL AND mena IS NOT NULL AND cena_bez_phe IS NOT NULL AND phe_za_jednotku IS NOT NULL))
);
-- Tři vstupy mají samostatné zapisovatele. Již přijatý podklad nemohou přepsat.
CREATE OR REPLACE VIEW wms.nakupni_objednavky AS
SELECT id,druh,subjekt,dodavatel,cislo,radek,cil,varianta,jednotka,mnozstvi,mena,cena_bez_phe,phe_za_jednotku,otisk_sha256
FROM wms.nakupni_doklady WHERE druh='objednavka' WITH LOCAL CHECK OPTION;
ALTER VIEW wms.nakupni_objednavky ALTER COLUMN druh SET DEFAULT 'objednavka';
GRANT INSERT ON wms.nakupni_objednavky TO pol_wms_objednavky;
CREATE OR REPLACE VIEW wms.skladove_prijemky AS
SELECT id,druh,subjekt,dodavatel,cislo,radek,polozka_objednavky,cil,varianta,jednotka,mnozstvi,sklad,otisk_sha256
FROM wms.nakupni_doklady WHERE druh='prijemka' WITH LOCAL CHECK OPTION;
ALTER VIEW wms.skladove_prijemky ALTER COLUMN druh SET DEFAULT 'prijemka';
GRANT INSERT ON wms.skladove_prijemky TO db_eshop;
CREATE OR REPLACE VIEW wms.nakupni_faktury AS
SELECT id,druh,subjekt,dodavatel,cislo,radek,polozka_objednavky,cil,varianta,jednotka,mnozstvi,mena,cena_bez_phe,phe_za_jednotku,otisk_sha256
FROM wms.nakupni_doklady WHERE druh='faktura' WITH LOCAL CHECK OPTION;
ALTER VIEW wms.nakupni_faktury ALTER COLUMN druh SET DEFAULT 'faktura';
GRANT INSERT ON wms.nakupni_faktury TO pol_wms_faktury;

CREATE TABLE IF NOT EXISTS wms.nakupni_prijmy (
    id uuid PRIMARY KEY, objednavka uuid NOT NULL REFERENCES wms.nakupni_doklady,
    mnozstvi numeric NOT NULL CHECK (mnozstvi>0 AND mnozstvi<1e15),
    prijato_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS nakupni_prijmy_objednavka ON wms.nakupni_prijmy(objednavka);
CREATE TABLE IF NOT EXISTS wms.sparovane_doklady (
    doklad uuid PRIMARY KEY REFERENCES wms.nakupni_doklady,
    prijem uuid NOT NULL REFERENCES wms.nakupni_prijmy
);
CREATE INDEX IF NOT EXISTS sparovane_doklady_prijem ON wms.sparovane_doklady(prijem);

CREATE OR REPLACE FUNCTION wms.potvrd_nakup(p_id uuid,p_objednavka uuid,p_doklady uuid[])
RETURNS wms.nakupni_prijmy LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $f$
DECLARE
    o wms.nakupni_doklady;
    prijem wms.nakupni_prijmy;
    ids uuid[];
    pocet bigint;
    shoda boolean;
    dodano numeric;
    fakturovano numeric;
BEGIN
    SELECT array_agg(DISTINCT d ORDER BY d) INTO ids FROM unnest(p_doklady) AS d;
    IF p_id IS NULL OR ids IS NULL OR array_position(ids,NULL::uuid) IS NOT NULL
        OR cardinality(ids)<>cardinality(p_doklady)
    THEN RAISE EXCEPTION 'Chybí řádky nebo se některý opakuje' USING ERRCODE='22023'; END IF;

    SELECT * INTO STRICT o FROM wms.nakupni_doklady
    WHERE id=p_objednavka AND druh='objednavka' FOR UPDATE;
    SELECT * INTO prijem FROM wms.nakupni_prijmy WHERE id=p_id;
    IF FOUND THEN
        IF prijem.objednavka<>o.id OR ids IS DISTINCT FROM
            (SELECT array_agg(doklad ORDER BY doklad) FROM wms.sparovane_doklady WHERE sparovane_doklady.prijem=p_id)
        THEN RAISE EXCEPTION 'Identifikátor příjmu patří jiným dokladům' USING ERRCODE='23505'; END IF;
        RETURN prijem;
    END IF;

    SELECT count(*), bool_and(
        polozka_objednavky IS NOT DISTINCT FROM o.id AND druh IN ('prijemka','faktura') AND
        (subjekt,dodavatel,cil,varianta,jednotka)=(o.subjekt,o.dodavatel,o.cil,o.varianta,o.jednotka) AND
        (druh='prijemka' OR (mena,cena_bez_phe,phe_za_jednotku)=(o.mena,o.cena_bez_phe,o.phe_za_jednotku))
    ), sum(mnozstvi) FILTER (WHERE druh='prijemka'), sum(mnozstvi) FILTER (WHERE druh='faktura')
    INTO pocet,shoda,dodano,fakturovano FROM wms.nakupni_doklady WHERE id=ANY(ids);
    IF pocet<>cardinality(ids) OR shoda IS NOT TRUE OR dodano IS NULL OR fakturovano IS NULL
        OR dodano<>fakturovano
    THEN RAISE EXCEPTION 'Objednávka, příjemka a faktura se neshodují' USING ERRCODE='P1004'; END IF;
    IF EXISTS (SELECT FROM wms.sparovane_doklady WHERE doklad=ANY(ids))
    THEN RAISE EXCEPTION 'Řádek je již spárován' USING ERRCODE='23505'; END IF;
    UPDATE wms.nakupni_doklady SET cerpano=cerpano+dodano
    WHERE id=o.id AND cerpano+dodano<=mnozstvi;
    IF NOT FOUND THEN RAISE EXCEPTION 'Příjem přesahuje množství objednávky' USING ERRCODE='P1004'; END IF;

    INSERT INTO wms.nakupni_prijmy(id,objednavka,mnozstvi) VALUES(p_id,o.id,dodano) RETURNING * INTO prijem;
    INSERT INTO wms.sparovane_doklady(doklad,prijem) SELECT d,p_id FROM unnest(ids) AS d;
    RETURN prijem;
END $f$;

CREATE OR REPLACE VIEW wms.prijaty_material AS
SELECT p.id AS prijem,p.prijato_at,p.objednavka,d.id AS prijemka,d.sklad,d.cil,d.varianta,d.jednotka,d.mnozstvi
FROM wms.nakupni_prijmy p JOIN wms.sparovane_doklady s ON s.prijem=p.id
JOIN wms.nakupni_doklady d ON d.id=s.doklad WHERE d.druh='prijemka';
REVOKE ALL ON FUNCTION wms.potvrd_nakup(uuid,uuid,uuid[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION wms.potvrd_nakup(uuid,uuid,uuid[]) TO db_eshop;
GRANT SELECT ON wms.prijaty_material TO db_eshop;
COMMIT;
