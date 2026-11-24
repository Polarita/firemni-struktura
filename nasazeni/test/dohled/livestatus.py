"""Čtení výhradně lokálního soketu Nagios Livestatus uvnitř Checkmk."""
import json
import socket
import sys

PATH="/omd/sites/polarita/tmp/run/live"


def services():
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as channel:
        channel.settimeout(7)
        channel.connect(PATH)
        channel.sendall(b"GET services\nColumns: description state state_type last_check\nFilter: host_name = polarita-hq\nOutputFormat: json\n\n")
        channel.shutdown(socket.SHUT_WR)
        with channel.makefile("rb") as stream:
            rows=json.load(stream)
    return {desc:{"stav":state,"typ":kind,"cas":epoch} for desc,state,kind,epoch in rows if desc.startswith("Polarita ")}


if __name__=="__main__":
    print(json.dumps(services()))
