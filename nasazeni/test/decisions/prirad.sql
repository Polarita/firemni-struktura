BEGIN;
CREATE TEMP TABLE vstup ON COMMIT DROP AS SELECT * FROM jsonb_to_recordset(:'vzor'::jsonb)
    AS r(approval uuid, company uuid, spravce text, obsah jsonb);
DO $$
DECLARE r record; detail jsonb; pripad text; navrh uuid;
BEGIN
    IF (SELECT count(*) FROM vstup) <> 3 OR
       (SELECT count(DISTINCT (obsah #>> '{polarita,spis}')) FROM vstup) <> 3 THEN
        RAISE EXCEPTION 'Neúplný soupis zkušebních schválení';
    END IF;
    FOR r IN SELECT * FROM vstup LOOP
        detail := r.obsah->'polarita';
        pripad := detail->>'spis';
        navrh := (detail->>'id')::uuid;
        IF pripad IS NULL OR pripad NOT IN ('TEST-POL-0000-00011','TEST-POL-0000-00012','TEST-POL-0000-00013')
            OR detail IS DISTINCT FROM jsonb_build_object('id',navrh,'spis',pripad,'test',true,'fronta','URGENT',
                         'pred',jsonb_build_object('stav','rozpracován','verze',1),
                         'po',jsonb_build_object('stav','ke kontrole','verze',2))
            OR NOT EXISTS (
                SELECT FROM public.approvals a JOIN public."user" u ON u.id=r.spravce
                JOIN public.instance_user_roles ur ON ur.user_id=u.id AND ur.role='instance_admin'
                WHERE a.id=r.approval AND a.company_id=r.company AND a.type='request_board_approval'
                 AND a.payload=r.obsah AND a.requested_by_user_id=r.spravce AND a.requested_by_agent_id IS NULL
                 AND u.email='spravce@polarita.test') THEN RAISE EXCEPTION 'Nesouhlasí zdroj vzoru'; END IF;
        IF NOT EXISTS (SELECT FROM polarita.test_vazba v WHERE v.navrh=(detail->>'id')::uuid) THEN
            INSERT INTO polarita.test_spis(cislo, stav) VALUES (pripad, 'rozpracován');
            PERFORM polarita.test_navrh(navrh,pripad,1,'ke kontrole','URGENT');
            INSERT INTO polarita.test_vazba(navrh,approval,company,spravce,obsah)
                VALUES(navrh,r.approval,r.company,r.spravce,r.obsah);
        END IF;
        IF NOT EXISTS (SELECT FROM polarita.test_vazba v WHERE v.navrh=(detail->>'id')::uuid AND
                       (v.approval,v.company,v.spravce,v.obsah)=(r.approval,r.company,r.spravce,r.obsah)) THEN
            RAISE EXCEPTION 'Původní vazba odkazuje na jiné hlasování';
        END IF;
    END LOOP;
END $$;
COMMIT;
