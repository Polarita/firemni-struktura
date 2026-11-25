"""Poslední známý stav každého konektoru z čtecí přípojky servisního spisu."""
from contextlib import closing
from pathlib import Path
import sqlite3

DB = Path("/var/lib/polarita-ocpp-test/telemetrie.sqlite")


def stav(kod):
    if not DB.exists():
        return []
    with closing(sqlite3.connect(DB.as_uri()+"?mode=ro", uri=True, timeout=3)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("""
            SELECT stanice,evse,konektor,stav,cas,pocet FROM (
                SELECT *, count(*) OVER w AS pocet,
                    row_number() OVER (PARTITION BY stanice,evse,konektor ORDER BY cas DESC,rowid DESC) AS poradi
                  FROM udalost WHERE spis=? WINDOW w AS (PARTITION BY stanice,evse,konektor)
            ) WHERE poradi=1 ORDER BY stanice,evse,konektor
            """,(kod,))
        return [dict(row) for row in rows]
