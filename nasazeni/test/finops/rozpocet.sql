-- Místní účetní kniha pro poskytovatele TEST. Veřejné tabulky čte vždy přes pohled.
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.finops.migrace',0));
DO $$
DECLARE role_name text;
BEGIN
    IF current_database() <> 'db_paperclip' AND current_database() !~ '^pol_finops_zk_[a-f0-9]{32}$' THEN RAISE EXCEPTION 'Neplatný cíl FinOps'; END IF;
    FOREACH role_name IN ARRAY ARRAY['pol_finops_owner','pol_finops_propose','pol_finops_call','pol_finops_release','pol_finops_read']
    LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname=role_name) THEN
            EXECUTE format('CREATE ROLE %I %s',role_name,CASE WHEN role_name='pol_finops_owner' THEN 'NOLOGIN' ELSE 'LOGIN' END);
        END IF;
        IF EXISTS (SELECT FROM pg_authid WHERE rolname=role_name AND
            (rolcanlogin<>(role_name<>'pol_finops_owner') OR rolpassword IS NOT NULL OR rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls))
        OR EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member WHERE r.rolname=role_name)
        THEN RAISE EXCEPTION 'Neočekávaná oprávnění účtu FinOps'; END IF;
    END LOOP;
END $$;
DO $$ BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO pol_finops_read,pol_finops_call,pol_finops_release,pol_finops_propose',current_database());
END $$;
CREATE SCHEMA IF NOT EXISTS polarita_finops AUTHORIZATION pol_finops_owner;
DO $$ BEGIN
    IF (SELECT nspowner FROM pg_namespace WHERE nspname='polarita_finops') <> 'pol_finops_owner'::regrole
    THEN RAISE EXCEPTION 'Cizí schéma FinOps'; END IF;
END $$;
-- Živé identity, limity a potvrzení pocházejí přímo z Paperclipu.
CREATE OR REPLACE VIEW polarita_finops.kvoty AS
    SELECT c.id AS firma, a.metadata->>'polaritaId' AS pozice, a.id AS agent,
           a.budget_monthly_cents AS kvota, c.budget_monthly_cents AS strop
    FROM public.companies c JOIN public.agents a ON a.company_id=c.id
    WHERE c.name='Polarita s.r.o.' AND c.budget_monthly_cents=47000 AND a.metadata->>'polaritaId' ~ '^[0-9]{5}$';
CREATE OR REPLACE VIEW polarita_finops.hlasovani AS
    SELECT h.id, h.company_id AS firma, h.payload->'polaritaFinOps' AS rozsah, h.decided_at
    FROM public.approvals h JOIN polarita_finops.kvoty q ON q.firma=h.company_id AND q.pozice='11001'
    JOIN public."user" u ON u.id=h.decided_by_user_id
    WHERE ((h.requested_by_user_id IS NULL AND h.requested_by_agent_id=q.agent)
        OR (h.requested_by_user_id=u.id AND h.requested_by_agent_id IS NULL))
      AND h.type='request_board_approval'
      AND h.status='approved' AND h.decided_at IS NOT NULL AND u.email='spravce@polarita.test'
      AND EXISTS (SELECT FROM public.instance_user_roles r WHERE r.user_id=u.id AND r.role='instance_admin');
-- Nativní placené události zahrnuje stopka i před prvním použitím lokálního protějšku.
CREATE OR REPLACE VIEW polarita_finops.nativni_naklady AS
    SELECT e.company_id AS firma, e.agent_id AS agent,
           date_trunc('month',e.occurred_at AT TIME ZONE 'UTC')::date AS mesic,
           sum(greatest(e.cost_cents,0)) AS centy
    FROM public.cost_events e JOIN public.companies c ON c.id=e.company_id
    WHERE c.name='Polarita s.r.o.' GROUP BY 1,2,3;
GRANT SELECT ON polarita_finops.kvoty, polarita_finops.hlasovani, polarita_finops.nativni_naklady TO pol_finops_owner;
SET LOCAL ROLE pol_finops_owner;
CREATE TABLE IF NOT EXISTS polarita_finops.navrhy (
    id uuid PRIMARY KEY, mesic date NOT NULL, prijemce text NOT NULL,
    ukol uuid NOT NULL, centy integer NOT NULL CHECK (centy BETWEEN 1 AND 7050)
);
CREATE TABLE IF NOT EXISTS polarita_finops.uvolneni (
    hlas uuid PRIMARY KEY, navrh uuid NOT NULL UNIQUE REFERENCES polarita_finops.navrhy(id), mesic date NOT NULL, pozice text NOT NULL CHECK (pozice<>'17005'),
    ukol uuid NOT NULL, centy integer NOT NULL CHECK (centy BETWEEN 1 AND 7050)
);
CREATE TABLE IF NOT EXISTS polarita_finops.volani (
    id uuid PRIMARY KEY, mesic date NOT NULL, pozice text NOT NULL, ukol uuid NOT NULL,
    druh text NOT NULL CHECK (druh IN ('provoz','P1','eval')),
    maximum integer NOT NULL CHECK (maximum BETWEEN 1 AND 47000),
    vysledek integer CHECK (vysledek BETWEEN 0 AND maximum),
    zadany_hlas uuid,
    hlas uuid REFERENCES polarita_finops.uvolneni(hlas)
);
CREATE INDEX IF NOT EXISTS volani_mesic ON polarita_finops.volani(mesic,pozice);
CREATE OR REPLACE FUNCTION polarita_finops.mesic() RETURNS date
LANGUAGE sql STABLE SET search_path=pg_catalog AS $$
    SELECT date_trunc('month',statement_timestamp() AT TIME ZONE 'UTC')::date;
$$;
-- Návrh může evidovat jen vyhrazená identita CEO. Údaje z formuláře nejsou oprávněním.
CREATE OR REPLACE FUNCTION polarita_finops.navrh(klic uuid, kdo text, ukol_id uuid, castka integer) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE n polarita_finops.navrhy; obdobi date := polarita_finops.mesic();
BEGIN
    IF klic IS NULL OR kdo IS NULL OR ukol_id IS NULL OR castka IS NULL OR castka NOT BETWEEN 1 AND 7050
        OR kdo='17005' OR NOT EXISTS (SELECT FROM polarita_finops.kvoty WHERE pozice=kdo)
    THEN RAISE EXCEPTION 'Neplatný návrh P1'; END IF;
    INSERT INTO polarita_finops.navrhy VALUES(klic,obdobi,kdo,ukol_id,castka) ON CONFLICT DO NOTHING;
    SELECT * INTO STRICT n FROM polarita_finops.navrhy WHERE id=klic;
    IF (n.mesic,n.prijemce,n.ukol,n.centy) IS DISTINCT FROM (obdobi,kdo,ukol_id,castka)
    THEN RAISE EXCEPTION 'Kolize ID návrhu P1'; END IF;
END $$;
CREATE OR REPLACE FUNCTION polarita_finops.uvolni(schvaleni uuid, navrh_id uuid, prijemce text, ukol_id uuid, castka integer)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE obdobi date := polarita_finops.mesic(); vzor jsonb;
BEGIN
    IF schvaleni IS NULL OR prijemce IS NULL OR ukol_id IS NULL OR castka IS NULL OR
        castka NOT BETWEEN 1 AND 7050 OR prijemce='17005' THEN RAISE EXCEPTION 'Neplatné uvolnění P1'; END IF;
    IF NOT EXISTS (SELECT FROM polarita_finops.navrhy n WHERE n.id=navrh_id AND
        (n.mesic,n.prijemce,n.ukol,n.centy)=(obdobi,uvolni.prijemce,ukol_id,castka))
    THEN RAISE EXCEPTION 'Chybí návrh 11001'; END IF;
    vzor := jsonb_build_object('navrh',navrh_id,'rezim','TEST','mesic',to_char(obdobi,'YYYY-MM'),'pozice',prijemce,'ukol',ukol_id,'centy',castka);
    IF NOT EXISTS (SELECT FROM polarita_finops.hlasovani h JOIN polarita_finops.kvoty q ON q.firma=h.firma
        WHERE h.id=schvaleni AND h.rozsah=vzor AND q.pozice=prijemce
          AND date_trunc('month',h.decided_at AT TIME ZONE 'UTC')::date=obdobi)
    THEN RAISE EXCEPTION 'P1 chybí jmenovité rozhodnutí správce na návrh 11001'; END IF;
    INSERT INTO polarita_finops.uvolneni VALUES (schvaleni,navrh_id,obdobi,prijemce,ukol_id,castka) ON CONFLICT (hlas) DO NOTHING;
END $$;
CREATE OR REPLACE FUNCTION polarita_finops.rezervuj(klic uuid, kdo text, ukol_id uuid, typ text, odhad integer, schvaleni uuid DEFAULT NULL)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE obdobi date := polarita_finops.mesic(); q record; stara polarita_finops.volani;
    celkem numeric; provoz numeric; rezerva numeric; cerpano numeric; povoleno integer; h uuid;
BEGIN
    IF klic IS NULL OR kdo IS NULL OR ukol_id IS NULL OR typ IS NULL OR typ NOT IN ('provoz','P1','eval')
        OR odhad IS NULL OR odhad NOT BETWEEN 1 AND 47000 OR (typ='eval' AND kdo<>'17005')
        OR (typ<>'P1' AND schvaleni IS NOT NULL) THEN RAISE EXCEPTION 'Neúplný nebo neplatný požadavek'; END IF;
    IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'FinOps vyžaduje READ COMMITTED'; END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('polarita.finops.vydaj',0));
    SELECT * INTO stara FROM polarita_finops.volani WHERE id=klic;
    IF FOUND THEN
        IF (stara.pozice,stara.ukol,stara.druh,stara.maximum) IS DISTINCT FROM (kdo,ukol_id,typ,odhad)
            OR stara.zadany_hlas IS DISTINCT FROM schvaleni THEN RAISE EXCEPTION 'Kolize ID volání'; END IF;
        RETURN 'OPAKOVANI';
    END IF;
    IF (SELECT count(*)<>20 OR count(DISTINCT firma)<>1 OR count(DISTINCT pozice)<>20 OR sum(kvota)<>39950
        FROM polarita_finops.kvoty) THEN RAISE EXCEPTION 'Neúplné živé kvóty z Paperclipu'; END IF;
    SELECT * INTO STRICT q FROM polarita_finops.kvoty WHERE pozice=kdo;
    SELECT coalesce(sum(coalesce(vysledek,maximum)),0),
        coalesce(sum(coalesce(vysledek,maximum)) FILTER (WHERE pozice=kdo AND hlas IS NULL),0),
        coalesce(sum(coalesce(vysledek,maximum)) FILTER (WHERE hlas IS NOT NULL),0),
        coalesce(sum(coalesce(vysledek,maximum)) FILTER (WHERE hlas=schvaleni),0)
        INTO celkem,provoz,rezerva,cerpano FROM polarita_finops.volani WHERE mesic=obdobi;
    SELECT celkem+coalesce(sum(centy),0),provoz+coalesce(sum(centy) FILTER(WHERE agent=q.agent),0)
      INTO celkem,provoz FROM polarita_finops.nativni_naklady WHERE firma=q.firma AND mesic=obdobi;
    IF celkem+odhad>q.strop THEN RETURN 'FINOPS_HARD_STOP'; END IF;
    IF provoz+odhad>q.kvota THEN
        IF typ<>'P1' THEN RETURN 'AGENT_QUOTA_EXHAUSTED'; END IF;
        SELECT u.centy INTO povoleno FROM polarita_finops.uvolneni u JOIN polarita_finops.hlasovani a ON a.id=u.hlas
            WHERE u.hlas=schvaleni AND u.mesic=obdobi AND u.pozice=kdo AND u.ukol=ukol_id AND a.firma=q.firma
                AND a.rozsah=jsonb_build_object('navrh',u.navrh,'rezim','TEST','mesic',to_char(obdobi,'YYYY-MM'),
                        'pozice',kdo,'ukol',ukol_id,'centy',u.centy);
        IF povoleno IS NULL THEN RETURN 'P1_RESERVE_NOT_APPROVED'; END IF;
        IF cerpano+odhad>povoleno OR rezerva+odhad>7050 THEN RETURN 'P1_RESERVE_AMOUNT_EXCEEDED'; END IF;
        h := schvaleni;
    END IF;
    INSERT INTO polarita_finops.volani(id,mesic,pozice,ukol,druh,maximum,zadany_hlas,hlas) VALUES(klic,obdobi,kdo,ukol_id,typ,odhad,schvaleni,h);
    RETURN CASE WHEN h IS NULL THEN 'BUDGET_OK' ELSE 'P1_RESERVE_USED' END;
END $$;
CREATE OR REPLACE FUNCTION polarita_finops.zauctuj(klic uuid, skutecnost integer) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v polarita_finops.volani;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('polarita.finops.vydaj',0));
    SELECT * INTO STRICT v FROM polarita_finops.volani WHERE id=klic FOR UPDATE;
    IF skutecnost IS NULL OR skutecnost NOT BETWEEN 0 AND v.maximum OR
        (v.vysledek IS NOT NULL AND v.vysledek<>skutecnost) THEN RAISE EXCEPTION 'Nesouhlasí vyúčtování'; END IF;
    UPDATE polarita_finops.volani SET vysledek=skutecnost WHERE id=klic AND vysledek IS NULL;
END $$;
CREATE OR REPLACE FUNCTION polarita_finops.stav() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
    WITH mes AS (SELECT polarita_finops.mesic() AS m),
    mistni AS (
        SELECT v.pozice,
            coalesce(sum(coalesce(v.vysledek,v.maximum)) FILTER (WHERE v.hlas IS NULL),0) AS provoz,
            coalesce(sum(coalesce(v.vysledek,v.maximum)) FILTER (WHERE v.hlas IS NOT NULL),0) AS p1,
            coalesce(sum(v.maximum) FILTER (WHERE v.vysledek IS NULL),0) AS drzeno
        FROM polarita_finops.volani v,mes WHERE v.mesic=mes.m GROUP BY v.pozice
    ), radky AS (
        SELECT q.pozice,q.kvota,coalesce(v.provoz,0)+coalesce(n.centy,0) AS provoz,
            coalesce(v.p1,0) AS p1,coalesce(v.drzeno,0) AS drzeno
        FROM polarita_finops.kvoty q CROSS JOIN mes LEFT JOIN mistni v USING(pozice)
        LEFT JOIN polarita_finops.nativni_naklady n ON n.firma=q.firma AND n.agent=q.agent AND n.mesic=mes.m
    ), soucet AS (
        SELECT coalesce((SELECT sum(provoz+p1) FROM mistni),0) +
          coalesce((SELECT sum(centy) FROM polarita_finops.nativni_naklady,mes WHERE mesic=mes.m),0) AS celkem
    )
    SELECT jsonb_build_object('mesic',to_char(mes.m,'YYYY-MM'),'mena','USD','strop_cent',47000,
        'provoz_cent',39950,'rezerva_cent',7050,'cerpano_a_rezervovano_cent',soucet.celkem,
        'varovani_80',soucet.celkem>=37600,'globalni_stop',soucet.celkem>=47000,
        'pozice',(SELECT jsonb_agg(to_jsonb(r)||jsonb_build_object('varovani_80',r.provoz*5>=r.kvota*4)
                         ORDER BY r.pozice) FROM radky r)) FROM mes,soucet;
$$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA polarita_finops FROM PUBLIC;
GRANT USAGE ON SCHEMA polarita_finops TO pol_finops_call,pol_finops_read,pol_finops_release,pol_finops_propose;
GRANT EXECUTE ON FUNCTION polarita_finops.rezervuj(uuid,text,uuid,text,integer,uuid),
    polarita_finops.zauctuj(uuid,integer) TO pol_finops_call;
GRANT EXECUTE ON FUNCTION polarita_finops.navrh(uuid,text,uuid,integer) TO pol_finops_propose;
GRANT EXECUTE ON FUNCTION polarita_finops.uvolni(uuid,uuid,text,uuid,integer) TO pol_finops_release;
GRANT EXECUTE ON FUNCTION polarita_finops.stav() TO pol_finops_read;
RESET ROLE;
COMMIT;
