"""Zkouší katalog a negativní i kladné požadavky běžného MCP klienta přes stdio."""
import asyncio
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def verify(script, state, initial):
    spec = StdioServerParameters(command=sys.executable, args=["-I", str(script)], env={"POLARITA_ADS_TEST_STATE":state})
    async with stdio_client(spec) as (reader, writer), ClientSession(reader, writer) as client:
        await client.initialize()
        catalog = {tool.name for tool in (await client.list_tools()).tools}
        summaries = {"gsc_list_sites","zbozi_list_offers","heureka_list_offers","ecomail_list_campaigns","umami_conversions","poas_margin"}
        providers = ("google","meta","sklik")
        assert catalog == summaries | {p+"_"+a for p in providers for a in ("list_campaigns","create_campaign")}
        for name in summaries:
            reply = await client.call_tool(name,{})
            assert not reply.isError and json.loads(reply.content[0].text)["source"] == "local"
        draft = {"draft_id":"TEST-01","name":"Učební kampaň","status":"PAUSED","spend_cap_halere":10000}
        for provider in providers:
            create = provider+"_create_campaign"
            for invalid in ({"status":"ENABLED"},{"spend_cap_halere":0},{"mutation_confirm":True},{"access_token":"fixture"}):
                assert (await client.call_tool(create, {**draft,**invalid})).isError
            assert (await client.call_tool(create,{k:v for k,v in draft.items() if k!="spend_cap_halere"})).isError
            if initial:
                rows = await client.call_tool(provider+"_list_campaigns",{})
                assert json.loads(rows.content[0].text)["result"] == []
            for _ in range(2):
                good = await client.call_tool(create,draft)
                assert not good.isError and json.loads(good.content[0].text)["result"] == {"provider":provider,**draft}
            assert (await client.call_tool(create,{**draft,"name":"Jiná kampaň"})).isError
            rows = await client.call_tool(provider+"_list_campaigns",{})
            assert json.loads(rows.content[0].text)["result"] == [{"provider":provider,**draft}]
        for name in ("google_run_query","meta_update_campaign","ga4_run_report","gsc_submit_sitemap","ecomail_send"):
            assert (await client.call_tool(name,{})).isError

async def main():
    with TemporaryDirectory() as tmp:
        for initial in (True,False):
            await verify(Path(sys.argv[1]).resolve(strict=True), tmp, initial)
    print("MCP přes stdio ověřil 12 nástrojů, 3 trvale pozastavené návrhy, jejich opakování a obnovu po restartu. Aktivace, změna limitu a odeslání byly odmítnuty.")

if __name__ == "__main__":
    asyncio.run(main())
