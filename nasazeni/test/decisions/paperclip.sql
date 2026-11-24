-- Od výrobce pouze čteme schválení, profil a roli správce. Zápisy patří do vlastního schématu.
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.decisions_paperclip.v1',0));
DO $$
BEGIN
    IF current_database() <> 'db_paperclip' THEN RAISE EXCEPTION 'Chybná databáze'; END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='pol_decisions_bridge') THEN
        CREATE ROLE pol_decisions_bridge LOGIN;
    END IF;
    IF EXISTS (SELECT FROM pg_authid WHERE rolname='pol_decisions_bridge' AND
        (NOT rolcanlogin OR rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls OR rolpassword IS NOT NULL))
        OR EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON m.member=r.oid WHERE r.rolname='pol_decisions_bridge') THEN
        RAISE EXCEPTION 'Cizí oprávnění účtu mostu';
    END IF;
END $$;
GRANT CONNECT ON DATABASE db_paperclip TO pol_decisions_bridge;
GRANT USAGE ON SCHEMA polarita TO pol_decisions_bridge;
CREATE TABLE IF NOT EXISTS polarita.test_vazba (
    navrh uuid PRIMARY KEY REFERENCES polarita.test_rozhodnuti(id),
    approval uuid UNIQUE NOT NULL,
    company uuid NOT NULL,
    spravce text NOT NULL,
    obsah jsonb NOT NULL,
    vysledek text CHECK (vysledek IN ('potvrzeno','zamitnuto','zastarale','nesouhlas')),
    posouzeno timestamptz,
    CHECK ((vysledek IS NULL) = (posouzeno IS NULL))
);
CREATE OR REPLACE VIEW polarita.test_overene_hlasovani AS
    SELECT v.navrh, a.status, a.decided_at,
        COALESCE(a.type='request_board_approval' AND a.company_id=v.company AND a.payload=v.obsah
          AND a.decided_by_user_id=v.spravce AND a.decided_at IS NOT NULL AND a.requested_by_agent_id IS NULL
          AND a.requested_by_user_id=v.spravce AND u.email='spravce@polarita.test'
          AND EXISTS (SELECT FROM public.instance_user_roles r WHERE r.user_id=v.spravce AND r.role='instance_admin'),false) AS sedi
    FROM polarita.test_vazba v JOIN public.approvals a ON a.id=v.approval
    LEFT JOIN public."user" u ON u.id=v.spravce WHERE v.vysledek IS NULL;
GRANT SELECT ON polarita.test_overene_hlasovani, polarita.test_vazba TO pol_decisions_owner;
GRANT UPDATE (vysledek,posouzeno) ON polarita.test_vazba TO pol_decisions_owner;
GRANT CREATE ON SCHEMA polarita TO pol_decisions_owner;
SET LOCAL ROLE pol_decisions_owner;
CREATE OR REPLACE FUNCTION polarita.test_prevez() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE hlas record; vys text; akce text;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('polarita.prevez.hlasovani',0));
    FOR hlas IN SELECT h.*, z.dostupne FROM polarita.test_overene_hlasovani h
        JOIN polarita.test_rozhodnuti z ON z.id=h.navrh WHERE h.status IN ('approved','rejected')
    LOOP
        IF NOT hlas.sedi OR hlas.decided_at < hlas.dostupne THEN
            vys := 'nesouhlas';
        ELSE
            akce := CASE hlas.status WHEN 'approved' THEN 'mutation_confirm' ELSE 'mutation_cancel' END;
            BEGIN
                PERFORM polarita.test_rozhodni(hlas.navrh, akce);
                vys := CASE hlas.status WHEN 'approved' THEN 'potvrzeno' ELSE 'zamitnuto' END;
            EXCEPTION WHEN serialization_failure THEN vys := 'zastarale';
            END;
        END IF;
        UPDATE polarita.test_vazba SET vysledek=vys,posouzeno=statement_timestamp()
            WHERE navrh=hlas.navrh AND vysledek IS NULL;
    END LOOP;
END $$;
REVOKE ALL ON FUNCTION polarita.test_prevez() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION polarita.test_prevez() TO pol_decisions_bridge;
RESET ROLE;
REVOKE CREATE ON SCHEMA polarita FROM pol_decisions_owner;
COMMIT;
