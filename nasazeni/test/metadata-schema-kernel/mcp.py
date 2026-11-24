"""Nativní MCP stdio pro účet s právem SELECT na vygenerované entitě."""
import json
import sys

from model import load, tool
from zaznamy import Problem, read

VERSION = "2026-07-28"
PREFIX = "io.modelcontextprotocol/"


def response(data, req):
    result = {"jsonrpc": "2.0", "id": req.get("id") if isinstance(req, dict) else None}

    def error(code, message, details=None):
        result["error"] = {"code": code, "message": message}
        if details:
            result["error"]["data"] = details
        return result

    if not isinstance(req, dict) or req.get("jsonrpc") != "2.0" or not isinstance(req.get("method"), str):
        return error(-32600, "Neplatný požadavek")
    if "id" not in req:
        return None
    params = req.get("params", {})
    meta = params.get("_meta") if isinstance(params, dict) else None
    if not isinstance(meta, dict) or not isinstance(meta.get(PREFIX+"clientCapabilities"), dict) or not isinstance(meta.get(PREFIX+"protocolVersion"), str):
        return error(-32602, "Chybí verze nebo schopnosti klienta")
    if meta[PREFIX+"protocolVersion"] != VERSION:
        return error(-32022, "Nepodporovaná verze protokolu",
                     {"supported": [VERSION], "requested": meta[PREFIX+"protocolVersion"]})
    out = {"resultType": "complete", "_meta": {PREFIX+"serverInfo": {"name": "metadata-schema-kernel", "version": "1.0"}}}
    definition = tool(data)
    if req["method"] == "server/discover":
        out.update(supportedVersions=[VERSION], capabilities={"tools": {}})
    elif req["method"] == "tools/list":
        out.update(tools=[definition])
    elif req["method"] == "tools/call":
        args = params.get("arguments")
        if params.get("name") != definition["name"] or not isinstance(args, dict) or set(args) != {"id"}:
            return error(-32602, "Neznámý nástroj nebo parametry")
        try:
            row = read(data, args["id"])
            out.update(structuredContent=row, content=[{"type": "text", "text": json.dumps(row, ensure_ascii=False)}])
        except Problem as exc:
            out.update(isError=True, content=[{"type": "text", "text": str(exc)}])
        except (RuntimeError, OSError) as exc:
            print(type(exc).__name__, file=sys.stderr, flush=True)
            out.update(isError=True, content=[{"type": "text", "text": "Databáze není dostupná"}])
    elif req["method"] == "ping":
        pass
    else:
        return error(-32601, "Neznámá metoda")
    result["result"] = out
    return result


if __name__ == "__main__":
    data = load(sys.argv[1])
    for line in sys.stdin:
        try:
            result = response(data, json.loads(line))
        except (ValueError, RecursionError):
            result = {"jsonrpc":"2.0", "id":None, "error":{"code":-32700,"message":"Neplatný JSON"}}
        if result is not None:
            print(json.dumps(result, ensure_ascii=False), flush=True)
