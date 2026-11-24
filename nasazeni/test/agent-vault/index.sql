\set ON_ERROR_STOP on
BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='pol_vault_read') THEN CREATE ROLE pol_vault_read LOGIN; END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='pol_vault_index') THEN CREATE ROLE pol_vault_index LOGIN; END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname IN ('pol_vault_index','pol_vault_read') AND
        (rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls OR NOT rolcanlogin))
        OR EXISTS (SELECT FROM pg_auth_members WHERE member IN ('pol_vault_read'::regrole,'pol_vault_index'::regrole))
        THEN RAISE EXCEPTION 'Neočekávaná oprávnění identity znalostí'; END IF;
END $$;
SET LOCAL search_path = vault_search,pg_catalog;
CREATE TABLE IF NOT EXISTS stranky(cesta text PRIMARY KEY, objekt text NOT NULL);
CREATE TABLE IF NOT EXISTS uryvky(cesta text REFERENCES stranky ON DELETE CASCADE, poradi int NOT NULL,
    zacatek int NOT NULL CHECK(zacatek>=0), konec int NOT NULL CHECK(konec>zacatek),
    vektor vector(384) NOT NULL, PRIMARY KEY(cesta,poradi));
CREATE INDEX IF NOT EXISTS uryvky_kosinus ON uryvky USING hnsw(vektor vector_cosine_ops);
CREATE TABLE IF NOT EXISTS stav(id int PRIMARY KEY CHECK(id=1), revize text NOT NULL, model text NOT NULL);
REVOKE ALL ON stranky,uryvky,stav FROM PUBLIC;
GRANT CONNECT ON DATABASE db_erp_lhutnik TO pol_vault_read,pol_vault_index;
GRANT USAGE ON SCHEMA vault_search TO pol_vault_read,pol_vault_index;
GRANT SELECT ON stranky,uryvky,stav TO pol_vault_read,pol_vault_index;
GRANT INSERT,UPDATE,DELETE ON stranky,uryvky,stav TO pol_vault_index;
COMMIT;
