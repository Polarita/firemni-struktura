"""Ověří pečeť službou pod jejím účtem a validaci jako odlišný uživatel bez soukromé identity."""
import base64
import hashlib
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile

VM = "pecet-test"
python = "/opt/polarita-pecet/bin/python"
script = "/opt/polarita-pecet/dokument.py"


def command(uid):
    return ["incus", "exec", "-T", VM, "--user", str(uid), "--group", str(uid), "--", python, script]


def call(uid, *args, data=b""):
    return subprocess.run([*command(uid), *args], input=data, capture_output=True, check=True, timeout=40).stdout


def main():
    if subprocess.check_output(["hostname", "-s"]).strip() != b"polarita-hq":
        raise SystemExit("Zkouška patří do firemní VM")
    if subprocess.check_output(["incus", "exec", "-T", VM, "--", "findmnt", "-n", "-o", "FSTYPE",
                                "-T", "/run/secrets/pecet-test"]).strip() != b"tmpfs":
        raise RuntimeError("Identita musí pocházet z tmpfs")
    os.umask(0o077)
    output = Path("/srv/polarita/workspace/dukazy/blok-04/pecet")
    output.mkdir(parents=True, exist_ok=True)
    sample = call(65533, "--vzor", "predavaci-protokol")
    ca = call(65534, "--verejny-koren").decode().strip()
    for kind in ("contract", "revizni-zprava", "podpis-deniku", "neznamy"):
        r = subprocess.run([*command(65534), "--pecet", kind], input=sample, capture_output=True)
        if r.returncode != 1 or r.stdout or r.stderr.strip() != b"SEAL_NOT_A_PERSONAL_SIGNATURE":
            raise RuntimeError("Chybné odmítnutí " + kind)
    verified = set()
    for kind in ("predavaci-protokol", "seznameni-monitoring", "archivni-kopie-deniku"):
        pdf = call(65534, "--pecet", kind, data=call(65533, "--vzor", kind))
        encoded = base64.b64encode(pdf).decode()
        call(65533, "--overit", data=json.dumps({"pdf": encoded, "ca": ca}).encode())
        with tempfile.NamedTemporaryFile(dir=output, delete=False) as f:
            f.write(pdf)
        os.replace(f.name, output / (kind + ".pdf"))
        print("Ověřena testovací organizační pečeť a místní časové razítko pro " + kind)
        verified.add(hashlib.sha256(pdf).hexdigest() + " " + kind + ".pdf")
    # Historie znalostního Gitu může obsahovat dřívější ověřené otisky stejného vzoru.
    config = Path("/etc/polarita")
    config.mkdir(exist_ok=True)
    listing = config/"znalostni-test-pecete"
    with (config/".znalostni-pecete.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if listing.exists():
            verified.update(listing.read_text().splitlines())
        pending = listing.with_suffix(".next")
        pending.write_text("\n".join(sorted(verified))+"\n")
        pending.chmod(0o644)
        os.replace(pending, listing)
    remote = "reditelstvi-test/usr/local/share/predavaci-protokol-test.pdf.next"
    subprocess.run(["incus", "file", "push", "--mode", "0644", output / "predavaci-protokol.pdf", remote], check=True)
    subprocess.run(["incus", "exec", "-T", "reditelstvi-test", "--", "mv",
                    "/usr/local/share/predavaci-protokol-test.pdf.next", "/usr/local/share/predavaci-protokol-test.pdf"], check=True)
    print("Smlouva, revizní zpráva, osobní podpis deníku a neznámá třída byly odmítnuty.")


if __name__ == "__main__":
    main()
