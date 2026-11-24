"""Exportuje datový svazek, skutečně jej obnoví a ověří shodu testovacího záznamu."""
import base64
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import pristupy as p


def run(*cmd, data=None, timeout=180):
    return subprocess.run(cmd, input=data if data is not None else b"",
                          stdout=subprocess.PIPE, timeout=timeout, check=True).stdout


def main():
    if run("hostname", "-s").strip() != b"polarita-hq":
        raise SystemExit("Zkouška obnovy patří do firemní VM")
    os.umask(0o077)
    payload = json.load(sys.stdin)
    seal = base64.b64decode(payload["seal"], validate=True)
    if len(seal) != 32 or len(payload["shares"]) != 5:
        raise ValueError("Neúplný testovací balíček obnovy")
    p.HTTP = p.build_opener(p.ProxyHandler({}), p.HTTPSHandler(context=p.ssl.create_default_context(cafile=str(p.WORK / "ca.crt"))))
    manager = p.login(p.recover("bao-sprava"))
    token = p.login(p.credentials("reditelstvi-test", manager))
    original = p.request("GET", "test/data/reditelstvi", token=token)["data"]["data"]["vzorek"]
    digest = hashlib.sha256(original.encode()).hexdigest()
    for t in (token, manager):
        p.request("POST", "auth/token/revoke-self", {}, t)

    backup = Path("/srv/polarita/backups/openbao")
    backup.mkdir(mode=0o700, parents=True, exist_ok=True)
    name = "obnova-bao-" + secrets.token_hex(5)
    vol = name + "-data"
    src = Path(__file__).resolve().parent
    with ExitStack() as cleanup:
        tmp = Path(cleanup.enter_context(tempfile.TemporaryDirectory(dir=backup)))
        archive = tmp / "svazek.tar"
        run("incus", "storage", "volume", "export", "default", "openbao-test-raft", str(archive), "--compression=none", "--volume-only")
        run("incus", "storage", "volume", "import", "default", str(archive), vol)
        cleanup.callback(run, "incus", "storage", "volume", "delete", "default", vol)
        run("incus", "init", "local:polarita-openbao-test-2.7.3", name, "-p", "default", "-p", "sandbox_airgap",
            "-c", "limits.memory=320MiB", "-c", "limits.memory.swap=false")
        cleanup.callback(run, "incus", "delete", "-f", name)
        run("incus", "config", "device", "add", name, "raft", "disk", "pool=default", "source=" + vol,
            "path=/var/lib/polarita-openbao")
        run("incus", "start", name)

        def inside(*args, data=None):
            return run("incus", "exec", "-T", name, "--", *args, data=data)
        inside("sh", "-ec", 'for i in $(seq 1 60); do if systemctl show --property=Version --value >/dev/null 2>&1 && test -S /run/systemd/private; then exit 0; fi; sleep 1; done; exit 1')
        inside("sh", "-ec", 'test "$(ls /sys/class/net)" = lo; useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin openbao; install -d /etc/polarita-openbao')
        config = (src / "server.hcl").read_text().replace("10.239.33.10", "127.0.0.1")
        # Zvláštní obnovovací listener existuje pouze v jednorázové kopii bez síťové karty.
        config = config.replace('listener "tcp" {', 'listener "tcp" {\n  disable_unauthed_generate_root_endpoints = false')
        run("incus", "file", "push", "--mode=0644", "-", name + "/etc/polarita-openbao/server.hcl", data=config.encode())
        run("incus", "file", "push", "--mode=0644", str(src / "openbao.service"), name + "/etc/systemd/system/openbao.service")
        inside("sh", "-ec", 'test "$(findmnt -no FSTYPE /run)" = tmpfs; install -d -m 0750 -o root -g openbao /run/openbao-seal; umask 077; cat >/run/openbao-seal/klíč; chown openbao /run/openbao-seal/klíč; chmod 0400 /run/openbao-seal/klíč; systemctl daemon-reload; systemctl start openbao', data=seal)
        inside("sh", "-ec", 'for i in $(seq 1 60); do if curl --fail --silent --cacert /var/lib/polarita-openbao/tls/server.crt https://127.0.0.1:8200/v1/sys/health >/dev/null; then rm /run/openbao-seal/klíč; exit 0; fi; sleep 1; done; exit 1')
        run("incus", "file", "push", "--mode=0400", str(src / "cteni-obnovy.py"), name + "/run/cteni.py")
        result = inside("python3", "/run/cteni.py", data=json.dumps({"shares": payload["shares"], "digest": digest}).encode())
        print(result.decode().strip(), flush=True)
        archive.chmod(0o600)
        archive.replace(backup / "posledni.tar")
    print("Ověřený export je uložen na šifrovaném ZFS. Dočasná instance a její svazek byly odstraněny.")


if __name__ == "__main__":
    main()
