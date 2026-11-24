"""Popis vlastní entity TEST sdílený SQL, webem, OpenAPI a MCP."""
import hashlib
import json
from pathlib import Path
import re

TARGETS = {("db_erp_lhutnik", "polarita_test_metadata")}
ID = {"type": "string", "format": "uuid"}
VERSION = {"type": "integer", "minimum": 1}


def name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,37}", value):
        raise ValueError("Neplatné jméno entity nebo sloupce")
    return value


def title(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 120:
        raise ValueError("Chybí čitelný název")


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicitní klíč {key}")
        result[key] = value
    return result


def load(path):
    path = Path(path)
    if path.suffix == ".json":
        data = json.loads(path.read_text(), object_pairs_hook=unique)
    elif path.suffix in {".yml", ".yaml"}:
        import yaml

        class Loader(yaml.SafeLoader):
            pass

        def mapping(loader, node):
            return unique(loader.construct_pairs(node, deep=True))
        Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
        data = yaml.load(path.read_text(), Loader=Loader)
    else:
        raise ValueError("Schéma musí být JSON nebo YAML")
    if not isinstance(data, dict) or set(data) != {"database", "schema", "entity", "title", "fields"}:
        raise ValueError("Neplatný popis entity")
    if (data["database"], data["schema"]) not in TARGETS:
        raise ValueError("Cíl není vyhrazený vlastnímu modulu TEST")
    name(data["entity"])
    title(data["title"])
    fields = data["fields"]
    if not isinstance(fields, dict) or not 1 <= len(fields) <= 40:
        raise ValueError("Entita musí mít 1 až 40 polí")
    keys = {"string": {"maxLength"}, "integer": {"minimum", "maximum"}, "boolean": set()}
    for key, field in fields.items():
        name(key)
        if key in {"id", "version", "tableoid", "xmin", "xmax", "cmin", "cmax", "ctid"} or not isinstance(field, dict):
            raise ValueError("Vyhrazené nebo neplatné pole")
        kind = field.get("type")
        if kind not in keys or set(field) != {"type", "title"} | keys[kind]:
            raise ValueError(f"Nepodporovaný popis pole {key}")
        title(field["title"])
        if kind == "string" and (type(field["maxLength"]) is not int or not 1 <= field["maxLength"] <= 4096):
            raise ValueError("Neplatná délka textu")
        if kind == "integer" and (type(field["minimum"]) is not int or type(field["maximum"]) is not int
                                  or not -(2**31) <= field["minimum"] <= field["maximum"] < 2**31):
            raise ValueError("Neplatný rozsah celého čísla")
    return data


def obj(fields):
    return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}


def record(data):
    return obj({"id": ID, "version": VERSION, **data["fields"]})


def table(data):
    return f'"{data["schema"]}"."meta_{data["entity"]}"'


def migrations(data):
    target = table(data)
    digest = "polarita-metadata-v1:" + hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    # Všechny identifikátory prošly name()/TARGETS. Do SQL se nevkládají názvy pro uživatele.
    columns = ["id uuid PRIMARY KEY DEFAULT gen_random_uuid()", "version bigint NOT NULL DEFAULT 1 CHECK (version > 0)"]
    for key, field in data["fields"].items():
        col = f'"{key}"'
        if field["type"] == "string":
            sql = f'varchar({field["maxLength"]})'
        elif field["type"] == "integer":
            sql = f'integer CHECK ({col} BETWEEN {field["minimum"]} AND {field["maximum"]})'
        else:
            sql = "boolean"
        columns.append(f"{col} {sql} NOT NULL")
    header = f"""BEGIN;
SET LOCAL search_path TO pg_catalog;
SELECT pg_advisory_xact_lock(hashtextextended('{target}', 0));
DO $migration$
DECLARE existing regclass;
BEGIN
    IF current_database() <> '{data["database"]}' THEN RAISE EXCEPTION 'Nesprávná databáze'; END IF;
    existing := to_regclass('{target}');
    IF existing IS NOT NULL AND NOT EXISTS (
        SELECT FROM pg_class WHERE oid = existing AND relkind = 'r' AND relowner = current_user::regrole
        AND obj_description(oid, 'pg_class') = '{digest}'
    ) THEN RAISE EXCEPTION 'Odlišná tabulka nebo revize schématu'; END IF;
"""
    end = "END\n$migration$;\nCOMMIT;\n"
    definition = ",\n            ".join(columns)
    up = header + f"""    IF existing IS NULL THEN
        CREATE TABLE {target} (
            {definition}
        );
        COMMENT ON TABLE {target} IS '{digest}';
    END IF;
""" + end
    down = header + f"""    IF existing IS NOT NULL THEN
        LOCK TABLE {target} IN ACCESS EXCLUSIVE MODE;
        IF EXISTS (SELECT FROM {target}) THEN RAISE EXCEPTION 'Tabulka obsahuje záznamy'; END IF;
        DROP TABLE {target} RESTRICT;
    END IF;
""" + end
    return up, down


def tool(data):
    return {"name": "get_" + data["entity"], "description": "Načte záznam včetně aktuální verze.",
            "inputSchema": obj({"id": ID}), "outputSchema": record(data), "annotations": {"readOnlyHint": True}}


BRANCH = {"type": "integer", "minimum": 101, "maximum": 999}
CASE_NUMBER = {"type": "string", "pattern": "^POL-[0-9]{4}-[0-9]{5}$"}
CASE_ALIAS = {"type": "string", "pattern": "^POL-[1-9][0-9]{2}-[0-9]{4}-[0-9]{5}$"}
CASE_LOOKUP = {"oneOf": [CASE_NUMBER, CASE_ALIAS]}
CASE_CARD = obj({"pozadavek": ID, "branch_id": BRANCH, "zalozeno": {"type": "string", "format": "date-time"},
                 "case_id": CASE_NUMBER, "alias": CASE_ALIAS})
CASE_TOOL = {"name": "spisy_najdi", "description": "Načte kartu spisu podle čísla nebo pobočkového aliasu.",
             "inputSchema": obj({"oznaceni": CASE_LOOKUP}), "outputSchema": CASE_CARD,
             "annotations": {"readOnlyHint": True}}


def openapi(data):
    def content(schema):
        return {"application/json": {"schema": schema}}
    success = {"description": "Záznam a jeho aktuální verze", "content": content(record(data)),
               "headers": {"ETag": {"schema": {"type": "string"}}}}
    body = {"required": True, "content": content(obj(data["fields"]))}
    route = "/api/" + data["entity"]
    return {"openapi": "3.2.1", "info": {"title": data["title"], "version": "1.0"},
            "paths": {"/api/spisy": {"post": {"description": "Založí spis nebo vrátí spis pro stejný požadavek.",
                        "requestBody": {"required": True, "content": content(obj({"pozadavek": ID, "branch_id": BRANCH}))},
                        "responses": {"200": {"description": "Karta spisu", "content": content(CASE_CARD)},
                                      "400": {"description": "Neplatný požadavek nebo pobočka"},
                                      "409": {"description": "Kolize požadavku nebo vyčerpaná řada"}}}},
                      "/api/spisy/{oznaceni}": {"get": {"parameters": [{"name": "oznaceni", "in": "path", "required": True,
                        "schema": CASE_LOOKUP}], "responses": {"200": {"description": "Karta spisu", "content": content(CASE_CARD)},
                        "400": {"description": "Neplatné označení"}, "404": {"description": "Spis nenalezen"}}}},
                      route: {"post": {"requestBody": body,
                                        "responses": {"201": success, "400": {"description": "Neplatná pole"}}}},
                      route + "/{id}": {
                          "parameters": [{"name": "id", "in": "path", "required": True, "schema": ID}],
                          "get": {"responses": {"200": success, "404": {"description": "Záznam nenalezen"}}},
                          "put": {"parameters": [{"name": "If-Match", "in": "header", "required": True,
                                                 "schema": {"type": "string"}}], "requestBody": body,
                                  "responses": {"200": success, "400": {"description": "Neplatná pole"},
                                                "404": {"description": "Záznam nenalezen"},
                                                "412": {"description": "Verze se změnila"},
                                                "428": {"description": "Chybí If-Match"}}}}}}
