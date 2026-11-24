"""Čtecí sondy ve firemní VM. Do Checkmk putují výhradně stavy a číselné metriky."""
from concurrent.futures import ThreadPoolExecutor
import csv
import json
import os
from pathlib import Path
import smtplib
import socket
import ssl
import subprocess
import time
from urllib.request import HTTPSHandler, ProxyHandler, build_opener


def run(*args):
    return subprocess.run(args,check=True,capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=10).stdout.strip()


def inside(name,*args):
    return run("incus","exec","-T",name,"--",*args)


def state(ok,summary,metrics="-"):
    return (0 if ok else 2,metrics,summary)


def pool():
    data = run("zpool","list","-Hp","-o","health,capacity","polarita_zfs").split()
    capacity = int(data[1].rstrip("%"))
    return state(data[0]=="ONLINE" and capacity<90,f"{data[0]}, využito {capacity} %",f"used={capacity}%;80;90")


def memory():
    info = dict((line.split(":")[0],int(line.split()[1])) for line in Path("/proc/meminfo").read_text().splitlines())
    available = info["MemAvailable"]//1024
    return state(available>=120,f"Dostupných {available} MiB",f"available={available}MiB")


def cpu():
    avg = os.getloadavg()[0]
    cores = len(os.sched_getaffinity(0))
    return (1 if avg>cores*3 else 0,f"load1={avg:.2f}",f"Minutová zátěž {avg:.2f} na {cores} CPU")


def instances():
    rows = list(csv.reader(run("incus","list","--format","csv","-c","ns").splitlines()))
    expected = {"caddy-test","headscale-test","stalwart-mx-test","openbao-test","vaultwarden-test",
                "postgres-test","valkey-test","garage-test","gitea-test","gitea-runner-test",
                "reditelstvi-test","keycloak-test","pecet-test","clamav-signatury-test","restic-test","checkmk-test"}
    missing = expected-set(name for name,status in rows if status=="RUNNING")
    if "karantena-test" not in dict(rows):
        missing.add("karantena-test")
    run("systemctl","is-active","--quiet","polarita-karantena.path","polarita-karantena.timer")
    return state(not missing,("Nedostupné "+", ".join(sorted(missing))) if missing else f"Běží {len(expected)} trvalých instancí a příjem fronty karantény",f"running={sum(s=='RUNNING' for _,s in rows)}")


def interfaces():
    links = [p for p in Path("/sys/class/net").glob("*") if p.name in {"enp5s0","eth0","app_internal","data_vault","dmz_edge"}]
    active = [p.name for p in links if (p/"operstate").read_text().strip()=="up"]
    required = {"app_internal","dmz_edge","data_vault"}
    return state(required.issubset(active),"Aktivní "+", ".join(sorted(active)))


def bao():
    ctx=ssl.create_default_context(cafile="/srv/polarita/infra/openbao-test/ca.crt")
    http=build_opener(ProxyHandler({}),HTTPSHandler(context=ctx))
    with http.open("https://10.239.33.10:8200/v1/sys/seal-status",timeout=5) as res:
        data=json.load(res)
    return state(data["initialized"] and not data["sealed"],f"Inicializován {data['initialized']}, uzamčen {data['sealed']}")


def proxy():
    ctx=ssl.create_default_context(cafile="/srv/polarita/infra/hrana/headscale-test-ca.crt")
    with socket.create_connection(("10.239.31.10",8443),timeout=5) as raw, ctx.wrap_socket(raw,server_hostname="vpn.polarita.test") as tls:
        remain=ssl.cert_time_to_seconds(tls.getpeercert()["notAfter"])-time.time()
    hours=remain/3600
    return state(hours>1,f"TLS pro vpn.polarita.test zbývá {hours:.1f} h",f"expiry={int(remain)}s")


def postgres():
    out=inside("postgres-test","runuser","-u","postgres","--","psql","-XqAt","-d","postgres","-c","select 1")
    return state(out=="1","Lokální uživatel postgres přečetl kontrolní hodnotu")


def pgbouncer():
    inside("postgres-test","pg_isready","-h","127.0.0.1","-p","6432","-d","db_eshop","-U","db_eshop")
    return state(True,"PgBouncer přijímá připojení")


def valkey():
    cert=inside("valkey-test","cat","/run/secrets/valkey-cert")
    ctx=ssl.create_default_context(cadata=cert)
    with socket.create_connection(("10.239.33.13",6379),timeout=5) as raw, ctx.wrap_socket(raw,server_hostname="10.239.33.13") as tls:
        tls.sendall(b"*1\r\n$4\r\nPING\r\n")
        response=tls.recv(256)
    return state(response.startswith(b"-NOAUTH"),"TLS odpověď vyžaduje oprávnění klienta")


def garage():
    out=inside("garage-test","curl","--noproxy","*","-fsS","--max-time","5","http://127.0.0.1:3903/health")
    ok = "fully operational" in out.lower()
    return state(ok, "Cluster je v provozu" if ok else "Garage hlásí omezený provoz")


def mx():
    with smtplib.SMTP(timeout=5,local_hostname="monitor.polarita.test") as client:
        welcome=client.connect("10.239.31.12",25)[0]
        ehlo=client.ehlo()[0]
        return state(welcome==220 and ehlo==250 and client.has_extn("starttls"),"SMTP port 25 nabízí STARTTLS")


def queue():
    raw=run("bash",str(Path(__file__).resolve().with_name("fronta_mx.sh")))
    count=int(raw)
    return (2 if count>=100 else 1 if count>=25 else 0,f"queued={count};25;100",f"Počet zpráv v odchozí frontě {count}")


def rocks():
    inside("stalwart-mx-test","test","-s","/var/lib/stalwart/rocksdb/CURRENT")
    row=inside("stalwart-mx-test","df","-Pk","/var/lib/stalwart/rocksdb").splitlines()[-1].split()
    percent=int(row[-2].rstrip("%"))
    return state(percent<90,f"RocksDB využívá {percent} % dostupného svazku",f"used={percent}%;80;90")


def age(path,limit):
    hours=(time.time()-Path(path).stat().st_mtime)/3600
    return state(0<=hours<limit,f"Poslední úspěch před {hours:.1f} h",f"age={int(hours*3600)}s")


def sample():
    with socket.create_connection(("127.0.0.1",18419),timeout=4) as conn:
        return state(conn.recv(16)==b"POLARITA OK\n","Kontrolní služba odpověděla")


PROBES={"OpenZFS":pool,"RAM":memory,"CPU":cpu,"Incus":instances,"Sitova rozhrani":interfaces,
        "OpenBao":bao,"Caddy TLS":proxy,"PostgreSQL":postgres,"PgBouncer":pgbouncer,
        "Valkey TLS":valkey,"Garage":garage,"MX SMTP":mx,"MX fronta":queue,"MX RocksDB":rocks,
        "Stari zalohy":lambda:age("/srv/polarita/infra/restic-test/posledni-otisk",30),
        "Posledni obnova":lambda:age("/srv/polarita/infra/restic-test/posledni-overena-obnova.json",8*24),
        "Zkusebni sluzba":sample}


def measure(item):
    name,probe=item
    try:
        return name,probe()
    except (OSError,subprocess.SubprocessError,ValueError,KeyError,IndexError) as error:
        return name,(2,"-","Sonda neuspěla ("+type(error).__name__+")")


def main():
    if socket.gethostname().split(".")[0]!="polarita-hq" or os.geteuid():
        raise SystemExit("Sběr potřebuje firemní VM")
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=dict(pool.map(measure,PROBES.items()))
    body=json.dumps({"cas":int(time.time()),"sluzby":results},ensure_ascii=False).encode()
    subprocess.run(["incus","exec","-T","checkmk-test","--","bash","-ec",
                    """set -euo pipefail
install -d -m 0755 /var/lib/polarita-dohled
cd /var/lib/polarita-dohled
t=$(mktemp .stav-XXXXXXXX)
trap 'rm -f "$t"' EXIT
cat >"$t"
chmod 0644 "$t"
mv -T "$t" stav.json"""],
                   input=body,check=True,timeout=15)
    for name,(status,metric,message) in results.items():
        print(name,status,message)


if __name__=="__main__":
    main()
