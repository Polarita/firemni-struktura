# -*- coding: utf-8 -*-
"""
Unit and integration tests of the Polarita Eval Suite runner (package S2, Version 2.8).
Jednotkové a integrační testy runneru Eval Suite Polarita (balíček S2, Verze 2.8).

Usage / Použití:  python -m unittest -v test_eval_suite
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import audio_fixtures
import build_dataset
import reference_policy
import run_eval_suite

HERE = Path(__file__).resolve().parent
DATASET = HERE / "eval_suite_polarita_extended.json"


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
        self.assertEqual(run_eval_suite.main(["--mode", "live", "--endpoint", "https://polarita.cz/eval/decide"]), 2)
        self.assertEqual(run_eval_suite.main(["--mode", "live", "--endpoint", "http://example.com/eval/decide"]), 2)
        run_eval_suite.validate_live_endpoint("https://decisions.int.polarita.cz/eval/decide")

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
        self.assertEqual(reference_policy.decide({**base, "actor_auth": "1001_yubikey"})["decision"], "ALLOW")


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
                self.assertEqual(run_eval_suite.main(["--mode", "live", "--endpoint", url, "--out-dir", tmp, "--no-audio"]), 0)
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

    def test_live_mode_requires_endpoint_and_survives_unreachable_gateway(self) -> None:
        self.assertEqual(run_eval_suite.main(["--mode", "live"]), 2)
        document = run_eval_suite.load_dataset(DATASET)
        report = run_eval_suite.run(document, "live", "base", "http://127.0.0.1:9/eval/decide", 1.0, None)
        self.assertEqual((report["passed"], report["verdict"]), (0, "FAIL"))


if __name__ == "__main__":
    unittest.main()
