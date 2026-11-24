"""Jedno potvrzení příjmu přes privátní socket v PostgreSQL instanci."""
import json
import re
import subprocess
import sys
from uuid import UUID

def registruj(data):
    case, key, sha, size = (data[k] for k in ("spis", "id", "sha256", "bajtu"))
    if (not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}", case) or str(UUID(key)) != key
            or not re.fullmatch(r"[0-9a-f]{64}", sha) or type(size) is not int or not 0 < size <= 64*1024**2):
        raise ValueError("Neplatné údaje")
    result = subprocess.run(["psql", "-XqAtw", "-d", "db_erp_lhutnik", "-v", "ON_ERROR_STOP=1",
            "-v", "kod="+case, "-v", "id="+key, "-v", "sha="+sha, "-v", "bajtu="+str(size)],
        input="SELECT polarita_test_spisy.prijmi_sanon(:'kod',:'id'::uuid,:'sha',:'bajtu'::integer);",
        capture_output=True, check=True, text=True, timeout=60)
    return json.loads(result.stdout)

if __name__ == "__main__":
    raw = sys.stdin.buffer.readline(513)
    if len(raw) > 512 or not raw.endswith(b"\n"):
        raise ValueError("Překročen limit požadavku")
    print(json.dumps(registruj(json.loads(raw))), flush=True)
