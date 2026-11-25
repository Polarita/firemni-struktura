-- Sken fyzického kusu, dodavatelská záruka a podklady expedice rozváděče.
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.wms.serie.ddl',0));
SET LOCAL ROLE pol_wms_ddl;
CREATE TABLE IF NOT EXISTS wms.zaruky_kusu (
    id uuid PRIMARY KEY,
    dodavatel text NOT NULL CHECK (length(btrim(dodavatel)) BETWEEN 1 AND 160),
    vyrobce text NOT NULL CHECK (length(btrim(vyrobce)) BETWEEN 1 AND 120),
    serie text NOT NULL CHECK (length(btrim(serie)) BETWEEN 1 AND 160),
    varianta text NOT NULL CHECK (length(btrim(varianta)) BETWEEN 1 AND 120),
    druh text NOT NULL CHECK (druh IN ('zarizeni','novy_rozvadec')),
    platnost daterange NOT NULL CHECK (NOT isempty(platnost) AND NOT lower_inf(platnost) AND NOT upper_inf(platnost)),
    doklad_sha256 text NOT NULL CHECK (doklad_sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE(vyrobce,serie)
);
CREATE TABLE IF NOT EXISTS wms.seriove_kusy (
    id uuid PRIMARY KEY, zaruka uuid UNIQUE NOT NULL REFERENCES wms.zaruky_kusu,
    sklad text NOT NULL REFERENCES wms.sklady, prijato_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS wms.doklady_rozvadece (
    kus uuid NOT NULL REFERENCES wms.seriove_kusy,
    druh text NOT NULL CHECK (druh IN ('vyrobni_pas','stitek_ce')),
    archiv_id bigint NOT NULL CHECK (archiv_id>0),
    sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    PRIMARY KEY(kus,druh), UNIQUE(kus,archiv_id), UNIQUE(kus,sha256)
);
CREATE TABLE IF NOT EXISTS wms.vydeje_kusu (
    id uuid PRIMARY KEY, kus uuid UNIQUE NOT NULL REFERENCES wms.seriove_kusy,
    spis text NOT NULL CHECK (spis ~ '^POL-[0-9]{4}-[0-9]{5}$'),
    vydano_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE OR REPLACE FUNCTION wms.prijmi_sken(p_id uuid,p_vyrobce text,p_serie text,p_varianta text,p_sklad text)
RETURNS wms.seriove_kusy LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $f$
DECLARE zar wms.zaruky_kusu; predchozi wms.seriove_kusy;
BEGIN
    SELECT * INTO STRICT zar FROM wms.zaruky_kusu WHERE vyrobce=p_vyrobce AND serie=p_serie AND varianta=p_varianta FOR SHARE;
    SELECT * INTO predchozi FROM wms.seriove_kusy WHERE id=p_id;
    IF NOT FOUND THEN
        IF NOT (zar.platnost @> (clock_timestamp() AT TIME ZONE 'Europe/Prague')::date)
        THEN RAISE EXCEPTION 'Dodavatelská záruka při příjmu není aktivní' USING ERRCODE='P1002'; END IF;
        INSERT INTO wms.seriove_kusy(id,zaruka,sklad) VALUES(p_id,zar.id,p_sklad) ON CONFLICT(id) DO NOTHING;
        SELECT * INTO STRICT predchozi FROM wms.seriove_kusy WHERE id=p_id;
    END IF;
    IF (predchozi.zaruka,predchozi.sklad) IS DISTINCT FROM (zar.id,p_sklad)
    THEN RAISE EXCEPTION 'Rozporné opakování příjmu' USING ERRCODE='23505'; END IF;
    RETURN predchozi;
END $f$;

CREATE OR REPLACE FUNCTION wms.vydej_sken(p_pohyb uuid,p_kus uuid,p_vyrobce text,p_serie text,p_sklad text,p_spis text)
RETURNS wms.vydeje_kusu LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $f$
DECLARE zar wms.zaruky_kusu; vydej wms.vydeje_kusu;
BEGIN
    SELECT z.* INTO STRICT zar FROM wms.seriove_kusy k JOIN wms.zaruky_kusu z ON z.id=k.zaruka
      WHERE k.id=p_kus AND k.sklad=p_sklad AND z.vyrobce=p_vyrobce AND z.serie=p_serie FOR UPDATE OF k FOR SHARE OF z;
    SELECT * INTO vydej FROM wms.vydeje_kusu WHERE kus=p_kus;
    IF FOUND THEN
        IF (vydej.id,vydej.spis) IS DISTINCT FROM (p_pohyb,p_spis)
        THEN RAISE EXCEPTION 'Kus je již vydán jiným pohybem' USING ERRCODE='23505'; END IF;
        RETURN vydej;
    END IF;
    IF NOT (zar.platnost @> (clock_timestamp() AT TIME ZONE 'Europe/Prague')::date)
    THEN RAISE EXCEPTION 'Dodavatelská záruka při výdeji není aktivní' USING ERRCODE='P1002'; END IF;
    IF zar.druh='novy_rozvadec' AND (SELECT count(*) FROM wms.doklady_rozvadece WHERE kus=p_kus)<>2
    THEN RAISE EXCEPTION 'Expedice vyžaduje výrobní pas i štítek CE tohoto kusu' USING ERRCODE='P1003'; END IF;
    INSERT INTO wms.vydeje_kusu(id,kus,spis) VALUES(p_pohyb,p_kus,p_spis) RETURNING * INTO vydej;
    RETURN vydej;
END $f$;

CREATE OR REPLACE VIEW wms.serie_prehled AS
SELECT k.id,z.vyrobce,z.serie,z.varianta,z.druh,k.sklad,k.prijato_at,z.dodavatel,
    lower(z.platnost) AS zaruka_od,upper(z.platnost)-1 AS zaruka_do,
    EXISTS(SELECT FROM wms.doklady_rozvadece d WHERE d.kus=k.id AND d.druh='vyrobni_pas') AS vyrobni_pas,
    EXISTS(SELECT FROM wms.doklady_rozvadece d WHERE d.kus=k.id AND d.druh='stitek_ce') AS stitek_ce,
    v.id AS vydej,v.spis,v.vydano_at
FROM wms.seriove_kusy k JOIN wms.zaruky_kusu z ON z.id=k.zaruka LEFT JOIN wms.vydeje_kusu v ON v.kus=k.id;
REVOKE ALL ON FUNCTION wms.prijmi_sken(uuid,text,text,text,text),wms.vydej_sken(uuid,uuid,text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION wms.prijmi_sken(uuid,text,text,text,text),wms.vydej_sken(uuid,uuid,text,text,text,text) TO db_eshop;
GRANT SELECT ON wms.serie_prehled TO db_eshop;
COMMIT;
