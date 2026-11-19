# -*- coding: utf-8 -*-
"""
Tests of the consistency check: the repository must pass and every rule must catch a planted defect.
Testy kontroly konzistence: repozitář musí projít a každé pravidlo musí zachytit podstrčenou vadu.

Usage / Použití:  python -m unittest -v test_check_consistency   (run inside nastroje/ / spustit v nastroje/)
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import check_consistency as cc
import sync_prompt_core


class RepositoryTests(unittest.TestCase):
    def test_repository_is_consistent_with_the_canon(self) -> None:
        self.assertEqual(cc.run().errors, [])

    def test_canon_budgets_sum_to_total(self) -> None:
        canon = json.loads(cc.CANON_PATH.read_text(encoding="utf-8"))
        self.assertEqual(sum(a["budget_usd"] for a in canon["agents"]), canon["budget_total_usd"])
        self.assertEqual(len(canon["agents"]), 20)

    def test_prompt_core_sync_is_idempotent(self) -> None:
        self.assertEqual(sync_prompt_core.main(["--check"]), 0)


class RuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.canon = json.loads(cc.CANON_PATH.read_text(encoding="utf-8"))
        self.path = cc.ROOT / "oddeleni" / "planted.md"  # never written to disk / nikdy se nezapisuje na disk

    def errors(self, function, text: str, *extra) -> list[str]:
        report = cc.Report()
        function(self.path, text, self.canon, *extra, report)
        return report.errors

    def test_forbidden_terms_are_caught(self) -> None:
        for planted in ("centrální sklad `CZ-101+`", "operace DownloadMessage", "obrana CA-MEL", "8směrný router",
                        "ČKAIT IE01", "librosa (MIT / BSD)", "konektor Mourek-Access", "server Albrechtice",
                        "spusť docker run nginx", "tým AI agentů", "vlákno #zakazky"):
            self.assertTrue(self.errors(cc.check_forbidden, planted, True), planted)

    def test_legal_numbers_and_standard_designations_are_caught(self) -> None:
        # EN: The blueprint names areas only; statute numbers, sections and standards are loaded after deployment.
        # CZ: Návod jmenuje jen oblasti; čísla předpisů, paragrafy a normy se načítají až po nasazení.
        for planted in ("podle zák. č. 250/2021 Sb.", "montér § 6", "dle § 316 odst. 2", "ČSN EN IEC 61439-1 ed. 3",
                        "výpočet dle IEC TR 60890", "nařízení (EU) 2023/1542", "směrnice 2014/35/EU", "čl. 28 GDPR",
                        "podpis dle eIDAS", "označení GPSR", "měření podle PPDS", "limit podle ZZVZ",
                        "osoba par6", "fitter_par6", "režim 92c", "SCRAP_92C_MISSING",
                        "pravidla flexinovely", "PRACOVNÍ PRÁVO, FLEXINOVELA A JMHZ"):
            self.assertTrue(self.errors(cc.check_forbidden, planted, True), planted)
        self.assertTrue(self.errors(cc.check_forbidden, "tým AI v balíčku", False))
        self.assertEqual(self.errors(cc.check_forbidden, "kód GS1 AI 21", False), [])
        for allowed in ("předplatné ČSN Online", "normy ČSN z normové báze", "čl. 5 této smlouvy", "GDPR", "RFC 3161",
                        "platná norma pro rozváděče nízkého napětí", "pracovněprávní předpisy", "300 hodin u dohod"):
            self.assertFalse(self.errors(cc.check_forbidden, allowed, True), allowed)

    def test_unknown_zone_and_wrong_database_counts_are_caught(self) -> None:
        self.assertTrue(self.errors(cc.check_names, "služba běží v zóně app_interal"))
        self.assertFalse(self.errors(cc.check_names, "zóny dmz_edge, app_internal, data_vault a sandbox_airgap"))
        self.assertTrue(self.errors(cc.check_database_sets, "celkem `8` servisních databází"))
        self.assertTrue(self.errors(cc.check_database_sets, "servisních: keycloak, zulip, stalwart, chatwoot, umami"))
        self.assertFalse(self.errors(cc.check_database_sets, "`6` doménových a `9` servisních databází"))

    def test_legitimate_text_is_not_flagged(self) -> None:
        clean = ("Na hostiteli není nainstalován Docker (0× Docker); ai agent `17003` `spravce-site` používá Incus. "
                 "Soubor 02-METODIKA-ROZSIROVANI-FIRMY-POBOCKY-ODDELENI-AI-LIDE.md; licence `MIT / ISC`; kód `AI_DISCLOSURE_MISSING`; GS1 AI 21.")
        self.assertEqual(self.errors(cc.check_forbidden, clean, True), [])

    def test_wrong_agent_pairing_is_caught(self) -> None:
        self.assertTrue(self.errors(cc.check_agents, "kontroluje `15001` `normovac`"))
        self.assertTrue(self.errors(cc.check_agents, "17003 · Roman Hájek"))
        self.assertEqual(self.errors(cc.check_agents, "kontroluje `15002` `normovac` a 17004 · Roman Hájek"), [])

    def test_unknown_database_and_channel_are_caught(self) -> None:
        self.assertTrue(self.errors(cc.check_names, "tabulka v `db_sklad`"))
        self.assertTrue(self.errors(cc.check_names, "téma v #14-zakazky"))
        self.assertEqual(self.errors(cc.check_names, "`db_hr_lide`, `db_erp_lhutnik` a kanál #14-elektro-a-zakazky"), [])

    def test_foreign_version_is_caught(self) -> None:
        self.assertTrue(self.errors(cc.check_versions, "# Dokument · Verze 0.9"))
        self.assertEqual(self.errors(cc.check_versions, f"# Dokument · Verze {self.canon['version']}"), [])

    def test_markdown_structure_defects_are_caught(self) -> None:
        with tempfile.TemporaryDirectory(dir=cc.ROOT) as tmp:
            path = Path(tmp) / "planted.md"
            for planted in ("| a | b |\n| :--- | :--- |\n| jen jeden sloupec |\n", "```text\nneuzavřený blok\n",
                            "[odkaz](./neexistuje.md)\n", "první řádek\r\ndruhý řádek\n"):
                report = cc.Report()
                cc.check_structure(path, planted, report)
                self.assertTrue(report.errors, planted)
            report = cc.Report()
            cc.check_structure(path, "| a | b |\n| :--- | :--- |\n| 1 | 2 |\n\n[web](https://example.org)\n", report)
            self.assertEqual(report.errors, [])


if __name__ == "__main__":
    unittest.main()
