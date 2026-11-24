import argparse
import json
import sys
from pamet import read, record, snapshot

def main():
    p = argparse.ArgumentParser(prog="agent_vault")
    commands = p.add_subparsers(dest="action",required=True)
    commands.add_parser("get-context").add_argument("path",nargs="?")
    for kind in ("log","adr"):
        commands.add_parser(kind).add_argument("key")
    q = commands.add_parser("search")
    q.add_argument("query")
    q.add_argument("--limit",type=int,default=5)
    commands.add_parser("index")
    args = p.parse_args()
    if args.action=="get-context":
        rev, entries = snapshot()
        if args.path is None:
            result = {"revize":rev,"stranky":sorted(entries)}
        elif args.path in entries:
            result = {"revize":rev,"cesta":args.path,"text":read(entries[args.path])}
        else:
            raise ValueError("Cesta není verzovanou znalostní stránkou.")
    elif args.action in ("log","adr"):
        data = sys.stdin.buffer.read(32769)
        if len(data)>32768:
            raise ValueError("Záznam přesahuje 32 KiB.")
        result = record(args.action,args.key,data.decode("utf-8"))
    elif args.action=="index":
        from hledani import refresh
        result = {"revize":refresh()}
    else:
        from hledani import search
        result = search(args.query,args.limit)
    print(json.dumps(result,ensure_ascii=False))

if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        sys.exit(str(error))
