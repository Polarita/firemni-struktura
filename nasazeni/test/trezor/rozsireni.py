"""Předá tři obnovovací podíly pouze při aktualizaci již inicializovaného TEST trezoru."""
import json
from pathlib import Path
import subprocess
import sys

if subprocess.check_output(["hostname", "-s"]).strip() != b"ejpovice":
    sys.exit("Testovací úschova patří na Ejpovice")
guest = ["incus", "exec", "-T", "--project", "polarita", "polarita-hq", "--"]
runner = guest + ["python3", sys.argv[1] + "/role.py"]
status = subprocess.run(runner + ["--kontrola"], check=False).returncode
if status != 42:
    sys.exit(status)
directory = Path("/etc/polarita-test-obnova")
envelope = subprocess.check_output(guest + ["cat", "/srv/polarita/data/bootstrap-test/openbao-test/obnova-podily.cms"])
shares = json.loads(subprocess.run(
    ["openssl", "cms", "-decrypt", "-binary", "-inform", "DER", "-recip", str(directory / "test.crt"),
     "-inkey", str(directory / "test.key")], input=envelope, capture_output=True, check=True).stdout)
if shares["threshold"] != 3 or len(set(shares["shares"])) != 5:
    sys.exit("Chybí testovací podíly pro obnovu")
subprocess.run(runner, input=json.dumps(shares["shares"][:3]).encode(), check=True)
