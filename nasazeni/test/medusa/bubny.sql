-- Celé milimetry od příjmu bubnu až po skutečně vydaný kus kabelu.
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.wms.bubny.ddl',0));
SET LOCAL ROLE pol_wms_ddl;
CREATE TABLE IF NOT EXISTS wms.sklady (
    kod text PRIMARY KEY, pobocka integer NOT NULL CHECK (pobocka BETWEEN 101 AND 999),
    druh text NOT NULL CHECK (druh IN ('centralni','pobocka','dodavka')),
    dohoda text CHECK (length(btrim(dohoda)) > 0),
    CHECK (druh <> 'dodavka' OR dohoda IS NOT NULL)
);
INSERT INTO wms.sklady(kod,pobocka,druh) VALUES ('MAIN-101',101,'centralni') ON CONFLICT(kod) DO NOTHING;
CREATE TABLE IF NOT EXISTS wms.bubny (
    id uuid PRIMARY KEY, stitek text NOT NULL UNIQUE CHECK (length(btrim(stitek)) BETWEEN 1 AND 120),
    varianta text NOT NULL CHECK (length(btrim(varianta)) BETWEEN 1 AND 120),
    sklad text NOT NULL REFERENCES wms.sklady, prijato_mm bigint NOT NULL CHECK (prijato_mm > 0),
    skladem_mm bigint NOT NULL, rezervovano_mm bigint NOT NULL DEFAULT 0,
    prijato_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (0 <= rezervovano_mm AND rezervovano_mm <= skladem_mm AND skladem_mm <= prijato_mm)
);
CREATE TABLE IF NOT EXISTS wms.rezervace_kabelu (
    id uuid PRIMARY KEY, buben uuid NOT NULL REFERENCES wms.bubny,
    spis text NOT NULL CHECK (spis ~ '^POL-[0-9]{4}-[0-9]{5}$'),
    delka_mm bigint NOT NULL CHECK (delka_mm > 0), zbyva_mm bigint NOT NULL,
    CHECK (zbyva_mm BETWEEN 0 AND delka_mm)
);
CREATE TABLE IF NOT EXISTS wms.pohyby_kabelu (
    id uuid PRIMARY KEY, rezervace uuid NOT NULL REFERENCES wms.rezervace_kabelu,
    druh text NOT NULL CHECK (druh IN ('vydej','uvolneni')), delka_mm bigint NOT NULL CHECK (delka_mm > 0),
    zapsano_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE OR REPLACE VIEW wms.bubny_prehled AS
SELECT id,stitek,varianta,sklad,prijato_mm,skladem_mm,rezervovano_mm,skladem_mm-rezervovano_mm AS volno_mm
FROM wms.bubny;

CREATE OR REPLACE FUNCTION wms.prijmi_buben(p_id uuid,p_stitek text,p_varianta text,p_sklad text,p_mm bigint)
RETURNS wms.bubny_prehled LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $f$
DECLARE stav wms.bubny_prehled;
BEGIN
    INSERT INTO wms.bubny(id,stitek,varianta,sklad,prijato_mm,skladem_mm)
    VALUES(p_id,p_stitek,p_varianta,p_sklad,p_mm,p_mm) ON CONFLICT(id) DO NOTHING;
    SELECT * INTO STRICT stav FROM wms.bubny_prehled WHERE id=p_id;
    IF (stav.stitek,stav.varianta,stav.sklad,stav.prijato_mm) IS DISTINCT FROM (p_stitek,p_varianta,p_sklad,p_mm)
    THEN RAISE EXCEPTION 'Rozporné opakování příjmu bubnu' USING ERRCODE='23505'; END IF;
    RETURN stav;
END $f$;

CREATE OR REPLACE FUNCTION wms.rezervuj_kabel(p_id uuid,p_buben uuid,p_spis text,p_mm bigint)
RETURNS wms.rezervace_kabelu LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $f$
DECLARE stav wms.rezervace_kabelu;
BEGIN
    INSERT INTO wms.rezervace_kabelu(id,buben,spis,delka_mm,zbyva_mm)
    VALUES (p_id,p_buben,p_spis,p_mm,p_mm) ON CONFLICT(id) DO NOTHING;
    IF FOUND THEN
        UPDATE wms.bubny SET rezervovano_mm=rezervovano_mm+p_mm
        WHERE id=p_buben AND p_mm <= skladem_mm-rezervovano_mm;
        IF NOT FOUND THEN RAISE EXCEPTION 'Na bubnu není dost volného kabelu' USING ERRCODE='P1001'; END IF;
    END IF;
    SELECT * INTO STRICT stav FROM wms.rezervace_kabelu WHERE id=p_id;
    IF (stav.buben,stav.spis,stav.delka_mm) IS DISTINCT FROM (p_buben,p_spis,p_mm)
    THEN RAISE EXCEPTION 'Rozporné opakování rezervace' USING ERRCODE='23505'; END IF;
    RETURN stav;
END $f$;

CREATE OR REPLACE FUNCTION wms.pohyb_kabelu(p_id uuid,p_rez uuid,p_stitek text,p_spis text,p_druh text,p_mm bigint)
RETURNS wms.rezervace_kabelu LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $f$
DECLARE stav wms.rezervace_kabelu;
BEGIN
    SELECT r.* INTO STRICT stav FROM wms.rezervace_kabelu r JOIN wms.bubny b ON b.id=r.buben
    WHERE r.id=p_rez AND b.stitek=p_stitek AND r.spis=p_spis FOR UPDATE OF r;
    INSERT INTO wms.pohyby_kabelu(id,rezervace,druh,delka_mm) VALUES(p_id,p_rez,p_druh,p_mm)
    ON CONFLICT(id) DO NOTHING;
    IF NOT FOUND THEN
        IF NOT EXISTS (SELECT FROM wms.pohyby_kabelu WHERE id=p_id AND rezervace=p_rez AND druh=p_druh AND delka_mm=p_mm)
        THEN RAISE EXCEPTION 'Rozporné opakování výdeje nebo uvolnění' USING ERRCODE='23505'; END IF;
        RETURN stav;
    END IF;
    IF p_mm > stav.zbyva_mm THEN RAISE EXCEPTION 'Požadavek přesahuje zbývající rezervaci' USING ERRCODE='P1001'; END IF;
    UPDATE wms.bubny SET rezervovano_mm=rezervovano_mm-p_mm,
        skladem_mm=skladem_mm-CASE WHEN p_druh='vydej' THEN p_mm ELSE 0 END
    WHERE id=stav.buben;
    UPDATE wms.rezervace_kabelu SET zbyva_mm=zbyva_mm-p_mm WHERE id=p_rez RETURNING * INTO stav;
    RETURN stav;
END $f$;
REVOKE ALL ON FUNCTION wms.prijmi_buben(uuid,text,text,text,bigint), wms.rezervuj_kabel(uuid,uuid,text,bigint),
    wms.pohyb_kabelu(uuid,uuid,text,text,text,bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION wms.prijmi_buben(uuid,text,text,text,bigint), wms.rezervuj_kabel(uuid,uuid,text,bigint),
    wms.pohyb_kabelu(uuid,uuid,text,text,text,bigint) TO db_eshop;
GRANT SELECT ON wms.bubny_prehled TO db_eshop;
COMMIT;
