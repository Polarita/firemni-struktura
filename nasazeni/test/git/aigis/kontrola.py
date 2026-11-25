"""Autoritativní kontrola runneru; čte strojové nálezy nativního AigisCode."""
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jazyky import over


def check(root, output):
    binary = Path(__file__).resolve().with_name("aigiscode")
    env = {"PATH":"/usr/bin:/bin", "HOME":str(output), "RAYON_NUM_THREADS":"1", "LANG":"C.UTF-8"}
    def analyze(tree, target):
        result = subprocess.run([binary,"analyze",tree,"--output-dir",target],env=env,stderr=subprocess.PIPE,text=True,timeout=900)
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        report = json.loads((target/"deterministic-findings.json").read_bytes())
        guard = json.loads((target/"guard-decision.json").read_bytes())
        if (Path(report["root"]).resolve() != tree or Path(guard["root"]).resolve() != tree
                or report["analyzed_files"] <= 0 or guard["verdict"] not in {"Allow","Warn","Block"}):
            raise ValueError("Výsledek nepatří analyzovanému zdroji nebo chybí pokrytí")
        return result, report, guard

    result, report, guard = analyze(root, output)
    reports = [report]
    if result.returncode:
        expected = ["native input coverage is incomplete; see input_coverage and semantic-graph.json parse_outcomes"]
        reasons = [("semantic_graph.parse_outcomes", "summary.input_coverage")]
        orphan = report["dead_code"]["backend_orphan_coverage"]
        if orphan["status"] == "deferred_input_coverage" and orphan["gap_count"] == 0:
            expected.append("Backend orphan analysis is deferred because native input coverage is incomplete.")
            reasons.append(("dead_code.backend_orphan_coverage",))
        blocks = [tuple(sorted(item["provenance"])) for item in guard["triggers"] if item["level"] == "Block"]
        if result.returncode != 1 or result.stderr.splitlines() != expected or sorted(blocks) != sorted(reasons):
            raise RuntimeError("Úplná kontrola neuspěla také mimo evidenci nepodporovaných jazyků")
        coverage = report["input_coverage"]
        if (coverage["status"] != "incomplete" or not coverage["unsupported_source_files"]
                or coverage["supported_source_files"] != coverage["parsed_source_files"]
                or any(coverage[k] for k in ("recovered_source_files","scope_limited_files",
                                            "files_without_parse_evidence","diagnostic_count"))):
            raise RuntimeError("AigisCode nezpracoval všechny podporované zdroje")
        graph = json.loads((output/"semantic-graph.json").read_bytes())
        unsupported = graph["unsupported_sources"]
        excluded = {root / item["file_path"] for item in unsupported}
        if len(excluded) != coverage["unsupported_source_files"]:
            raise RuntimeError("Chybí úplný seznam ostatních zdrojů")
        over(root, unsupported, output)
        projection = output.parent / "nativni-zdroje"
        def ignored(directory, names):
            return [n for n in names if n == ".git" or Path(directory)/n in excluded]
        shutil.copytree(root, projection, symlinks=True, ignore=ignored)
        target = output.parent/"nativni-vysledky"
        target.mkdir()
        result, report, guard = analyze(projection, target)
        reports.append(report)
        if orphan["status"] == "deferred_input_coverage":
            completed = report["dead_code"]["backend_orphan_coverage"]
            if completed["status"] != "complete" or completed["gap_count"]:
                raise RuntimeError("Opakovaná analýza nedokončila kontrolu osiřelých backendových souborů")
        second = json.loads((target/"semantic-graph.json").read_bytes())
        if graph["files"] != second["files"]:
            raise RuntimeError("Opakovaná analýza změnila seznam podporovaných zdrojů")
    if result.returncode or report["input_coverage"]["status"] != "complete":
        raise RuntimeError("Nativní analýza podporovaných jazyků nedoložila úplné pokrytí")
    cycles = {tuple(paths) for scan in reports for paths in scan["graph_analysis"]["strong_circular_dependencies"]}
    dead = [item for scan in reports for item in scan["dead_code"]["findings"]]
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
