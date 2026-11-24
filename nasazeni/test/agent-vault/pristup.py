"""Strojové SCRAM přístupy pro čtení a tvorbu indexu, pouze z účtu instalačního správce."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"databaze"))
from vytvoreni import verifier

def main():
    private = Path("/srv/polarita/data/bootstrap-test/agent-vault")
    private.mkdir(mode=0o700,exist_ok=True)
    if subprocess.check_output(["findmnt","-no","SOURCE","-T",private],text=True).strip()!="polarita_zfs/data/bootstrap-test":
        raise RuntimeError("Chybí šifrované úložiště strojových účtů")
    psql = ["incus","exec","-T","postgres-test","--","runuser","-u","postgres","--","psql","-XqAt",
            "-v","ON_ERROR_STOP=1","-d","db_erp_lhutnik"]
    for access in ("read","index"):
        path = private/access
        if not path.exists():
            with tempfile.NamedTemporaryFile(dir=private,delete=False) as f:
                f.write(secrets.token_hex(32).encode())
                f.flush()
                os.fsync(f.fileno())
            os.replace(f.name,path)
        if path.is_symlink() or path.stat().st_uid!=0 or path.stat().st_mode & 0o777 != 0o600:
            raise RuntimeError("Neplatná oprávnění strojového klíče")
        role = "pol_vault_"+access
        current = subprocess.check_output(psql,input=f"SELECT rolpassword FROM pg_authid WHERE rolname='{role}'",
                                          text=True).strip()
        expected = verifier(path.read_bytes(),current)
        if current!=expected:
            op = subprocess.run(psql,input=f"ALTER ROLE {role} PASSWORD '{expected}';",text=True,capture_output=True)
            if op.returncode:
                raise RuntimeError("PostgreSQL nenastavil strojové ověření")
if __name__=="__main__":
    main()
