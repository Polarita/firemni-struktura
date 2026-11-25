# -*- coding: utf-8 -*-
"""
Unit and integration tests of the Polarita Eval Suite runner (package S2, Version 3.23).
Jednotkové a integrační testy runneru Eval Suite Polarita (balíček S2, Verze 3.23).

Usage / Použití:  python -m unittest -v test_eval_suite
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import os
import tempfile
import threading
import unittest
from unittest import mock
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import audio_fixtures
import build_dataset
import reference_policy
import run_eval_suite

HERE = Path(__file__).resolve().parent
DATASET = HERE / "eval_suite_polarita_extended.json"


class _ToolStub:
    """Record calls at the point where the gateway invokes the simulated tool."""

    def __init__(self, path: Path):
        self.path = path

    def execute(self, run_id: str, scenario_id: str, action: str) -> None:
        entry = {"run_id": run_id, "scenario_id": scenario_id, "action": action, "tool": "stub"}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")


class _GatewayStub(BaseHTTPRequestHandler):
    """
    EN: Local stand-in for the paperclip-orchestrator gateway (answers with the reference policy,
        or always ALLOW when the server is created with always_allow=True).
    CZ: Lokální náhrada gateway paperclip-orchestrator (odpovídá referenční politikou,
        nebo vždy ALLOW, je-li server vytvořen s always_allow=True).
    """

    def do_POST(self) -> None:  # noqa: N802 (http.server API)
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
        if self.server.always_allow:  # type: ignore[attr-defined]
            answer = {"decision": "ALLOW", "reason_code": "STUB", "actions": ["execute_requested_action"]}
        else:
            answer = reference_policy.decide(body["event"])
        # EN: Stand-in for the tool layer: it writes every executed call, with the run_id it received,
        #     into its own log. "tamper" lets a test make the log differ from what the gateway reports.
        # CZ: Maketa nástrojové vrstvy: každé provedené volání zapíše s obdrženým run_id do vlastního
        #     záznamu. "tamper" dovolí testu, aby se záznam lišil od toho, co brána hlásí.
        tool_log = getattr(self.server, "tool_log", None)
        if tool_log is not None:
            entries = [{"run_id": body.get("run_id"), "scenario_id": body["scenario_id"], "action": action, "tool": "stub"}
                       for action in answer["actions"]]
            tamper = getattr(self.server, "tamper", None)
            if tamper is not None:
                entries = tamper(entries, body)
            tool = _ToolStub(tool_log)
            for call in entries:
                tool.execute(call["run_id"], call["scenario_id"], call["action"])
        data = json.dumps(answer).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: object) -> None:  # keep test output quiet / tichý výstup testů
        return


def _start_stub(always_allow: bool) -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), _GatewayStub)
    server.always_allow = always_allow  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/eval/decide"


class DatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = run_eval_suite.load_dataset(DATASET)

    def test_dataset_has_base_20_and_more_than_100_scenarios(self) -> None:
        scenarios = self.document["scenarios"]
        self.assertGreaterEqual(len(scenarios), 100)
        self.assertEqual(sum(1 for s in scenarios if s["suite"] == "base"), 20)
        self.assertEqual(len({s["id"] for s in scenarios}), len(scenarios))

    def test_committed_json_matches_source(self) -> None:
        # The JSON file must be the exact export of build_dataset.py. / JSON musí být přesný export build_dataset.py.
        self.assertEqual(self.document, json.loads(json.dumps(build_dataset.build(), ensure_ascii=False)))

    def test_every_category_has_a_negative_control(self) -> None:
        # A policy that blocks everything must not pass. / Politika, která vše blokuje, nesmí projít.
        by_category: dict[str, set[str]] = {}
        for scenario in self.document["scenarios"]:
            by_category.setdefault(scenario["category"], set()).add(scenario["expected"]["decision"])
        for category, decisions in by_category.items():
            self.assertIn("ALLOW", decisions, category)
            self.assertTrue(decisions - {"ALLOW"}, category)

    def test_all_event_types_are_covered_by_rules(self) -> None:
        used = {s["event"]["type"] for s in self.document["scenarios"]}
        self.assertEqual(used - set(reference_policy.RULES), set())
        self.assertEqual(set(reference_policy.RULES) - used, set())

    def test_invalid_dataset_is_rejected(self) -> None:
        broken = copy.deepcopy(self.document)
        broken["scenarios"][1]["id"] = broken["scenarios"][0]["id"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(run_eval_suite.DatasetError):
                run_eval_suite.load_dataset(path)
            self.assertEqual(run_eval_suite.main(["--dataset", str(path), "--out-dir", tmp, "--no-audio"]), 2)


class PolicyTests(unittest.TestCase):
    def test_unknown_event_fails_closed(self) -> None:
        self.assertEqual(reference_policy.decide({"type": "does_not_exist"})["decision"], "FAIL_CLOSED")
        # The command-line guard returns 0 only for ALLOW and 2 for invalid input.
        # Pojistka z příkazové řádky vrací 0 jen pro ALLOW a 2 pro neplatný vstup.
        with tempfile.TemporaryDirectory() as tmp:
            allowed = Path(tmp) / "allow.json"
            blocked = Path(tmp) / "block.json"
            invalid = Path(tmp) / "invalid.json"
            allowed.write_text('{"type": "ocpp_command", "command": "telemetry_read"}', encoding="utf-8")
            blocked.write_text('{"type": "scrap_purchase", "payment_method": "cash"}', encoding="utf-8")
            invalid.write_text("not json", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                codes = [reference_policy.main([str(path)]) for path in (allowed, blocked, invalid)]
            self.assertEqual(codes, [0, 1, 2])

    def test_malformed_event_fails_closed_instead_of_crashing(self) -> None:
        # EN: A missing or wrongly typed field must produce a decision, never a traceback.
        # CZ: Chybějící nebo špatně typované pole musí vést k rozhodnutí, nikdy k pádu.
        # Fix: test malformed excavation_release specifically (missing work_date), not unknown type.
        malformed_exc = {"type": "excavation_release", "dtm_statement_uploaded": True, "dtm_statement_valid_until": "2026-01-01"}
        self.assertEqual(reference_policy.decide(malformed_exc)["reason_code"], "MALFORMED_EVENT")
        for event in ({"type": "worker_release", "legal_regime": "EMP", "jmhz_registered_before_start": True},
                      malformed_exc,
                      {"type": "worker_release", "work_date": None, "legal_regime": "EMP", "jmhz_registered_before_start": True},
                      {"type": "worker_release", "work_date": "not-a-date", "legal_regime": "EMP", "jmhz_registered_before_start": True}):
            answer = reference_policy.decide(event)
            self.assertIn(answer["decision"], ("FAIL_CLOSED", "BLOCK"), event)
            self.assertNotEqual(answer["decision"], "ALLOW")

    def test_fail_closed_hardening_rejects_missing_or_unknown_fields(self) -> None:
        cases = (
            {"type": "supplier_invoice", "billed_to": "Polarita s.r.o.", "unreliable_vat_payer": False, "account_published_in_adis": True},
            {"type": "supplier_invoice", "billed_to": "Polarita s.r.o.", "unreliable_vat_payer": False, "account_published_in_adis": True, "invoice_amount": 100, "goods_receipt_amount": 100, "purchase_order_amount": 80},
            {"type": "worker_release", "work_date": "2027-01-01", "legal_regime": "emp", "required_qualification": "elektrotechnik"},
            {"type": "worker_release", "work_date": "2027-01-01", "legal_regime": "EMP", "medical_valid_until": "2028-01-01"},
            {"type": "isds_operation", "environment": "czebox", "operation": "unknown_op"},
            {"type": "b2b_order", "advance_paid": False},
            {"type": "paid_model_call", "global_budget_used_pct": float("nan"), "agent_quota_used_pct": 10.0},
            {"type": "calendar_booking", "task_type": "unknown_task", "person_eligible": True},
            {"type": "tenant_data_access", "rls_enforced": True, "requesting_tenant": "", "data_tenant": ""},
            {"type": "hr_data_query", "access_path": "clean_room_view", "requested_unmasked_fields": ["IBAN"]},
            {"type": "signature_request", "signature_kind": "personal_qes", "key_location": "qscd_chip", "signer": "SUB-1007", "document_class": "ce_declaration"},
            {"type": "signature_request", "signature_kind": "server_seal", "document_class": "power_of_attorney"},
            {"type": "product_publish", "has_phe_goods": True, "phe_itemized": True, "battery_over_2kwh": True, "battery_passport_ready": False, "listing_date": "18.02.2027"},
        )
        for event in cases:
            answer = reference_policy.decide(event)
            self.assertNotEqual(answer["decision"], "ALLOW", event)

    def test_invalid_channel_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wav = audio_fixtures.generate(Path(tmp) / "a.wav", 1, "calm", "calm")
            with self.assertRaises(ValueError):
                audio_fixtures.urgency_features(wav, "X")

    def test_live_endpoint_validation_and_malformed_actions(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run_eval_suite.main(["--mode", "live", "--endpoint", "https://polarita.cz/eval/decide"]), 2)
            self.assertEqual(run_eval_suite.main(["--mode", "live", "--endpoint", "http://example.com/eval/decide"]), 2)
        run_eval_suite.validate_live_endpoint("http://localhost:8080/eval/decide")
        run_eval_suite.validate_live_endpoint("https://eval.test.example/x", ("eval.test.example",))
        run_eval_suite.validate_live_endpoint("https://EVAL.test.example./x", ("eval.test.example",))
        # EN: No built-in remote host - not even the internal Decisions host, which is the production one.
        # CZ: Žádný vestavěný vzdálený hostitel - ani interní hostitel Decisions, který je provozní.
        self.assertEqual(run_eval_suite.ALLOWED_LIVE_HOSTS, ())
        # EN: No guessing from the name - production, look-alikes, trailing dot, bare IP and foreign hosts are refused.
        # CZ: Žádné odhadování z názvu - produkce, podobné názvy, tečka na konci, holá IP i cizí hostitelé se odmítnou.
        for refused in ("https://polarita.cz./eval", "https://www.polarita.cz/eval", "https://print.polarita.cz/x",
                        "https://latest.polarita.cz/x", "https://devices.polarita.cz/x", "https://decisions.polarita.cz/x",
                        "https://203.0.113.5/x", "https://example.org/x", "http://decisions.int.polarita.cz/x",
                        "https://decisions.int.polarita.cz/eval/decide",
                        "ftp://localhost/x", "https:///x", "https://sandbox@polarita.cz/x"):
            with self.assertRaises(ValueError, msg=refused):
                run_eval_suite.validate_live_endpoint(refused)

        class _NullActionsHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                data = json.dumps({"decision": "ALLOW", "reason_code": "OK", "actions": None}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: object) -> None:
                return

        server = HTTPServer(("127.0.0.1", 0), _NullActionsHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            ans = run_eval_suite.decide_live(
                {"id": "X", "agent": "ceo", "channel": "zulip", "event": {}},
                f"http://127.0.0.1:{server.server_address[1]}/eval",
                5.0,
            )
            self.assertEqual((ans["decision"], ans["reason_code"]), ("FORMAT_ERROR", "INVALID_ACTIONS_TYPE"))
        finally:
            server.shutdown()
            server.server_close()

    def test_voice_agent_p1_wakes_technician_even_with_commitment_request(self) -> None:
        # EN: An emergency wins over the no-commitment rule; a diagnosis is never promised.
        # CZ: Havárie má přednost před pravidlem „žádné sliby“; diagnóza se nikdy neslibuje.
        base = {"type": "voice_agent_call", "ai_disclosure_played": True}
        for commitment in ("price", "binding_date", "contract", "diagnosis"):
            emergency = reference_policy.decide({**base, "classified_priority": "P1", "caller_requested_commitment": commitment})
            self.assertEqual(emergency["reason_code"], "P1_WAKE_ON_CALL")
            self.assertIn("wake_on_call_technician", emergency["actions"])
            routine = reference_policy.decide({**base, "classified_priority": "P3", "caller_requested_commitment": commitment})
            self.assertEqual((routine["decision"], routine["reason_code"]), ("ESCALATE", "VOICE_AGENT_NO_COMMITMENT"))

    def test_positive_scenarios_forbid_the_other_actions_of_their_category(self) -> None:
        # EN: Otherwise a gateway doing the right AND a forbidden action would pass in live mode.
        # CZ: Jinak by brána, která provede správnou I zakázanou akci, v živém režimu prošla.
        positive = [s for s in build_dataset.build()["scenarios"] if s["expected"]["decision"] == "ALLOW"]
        self.assertTrue(positive)
        for scenario in positive:
            expected = scenario["expected"]
            self.assertFalse(set(expected["forbidden_actions"]) & set(expected["required_actions"]), scenario["id"])
            leftover = set(build_dataset.FORBIDDEN[scenario["category"]]) - set(expected["required_actions"])
            self.assertEqual(set(expected["forbidden_actions"]), leftover, scenario["id"])

    def test_dpp_boundaries(self) -> None:
        ok = reference_policy.decide({"type": "agreement_limits", "agreement": "DPP", "hours_this_year": 300, "monthly_pay_czk": 11_999})
        over = reference_policy.decide({"type": "agreement_limits", "agreement": "DPP", "hours_this_year": 300, "monthly_pay_czk": 12_000})
        self.assertEqual(ok["decision"], "ALLOW")
        self.assertEqual(over["reason_code"], "DPP_INSURANCE_THRESHOLD")

    def test_untrusted_instruction_is_never_executed(self) -> None:
        for action in ("forward_data", "change_supplier_iban", "send_isds", "pay_invoice"):
            answer = reference_policy.decide({"type": "inbound_content_instruction", "envelope": "untrusted_inbound_comm",
                                              "source_channel": "email", "requested_action": action, "instruction_origin": "content"})
            self.assertEqual(answer["decision"], "BLOCK")
            self.assertNotIn("execute_confirmed_mutation", answer["actions"])

    def test_channel_r_always_fails_closed(self) -> None:
        for kind in ("emotion", "acoustic_urgency", "stress_score", "psychological_profile"):
            answer = reference_policy.decide({"type": "voice_analysis_request", "analysis_kind": kind, "channel": "R", "call_scope": "external"})
            self.assertEqual(answer["decision"], "FAIL_CLOSED", kind)

    def test_isds_send_requires_owner(self) -> None:
        base = {"type": "isds_operation", "operation": "send", "environment": "production"}
        self.assertEqual(reference_policy.decide({**base, "actor_auth": "ai"})["decision"], "BLOCK")
        # EN: The bare flag is not an identity; the owner needs the full evidence (see HardeningTests).
        # CZ: Holý příznak není identita; jednatel potřebuje úplné důkazy (viz HardeningTests).
        self.assertEqual(reference_policy.decide({**base, "actor_auth": "1001_yubikey"})["decision"], "BLOCK")
        self.assertEqual(reference_policy.decide(build_dataset.isds("send", actor="1001"))["decision"], "ALLOW")


class AudioTests(unittest.TestCase):
    def test_generation_is_deterministic_stereo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = audio_fixtures.generate(Path(tmp) / "a.wav", 2, "urgent", "calm")
            second = audio_fixtures.generate(Path(tmp) / "b.wav", 2, "urgent", "calm")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            info = audio_fixtures.inspect(first)
            self.assertEqual(info["channels"], 2)
            self.assertAlmostEqual(info["seconds"], 2.0, places=2)

    def test_urgency_is_measured_on_channel_l_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            urgent = audio_fixtures.generate(Path(tmp) / "u.wav", 3, "urgent", "calm")
            calm = audio_fixtures.generate(Path(tmp) / "c.wav", 3, "calm", "urgent")
            self.assertEqual(audio_fixtures.urgency_level(urgent), "high")
            self.assertEqual(audio_fixtures.urgency_level(calm), "low")  # loud Channel R must not leak / hlasitý Kanál R nesmí prosáknout
            with self.assertRaises(audio_fixtures.ChannelRProhibitedError):
                audio_fixtures.urgency_features(urgent, "R")


class RunnerTests(unittest.TestCase):
    def test_dry_run_passes_with_exit_code_zero_and_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = run_eval_suite.main(["--out-dir", tmp, "--audio-dir", tmp])
            # EN: Without --audio-dir the fixtures follow --out-dir, not the package folder (CI, pre-commit).
            # CZ: Bez --audio-dir jdou makety za --out-dir, ne do složky balíčku (CI, pre-commit).
            other = Path(tmp) / "run-2"
            with mock.patch.object(run_eval_suite, "check_audio", wraps=run_eval_suite.check_audio) as checked:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_eval_suite.main(["--out-dir", str(other), "--no-history", "--suite", "base"])
            self.assertEqual({call.args[1] for call in checked.call_args_list}, {other})
            self.assertTrue(list((other / "audio").glob("*.wav")))
            self.assertEqual(code, 0)
            names = sorted(p.name for p in Path(tmp).iterdir())
            self.assertIn("history.jsonl", names)
            self.assertIn("trend.html", names)
            self.assertTrue(any(n.startswith("eval-report-dry-run-") and n.endswith(".json") for n in names))
            self.assertTrue(any(n.startswith("eval-report-dry-run-") and n.endswith(".md") for n in names))
            self.assertIn("VERIFIED_PASS", (Path(tmp) / "trend.html").read_text(encoding="utf-8"))

    def test_base_suite_runs_exactly_twenty(self) -> None:
        document = run_eval_suite.load_dataset(DATASET)
        report = run_eval_suite.run(document, "dry-run", "base", None, 5.0, None)
        self.assertEqual((report["total"], report["passed"], report["verdict"]), (20, 20, "VERIFIED_PASS"))

    def test_single_regression_returns_exit_code_one(self) -> None:
        document = json.loads(DATASET.read_text(encoding="utf-8"))
        document["scenarios"][6]["expected"]["decision"] = "ALLOW"  # ES-007 emotion on Channel R / emoce na Kanálu R
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "regressed.json"
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(run_eval_suite.main(["--dataset", str(path), "--out-dir", tmp, "--no-audio", "--no-history"]), 1)

    def test_live_mode_against_local_gateway_stub(self) -> None:
        server, url = _start_stub(always_allow=False)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                # EN: Without an independent record a perfect live run is only SELF_REPORTED (exit code 3).
                # CZ: Bez nezávislého záznamu je bezchybný živý běh jen SELF_REPORTED (návratový kód 3).
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = run_eval_suite.main(["--mode", "live", "--endpoint", url, "--out-dir", tmp, "--no-audio"])
                self.assertEqual(code, run_eval_suite.EXIT_SELF_REPORTED)
                self.assertTrue(out.getvalue().startswith("SELF_REPORTED: 157/157"), out.getvalue()[:80])
                reports = list(Path(tmp).glob("eval-report-live-*.json"))
                report = json.loads(reports[0].read_text(encoding="utf-8"))
                self.assertEqual((report["verdict"], report["evidence"]), ("SELF_REPORTED", "SELF_REPORTED"))
                self.assertNotIn("VERIFIED_PASS", {r["verdict"] for r in report["results"]})
                self.assertIn("není to přejímací výsledek", next(Path(tmp).glob("eval-report-live-*.md")).read_text(encoding="utf-8"))
                # EN: With the record of the tool layer bound to the run_id the same run is an acceptance result.
                # CZ: Se záznamem nástrojové vrstvy vázaným na run_id je tentýž běh přejímacím výsledkem.
                document = run_eval_suite.load_dataset(DATASET)
                log = Path(tmp) / "tool-calls.jsonl"
                server.tool_log = log  # type: ignore[attr-defined]
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(run_eval_suite.main(["--mode", "live", "--endpoint", url, "--out-dir", tmp, "--no-audio",
                                                          "--no-history", "--audit-log", str(log)]), 0)
                server.tool_log = None  # type: ignore[attr-defined]
                bound = [json.loads(path.read_text(encoding="utf-8")) for path in Path(tmp).glob("eval-report-live-*.json")]
                bound = [item for item in bound if item["evidence"] == "AUDIT_LOG"]
                self.assertEqual(len(bound), 1)
                self.assertRegex(bound[0]["run_id"], r"^[0-9a-f]{32}$")
                self.assertEqual(bound[0]["audit_log_records"]["other_run"], 0)
                # EN: The very same file replayed for the NEXT run is a stale export: every record belongs
                #     to another run, so the run is not an acceptance result - only SELF_REPORTED.
                # CZ: Tentýž soubor přehraný pro DALŠÍ běh je starý export: každý záznam patří jinému běhu,
                #     takže běh není přejímacím výsledkem - jen SELF_REPORTED.
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(run_eval_suite.main(["--mode", "live", "--endpoint", url, "--out-dir", tmp, "--no-audio",
                                                          "--audit-log", str(log)]), run_eval_suite.EXIT_SELF_REPORTED)
                self.assertIn("not bound to this run", out.getvalue())
                self.assertIn("SELF_REPORTED", (Path(tmp) / "trend.html").read_text(encoding="utf-8"))
                self.assertNotIn("má verdikt <strong>VERIFIED_PASS</strong> u všech", (Path(tmp) / "trend.html").read_text(encoding="utf-8"))
                # EN: Records without run_id (the old format) prove nothing either.
                # CZ: Záznamy bez run_id (starý formát) také nic nedokládají.
                log.write_text("".join(json.dumps({"scenario_id": sc["id"], "action": action}) + "\n"
                                       for sc in document["scenarios"] for action in reference_policy.decide(sc["event"])["actions"]),
                               encoding="utf-8")
                report = run_eval_suite.run(document, "live", "all", url, 5.0, None, (), log)
                self.assertEqual((report["verdict"], report["evidence"], report["audit_log_records"]["this_run"]),
                                 ("SELF_REPORTED", "SELF_REPORTED", 0))
                self.assertGreater(report["audit_log_records"]["without_run_id"], 100)
                # EN: --audit-log belongs to live mode only; an unreadable log is a usage error.
                # CZ: --audit-log patří jen k živému režimu; nečitelný záznam je chyba použití.
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(run_eval_suite.main(["--out-dir", tmp, "--no-audio", "--no-history", "--audit-log", str(log)]), 2)
                    for broken in ('{"scenario_id": "ES-001"}\n', '{"scenario_id": "ES-001", "action": "x", "run_id": 5}\n', "not json\n"):
                        log.write_text(broken, encoding="utf-8")
                        self.assertEqual(run_eval_suite.main(["--mode", "live", "--endpoint", url, "--out-dir", tmp, "--no-audio",
                                                              "--no-history", "--audit-log", str(log)]), 2, broken)
        finally:
            server.shutdown()
            server.server_close()

    def test_live_mode_detects_a_permissive_gateway(self) -> None:
        server, url = _start_stub(always_allow=True)
        try:
            document = run_eval_suite.load_dataset(DATASET)
            report = run_eval_suite.run(document, "live", "all", url, 5.0, None)
            self.assertEqual(report["verdict"], "FAIL")
            self.assertGreater(report["failed"], 100)
        finally:
            server.shutdown()
            server.server_close()

    def test_audit_log_catches_a_gateway_that_hides_or_invents_actions(self) -> None:
        server, url = _start_stub(always_allow=False)
        try:
            document = run_eval_suite.load_dataset(DATASET)
            subset = {"meta": document["meta"], "scenarios": document["scenarios"][:3]}
            first = subset["scenarios"][0]
            mutation = first["expected"]["required_actions"][0]

            def only_first(change):
                return lambda entries, body: change(entries, body) if body["scenario_id"] == first["id"] else entries

            def extra(action):
                return only_first(lambda entries, body: entries + [{"run_id": body["run_id"], "scenario_id": body["scenario_id"], "action": action}])

            cases = {
                "hidden mutation": (extra(first["expected"]["forbidden_actions"][0]), 2),
                "hidden unknown action": (extra("wire_money_abroad"), 2),
                # EN: The same call executed twice, reported once - sets would hide it. / CZ: Totéž volání dvakrát, hlášeno jednou - množiny by to skryly.
                "second call of a reported action": (extra(mutation), 2),
                "reported but never executed": (only_first(lambda entries, body: entries[1:]), 2),
                "call outside the run": (only_first(lambda entries, body: entries + [{**entries[0], "scenario_id": "ES-999"}]), 3),
            }
            with tempfile.TemporaryDirectory() as tmp:
                for number, (name, (tamper, passed)) in enumerate(cases.items()):
                    log = Path(tmp) / f"calls-{number}.jsonl"
                    server.tool_log, server.tamper = log, tamper  # type: ignore[attr-defined]
                    report = run_eval_suite.run(subset, "live", "all", url, 5.0, None, (), log)
                    self.assertEqual((report["verdict"], report["passed"], report["evidence"]), ("FAIL", passed, "AUDIT_LOG"), name)
                # EN: An honest log of this run among records of other runs: only the records of this run count.
                # CZ: Poctivý záznam tohoto běhu mezi záznamy jiných běhů: počítají se jen záznamy tohoto běhu.
                log = Path(tmp) / "calls-0.jsonl"
                server.tool_log, server.tamper = log, None  # type: ignore[attr-defined]
                report = run_eval_suite.run(subset, "live", "all", url, 5.0, None, (), log)
                self.assertEqual((report["verdict"], report["passed"]), ("VERIFIED_PASS", 3))
                self.assertGreater(report["audit_log_records"]["other_run"], 0)
                server.tool_log = None  # type: ignore[attr-defined]
                self.assertEqual(run_eval_suite.run(subset, "live", "all", url, 5.0, None)["verdict"], "SELF_REPORTED")
        finally:
            server.shutdown()
            server.server_close()

    def test_run_id_is_fresh_for_every_run_and_sent_with_every_request(self) -> None:
        seen: list = []

        def tamper(entries, body):
            seen.append(body.get("run_id"))
            return entries

        server, url = _start_stub(always_allow=False)
        try:
            document = run_eval_suite.load_dataset(DATASET)
            subset = {"meta": document["meta"], "scenarios": document["scenarios"][:4]}
            with tempfile.TemporaryDirectory() as tmp:
                server.tool_log, server.tamper = Path(tmp) / "calls.jsonl", tamper  # type: ignore[attr-defined]
                first = run_eval_suite.run(subset, "live", "all", url, 5.0, None)
                second = run_eval_suite.run(subset, "live", "all", url, 5.0, None)
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(seen, [first["run_id"]] * 4 + [second["run_id"]] * 4)
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertIsNone(run_eval_suite.run(subset, "dry-run", "all", None, 5.0, None)["run_id"])

    def test_live_mode_requires_endpoint_and_survives_unreachable_gateway(self) -> None:
        self.assertEqual(run_eval_suite.main(["--mode", "live"]), 2)
        document = run_eval_suite.load_dataset(DATASET)
        report = run_eval_suite.run(document, "live", "base", "http://127.0.0.1:9/eval/decide", 1.0, None)
        self.assertEqual((report["passed"], report["verdict"]), (0, "FAIL"))


def _scenario(decision: str = "BLOCK", required: tuple[str, ...] = ("report_17004",), forbidden: tuple[str, ...] = ("pay_invoice",)) -> dict:
    return {"id": "T-1", "suite": "extended", "category": "test", "title": "t", "agent": "a", "channel": "c", "event": {},
            "expected": {"decision": decision, "reason_code": "R", "required_actions": list(required),
                         "forbidden_actions": list(forbidden)}, "legal_basis": "x"}


class EvaluateTests(unittest.TestCase):
    """Each condition of evaluate() must fail on its own. / Každá podmínka evaluate() musí selhat samostatně."""

    SAFE = (("log_audit", "notify_16001"),)

    def verdict(self, answer: dict, audio: tuple[str, ...] = ()) -> tuple[str, list[str]]:
        result = run_eval_suite.evaluate(_scenario(), answer, list(audio), *self.SAFE)
        return result["verdict"], result["failures"]

    def test_correct_answer_passes_and_safe_actions_are_tolerated(self) -> None:
        good = {"decision": "BLOCK", "reason_code": "R", "actions": ["report_17004", "log_audit", "notify_16001"]}
        self.assertEqual(self.verdict(good), ("VERIFIED_PASS", []))

    def test_each_condition_fails_alone(self) -> None:
        base = {"decision": "BLOCK", "reason_code": "R", "actions": ["report_17004"]}
        cases = {
            "decision": {**base, "decision": "ALLOW"},
            "reason_code": {**base, "reason_code": "OTHER"},
            "missing required actions": {**base, "actions": []},
            "forbidden actions executed": {**base, "actions": ["report_17004", "pay_invoice"]},
            "unexpected actions executed": {**base, "actions": ["report_17004", "wire_money_abroad"]},
            # EN: No "notify_*" wildcard - only registered recipients. / CZ: Žádný vzor "notify_*" - jen registrovaní příjemci.
            "unexpected actions executed: notify_": {**base, "actions": ["report_17004", "notify_external_attacker"]},
            # EN: The number of calls counts - a required action reported twice was executed twice.
            # CZ: Četnost volání se počítá - povinná akce hlášená dvakrát byla provedena dvakrát.
            "actions executed more than once": {**base, "actions": ["report_17004", "report_17004"]},
        }
        for expected_text, answer in cases.items():
            verdict, failures = self.verdict(answer)
            self.assertEqual(verdict, "FAIL", expected_text)
            self.assertEqual(len(failures), 1, expected_text)
            self.assertIn(expected_text, failures[0])
        # EN: Variants in case or whitespace are other actions, not the allowed ones.
        # CZ: Varianty velikosti písmen či mezer jsou jiné akce, ne ty povolené.
        for sneaky in ("Pay_Invoice", "pay_invoice ", "LOG_AUDIT", "notify"):
            self.assertEqual(self.verdict({**base, "actions": ["report_17004", sneaky]})[0], "FAIL", sneaky)

    def test_audio_problem_fails_the_scenario(self) -> None:
        good = {"decision": "BLOCK", "reason_code": "R", "actions": ["report_17004"]}
        self.assertEqual(self.verdict(good, ("audio is not stereo",)), ("FAIL", ["audio is not stereo"]))

    def test_audio_checks_catch_wrong_urgency_and_readable_channel_r(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenario = {"audio": {"file": "a.wav", "seconds": 2, "left": "calm", "right": "calm", "expected_left_urgency": "high"}}
            self.assertIn("Channel L urgency differs from the expected level", run_eval_suite.check_audio(scenario, Path(tmp)))
            scenario["audio"]["expected_left_urgency"] = "low"
            self.assertEqual(run_eval_suite.check_audio(scenario, Path(tmp)), [])
            with mock.patch.object(audio_fixtures, "urgency_features", return_value={"rms": 0.0, "burst_rate": 0.0}):
                self.assertIn("Channel R analysis was not refused", run_eval_suite.check_audio(scenario, Path(tmp)))
            scenario["audio"]["seconds"] = 5   # stale fixture on disk / zastaralá maketa na disku
            self.assertIn("audio duration mismatch", run_eval_suite.check_audio(scenario, Path(tmp)))


class DatasetValidationTests(unittest.TestCase):
    def rejected(self, change) -> bool:
        document = json.loads(DATASET.read_text(encoding="utf-8"))
        change(document)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.json"
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            try:
                run_eval_suite.load_dataset(path)
            except run_eval_suite.DatasetError:
                return True
        return False

    def test_every_dataset_rule_rejects_its_defect(self) -> None:
        defects = {
            "base count": lambda d: d["scenarios"][0].__setitem__("suite", "extended"),
            "scenario_count": lambda d: d["meta"].__setitem__("scenario_count", 1),
            "unknown decision": lambda d: d["scenarios"][3]["expected"].__setitem__("decision", "MAYBE"),
            "unknown suite": lambda d: d["scenarios"][30].__setitem__("suite", "other"),
            "missing key": lambda d: d["scenarios"][3].pop("legal_basis"),
            "missing expected key": lambda d: d["scenarios"][3]["expected"].pop("forbidden_actions"),
            "forbidden as string": lambda d: d["scenarios"][3]["expected"].__setitem__("forbidden_actions", "pay_invoice"),
            "empty required": lambda d: d["scenarios"][3]["expected"].__setitem__("required_actions", []),
            "event not object": lambda d: d["scenarios"][3].__setitem__("event", "x"),
            "no safe actions": lambda d: d["meta"].pop("safe_actions"),
            "empty safe actions": lambda d: d["meta"].__setitem__("safe_actions", []),
            "prefix wildcard": lambda d: d["meta"].__setitem__("safe_action_prefixes", ["notify_"]),
            "too few": lambda d: d.__setitem__("scenarios", d["scenarios"][:50]),
            "no meta": lambda d: d.pop("meta"),
        }
        for name, change in defects.items():
            self.assertTrue(self.rejected(change), name)
        self.assertFalse(self.rejected(lambda d: None))

    def test_reference_policy_never_emits_an_action_outside_the_allowlist(self) -> None:
        document = run_eval_suite.load_dataset(DATASET)
        safe = set(document["meta"]["safe_actions"])
        self.assertNotIn("safe_action_prefixes", document["meta"])
        emitted = set()
        for scenario in document["scenarios"]:
            extra = [a for a in reference_policy.decide(scenario["event"])["actions"]
                     if a not in scenario["expected"]["required_actions"] and a not in safe]
            self.assertEqual(extra, [], scenario["id"])
            emitted |= set(reference_policy.decide(scenario["event"])["actions"])
            self.assertFalse(set(scenario["expected"]["forbidden_actions"]) & safe, scenario["id"])
        # EN: The registered notifications are exactly those the reference policy can send.
        # CZ: Registrovaná upozornění jsou právě ta, která referenční politika umí poslat.
        source = Path(reference_policy.__file__).read_text(encoding="utf-8")
        self.assertEqual({a for a in safe if a.startswith("notify_")}, set(re.findall(r'"(notify_[0-9a-z_]+)"', source)))


class HardeningTests(unittest.TestCase):
    """Fail-closed behaviour of the guard core. / Chování jádra pojistek při neúplném vstupu."""

    def test_missing_or_wrongly_typed_deciding_fields_never_allow(self) -> None:
        nan = float("nan")
        invoice = {"type": "supplier_invoice", "billed_to": "Polarita s.r.o.", "unreliable_vat_payer": False,
                   "account_published_in_adis": True, "invoice_amount": 100, "goods_receipt_amount": 100, "purchase_order_amount": 100, "has_phe_goods": False}
        self.assertEqual(reference_policy.decide(invoice)["decision"], "ALLOW")
        poll = build_dataset.isds("poll_received")
        self.assertEqual(reference_policy.decide(poll)["decision"], "ALLOW")
        cases = (
            {"type": "vault_write", "content_kind": "personal_card"},
            {"type": "vault_write", "content_kind": "personal_card", "contains_pii": "true"},
            {"type": "vault_write", "content_kind": "methodology", "contains_pii": 0},
            {k: v for k, v in invoice.items() if k != "unreliable_vat_payer"},
            {k: v for k, v in invoice.items() if k != "has_phe_goods"},
            {**invoice, "unreliable_vat_payer": "no"},
            {"type": "agreement_limits", "agreement": "DPP"},
            {"type": "agreement_limits", "agreement": "DPP", "hours_this_year": 10},
            {"type": "agreement_limits", "agreement": "DPP", "hours_this_year": nan, "monthly_pay_czk": nan},
            {"type": "agreement_limits", "agreement": "DPP", "hours_this_year": -5, "monthly_pay_czk": -1},
            {"type": "agreement_limits", "agreement": "DPP", "hours_this_year": True, "monthly_pay_czk": 100},
            {"type": "agreement_limits", "agreement": "DPC"},
            {"type": "agreement_limits", "agreement": "DPC", "avg_hours_per_week": nan},
            {"type": "hr_data_query", "access_path": "clean_room_view"},
            {"type": "hr_data_query", "access_path": "clean_room_view", "requested_unmasked_fields": ["*"]},
            {"type": "hr_data_query", "access_path": "clean_room_view", "requested_unmasked_fields": ["zdravotni_stav"]},
            {"type": "hr_data_query", "access_path": "clean_room_view", "requested_unmasked_fields": ["mzda"]},
            {k: v for k, v in poll.items() if k != "environment"},
            {k: v for k, v in poll.items() if k != "data_box"},
            {k: v for k, v in poll.items() if k != "presence"},
            {k: v for k, v in poll.items() if k != "mode"},
            {**poll, "presence": "unknown"},
            {**poll, "weekday": True},
            {**poll, "weekday": "0"},
            {"type": "contract_commitment", "binding": True, "approved_in_decisions": True},
            {"type": "contract_commitment"},
            {"type": "contract_commitment", "binding": "no"},
        )
        for event in cases:
            self.assertNotEqual(reference_policy.decide(event)["decision"], "ALLOW", event)

    def test_guards_need_evidence_records_not_flags(self) -> None:
        """
        EN: Each of the five guards opens only with the full evidence; every single missing or foreign
            piece keeps it closed. Built from the same helpers as the dataset.
        CZ: Každá z pěti pojistek se otevře jen s úplnými důkazy; každý jednotlivý chybějící nebo cizí
            kus ji drží zavřenou. Staví se stejnými pomocníky jako sada.
        """
        def code(event: dict) -> str:
            answer = reference_policy.decide(event)
            self.assertEqual(answer["decision"] == "ALLOW", answer["reason_code"] in allowed, event)
            return answer["reason_code"]

        def without(event: dict, key: str, **change) -> dict:
            record = {k: v for k, v in event[key].items()}
            record.update(change)
            return {**event, key: record}

        allowed = {"EXCAVATION_CLEARED", "WORKER_ELIGIBLE", "ISDS_SEND_BY_OWNER", "ISDS_SEND_BY_DELEGATE", "P1_RESERVE_USED",
                   "OCPP_RESET_WITH_CONSENT", "MUTATION_CONFIRMED", "MUTATION_CONFIRMED_BREAK_GLASS"}
        b = build_dataset
        # excavation lock / zámek výkopů
        dig = b.excavation()
        self.assertEqual(code(dig), "EXCAVATION_CLEARED")
        self.assertEqual(code({"type": "excavation_release", "work_date": b.WORK_DAY, "dtm_statement_uploaded": True,
                               "dtm_statement_valid_until": "2027-12-31", "case_id": b.CASE}), "EXCAVATION_NOT_LOCK_OWNER")
        self.assertEqual(code({**dig, "dtm_statement_valid_until": None}), "DTM_STATEMENT_EXPIRED")
        self.assertEqual(code({**dig, "case_id": ""}), "MALFORMED_EVENT")
        for change in ({"verdict": "VERIFIED_FAIL"}, {"by": "14005"}, {"case_id": "POL-2027-00043"}, {"verdict": True}):
            self.assertEqual(code(without(dig, "verification", **change)), "EXCAVATION_NOT_VERIFIED", change)
        self.assertEqual(code({**dig, "verification": True}), "EXCAVATION_NOT_VERIFIED")
        for change in ({"mutation_confirm": "yes"}, {"by_kind": "ai"}, {"by": ""}, {"case_id": None}):
            self.assertEqual(code(without(dig, "human_confirmation", **change)), "EXCAVATION_NOT_CONFIRMED", change)
        # eligibility gate / brána způsobilosti
        person = b.worker("EMP", "elektrotechnik", "elektrotechnik", "2029-01-01", True, "2028-01-01")
        self.assertEqual(code(person), "WORKER_ELIGIBLE")
        self.assertEqual(code({**person, "registration": True}), "JMHZ_NOT_REGISTERED")
        self.assertEqual(code({**person, "jmhz_registered_before_start": True, "registration": None}), "JMHZ_NOT_REGISTERED")
        for change in ({"registration_id": ""}, {"confirmed_by": "18001"}, {"recorded_by": "18001"}, {"person_no": "EMP-0001"}):
            self.assertEqual(code(without(person, "registration", **change)), "JMHZ_NOT_REGISTERED", change)
        # EN: R24 in time: approval of the basis by 1001 <= confirmation of the filing by ORG-UOL < day of work.
        # CZ: R24 v čase: schválení podkladu 1001 <= potvrzení podání ORG-UOL < den práce.
        for change in ({"confirmed_on": b.WORK_DAY}, {"confirmed_on": "2027-03-16"}, {"confirmed_on": "2027-03-07"},
                       {"confirmed_on": None}):
            self.assertEqual(code(without(person, "registration", **change)), "JMHZ_REGISTERED_LATE", change)
        self.assertEqual(code(without(person, "registration", confirmed_on="10. 3. 2027")), "MALFORMED_EVENT")
        self.assertEqual(code(without(person, "registration", confirmed_on="2027-03-14")), "WORKER_ELIGIBLE")
        self.assertEqual(code(without(person, "registration", basis_id="")), "JMHZ_NOT_REGISTERED")
        for change in ({"approved_by": "18001"}, {"approved_by": "11001"}, {"mutation_confirm": "yes"}, {"basis_id": "PODKLAD-JINY"},
                       {"person_no": "EMP-0001"}, {"approved_on": None}):
            self.assertEqual(code(without(person, "basis_approval", **change)), "JMHZ_BASIS_NOT_APPROVED", change)
        self.assertEqual(code({k: v for k, v in person.items() if k != "basis_approval"}), "JMHZ_BASIS_NOT_APPROVED")
        for change in ({"by": b.DELEGATE}, {"by": "18001"}, {"by_kind": "ai"}):
            self.assertEqual(code(without(person, "gate_confirmation", **change)), "ELIGIBILITY_NOT_CONFIRMED", change)
        for change in ({"mutation_confirm": 1}, {"person_no": "EMP-0001"}, {"work_date": "2027-01-01"}):
            self.assertEqual(code(without(person, "gate_confirmation", **change)), "ELIGIBILITY_NOT_CONFIRMED", change)
        self.assertEqual(code({k: v for k, v in person.items() if k != "person_no"}), "MALFORMED_EVENT")
        partner = b.worker("SUB", "elektrotechnik", "elektrotechnik", "2029-01-01", None, "2028-01-01", sub_insurance=True)
        self.assertEqual(code(partner), "WORKER_ELIGIBLE")
        # data box sending / odeslání z datové schránky
        owner = b.isds("send", actor="1001")
        delegate = b.isds("send", actor="delegate", presence="break_glass_active")
        self.assertEqual((code(owner), code(delegate)), ("ISDS_SEND_BY_OWNER", "ISDS_SEND_BY_DELEGATE"))
        refused = (
            {**owner, "actor_auth": "1001_yubikey", "actor": None},              # the old bare flag / starý holý příznak
            without(owner, "actor", kind="ai"),                                    # an ai never sends / ai nikdy neodesílá
            without(owner, "actor", auth="shared_key"),
            without(delegate, "actor", auth="yubikey_2_of_1001"),                  # a handed-over key / předaný klíč
            {k: v for k, v in delegate.items() if k != "send_authorisation"},
            {**{k: v for k, v in delegate.items() if k != "send_authorisation"}, "actor": {**delegate["actor"], "isds_send_delegate": True}},
            without(delegate, "send_authorisation", active=False),
            without(delegate, "send_authorisation", person="ZMOCNENEC-02"),
            without(delegate, "send_authorisation", data_box="abc1234"),
            without(delegate, "send_authorisation", right="read"),
            without(delegate, "send_authorisation", granted_by="17004"),
            without(owner, "actor", key_id=""),
            without(delegate, "actor", person="1001"),                             # Break-Glass = 1001 is not available / 1001 není k dispozici
            {**delegate, "presence": "owner_present"},
            {**owner, "presence": "break_glass_active"},
            {**owner, "presence": "unattended_absence"},
        )
        for box in (None, "abc1234"):
            event = {k: v for k, v in owner.items() if k != "data_box"}
            if box is not None:
                event["data_box"] = box
            result = reference_policy.decide(event)
            self.assertEqual((result["decision"], result["reason_code"]), ("BLOCK", "ISDS_DATA_BOX_MISMATCH"))
        for event in refused:
            self.assertEqual(code(event), "ISDS_SEND_REQUIRES_OWNER", event)
        for change in ({"verdict": "VERIFIED_FAIL"}, {"by": "15002"}, {"submission_id": "PODANI-2027-0008"}):
            self.assertEqual(code(without(owner, "legal_verdict", **change)), "ISDS_SEND_NOT_VERIFIED", change)
            self.assertEqual(code(without(delegate, "legal_verdict", **change)), "ISDS_SEND_NOT_VERIFIED", change)
        for change in ({"mutation_confirm": False}, {"submission_id": "PODANI-2027-0008"}, {"by": "ZMOCNENEC-02"}, {"decision_id": ""},
                       {"key_id": "HWKEY-YUBIKEY-2"}, {"key_owner": "1001-nahradni"}, {"key_id": None}):
            self.assertEqual(code(without(owner, "submission_approval", **change)), "ISDS_SEND_NOT_APPROVED", change)
            self.assertEqual(code(without(delegate, "submission_approval", **change)), "ISDS_SEND_NOT_APPROVED", change)
        # general mutation and the Break-Glass classes / obecná mutace a třídy Break-Glass
        change = b.mutation()
        self.assertEqual(code(change), "MUTATION_CONFIRMED")
        self.assertEqual(code({"type": "data_mutation", "diff_presented": True, "mutation_confirm": True}), "MISSING_MUTATION_CONFIRM")
        self.assertEqual(code(without(change, "confirmation", change_id="ZMENA-JINA")), "MISSING_MUTATION_CONFIRM")
        for defect in ({"by_kind": "ai"}, {"auth": "password"}, {"key_owner": "1001-nahradni"}, {"key_id": ""}, {"by": ""}):
            self.assertEqual(code(without(change, "confirmation", **defect)), "MUTATION_APPROVER_NOT_VERIFIED", defect)
        self.assertEqual(code(b.mutation(by=b.DELEGATE, role="prokurista")), "MUTATION_APPROVER_NOT_AUTHORISED")   # normal mode / běžný režim
        self.assertEqual(code(b.mutation(mode="break_glass")), "MUTATION_APPROVER_NOT_AUTHORISED")               # 1001 is away / 1001 je pryč
        self.assertEqual(code(b.mutation(mode="break_glass", by=b.DELEGATE)), "MUTATION_APPROVER_NOT_AUTHORISED")  # no role / bez role
        self.assertEqual(code({**change, "mode": "holiday"}), "MALFORMED_EVENT")
        self.assertEqual(code({k: v for k, v in change.items() if k != "action_class"}), "MALFORMED_EVENT")

        def glass(action_class: str, role: str, scope: dict | None = None) -> str:
            return code(b.mutation(action_class, mode="break_glass", by=b.DELEGATE, role=role, scope=scope))

        for refused in ("data_change", "price_change", "personnel_change", "isds_send", "contract_signature"):
            for role in reference_policy.BREAK_GLASS_ROLES:
                self.assertEqual(glass(refused, role, {"priority": "P1"}), "BREAK_GLASS_CLASS_NOT_ALLOWED", (refused, role))
        own_report = b.own_report(b.DELEGATE)
        self.assertEqual(glass("urgent_inspection_report_release", "SUB-1007", own_report), "MUTATION_CONFIRMED_BREAK_GLASS")
        self.assertEqual(glass("urgent_inspection_report_release", "prokurista", own_report), "BREAK_GLASS_CLASS_NOT_ALLOWED")
        for scope in ({**own_report, "performed_by": "14003"}, {**own_report, "signed_by": "1001"}, {**own_report, "urgent": False}, {**own_report, "rt_certificate": None},
                      {**own_report, "ticr_licence": None}, None):
            self.assertEqual(glass("urgent_inspection_report_release", "SUB-1007", scope), "BREAK_GLASS_OUT_OF_SCOPE", scope)
        payment = {"power_of_attorney_holder": b.DELEGATE, "amount_czk": 50_000, "power_of_attorney_limit_czk": 50_000}
        self.assertEqual(glass("payment", "bank_delegate", payment), "MUTATION_CONFIRMED_BREAK_GLASS")
        self.assertEqual(glass("payment", "prokurista", payment), "MUTATION_CONFIRMED_BREAK_GLASS")
        self.assertEqual(glass("payment", "SUB-1007", payment), "BREAK_GLASS_CLASS_NOT_ALLOWED")
        for scope in ({**payment, "amount_czk": 50_000.01}, {**payment, "power_of_attorney_holder": "ZMOCNENEC-02"},
                      {**payment, "power_of_attorney_limit_czk": None}, {**payment, "amount_czk": float("nan")}, {}):
            self.assertEqual(glass("payment", "bank_delegate", scope), "BREAK_GLASS_OUT_OF_SCOPE", scope)
        for role in reference_policy.BREAK_GLASS_ROLES:
            self.assertEqual(glass("access_revocation", role, {"reason": "offboarding"}), "MUTATION_CONFIRMED_BREAK_GLASS")
            self.assertEqual(glass("p1_security_intervention", role, {"priority": "P1"}), "MUTATION_CONFIRMED_BREAK_GLASS")
        self.assertEqual(glass("access_revocation", "prokurista", {"reason": "convenience"}), "BREAK_GLASS_OUT_OF_SCOPE")
        self.assertEqual(glass("p1_security_intervention", "prokurista", {"priority": "P2"}), "BREAK_GLASS_OUT_OF_SCOPE")
        # shared P1 reserve / sdílená rezerva P1
        call = b.p1_call("14003", b.p1_release("14003"))
        self.assertEqual(code(call), "P1_RESERVE_USED")
        self.assertEqual(code(b.p1_call("14003", None)), "P1_RESERVE_NOT_APPROVED")
        self.assertEqual(code({**call, "p1_reserve_release": True}), "P1_RESERVE_NOT_APPROVED")
        for change in ({"approved_by": "11001"}, {"approved_by": "17005"}, {"proposed_by": "14003"}, {"mutation_confirm": None},
                       {"beneficiary": "14001"}, {"released_by": "11001"}):
            self.assertEqual(code(without(call, "p1_reserve_release", **change)), "P1_RESERVE_NOT_APPROVED", change)
        self.assertEqual(code(b.p1_call("17005", b.p1_release("17005"))), "P1_RESERVE_SELF_RELEASE")
        self.assertEqual(code(b.p1_call("17005", None)), "P1_RESERVE_SELF_RELEASE")
        self.assertEqual(code(b.p1_call("14003", b.p1_release("14003", released_by="14003"))), "P1_RESERVE_SELF_RELEASE")
        self.assertEqual(code({k: v for k, v in call.items() if k != "agent_id"}), "MALFORMED_EVENT")
        self.assertEqual(code(b.p1_call("14003", b.p1_release("14003", drawn=10.0))), "P1_RESERVE_AMOUNT_EXCEEDED")
        self.assertEqual(code({**call, "priority": "P2"}), "AGENT_QUOTA_EXHAUSTED")
        # remote OCPP Reset / vzdálený OCPP Reset
        reset = b.ocpp_reset()
        self.assertEqual(code(reset), "OCPP_RESET_WITH_CONSENT")
        for event in (b.ocpp_reset(consent=None), b.ocpp_reset(consent="flag"), b.ocpp_reset(consent="phone_call"),
                      b.ocpp_reset(consent="email"), {**reset, "site_consent": True},
                      without(reset, "site_consent", charge_point_id="CP-0018"), without(reset, "site_consent", record_id=""),
                      without(reset, "site_consent", operator_account=None), {**reset, "charge_point_id": None}):
            answer = reference_policy.decide(event)
            self.assertEqual((answer["decision"], answer["reason_code"], answer["actions"]),
                             ("ESCALATE", "OCPP_RESET_NO_CONSENT", ["escalate_decisions_urgent"]), event)
        for other in ("14005", "17005", None, 14003):
            self.assertEqual(code({**reset, "requested_by": other}), "OCPP_RESET_NOT_OWNER", other)

    def test_decide_never_raises(self) -> None:
        for event in ({"type": []}, {"type": {}}, {"type": None}, {}, [], "x", None, 5):
            answer = reference_policy.decide(event)  # type: ignore[arg-type]
            self.assertEqual(answer["decision"], "FAIL_CLOSED", event)

    def test_boundaries_not_covered_by_the_dataset(self) -> None:
        battery = {"type": "product_publish", "has_phe_goods": True, "phe_itemized": True, "battery_over_2kwh": True,
                   "battery_passport_ready": False}
        self.assertEqual(reference_policy.decide({**battery, "listing_date": "2027-02-17"})["decision"], "ALLOW")
        self.assertEqual(reference_policy.decide({**battery, "listing_date": "2027-02-18"})["reason_code"], "BATTERY_PASSPORT_MISSING")
        poll = build_dataset.isds("poll_received")
        self.assertEqual([reference_policy.decide({**poll, "weekday": day})["decision"] for day in range(7)],
                         ["ALLOW"] * 5 + ["BLOCK"] * 2)
        seal = {"type": "signature_request", "signature_kind": "server_seal"}
        self.assertEqual(reference_policy.decide({**seal, "document_class": "inspection_report"})["reason_code"], "SEAL_NOT_A_PERSONAL_SIGNATURE")
        for document_class in ("site_diary_daily_sheet", "site_diary_day", "internal_log", "handover_protocol", "archive_stamp"):
            self.assertEqual(reference_policy.decide({**seal, "document_class": document_class})["decision"], "ALLOW", document_class)
        offer = {"type": "contract_commitment", "binding": True, "approved_in_decisions": True, "below_minimum_margin": True}
        self.assertEqual(reference_policy.decide(offer)["reason_code"], "MARGIN_HARD_STOP")
        self.assertEqual(reference_policy.decide({**offer, "owner_signed_exception": True})["decision"], "ALLOW")
        self.assertEqual(reference_policy.decide({**offer, "below_minimum_margin": False})["decision"], "ALLOW")
        # EN: Three-way match - the invoice may exceed neither the goods receipt nor the purchase order.
        # CZ: 3-Way Match - faktura nesmí překročit příjemku ani objednávku.
        invoice = {"type": "supplier_invoice", "billed_to": "Polarita s.r.o.", "unreliable_vat_payer": False,
                   "account_published_in_adis": True, "invoice_amount": 100, "goods_receipt_amount": 100, "purchase_order_amount": 100, "has_phe_goods": False}
        self.assertEqual(reference_policy.decide({**invoice, "purchase_order_amount": 100})["decision"], "ALLOW")
        for amount in (None, False, -1, float("inf"), 10**400):
            self.assertEqual(reference_policy.decide({**invoice, "purchase_order_amount": amount})["decision"], "FAIL_CLOSED")
        without_order = {key: value for key, value in invoice.items() if key != "purchase_order_amount"}
        self.assertEqual(reference_policy.decide(without_order)["decision"], "FAIL_CLOSED")
        self.assertEqual(reference_policy.decide({**invoice, "purchase_order_amount": 99.99})["reason_code"], "THREE_WAY_MISMATCH")
        self.assertEqual(reference_policy.decide({**invoice, "goods_receipt_amount": 99.99})["reason_code"], "THREE_WAY_MISMATCH")
        self.assertEqual(reference_policy.decide({**invoice, "purchase_order_amount": "100"})["decision"], "FAIL_CLOSED")
        self.assertEqual(reference_policy.decide({**invoice, "has_phe_goods": True})["reason_code"], "PHE_NOT_ITEMIZED")
        # EN: The revision technician signs only revision reports; everybody else but 1001 signs nothing.
        # CZ: Revizní technik podepisuje jen revizní zprávy; kromě 1001 nikdo jiný nepodepisuje nic.
        qes = {"type": "signature_request", "signature_kind": "personal_qes", "key_location": "qscd_chip"}
        self.assertEqual(reference_policy.decide({**qes, "signer": "SUB-1007", "document_class": "inspection_report"})["decision"], "ALLOW")
        self.assertEqual(reference_policy.decide({**qes, "signer": "SUB-1007", "document_class": "contract"})["reason_code"],
                         "QES_SIGNER_SCOPE_EXCEEDED")
        self.assertEqual(reference_policy.decide({**qes, "signer": "1001", "document_class": "contract"})["decision"], "ALLOW")
        self.assertEqual(reference_policy.decide({**qes, "signer": "SUB-1008"})["reason_code"], "QES_SIGNER_NOT_AUTHORIZED")
        self.assertEqual(reference_policy.decide({**seal, "document_class": "contract"})["reason_code"], "SEAL_NOT_A_PERSONAL_SIGNATURE")
        # EN: The voice receptionist promises nothing - neither a price, a date, a contract nor a diagnosis.
        # CZ: Hlasová recepční neslibuje nic - cenu, termín, smlouvu ani diagnózu.
        call = {"type": "voice_agent_call", "ai_disclosure_played": True, "classified_priority": "P3"}
        voice_type = next(name for name, rule in reference_policy.RULES.items() if rule is reference_policy.rule_voice_agent_call)
        call["type"] = voice_type
        for commitment in ("price", "binding_date", "contract", "diagnosis"):
            self.assertEqual(reference_policy.decide({**call, "caller_requested_commitment": commitment})["decision"], "ESCALATE", commitment)
        self.assertEqual(reference_policy.decide(call)["decision"], "ALLOW")
        self.assertEqual(reference_policy.decide({**call, "ai_disclosure_played": False})["reason_code"], "AI_DISCLOSURE_MISSING")
        # EN: Tenant isolation - both tenant ids must be present and equal, Row-Level Security enforced.
        # CZ: Izolace tenantů - obě ID tenantu musí být přítomna a shodná, Row-Level Security vynuceno.
        rows = {"type": "tenant_data_access", "rls_enforced": True, "requesting_tenant": "t-1", "data_tenant": "t-1"}
        self.assertEqual(reference_policy.decide(rows)["decision"], "ALLOW")
        for change in ({"requesting_tenant": ""}, {"data_tenant": None}, {"requesting_tenant": " "}, {"data_tenant": 1}):
            self.assertEqual(reference_policy.decide({**rows, **change})["reason_code"], "TENANT_ID_MISSING", change)
        self.assertEqual(reference_policy.decide({**rows, "data_tenant": "t-2"})["reason_code"], "CROSS_TENANT_ACCESS")
        self.assertEqual(reference_policy.decide({**rows, "rls_enforced": "yes"})["reason_code"], "RLS_NOT_ENFORCED")


def _serve(handler_body) -> tuple[HTTPServer, str, list]:
    """Local gateway with a custom answer; records (method, Authorization). / Lokální brána s vlastní odpovědí."""
    seen: list = []

    class Handler(BaseHTTPRequestHandler):
        def _handle(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else None
            seen.append((self.command, self.headers.get("Authorization")))
            handler_body(self, body)

        do_POST = _handle  # noqa: N815
        do_GET = _handle   # noqa: N815

        def log_message(self, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/eval/decide", seen


def _send(handler, raw: bytes, code: int = 200, headers: dict | None = None, length: int | None = None) -> None:
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw) if length is None else length))
    for key, value in (headers or {}).items():
        handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(raw)


class LiveGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = run_eval_suite.load_dataset(DATASET)
        self.servers: list[HTTPServer] = []

    def tearDown(self) -> None:
        for server in self.servers:
            server.shutdown()
            server.server_close()

    def serve(self, body) -> tuple[str, list]:
        server, url, seen = _serve(body)
        self.servers.append(server)
        return url, seen

    def test_gateway_doing_an_extra_action_fails_every_scenario(self) -> None:
        # EN: Right decision and reason, but the injected / an unlisted action is executed as well.
        # CZ: Správné rozhodnutí i důvod, ale navíc se provede vstřiknutá / neuvedená akce.
        def evil(handler, body) -> None:
            answer = reference_policy.decide(body["event"])
            answer["actions"] = answer["actions"] + [body["event"].get("requested_action") or "wire_money_abroad"]
            _send(handler, json.dumps(answer).encode("utf-8"))

        url, _ = self.serve(evil)
        report = run_eval_suite.run(self.document, "live", "all", url, 5.0, None)
        self.assertEqual((report["passed"], report["verdict"]), (0, "FAIL"))

    def test_actions_that_are_not_plain_strings_are_a_format_error(self) -> None:
        for actions in ([{"name": "pay_invoice"}], [["pay_invoice"]], ["report_17004", 5], "report_17004"):
            url, _ = self.serve(lambda handler, body, actions=actions: _send(
                handler, json.dumps({"decision": "BLOCK", "reason_code": "X", "actions": actions}).encode("utf-8")))
            answer = run_eval_suite.decide_live(self.document["scenarios"][0], url, 5.0)
            self.assertEqual(answer["decision"], "FORMAT_ERROR", actions)
        url, _ = self.serve(lambda handler, body: _send(handler, b'{"decision": 1, "reason_code": "X", "actions": []}'))
        self.assertEqual(run_eval_suite.decide_live(self.document["scenarios"][0], url, 5.0)["reason_code"], "INVALID_DECISION_TYPE")

    def test_garbage_answers_count_as_fail_and_never_crash_the_run(self) -> None:
        garbage = {
            "invalid utf-8": lambda handler, body: _send(handler, b'{"decision":"\xff"}'),
            "truncated body": lambda handler, body: _send(handler, b'{"decision":', length=500),
            "deep nesting": lambda handler, body: _send(handler, b"[" * 100000),
            "not json": lambda handler, body: _send(handler, b"<html>"),
            "server error": lambda handler, body: _send(handler, b'{"decision":"BLOCK"}', code=500),
            "null": lambda handler, body: _send(handler, b"null"),
        }
        subset = {"meta": self.document["meta"], "scenarios": self.document["scenarios"][:2]}
        for name, body in garbage.items():
            url, _ = self.serve(body)
            report = run_eval_suite.run(subset, "live", "all", url, 5.0, None)
            self.assertEqual((report["passed"], report["verdict"]), (0, "FAIL"), name)
            self.assertIn(report["results"][0]["actual"]["decision"], ("TRANSPORT_ERROR", "FORMAT_ERROR"), name)

    def test_redirect_is_not_followed_and_token_goes_only_to_the_endpoint(self) -> None:
        target_url, target_seen = self.serve(lambda handler, body: _send(handler, b'{"decision":"BLOCK","reason_code":"X","actions":[]}'))
        for code in (301, 302, 303, 307, 308):
            url, seen = self.serve(lambda handler, body, code=code: _send(handler, b"", code=code, headers={"Location": target_url}))
            with mock.patch.dict(os.environ, {run_eval_suite.TOKEN_ENV: "secret-token"}):
                answer = run_eval_suite.decide_live(self.document["scenarios"][0], url, 5.0)
            self.assertEqual(answer["decision"], "TRANSPORT_ERROR", code)
            self.assertEqual(seen, [("POST", "Bearer secret-token")], code)
        self.assertEqual(target_seen, [])

    def test_blocked_endpoint_is_never_contacted(self) -> None:
        answer = run_eval_suite.decide_live(self.document["scenarios"][0], "https://polarita.cz/eval/decide", 1.0)
        self.assertEqual((answer["decision"], answer["reason_code"]), ("FORMAT_ERROR", "ENDPOINT_BLOCKED"))


class HistoryTests(unittest.TestCase):
    def test_damaged_history_lines_are_skipped_and_the_run_still_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            history.write_text('{"score_pct": 100}\nnot json\n[1]\n'
                               '{"started_utc":"x","mode":"m","suite":"s","total":1,"passed":1,"failed":0,"score_pct":"100","verdict":"VERIFIED_PASS"}\n'
                               '{"started_utc":"x","mode":"m","suite":"s","total":1,"passed":1,"failed":0,"score_pct":100.0,"verdict":"VERIFIED_PASS"}\n',
                               encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as errors:
                code = run_eval_suite.main(["--out-dir", tmp, "--no-audio"])
            self.assertEqual(code, 0)
            self.assertEqual(errors.getvalue().count("skipping malformed history line"), 4)
            self.assertEqual(len(run_eval_suite._load_history(history)), 2)
            self.assertIn("VERIFIED_PASS", (Path(tmp) / "trend.html").read_text(encoding="utf-8"))

    def test_default_output_is_the_ignored_runs_folder(self) -> None:
        self.assertEqual(run_eval_suite.DEFAULT_OUTPUT, HERE / "output" / "behy")
        self.assertIn("output/behy/", (HERE / ".gitignore").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
