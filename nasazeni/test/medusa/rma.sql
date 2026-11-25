-- F26. Příjem podání a jeho klasifikace mají samostatnou historii.
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.wms.rma.ddl',0));
DO $role$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='pol_wms_ddl') THEN
        CREATE ROLE pol_wms_ddl NOLOGIN;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname='pol_wms_ddl' AND
        (rolcanlogin OR rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls))
        OR EXISTS (SELECT FROM pg_auth_members WHERE member='pol_wms_ddl'::regrole)
    THEN RAISE EXCEPTION 'Neočekávaná oprávnění správce WMS'; END IF;
END
$role$;
GRANT USAGE,CREATE ON SCHEMA wms TO pol_wms_ddl;
GRANT USAGE ON SCHEMA wms TO db_eshop;
SET LOCAL ROLE pol_wms_ddl;
CREATE TABLE IF NOT EXISTS wms.rma (
    id uuid PRIMARY KEY,
    objednavka text CHECK (length(objednavka) BETWEEN 1 AND 120),
    received_at timestamptz NOT NULL CHECK (isfinite(received_at)),
    puvodni_uplatneni timestamptz CHECK (isfinite(puvodni_uplatneni)),
    prvni_druh text NOT NULL CHECK (prvni_druh IN ('k_posouzeni','b2b_servis','b2c_reklamace')),
    CHECK (prvni_druh <> 'b2c_reklamace' OR puvodni_uplatneni IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS wms.rma_klasifikace (
    rma uuid NOT NULL REFERENCES wms.rma,
    verze integer NOT NULL CHECK (verze > 1),
    pozadavek uuid NOT NULL,
    druh text NOT NULL CHECK (druh IN ('k_posouzeni','b2b_servis','b2c_reklamace')),
    dolozene_uplatneni timestamptz CHECK (isfinite(dolozene_uplatneni)),
    zapsano timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(rma,verze), UNIQUE(rma,pozadavek)
);
CREATE OR REPLACE VIEW wms.rma_prehled AS
SELECT r.id,r.objednavka,r.received_at,
    coalesce(r.puvodni_uplatneni, historie.uplatneni) AS complaint_asserted_at,
    coalesce(posledni.druh,r.prvni_druh) AS druh, coalesce(posledni.verze,1) AS verze
FROM wms.rma r
LEFT JOIN LATERAL (SELECT k.druh,k.verze FROM wms.rma_klasifikace k WHERE k.rma=r.id ORDER BY k.verze DESC LIMIT 1) posledni ON true
LEFT JOIN LATERAL (SELECT k.dolozene_uplatneni AS uplatneni FROM wms.rma_klasifikace k
    WHERE k.rma=r.id AND k.dolozene_uplatneni IS NOT NULL ORDER BY k.verze LIMIT 1) historie ON true;

CREATE OR REPLACE FUNCTION wms.prijmi_rma(p_id uuid,p_obj text,p_received timestamptz,p_asserted timestamptz,p_druh text)
RETURNS wms.rma_prehled LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $f$
DECLARE vysledek wms.rma_prehled;
BEGIN
    IF greatest(p_received,p_asserted) > clock_timestamp() THEN
        RAISE EXCEPTION 'Čas události je v budoucnosti' USING ERRCODE='22023';
    END IF;
    INSERT INTO wms.rma VALUES (p_id,p_obj,p_received,p_asserted,p_druh) ON CONFLICT(id) DO NOTHING;
    IF NOT EXISTS (SELECT FROM wms.rma WHERE id=p_id AND objednavka IS NOT DISTINCT FROM p_obj
        AND received_at=p_received AND puvodni_uplatneni IS NOT DISTINCT FROM p_asserted AND prvni_druh=p_druh)
    THEN RAISE EXCEPTION 'Identifikátor patří jinému podání' USING ERRCODE='23505'; END IF;
    SELECT * INTO STRICT vysledek FROM wms.rma_prehled WHERE id=p_id;
    RETURN vysledek;
END $f$;

CREATE OR REPLACE FUNCTION wms.zarad_rma(p_id uuid,p_pozadavek uuid,p_verze integer,p_druh text,p_asserted timestamptz)
RETURNS wms.rma_prehled LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $f$
DECLARE stav wms.rma_prehled;
        hotovo wms.rma_klasifikace;
BEGIN
    PERFORM 1 FROM wms.rma WHERE id=p_id FOR UPDATE;
    SELECT * INTO STRICT stav FROM wms.rma_prehled WHERE id=p_id;
    SELECT * INTO hotovo FROM wms.rma_klasifikace WHERE rma=p_id AND pozadavek=p_pozadavek;
    IF FOUND THEN
        IF hotovo.verze IS DISTINCT FROM p_verze+1 OR hotovo.druh IS DISTINCT FROM p_druh
            OR hotovo.dolozene_uplatneni IS DISTINCT FROM p_asserted
        THEN RAISE EXCEPTION 'Rozporné opakování změny' USING ERRCODE='23505'; END IF;
        RETURN stav;
    END IF;
    IF stav.verze IS DISTINCT FROM p_verze THEN RAISE EXCEPTION 'Zastaralá verze reklamace' USING ERRCODE='40001'; END IF;
    IF p_asserted > clock_timestamp() OR (p_asserted IS NOT NULL AND stav.complaint_asserted_at IS NOT NULL
        AND p_asserted <> stav.complaint_asserted_at)
    THEN RAISE EXCEPTION 'Neplatná změna okamžiku uplatnění' USING ERRCODE='22023'; END IF;
    IF p_druh='b2c_reklamace' AND coalesce(stav.complaint_asserted_at,p_asserted) IS NULL
    THEN RAISE EXCEPTION 'Doložte okamžik uplatnění reklamace' USING ERRCODE='22023'; END IF;
    INSERT INTO wms.rma_klasifikace(rma,verze,pozadavek,druh,dolozene_uplatneni)
    VALUES(p_id,p_verze+1,p_pozadavek,p_druh,p_asserted);
    SELECT * INTO STRICT stav FROM wms.rma_prehled WHERE id=p_id;
    RETURN stav;
END $f$;
REVOKE ALL ON FUNCTION wms.prijmi_rma(uuid,text,timestamptz,timestamptz,text), wms.zarad_rma(uuid,uuid,integer,text,timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION wms.prijmi_rma(uuid,text,timestamptz,timestamptz,text), wms.zarad_rma(uuid,uuid,integer,text,timestamptz) TO db_eshop;
GRANT SELECT ON wms.rma_prehled TO db_eshop;
COMMIT;
