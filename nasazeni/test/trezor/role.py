"""Aktualizace oprávnění běžícího TEST trezoru s kvórem vlastníka. Tajemství zůstávají v RAM."""
import base64
from contextlib import contextmanager, nullcontext
import fcntl
import json
import ssl
import subprocess
import sys
import time
from urllib.error import HTTPError
import pristupy as p


def run(*args, data=b""):
    return subprocess.run(args, input=data, stdout=subprocess.PIPE, timeout=180, check=True).stdout


def quorum(api, shares):
    attempt = api("POST", "attempt", {})
    if attempt.get("required") != 3 or len(set(shares)) != 3:
        raise RuntimeError("Počet oprávněných podílů nesouhlasí")
    try:
        for i, share in enumerate(shares, 1):
            result = api("POST", "update", {"nonce": attempt["nonce"], "key": share})
            if result["complete"] != (i == 3):
                raise RuntimeError("Trezor odmítl kvórum")
        encoded = result["encoded_token"]
        encrypted = base64.b64decode(encoded + "=" * (-len(encoded) % 4))
        return bytes(a ^ b for a, b in zip(encrypted, attempt["otp"].encode(), strict=True)).decode()
    except Exception:
        api("DELETE", "attempt", None)
        raise


@contextmanager
def local_recovery():
    # Přechod z vydání 3.4. Správní socket vlastní openbao, má režim 0600 a existuje pouze v /run.
    inside = ["incus", "exec", "-T", "openbao-test", "--"]
    directory = "/run/polarita-migrace"
    override = "/run/systemd/system/openbao.service.d/70-polarita-migrace.conf"
    run(*inside, "install", "-d", "-m", "0700", "-o", "openbao", "-g", "openbao", directory)
    run(*inside, "install", "-d", "-m", "0755", "/run/systemd/system/openbao.service.d")
    conf = ('listener "unix" {\n address = "' + directory + '/sprava.sock"\n socket_mode = "0600"\n'
            ' tls_disable = true\n disable_unauthed_generate_root_endpoints = false\n}\n')
    dropin = ('[Service]\nExecStart=\nExecStart=/usr/local/bin/bao server -config=/etc/polarita-openbao/server.hcl'
              ' -config=' + directory + '/listener.hcl\nReadWritePaths=' + directory + '\n')
    def restart():
        run(*inside, "systemctl", "daemon-reload")
        run(*inside, "systemctl", "stop", "openbao")
        run("systemctl", "start", "polarita-openbao-start.service")
        for _ in range(45):
            try:
                if p.request("GET", "sys/health")["sealed"] is False:
                    return
            except OSError:
                pass
            time.sleep(1)
        raise RuntimeError("Trezor nedokončil start")
    try:
        run("incus", "file", "push", "--mode=0644", "-", "openbao-test" + directory + "/listener.hcl", data=conf.encode())
        run("incus", "file", "push", "--mode=0644", "-", "openbao-test" + override, data=dropin.encode())
        restart()
        sock = directory + "/sprava.sock"
        run(*inside, "test", "-S", sock)
        run(*inside, "chmod", "0600", sock)
        if run(*inside, "stat", "-c", "%a %U", sock).strip() != b"600 openbao":
            raise RuntimeError("Chybná oprávnění místního socketu")
        def call(method, path, body):
            args = ["curl", "--fail", "--silent", "--show-error", "--max-time", "20", "--unix-socket", sock,
                    "-X", method, "-H", "Content-Type: application/json"]
            if body is not None:
                args.extend(["--data-binary", "@-"])
            raw = run(*inside, *args, "http://localhost/v1/sys/generate-root/" + path,
                      data=b"" if body is None else json.dumps(body).encode())
            return json.loads(raw) if raw else {}
        yield call
    finally:
        run(*inside, "rm", "-f", override)
        restart()
        run(*inside, "rm", "-f", directory + "/listener.hcl", directory + "/sprava.sock")


def main():
    if run("hostname", "-s").strip() != b"polarita-hq":
        sys.exit("Migrace patří do firemní VM")
    if not (p.VAULT / "inicializovano").exists():
        return 0
    if (p.WORK / "uzamceno").exists():
        raise RuntimeError("Trezor byl úmyslně uzamčen")
    p.HTTP = p.build_opener(p.ProxyHandler({}), p.HTTPSHandler(context=ssl.create_default_context(cafile=str(p.WORK / "ca.crt"))))
    manager = p.login(p.recover("bao-sprava"))
    try:
        def authenticated(method, path, body):
            out = p.request(method, "sys/generate-root-token/" + path, body, manager)
            return out.get("data", out)
        try:
            authenticated("GET", "attempt", None)
            modern = True
        except HTTPError as err:
            if err.code != 403:
                raise
            modern = False
        if modern:
            for role in p.FIXTURES:
                try:
                    p.request("GET", "auth/approle/role/" + role + "/role-id", token=manager)
                except HTTPError as err:
                    if err.code not in (403, 404):
                        raise
                    break
            else:
                role = p.login(p.credentials("keycloak-test", manager))
                try:
                    try:
                        p.request("GET", "test/data/databaze/keycloak", token=role)
                    except HTTPError as err:
                        if err.code == 404:
                            return 0
                        if err.code != 403:
                            raise
                    else:
                        return 0
                finally:
                    p.request("POST", "auth/token/revoke-self", {}, role)
        if "--kontrola" in sys.argv:
            return 42
        shares = json.load(sys.stdin)
        with (nullcontext(authenticated) if modern else local_recovery()) as api:
            token = quorum(api, shares)
            try:
                p.configure(token)
            finally:
                p.request("POST", "auth/token/revoke-self", {}, token)
            p.expect_forbidden("GET", "auth/token/lookup-self", token)
        authenticated("GET", "attempt", None)
        print("Správce aktualizoval politiky s kvórem tří podílů. Dočasný root token byl zneplatněn.")
        return 0
    finally:
        p.request("POST", "auth/token/revoke-self", {}, manager)


if __name__ == "__main__":
    with (p.WORK / ".pristupy-lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        sys.exit(main())
