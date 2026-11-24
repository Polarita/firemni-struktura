"""Autoritativní kontrola runneru; čte strojové nálezy nativního AigisCode."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def check(root, output):
    binary = Path(__file__).resolve().with_name("aigiscode")
    env = {"PATH":"/usr/bin:/bin", "HOME":str(output), "RAYON_NUM_THREADS":"1", "LANG":"C.UTF-8"}
    subprocess.run([binary,"analyze",root,"--output-dir",output],check=True,env=env,timeout=900)
    report = json.loads((output/"deterministic-findings.json").read_text())
    guard = json.loads((output/"guard-decision.json").read_text())
    if (Path(report["root"]).resolve() != root or Path(guard["root"]).resolve() != root
            or report["analyzed_files"] <= 0 or guard["verdict"] not in {"Allow","Warn","Block"}):
        raise ValueError("Výsledek nepatří analyzovanému zdroji nebo chybí pokrytí")
    cycles = report["graph_analysis"]["strong_circular_dependencies"]
    dead = report["dead_code"]["findings"]
    if any(item["proof_tier"] not in {"Certain", "Strong", "Heuristic"} for item in dead):
        raise ValueError("Neznámá síla důkazu AigisCode")
    certain = [item for item in dead if item["proof_tier"] == "Certain"]
    print(f'AigisCode prověřil {report["analyzed_files"]} souborů, verdikt {guard["verdict"]}.', flush=True)
    for paths in cycles:
        print("Silný cyklus:", ", ".join(paths), file=sys.stderr)
    for item in certain:
        print("Prokázaný mrtvý kód:", item["file_path"], item["name"], file=sys.stderr)
    if guard["verdict"] == "Block":
        print("Architektonická brána:", guard["summary"], file=sys.stderr)
    return not (cycles or certain or guard["verdict"] == "Block")


if __name__ == "__main__":
    root = Path(sys.argv[1]).resolve(strict=True)
    with tempfile.TemporaryDirectory(dir=os.environ.get("POLARITA_CI_WORK")) as parent:
        output = Path(parent)/"vysledky"
        output.mkdir()
        sys.exit(0 if check(root,output) else 1)
