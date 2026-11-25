"""Běžný klient reklamního MCP smí získat pouze součty místních kampaní."""
import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    spec = StdioServerParameters(command="/usr/local/sbin/polarita-ads-mcp-test")
    async with stdio_client(spec) as (reader, writer), ClientSession(reader, writer) as client:
        await client.initialize()
        reply = await client.call_tool("ecomail_list_campaigns", {})
        if reply.isError:
            raise RuntimeError("Reklamní MCP odmítlo čtení kampaní.")
        envelope = json.loads(reply.content[0].text)
    result = envelope["result"]
    rows = result["campaigns"]
    if envelope["source"] != "local" or envelope["environment"] != "TEST" or not result["available"]:
        raise RuntimeError("MCP nevrátil místní testovací přehled.")
    if any(set(row) != {"seznam","kolo","souhlas","zakaznik"} for row in rows):
        raise RuntimeError("Výstup obsahuje neočekávané položky.")
    if sorted((r["kolo"],r["souhlas"],r["zakaznik"]) for r in rows if r["seznam"] == sys.argv[1]) != [(1,1,1),(2,0,1)]:
        raise RuntimeError("Součty obou kampaní nesouhlasí.")
    print("Reklamní MCP potvrdilo dva příjemce v prvním kole a jednoho po odhlášení. Výstup obsahuje pouze součty podle titulu a kampaně.")

if __name__ == "__main__":
    asyncio.run(main())
