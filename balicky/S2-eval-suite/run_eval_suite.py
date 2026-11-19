# -*- coding: utf-8 -*-
"""
Deterministic evaluator of the Polarita Eval Suite 100+ (package S2, Version 2.8).
Deterministický hodnotitel sady Eval Suite 100+ Polarita (balíček S2, Verze 2.8).

EN: Runs every scenario of eval_suite_polarita_extended.json either against the built-in
    reference policy (dry-run, no network, no paid services) or against a live gateway
    endpoint of paperclip-orchestrator (live). Writes a JSON + Markdown audit protocol,
    appends the run to history.jsonl and regenerates the web trend report trend.html.
    Exit code 0 is returned only for a 100 % VERIFIED_PASS score.
CZ: Spustí každý scénář z eval_suite_polarita_extended.json buď proti vestavěné referenční
    politice (dry-run, bez sítě, bez placených služeb), nebo proti živému gateway endpointu
    paperclip-orchestrator (live). Zapíše JSON + Markdown auditní protokol, připíše běh do
    history.jsonl a přegeneruje webový trendový report trend.html.
    Návratový kód 0 se vrací pouze při skóre 100 % VERIFIED_PASS.

Usage / Použití:
    python run_eval_suite.py                                  # dry-run, all scenarios / všechny scénáře
    python run_eval_suite.py --suite base                     # only the 20 base traps / jen 20 základních chytáků
    python run_eval_suite.py --mode live --endpoint https://decisions.int.polarita.cz/eval/decide

Exit codes / Návratové kódy: 0 = 100 % VERIFIED_PASS, 1 = at least one FAIL, 2 = invalid dataset or usage.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import audio_fixtures
import reference_policy

HERE = Path(__file__).resolve().parent
DEFAULT_DATASET = HERE / "eval_suite_polarita_extended.json"
DEFAULT_OUTPUT = HERE / "output"
TOKEN_ENV = "POLARITA_EVAL_TOKEN"  # bearer token for live mode; never printed / token pro live režim; nikdy se nevypisuje

REQUIRED_SCENARIO_KEYS = ("id", "suite", "category", "title", "agent", "channel", "event", "expected", "legal_basis")
REQUIRED_EXPECTED_KEYS = ("decision", "reason_code", "required_actions", "forbidden_actions")


class DatasetError(ValueError):
    """Invalid dataset. / Neplatná datová sada."""


def load_dataset(path: Path) -> dict[str, Any]:
    """
    EN: Load and validate the dataset structure (ids, counts, vocabulary).
    CZ: Načte datovou sadu a ověří její strukturu (id, počty, slovník rozhodnutí).
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DatasetError(f"cannot read dataset {path}: {error}") from error
    scenarios = document.get("scenarios")
    meta = document.get("meta", {})
    if not isinstance(scenarios, list) or not scenarios:
        raise DatasetError("dataset has no scenarios")
    seen: set[str] = set()
    for scenario in scenarios:
        for key in REQUIRED_SCENARIO_KEYS:
            if key not in scenario:
                raise DatasetError(f"scenario {scenario.get('id', '?')} misses key {key}")
        if scenario["id"] in seen:
            raise DatasetError(f"duplicate scenario id {scenario['id']}")
        seen.add(scenario["id"])
        for key in REQUIRED_EXPECTED_KEYS:
            if key not in scenario["expected"]:
                raise DatasetError(f"scenario {scenario['id']} misses expected.{key}")
        if scenario["expected"]["decision"] not in reference_policy.DECISIONS:
            raise DatasetError(f"scenario {scenario['id']} has unknown decision")
        if scenario["suite"] not in ("base", "extended"):
            raise DatasetError(f"scenario {scenario['id']} has unknown suite")
    base_count = sum(1 for scenario in scenarios if scenario["suite"] == "base")
    if base_count != 20:
        raise DatasetError(f"base suite must have 20 scenarios, found {base_count}")
    if meta.get("scenario_count") != len(scenarios):
        raise DatasetError("meta.scenario_count does not match the number of scenarios")
    if len(scenarios) < 100:
        raise DatasetError("extended suite must have at least 100 scenarios")
    return document


def decide_dry_run(scenario: dict[str, Any]) -> dict[str, Any]:
    """Reference policy answer. / Odpověď referenční politiky."""
    return reference_policy.decide(scenario["event"])


def validate_live_endpoint(endpoint: str) -> None:
    """Reject non-HTTPS (except localhost) and production Polarita endpoints in live mode."""
    parsed = urllib.parse.urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("live endpoint has no hostname")
    if parsed.scheme == "http":
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("live endpoint must use https:// (http allowed only for localhost)")
    elif parsed.scheme != "https":
        raise ValueError("live endpoint must use https://")
    if (host in ("polarita.cz", "polarita.eu") or host.endswith((".polarita.cz", ".polarita.eu"))) and not any(
        tag in host for tag in ("test", "staging", "sandbox", "dev", "eval", "int.")
    ):
        raise ValueError(f"refusing live run against production host: {host}")


def decide_live(scenario: dict[str, Any], endpoint: str, timeout: float) -> dict[str, Any]:
    """
    EN: Ask the live gateway. Contract: POST JSON {scenario_id, agent, channel, event, transcript_mock}
        -> JSON {decision, reason_code, actions}. Any transport or format error counts as FAIL.
    CZ: Dotáže se živého gateway. Kontrakt: POST JSON {scenario_id, agent, channel, event, transcript_mock}
        -> JSON {decision, reason_code, actions}. Chyba přenosu či formátu se počítá jako FAIL.
    """
    try:
        validate_live_endpoint(endpoint)
    except ValueError:
        return {"decision": "FORMAT_ERROR", "reason_code": "ENDPOINT_BLOCKED", "actions": []}
    payload = json.dumps({
        "scenario_id": scenario["id"],
        "agent": scenario["agent"],
        "channel": scenario["channel"],
        "event": scenario["event"],
        "transcript_mock": scenario.get("transcript_mock"),
    }, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    token = os.environ.get(TOKEN_ENV)
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            answer = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
        return {"decision": "TRANSPORT_ERROR", "reason_code": type(error).__name__, "actions": []}
    if not isinstance(answer, dict):
        return {"decision": "FORMAT_ERROR", "reason_code": "NOT_AN_OBJECT", "actions": []}
    raw_actions = answer.get("actions", [])
    if not isinstance(raw_actions, list):
        return {"decision": "FORMAT_ERROR", "reason_code": "INVALID_ACTIONS_TYPE", "actions": []}
    return {
        "decision": str(answer.get("decision", "")),
        "reason_code": str(answer.get("reason_code", "")),
        "actions": [str(item) for item in raw_actions if isinstance(item, (str, int))],
    }


def check_audio(scenario: dict[str, Any], audio_root: Path) -> list[str]:
    """
    EN: Generate (if missing) and verify the synthetic stereo fixture of a scenario.
    CZ: Vygeneruje (pokud chybí) a ověří syntetickou stereo maketu scénáře.
    """
    spec = scenario.get("audio")
    if not spec:
        return []
    problems: list[str] = []
    path = audio_root / spec["file"]
    if not path.exists():
        audio_fixtures.generate(path, spec["seconds"], spec["left"], spec["right"])
    info = audio_fixtures.inspect(path)
    if info["channels"] != 2:
        problems.append("audio is not stereo")
    if abs(info["seconds"] - spec["seconds"]) > 0.05:
        problems.append("audio duration mismatch")
    expected_level = spec.get("expected_left_urgency")
    if expected_level and audio_fixtures.urgency_level(path, "L") != expected_level:
        problems.append("Channel L urgency differs from the expected level")
    try:
        audio_fixtures.urgency_features(path, "R")
        problems.append("Channel R analysis was not refused")
    except audio_fixtures.ChannelRProhibitedError:
        pass
    return problems


def evaluate(scenario: dict[str, Any], answer: dict[str, Any], audio_problems: list[str]) -> dict[str, Any]:
    """
    EN: Compare the answer with the expected result. All four conditions must hold.
    CZ: Porovná odpověď s očekávaným výsledkem. Musí platit všechny čtyři podmínky.
    """
    expected = scenario["expected"]
    actions = set(answer.get("actions", []))
    failures: list[str] = []
    if answer.get("decision") != expected["decision"]:
        failures.append(f"decision {answer.get('decision')} != {expected['decision']}")
    if answer.get("reason_code") != expected["reason_code"]:
        failures.append(f"reason_code {answer.get('reason_code')} != {expected['reason_code']}")
    missing = [item for item in expected["required_actions"] if item not in actions]
    if missing:
        failures.append("missing required actions: " + ", ".join(missing))
    forbidden = [item for item in expected["forbidden_actions"] if item in actions]
    if forbidden:
        failures.append("forbidden actions executed: " + ", ".join(forbidden))
    failures.extend(audio_problems)
    return {
        "id": scenario["id"],
        "suite": scenario["suite"],
        "category": scenario["category"],
        "title": scenario["title"],
        "agent": scenario["agent"],
        "expected": {"decision": expected["decision"], "reason_code": expected["reason_code"]},
        "actual": {"decision": answer.get("decision"), "reason_code": answer.get("reason_code"), "actions": sorted(actions)},
        "verdict": "VERIFIED_PASS" if not failures else "FAIL",
        "failures": failures,
    }


def run(dataset: dict[str, Any], mode: str, suite: str, endpoint: str | None, timeout: float,
        audio_root: Path | None) -> dict[str, Any]:
    """Run the selected scenarios and build the report. / Spustí vybrané scénáře a sestaví report."""
    scenarios = [s for s in dataset["scenarios"] if suite == "all" or s["suite"] == suite]
    results = []
    for scenario in scenarios:
        answer = decide_dry_run(scenario) if mode == "dry-run" else decide_live(scenario, endpoint or "", timeout)
        audio_problems = check_audio(scenario, audio_root) if audio_root is not None else []
        results.append(evaluate(scenario, answer, audio_problems))
    passed = sum(1 for result in results if result["verdict"] == "VERIFIED_PASS")
    total = len(results)
    categories: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = categories.setdefault(result["category"], {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += 1 if result["verdict"] == "VERIFIED_PASS" else 0
    return {
        "suite_name": dataset["meta"].get("name"),
        "suite_version": dataset["meta"].get("version"),
        "mode": mode,
        "suite": suite,
        "endpoint": endpoint if mode == "live" else None,
        "started_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "score_pct": round(100.0 * passed / total, 2) if total else 0.0,
        "verdict": "VERIFIED_PASS" if total and passed == total else "FAIL",
        "audio_checked": audio_root is not None,
        "categories": categories,
        "results": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Markdown audit protocol for 17004 klicnik and 17005 ai-provoz. / Markdown auditní protokol."""
    lines = [
        f"# Auditní protokol Eval Suite — {report['verdict']}",
        "",
        f"- Sada: `{report['suite_name']}` verze `{report['suite_version']}` (výběr: `{report['suite']}`)",
        f"- Režim: `{report['mode']}`" + (f" · endpoint `{report['endpoint']}`" if report["endpoint"] else ""),
        f"- Čas běhu (UTC): `{report['started_utc']}`",
        f"- Výsledek: **{report['passed']} / {report['total']}** (`{report['score_pct']} %`) · zvukové makety ověřeny: `{'ano' if report['audio_checked'] else 'ne'}`",
        "- Určeno pro: `17004 klicnik`, `17005 ai-provoz`",
        "",
        "## Výsledky podle kategorií",
        "",
        "| Kategorie | Prošlo | Celkem |",
        "| :--- | ---: | ---: |",
    ]
    for name in sorted(report["categories"]):
        bucket = report["categories"][name]
        lines.append(f"| `{name}` | {bucket['passed']} | {bucket['total']} |")
    failed = [result for result in report["results"] if result["verdict"] != "VERIFIED_PASS"]
    lines += ["", "## Neúspěšné scénáře", ""]
    if not failed:
        lines.append("Žádné — všechny scénáře mají verdikt `VERIFIED_PASS`.")
    for result in failed:
        lines.append(f"- **{result['id']}** ({result['agent']}) — {result['title']}: " + "; ".join(result["failures"]))
    lines.append("")
    return "\n".join(lines)


def render_trend(history: list[dict[str, Any]], latest: dict[str, Any]) -> str:
    """
    EN: Self-contained HTML trend report (inline SVG, no external resources).
    CZ: Samostatný HTML trendový report (vložené SVG, žádné externí zdroje).
    """
    runs = history[-60:]
    width, height, pad = 860, 220, 36
    points = []
    for index, item in enumerate(runs):
        x = pad + (width - 2 * pad) * (index / max(1, len(runs) - 1))
        y = height - pad - (height - 2 * pad) * (item["score_pct"] / 100.0)
        points.append((x, y, item))
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points)
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{"#0b6b49" if item["verdict"] == "VERIFIED_PASS" else "#a9420b"}">'
        f'<title>{html.escape(str(item["started_utc"]))} · {html.escape(str(item["mode"]))} · {item["passed"]}/{item["total"]}</title></circle>'
        for x, y, item in points)
    rows = "".join(
        f"<tr><td>{html.escape(str(item['started_utc']))}</td><td>{html.escape(str(item['mode']))}</td><td>{html.escape(str(item['suite']))}</td>"
        f"<td class='num'>{item['passed']} / {item['total']}</td><td class='num'>{item['score_pct']} %</td>"
        f"<td class='{'ok' if item['verdict'] == 'VERIFIED_PASS' else 'bad'}'>{html.escape(str(item['verdict']))}</td></tr>"
        for item in reversed(runs))
    category_rows = "".join(
        f"<tr><td><code>{html.escape(name)}</code></td><td class='num'>{bucket['passed']}</td><td class='num'>{bucket['total']}</td></tr>"
        for name, bucket in sorted(latest["categories"].items()))
    failed_rows = "".join(
        f"<tr><td>{html.escape(result['id'])}</td><td>{html.escape(result['agent'])}</td><td>{html.escape(result['title'])}</td>"
        f"<td>{html.escape('; '.join(result['failures']))}</td></tr>"
        for result in latest["results"] if result["verdict"] != "VERIFIED_PASS")
    failed_block = (f"<table><thead><tr><th>ID</th><th>ai</th><th>Scénář</th><th>Důvod</th></tr></thead><tbody>{failed_rows}</tbody></table>"
                    if failed_rows else "<p>Žádné — poslední běh má verdikt <strong>VERIFIED_PASS</strong> u všech scénářů.</p>")
    return f"""<!DOCTYPE html>
<html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eval Suite Polarita — trend</title>
<style>
:root {{ --bg:#f4f7fa; --fg:#102c41; --muted:#465d6d; --card:#fff; --line:#cfdce4; --ok:#0b6b49; --bad:#a9420b; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0f1b24; --fg:#e6eef3; --muted:#9db1bf; --card:#172733; --line:#2b4252; --ok:#4ccf9a; --bad:#ff9a66; }} }}
body {{ background:var(--bg); color:var(--fg); font-family:"Segoe UI",Roboto,Arial,sans-serif; margin:0; padding:16px; }}
main {{ max-width:920px; margin:0 auto; }}
h1 {{ font-size:1.4rem; margin:0 0 4px; }} h2 {{ font-size:1.05rem; margin:24px 0 8px; }}
p.sub {{ color:var(--muted); margin:0 0 16px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px; overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; font-size:.9rem; }} th,td {{ text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); }}
td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; }} td.ok {{ color:var(--ok); font-weight:700; }} td.bad {{ color:var(--bad); font-weight:700; }}
svg {{ width:100%; height:auto; }} .axis {{ stroke:var(--line); }} .trend {{ fill:none; stroke:var(--fg); stroke-width:2; }} text {{ fill:var(--muted); font-size:11px; }}
</style></head><body><main>
<h1>Eval Suite Polarita — trendový report</h1>
<p class="sub">Sada <code>{html.escape(str(latest['suite_name']))}</code> verze {html.escape(str(latest['suite_version']))} · poslední běh {html.escape(str(latest['started_utc']))} · režim {html.escape(str(latest['mode']))} · <strong>{latest['passed']} / {latest['total']} ({latest['score_pct']} %)</strong> · {html.escape(str(latest['verdict']))}</p>
<div class="card"><svg viewBox="0 0 {width} {height}" role="img" aria-label="Vývoj úspěšnosti v čase">
<line class="axis" x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}"/><line class="axis" x1="{pad}" y1="{pad}" x2="{pad}" y2="{height - pad}"/>
<line class="axis" stroke-dasharray="4 4" x1="{pad}" y1="{pad}" x2="{width - pad}" y2="{pad}"/>
<text x="4" y="{pad + 4}">100 %</text><text x="12" y="{height - pad + 4}">0 %</text>
<polyline class="trend" points="{polyline}"/>{dots}</svg></div>
<h2>Poslední běh podle kategorií</h2>
<div class="card"><table><thead><tr><th>Kategorie</th><th class="num">Prošlo</th><th class="num">Celkem</th></tr></thead><tbody>{category_rows}</tbody></table></div>
<h2>Neúspěšné scénáře posledního běhu</h2>
<div class="card">{failed_block}</div>
<h2>Historie běhů (nejnovější nahoře)</h2>
<div class="card"><table><thead><tr><th>Čas (UTC)</th><th>Režim</th><th>Výběr</th><th class="num">Prošlo</th><th class="num">Skóre</th><th>Verdikt</th></tr></thead><tbody>{rows}</tbody></table></div>
</main></body></html>
"""


def _load_history(history_path: Path) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for lineno, line in enumerate(history_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if isinstance(entry, dict) and "score_pct" in entry:
                history.append(entry)
        except json.JSONDecodeError:
            print(f"warning: skipping malformed history line {lineno} in {history_path}", file=sys.stderr)
    return history


def write_outputs(report: dict[str, Any], out_dir: Path, keep_history: bool) -> dict[str, Path]:
    """Write report files and the trend page. / Zapíše soubory reportu a trendovou stránku."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-%fZ")
    stem = f"eval-report-{report['mode']}-{stamp}"
    suffix = 0
    while (out_dir / f"{stem}.json").exists() or (out_dir / f"{stem}.md").exists():
        suffix += 1
        stem = f"eval-report-{report['mode']}-{stamp}-{suffix}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    written = {"json": json_path, "markdown": md_path}
    if keep_history:
        history_path = out_dir / "history.jsonl"
        summary = {key: report[key] for key in ("started_utc", "mode", "suite", "total", "passed", "failed", "score_pct", "verdict")}
        with history_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(summary, ensure_ascii=False) + "\n")
        history = _load_history(history_path)
        trend_path = out_dir / "trend.html"
        trend_path.write_text(render_trend(history, report), encoding="utf-8", newline="\n")
        written["history"] = history_path
        written["trend"] = trend_path
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Polarita Eval Suite 100+ runner (package S2)")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--mode", choices=("dry-run", "live"), default="dry-run")
    parser.add_argument("--endpoint", help="live gateway URL of paperclip-orchestrator (required for --mode live)")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--suite", choices=("all", "base", "extended"), default="all")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audio-dir", type=Path, default=HERE, help="root for generated audio fixtures")
    parser.add_argument("--no-audio", action="store_true", help="skip synthetic audio checks")
    parser.add_argument("--no-history", action="store_true", help="do not append history.jsonl / trend.html")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # UTF-8 console output on Windows / UTF-8 výstup konzole na Windows
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if args.mode == "live":
        if not args.endpoint:
            print("error: --endpoint is required for --mode live", file=sys.stderr)
            return 2
        try:
            validate_live_endpoint(args.endpoint)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
    try:
        dataset = load_dataset(args.dataset)
    except DatasetError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    report = run(dataset, args.mode, args.suite, args.endpoint, args.timeout, None if args.no_audio else args.audio_dir)
    written = write_outputs(report, args.out_dir, not args.no_history)
    print(f"{report['verdict']}: {report['passed']}/{report['total']} ({report['score_pct']} %) · mode={report['mode']} · suite={report['suite']}")
    for result in report["results"]:
        if result["verdict"] != "VERIFIED_PASS":
            print(f"  FAIL {result['id']} {result['title']}: {'; '.join(result['failures'])}")
    for label, path in written.items():
        print(f"  {label}: {path}")
    return 0 if report["verdict"] == "VERIFIED_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
