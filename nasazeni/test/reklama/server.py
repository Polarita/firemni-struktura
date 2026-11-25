"""Soukromý stdio server místní Gitea pro syntetickou reklamu v ředitelství."""
import asyncio
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("polarita-ads-mcp")
CAMPAIGNS = ("google", "meta", "sklik")
CAP = 10000  # Haléře české koruny, pouze účetní model v TEST.
REPORTS = {
    "gsc_list_sites": {"siteEntry": [{"siteUrl": "sc-domain:polarita.test", "permissionLevel": "siteOwner"}]},
    "zbozi_list_offers": {"offers": [{"id": "TEST-Z1", "currency": "CZK"}]},
    "heureka_list_offers": {"offers": [{"id": "TEST-H1", "currency": "CZK"}]},
    "ecomail_list_campaigns": {"campaigns": []},
    "umami_conversions": {},
    "poas_margin": {"available": False, "planned_block": 11},
}
EMPTY = {"type": "object", "properties": {}, "additionalProperties": False}
DRAFT = {"type": "object", "additionalProperties": False,
         "properties": {"draft_id": {"type": "string", "pattern": "^[A-Z0-9-]{1,64}$"},
                        "name": {"type": "string", "minLength": 1, "maxLength": 100},
                        "status": {"const": "PAUSED"},
                        "spend_cap_halere": {"type": "integer", "const": CAP}},
         "required": ["draft_id", "name", "status", "spend_cap_halere"]}

@server.list_tools()
async def list_tools():
    tools = [Tool(name=name, description="Místní syntetický přehled TEST.", inputSchema=EMPTY) for name in REPORTS]
    for provider in CAMPAIGNS:
        tools.append(Tool(name=provider+"_list_campaigns", description="Uložené místní koncepty TEST.", inputSchema=EMPTY))
        tools.append(Tool(name=provider+"_create_campaign", description="Uloží nebo zopakuje pozastavený koncept s pevným stropem v TEST.", inputSchema=DRAFT))
    return tools

def campaign(provider, action, args):
    state = Path(os.environ["POLARITA_ADS_TEST_STATE"])
    with closing(sqlite3.connect(state / "kampane.sqlite3", timeout=10)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("""CREATE TABLE IF NOT EXISTS drafts (
            provider TEXT NOT NULL CHECK(provider IN ('google','meta','sklik')),
            draft_id TEXT NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL CHECK(status='PAUSED'),
            spend_cap_halere INTEGER NOT NULL CHECK(spend_cap_halere=10000),
            PRIMARY KEY(provider,draft_id)) STRICT""")
        if action == "list_campaigns":
            return [dict(row) for row in db.execute("SELECT * FROM drafts WHERE provider=? ORDER BY draft_id", (provider,))]
        db.execute("""INSERT INTO drafts VALUES (?,?,?,?,?) ON CONFLICT(provider,draft_id) DO NOTHING""",
                   (provider, args["draft_id"], args["name"], args["status"], args["spend_cap_halere"]))
        row = dict(db.execute("SELECT * FROM drafts WHERE provider=? AND draft_id=?", (provider,args["draft_id"])).fetchone())
        if row != {"provider": provider, **args}:
            raise ValueError("Identifikátor již patří jinému konceptu.")
        return row

@server.call_tool()
async def call_tool(name, arguments):
    if name == "umami_conversions":
        try:
            result = json.loads(Path("/var/lib/polarita-umami-test/konverze.json").read_text())
            age = datetime.now(timezone.utc) - datetime.fromisoformat(result["checked_at"])
            result["available"] = 0 <= age.total_seconds() <= 900
        except FileNotFoundError:
            result = {"available": False, "event": "prevzeti-sanonu"}
    elif name in REPORTS:
        result = REPORTS[name]
    else:
        provider, _, action = name.partition("_")
        if provider not in CAMPAIGNS or action not in ("list_campaigns", "create_campaign"):
            raise ValueError("Neznámá operace TEST.")
        result = campaign(provider, action, arguments)
    return [TextContent(type="text", text=json.dumps({"environment":"TEST", "source":"local", "result":result}, ensure_ascii=False))]

async def serve():
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())

def main():
    os.umask(0o077)
    asyncio.run(serve())

if __name__ == "__main__":
    main()
