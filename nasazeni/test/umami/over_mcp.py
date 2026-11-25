"""Přečte zveřejněný součet běžným klientem reklamního MCP v ředitelství."""
import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    expected = json.loads(Path("/var/lib/polarita-umami-test/konverze.json").read_text())
    command = StdioServerParameters(command="/usr/local/sbin/polarita-ads-mcp-test")
    async with stdio_client(command) as (reader, writer), ClientSession(reader, writer) as client:
        await client.initialize()
        reply = await client.call_tool("umami_conversions", {})
        if reply.isError:
            raise RuntimeError("Reklamní MCP odmítlo čtení součtů.")
        envelope = json.loads(reply.content[0].text)
    if envelope != {"environment": "TEST", "source": "local", "result": expected} or expected["available"] is not True:
        raise RuntimeError("Reklamní MCP nevrátilo čerstvý výsledek posledního sběru.")
    if set(expected) != {"available", "website", "event", "days", "checked_at"} or expected["event"] != "prevzeti-sanonu":
        raise RuntimeError("Nesouhlasí rozsah zveřejněných dat.")
    if any(set(row) != {"day", "received"} for row in expected["days"]):
        raise RuntimeError("Denní přehled má obsahovat pouze den a počet převzetí.")
    count = sum(row["received"] for row in expected["days"])
    print(f"Reklamní MCP potvrdilo aktuální denní součty z Umami. Celkem převzetí: {count}.")


if __name__ == "__main__":
    asyncio.run(main())
