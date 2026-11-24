"""Ověří pro příštího klienta skutečný systémový příkaz a uložený předávací vzor."""
import asyncio
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    spec = StdioServerParameters(command="/usr/local/sbin/polarita-ads-mcp-test")
    draft = {"draft_id":"TEST-PREDANI-01","name":"Předávací ukázka","status":"PAUSED","spend_cap_halere":10000}
    for action in ("write","read"):
        async with stdio_client(spec) as (reader, writer), ClientSession(reader, writer) as client:
            await client.initialize()
            if action == "write":
                denied = await client.call_tool("sklik_create_campaign",{**draft,"status":"ENABLED"})
                if not denied.isError:
                    raise RuntimeError("Rozhraní povolilo aktivaci")
                reply = await client.call_tool("sklik_create_campaign",draft)
                if reply.isError or json.loads(reply.content[0].text)["result"] != {"provider":"sklik",**draft}:
                    raise RuntimeError("Rozhraní nepotvrdilo místní koncept")
            else:
                reply = await client.call_tool("sklik_list_campaigns",{})
                found = [r for r in json.loads(reply.content[0].text)["result"] if r["draft_id"] == draft["draft_id"]]
                if reply.isError or found != [{"provider":"sklik",**draft}]:
                    raise RuntimeError("Po novém připojení chybí původní koncept")
    print("Systémový příkaz MCP uložil předávací koncept TEST-PREDANI-01 a další připojení přečetlo jediný exemplář ve stavu PAUSED.")

if __name__ == "__main__":
    asyncio.run(main())
