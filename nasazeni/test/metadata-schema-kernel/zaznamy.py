"""Ověřená data a atomický zápis s verzí v PostgreSQL přes místní peer účet."""
import json
import subprocess
from uuid import UUID

from model import table


class Problem(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def identifier(key):
    try:
        if not isinstance(key, str) or str(UUID(key)) != key:
            raise ValueError()
    except ValueError:
        raise Problem(400, "Neplatné ID") from None
    return key


def values(data, body):
    if not isinstance(body, dict) or body.keys() != data["fields"].keys():
        raise Problem(400, "Pole záznamu neodpovídají schématu")
    for key, field in data["fields"].items():
        value = body[key]
        if field["type"] == "integer":
            valid = type(value) is int and field["minimum"] <= value <= field["maximum"]
        elif field["type"] == "boolean":
            valid = type(value) is bool
        else:
            valid = isinstance(value, str) and "\x00" not in value and len(value) <= field["maxLength"]
            if valid:
                try:
                    value.encode()
                except UnicodeEncodeError:
                    valid = False
        if not valid:
            raise Problem(400, f"Neplatná hodnota pole {key}")
    return json.dumps(body, ensure_ascii=False)


def query(data, sql, **bindings):
    # Data putují citovanými proměnnými psql. SQL obsahuje jen generované identifikátory.
    cmd = ["psql", "-XqAtw", "-v", "ON_ERROR_STOP=1", "-d", data["database"]]
    for key, value in bindings.items():
        cmd.extend(["-v", key + "=" + value])
    try:
        out = subprocess.run(cmd, input=sql, text=True, capture_output=True, timeout=15)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Vypršel čas databázového příkazu") from exc
    if out.returncode:
        raise RuntimeError("Databázový příkaz selhal")
    return json.loads(out.stdout) if out.stdout.strip() else None


def read(data, key):
    row = query(data, f"SELECT to_jsonb(r) FROM {table(data)} r WHERE id=:'id'::uuid;", id=identifier(key))
    if row is None:
        raise Problem(404, "Záznam nenalezen")
    return row


def write(data, body, key=None, version=None):
    target = table(data)
    columns = ", ".join(f'"{column}"' for column in data["fields"])
    bindings = {"body": values(data, body)}
    cast = f"jsonb_populate_record(NULL::{target}, :'body'::jsonb)"
    if key is None:
        sql = f"INSERT INTO {target} AS r ({columns}) SELECT {columns} FROM {cast} RETURNING to_jsonb(r);"
    else:
        bindings.update(id=identifier(key), version=str(version))
        sql = f"""UPDATE {target} AS r SET ({columns}) = (SELECT {columns} FROM {cast}),
                  version=r.version+1 WHERE r.id=:'id'::uuid AND r.version=:'version'::bigint
                  RETURNING to_jsonb(r);"""
    row = query(data, sql, **bindings)
    if row is None:
        read(data, key)
        raise Problem(412, "Záznam má jinou verzi")
    return row
