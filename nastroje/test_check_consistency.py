# -*- coding: utf-8 -*-
"""
Tests of the consistency check: the repository must pass and every rule must catch a planted defect.
Testy kontroly konzistence: repozitář musí projít a každé pravidlo musí zachytit podstrčenou vadu.

EN: Three layers. RepositoryTests - the real folder passes. RuleTests - every rule function catches its
    planted defect and leaves legitimate text alone. FullRunTests - the whole program is started on a
    temporary copy of the folder (outside Git, so the file-system fallback is exercised too): the clean
    copy gives the same result as the folder itself, the copy with planted defects ends with exit code 1
    and names every defect. Nothing is ever written into the folder itself.
CZ: Tři vrstvy. RepositoryTests - skutečná složka projde. RuleTests - každá funkce pravidla zachytí svou
    podstrčenou vadu a legitimní text nechá být. FullRunTests - celý program se spustí nad dočasnou kopií
    složky (mimo Git, takže se prověří i náhradní procházení souborů): čistá kopie dá stejný výsledek jako
    složka sama, kopie s podstrčenými vadami skončí návratovým kódem 1 a každou vadu jmenuje. Do složky
    samotné se nikdy nic nezapisuje.

Usage / Použití:  python -m unittest -v test_check_consistency
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import bump_version
import check_consistency as cc
import sync_prompt_core

NBSP = " "

# EN: One planted defect for every forbidden pattern of the canon. test_every_forbidden_rule_of_the_canon_
#     has_a_planted_defect fails when the canon gets a new rule without an example here.
# CZ: Jedna podstrčená vada ke každému zakázanému vzoru kanonu. Test
#     test_every_forbidden_rule_of_the_canon_has_a_planted_defect selže, když kanon dostane nové pravidlo
#     bez příkladu zde.
FORBIDDEN_EXAMPLES = (
    "centrální sklad `CZ-101+`",
    "označen kódem skladu `CZ-102`",
    "operace DownloadMessage",
    "endpoint ws.mojedatovka.cz",
    "obrana CA-MEL",
    "8směrný router",
    "osmisměrný router",
    "ČKAIT IE01",
    "autorizace TE01",
    "librosa (MIT / BSD)",
    "konektor Mourek-Access",
    "limit DPP (`12 000 Kč` / `300 h`)",
    "server Albrechtice",
    "pobočka Děčín",
    "síť tail6ca0e4",
    "spusť docker run nginx",
    "docker compose up -d",
    "apt-get install -y docker.io",
    "tým AI agentů",
    "AI-first řešení",
    "vlákno #zakazky",
    "kanál #marketing",
    "přepínání oken v herdr",
    "podle zák. č. 250/2021 Sb.",
    "vyhlášeno pod č. 10/2010 Sb. m. s.",
    "montér § 6",
    "dle §316 odst. 2",
    "ČSN EN IEC 61439-1 ed. 3",
    "ČSN 33 2000",
    "výpočet dle IEC TR 60890",
    "systém podle ISO 9001",
    "podle EN 50110",
    "nařízení (EU) 2023/1542",
    "směrnice 2014/35/EU",
    "nařízení EU 2016/679",
    "čl. 28 GDPR",
    "čl. 6 odst. 1",
    "GDPR čl. 15",
    "rozváděč podle 61439",
    "novela Lex OZE",
    "pravidla flexinovely",
    "PRACOVNÍ PRÁVO, FLEXINOVELA A JMHZ",
    "podle EU ai Act",
    "ručení podle ZDPH",
    "podpis dle eIDAS",
    "označení GPSR",
    "měření podle PPDS",
    "limit podle ZZVZ",
    "osoba par6",
    "fitter_par6",
    "režim 92c",
    "SCRAP_92C_MISSING",
    "narozen 04.06.1969",
    "bytem Zázvorkova",
    "č. p. 1996/28",
)

LEGITIMATE_TEXT = (
    "Na hostiteli není nainstalován Docker (0× Docker); ai agent `17003` `spravce-site` používá Incus.",
    "Soubor 02-METODIKA-ROZSIROVANI-FIRMY-POBOCKY-ODDELENI-AI-LIDE.md; licence `MIT / ISC`; kód `AI_DISCLOSURE_MISSING`; GS1 AI 21.",
    "předplatné ČSN Online", "normy ČSN z normové báze", "čl. 5 této smlouvy", "GDPR", "RFC 3161",
    "platná norma pro rozváděče nízkého napětí", "pracovněprávní předpisy", "300 hodin u dohod",
    "limit DPP je `300 h` / `11 999 Kč`", "pobočka `CZ-101` a sklad `MAIN-101`", "operace MessageDownload",
    "8cestný router comm-gateway", "autorizace IE02 / TE03", "kanál #14-elektro-a-zakazky", "částka 1 250 Kč, 12 % DPH",
    "modul finance-uol-marze-engine", "splatnost 14 dnů, odstavec 3 této smlouvy", "telefon 2024/25", "ID 614390",
)


def load_canon() -> dict:
    return json.loads(cc.CANON_PATH.read_text(encoding="utf-8"))


class RepositoryTests(unittest.TestCase):
    def test_repository_is_consistent_with_the_canon(self) -> None:
        self.assertEqual(cc.run().errors, [])

    def test_canon_budgets_sum_to_total(self) -> None:
        canon = load_canon()
        self.assertEqual(sum(a["budget_usd"] for a in canon["agents"]), canon["budget_total_usd"])
        self.assertEqual(len(canon["agents"]), canon["documents"]["agent_cards"])

    def test_prompt_core_sync_is_idempotent(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sync_prompt_core.main(["--check"]), 0)

    def test_every_text_file_is_checked_whatever_its_suffix(self) -> None:
        checked = {cc.rel(path) for path in cc.all_files()}
        for expected in ("README.md", ".gitignore", ".gitattributes", "nastroje/pre-commit", "nastroje/kanon.json",
                         "nastroje/build_org_pdfs.py", "balicky/ci-gitea-actions-priklad.yml",
                         "balicky/S3-konfigurator-a-tarify/konfigurator.html", "balicky/S3-konfigurator-a-tarify/cenik.json",
                         "balicky/S1-generator-cistopisu/requirements.txt"):
            self.assertIn(expected, checked)
        self.assertFalse([name for name in checked if name.lower().endswith((".pdf", ".wav", ".pyc")) or "__pycache__" in name])
        # EN: Without Git the same files are found by walking the folder. / CZ: Bez Gitu se tytéž soubory najdou procházením složky.
        with mock.patch.dict(os.environ, {cc.NO_GIT_ENV: "1"}):
            walked = {cc.rel(path) for path in cc.all_files()}
        self.assertFalse(checked - walked)


class RuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.canon = load_canon()
        self.path = cc.ROOT / "oddeleni" / "planted.md"  # never written to disk / nikdy se nezapisuje na disk

    def errors(self, function, text: str, *extra, path: Path | None = None) -> list[str]:
        report = cc.Report()
        function(path or self.path, text, self.canon, *extra, report)
        return report.errors

    # --- forbidden terms / zakázané výrazy ---

    def test_every_forbidden_example_is_caught(self) -> None:
        for planted in FORBIDDEN_EXAMPLES:
            self.assertTrue(self.errors(cc.check_forbidden, planted, True), planted)

    def test_every_forbidden_rule_of_the_canon_has_a_planted_defect(self) -> None:
        for rule in self.canon["forbidden"]:
            pattern = re.compile(rule["pattern"])
            self.assertTrue(any(pattern.search(example) for example in FORBIDDEN_EXAMPLES),
                            f"add a planted defect for /{rule['pattern']}/ to FORBIDDEN_EXAMPLES")
            # EN: Every alternative of the pattern must have its own example (a dead alternative is a dead rule).
            # CZ: Každá alternativa vzoru musí mít vlastní příklad (mrtvá alternativa je mrtvé pravidlo).
            for example in FORBIDDEN_EXAMPLES:
                if pattern.search(example):
                    self.assertTrue(self.errors(cc.check_forbidden, example, True), example)

    def test_peppol_machine_identifiers(self) -> None:
        script = cc.ROOT / "nasazeni/test/finance/peppol/pravidla.sh"
        filename = "PEPPOL-EN16931-UBL.sch"
        self.assertEqual(self.errors(cc.check_forbidden, filename, False, path=script), [])
        self.assertTrue(self.errors(cc.check_forbidden, filename+" a EN 12345", False, path=script))
        self.assertTrue(self.errors(cc.check_forbidden, filename, True, path=cc.ROOT/"README.md"))

    def test_forbidden_term_is_caught_with_a_non_breaking_space(self) -> None:
        for planted in (f"montér §{NBSP}6", "montér §&nbsp;6", f"zák. č. 250/2021{NBSP}Sb.", f"ČSN{NBSP}EN 61439", f"docker{NBSP}run x",
                        "limit podle § 6", f"MIT{NBSP}/{NBSP}BSD"):
            self.assertTrue(self.errors(cc.check_forbidden, planted, True), repr(planted))

    def test_forbidden_scope_and_exemptions(self) -> None:
        scoped = [rule for rule in self.canon["forbidden"] if rule.get("scope") == "core"]
        for rule in scoped:
            example = next(e for e in FORBIDDEN_EXAMPLES if re.search(rule["pattern"], e))
            others = [r for r in self.canon["forbidden"] if r is not rule and re.search(r["pattern"], example)]
            if not others:
                self.assertEqual(self.errors(cc.check_forbidden, example, False), [], example)
        self.assertTrue(self.errors(cc.check_forbidden, "tým AI v balíčku", False))
        self.assertEqual(self.errors(cc.check_forbidden, "kód GS1 AI 21", False), [])
        # EN: Only the check itself, its tests and the canon may quote the forbidden terms.
        # CZ: Zakázané výrazy smí citovat jen kontrola sama, její testy a kanon.
        for exempt in ("nastroje/check_consistency.py", "nastroje/test_check_consistency.py", "nastroje/kanon.json"):
            self.assertEqual(self.errors(cc.check_forbidden, "montér § 6", False, path=cc.ROOT / exempt), [])
        for checked in ("nastroje/bump_version.py", "nastroje/pre-commit", "balicky/S2-eval-suite/reference_policy.py", "LICENSE"):
            self.assertTrue(self.errors(cc.check_forbidden, "montér § 6", False, path=cc.ROOT / checked), checked)

    def test_legitimate_text_is_not_flagged(self) -> None:
        for clean in LEGITIMATE_TEXT:
            self.assertEqual(self.errors(cc.check_forbidden, clean, True), [], clean)
            for function in (cc.check_agents, cc.check_names, cc.check_company, cc.check_versions, cc.check_database_sets):
                self.assertEqual(self.errors(function, clean), [], clean)

    # --- agents / agenti ---

    def test_wrong_agent_pairing_is_caught(self) -> None:
        for planted in ("kontroluje `15001` `normovac`", "kontroluje 15001 normovac", "`15001` (`normovac`)", "15001 – normovac",
                        "15001 · normovac", "**15001** **normovac**", "15001: normovac", f"15001{NBSP}normovac",
                        "`normovac` (`15001`)", "normovac (15001)", "agent pravni-specialista (`15002`)",
                        "17003 · Roman Hájek", "17003 Roman Hájek", "`17003` — Roman Hájek"):
            self.assertTrue(self.errors(cc.check_agents, planted), planted)
        for clean in ("kontroluje `15002` `normovac` a 17004 · Roman Hájek", "`normovac` (`15002`)", "| `15001` | `15002` normovac |",
                      "15001 a 15002 normovac", "spis 15001-normy", "agent 15001 schvaluje", "částka 15001 Kč",
                      "17004 Roman Hájek a Marek Kovář", "17004 · Roman Hájek, 11001 · Marek Kovář"):
            self.assertEqual(self.errors(cc.check_agents, clean), [], clean)

    def test_builder_agent_headings_must_match_the_canon(self) -> None:
        def problems(line: str) -> list[str]:
            report = cc.Report()
            cc.check_builder_agents("nastroje/build_org_pdfs.py", line, self.canon, report)
            return report.errors

        agent = self.canon["agents"][0]
        good = f'"{agent["id"]} · {agent["name"].upper()} (ai · {agent["sysid"]} · {agent["budget_usd"]} USD)"'
        self.assertEqual(problems(good), [])
        self.assertTrue(problems(good.replace(f'{agent["budget_usd"]} USD', f'{agent["budget_usd"] + 5} USD')))
        self.assertTrue(problems(good.replace(f'· {agent["sysid"]} ·', "· klicnik ·")))
        self.assertTrue(problems(good.replace(agent["name"].upper(), "JAN NOVÁK")))
        self.assertTrue(problems(good.replace(agent["id"], "19999")))
        # EN: An amount written in another way is an error, not a skipped line. / CZ: Jinak zapsaná částka je chyba, ne přeskočený řádek.
        budget = f'{agent["budget_usd"]} USD'
        for other in ("1.00 USD", f'{agent["budget_usd"]}.00 USD', f'{agent["budget_usd"]},00 USD', f'{agent["budget_usd"]} EUR',
                      f'{agent["budget_usd"]}{NBSP}USD měsíčně', "USD", f'0{agent["budget_usd"]}1 USD', f'${agent["budget_usd"]}'):
            self.assertTrue(problems(good.replace(budget, other)), other)
        self.assertEqual(problems(good.replace(budget, f'{agent["budget_usd"]}{NBSP}USD')), [])
        self.assertTrue(problems(good.replace(f' · {budget}', "")))                       # no amount / bez částky
        self.assertTrue(problems(good.replace(f'ai · {agent["sysid"]} · ', "ai · ")))     # no system id / bez systémového ID
        # EN: Every expected heading must be present. / CZ: Každý očekávaný nadpis musí být přítomen.
        everything = "\n".join(f'"{a["id"]} · {a["name"].upper()} (ai · {a["sysid"]} · {a["budget_usd"]} USD)"' for a in self.canon["agents"])
        report = cc.Report()
        cc.check_builder_agents("nastroje/build_org_pdfs.py", everything, self.canon, report, True)
        self.assertEqual(report.errors, [])
        report = cc.Report()
        cc.check_builder_agents("nastroje/build_org_pdfs.py", everything.split("\n", 1)[1], self.canon, report, True)
        self.assertEqual(len(report.errors), 1)
        self.assertIn(f'heading of agent {self.canon["agents"][0]["id"]} is missing', report.errors[0])
        self.assertIn("nastroje/build_org_pdfs.py", cc.BUILDERS_WITH_ALL_AGENT_HEADINGS)

    # --- names / názvy ---

    def test_unknown_database_channel_and_zone_are_caught(self) -> None:
        for planted in ("tabulka v `db_sklad`", "tabulka v db_sklad2", "schéma db_HR_lide", "db_erp_lhutnik2", "db_hr",
                        "téma v #14-zakazky", "kanál #99-neznamy", "kanál #14-Elektro-a-zakazky",
                        "služba běží v zóně app_interal", "zóna data_vault2", "zóna sandbox_air_gap", "dmz_Edge"):
            self.assertTrue(self.errors(cc.check_names, planted), planted)
        for clean in ("`db_hr_lide`, `db_erp_lhutnik` a kanál #14-elektro-a-zakazky", "zóny dmz_edge, app_internal, data_vault a sandbox_airgap",
                      "[kapitola](./README.md#14-zakazky)", "[kapitola](#12-neco-jineho)", "barva #112233", "pull request #12",
                      "odkaz https://example.org/#14-zakazky"):
            self.assertEqual(self.errors(cc.check_names, clean), [], clean)

    def test_names_are_checked_outside_markdown_too(self) -> None:
        for name in ("balicky/x/skript.py", "balicky/x/schema.sql", "balicky/x/modul.ts", "balicky/x/data.json", "balicky/x/Makefile"):
            path = cc.ROOT / name
            self.assertTrue(self.errors(cc.check_names, "SELECT * FROM db_sklad.t", path=path), name)
            self.assertTrue(self.errors(cc.check_names, "post to #14-zakazky", path=path), name)
            self.assertTrue(self.errors(cc.check_agents, "owner: 15001 normovac", path=path), name)
            self.assertTrue(self.errors(cc.check_versions, "# Polarita, Verze 0.9", path=path), name)
        # EN: Outside Markdown a zone-like identifier counts only on a line that speaks about a zone or network.
        # CZ: Mimo Markdown se identifikátor podobný zóně počítá jen na řádku, který mluví o zóně nebo síti.
        yaml = cc.ROOT / "balicky/x/konfigurace.yaml"
        self.assertTrue(self.errors(cc.check_names, "zone: app_interal", path=yaml))
        self.assertTrue(self.errors(cc.check_names, "network: data_vaults", path=yaml))
        self.assertEqual(self.errors(cc.check_names, "data_processing_agreement_signed: true", path=yaml), [])
        self.assertEqual(self.errors(cc.check_names, "data_dir = app_config.data_root", path=cc.ROOT / "balicky/x/skript.py"), [])

    # --- company / firma ---

    def test_company_identifiers_and_budget_cap_must_match_the_canon(self) -> None:
        company = self.canon["company"]
        total = self.canon["budget_total_usd"]
        for planted in ("IČO: 12345678", "IČ 12345678", "IČO `12345678`", f"IČO:{NBSP}12345678", "Polarita s.r.o., IČO **12345678**",
                        "DIČ: CZ12345678", "DIČ `CZ12345678`", "datová schránka `abc1234`", "ID schránky ISDS: `x9bbdva`",
                        f"celofiremní strop `{total + 10} USD`", f"měsíční strop je {total - 20} USD", f"stropem **{total + 30} USD**",
                        # EN: Shorter and longer wrong amounts, thousands separator, decimals. / CZ: Kratší i delší chybné částky, oddělovač tisíců, desetinná místa.
                        "celofiremní strop `70 USD`", f"strop 1{total} USD", f"strop je 1{NBSP}{total} USD", "FinOps strop 4 USD",
                        f"strop {total},50 USD", f"stropu {total}0 USD měsíčně", "strop 47 USD"):
            self.assertTrue(self.errors(cc.check_company, planted), planted)
        for clean in (f"IČO: {company['ico']}", f"DIČ: {company['dic']}", f"datová schránka `{company['isds']}`", "IČO: 00000000",
                      f"celofiremní strop `{total} USD`", "strop agenta je `35 USD`", "objednávka č. 12345678", "schránka `czebox`",
                      "limit 500 USD na nákup", "ISDS režim `PAUSED`",
                      f"strop {total} USD (85 + 15 %), podíl role 10 USD", f"<td>strop {total} USD</td><td>10 USD</td>",
                      "strop agentů 17005 a 17004 je 35 USD", f"strop je {total} USD"):
            self.assertEqual(self.errors(cc.check_company, clean), [], clean)
        # EN: Sample contracts of package S1 name fictitious counterparties. / CZ: Vzorové smlouvy S1 jmenují fiktivní protistrany.
        sample = cc.ROOT / "balicky/S1-generator-cistopisu/data/01-smlouva-o-dilo.json"
        self.assertEqual(self.errors(cc.check_company, '"objednatel_ico": "IČO: 12345678"', path=sample), [])
        self.assertTrue(self.errors(cc.check_company, f"strop {total + 10} USD", path=sample))

    def test_wrong_database_counts_are_caught(self) -> None:
        domain, service = len(self.canon["domain_databases"]), len(self.canon["service_databases"])
        for planted in (f"celkem `{service - 1}` servisních databází", f"{domain + 1} doménových databází",
                        f"**{service + 1}** dalších servisních databází", f"{service - 1}{NBSP}servisních databází",
                        "servisních: keycloak, zulip, stalwart, chatwoot, umami"):
            self.assertTrue(self.errors(cc.check_database_sets, planted), planted)
        self.assertEqual(self.errors(cc.check_database_sets, f"`{domain}` doménových a `{service}` servisních databází"), [])
        self.assertEqual(self.errors(cc.check_database_sets, "servisních: " + ", ".join(self.canon["service_databases"])), [])

    # --- versions / verze ---

    def test_foreign_version_is_caught_in_every_written_form(self) -> None:
        current = self.canon["version"]
        for planted in ("# Dokument · Verze 0.9", f"# Dokument · Verze {current}.1", "ve verzi 0.9", "od Verzi 0.9", "s verzí 0.9",
                        "VERZE 0.9", "Verze: 0.9", "Verze **0.9**", "verze `0.9`", f"Verze{NBSP}0.9", "Verze&nbsp;0.9", "Version 0.9",
                        "tag Polarita-0.9", "blueprint v0.9", "návrh v0.9", "Polarita-0.9.zip"):
            self.assertTrue(self.errors(cc.check_versions, planted), repr(planted))
        for clean in (f"# Dokument · Verze {current}", f"ve verzi **{current}**", f"tag Polarita-{current}", "Python 3.12", "TLS 1.3",
                      "PostgreSQL 16.4", "ceník verze sady", "protokol OCPP 1.6", "verze modelu se zapisuje do registru"):
            self.assertEqual(self.errors(cc.check_versions, clean), [], clean)
        allowed = cc.ROOT / self.canon["version_allowlist_files"][0]
        self.assertEqual(self.errors(cc.check_versions, "historie: Verze 0.9", path=allowed), [])

    # --- budgets and counts / rozpočty a počty ---

    def test_budget_and_count_defects_are_caught(self) -> None:
        def budget_errors(change) -> list[str]:
            canon = copy.deepcopy(self.canon)
            change(canon)
            report = cc.Report()
            cc.check_budgets(canon, report)
            return report.errors

        def count_errors(change) -> list[str]:
            canon = copy.deepcopy(self.canon)
            change(canon)
            report = cc.Report()
            cc.check_counts(canon, report)
            return report.errors

        baseline = budget_errors(lambda canon: None)
        agent_id = self.canon["agents"][3]["id"]
        cases = {
            "agent budgets sum": lambda canon: canon.__setitem__("budget_total_usd", 999),
            f"catalogue row of agent {agent_id}": lambda canon: canon["agents"][3].__setitem__("budget_usd", 1),
            f"personnel table row of agent {agent_id}": lambda canon: canon["agents"][3].__setitem__("budget_usd", 1),
            f"heading of agent {agent_id} does not match": lambda canon: canon["agents"][3].__setitem__("budget_usd", 1),
            "card heading does not match": lambda canon: canon["agents"][3].__setitem__("name", "Jan Novák"),
            f"card file of agent {agent_id} is missing or misnamed": lambda canon: canon["agents"][3].__setitem__("sysid", "jiny"),
            "heading names unknown agent": lambda canon: canon["agents"].pop(3),
        }
        for expected, change in cases.items():
            found = [e for e in budget_errors(change) if e not in baseline]
            self.assertTrue(any(expected in e for e in found), expected)

        count_baseline = count_errors(lambda canon: None)
        for key in self.canon["documents"]:
            found = [e for e in count_errors(lambda canon, key=key: canon["documents"].__setitem__(key, 99)) if e not in count_baseline]
            self.assertTrue(any(f"documents.{key}" in e for e in found), key)
        found = count_errors(lambda canon: canon["agents"].pop())
        self.assertTrue(any("but the canon lists" in e for e in found))
        found = count_errors(lambda canon: canon["documents"].__setitem__("core_pdf", self.canon["documents"]["core_pdf"] + 1))
        self.assertTrue(any("documents, canon says" in e for e in found))
        found = count_errors(lambda canon: canon["documents"].__setitem__("core_markdown", self.canon["documents"]["core_markdown"] + 1))
        self.assertTrue(any("× .md, canon says" in e for e in found))

    # --- prompt core / jádro promptu ---

    def test_prompt_core_personalization_is_really_applied(self) -> None:
        core = sync_prompt_core.load_core()
        generic = "\n".join(core)
        agents = {agent["sysid"]: agent for agent in self.canon["agents"]}
        self.assertEqual(set(sync_prompt_core.PERSONALIZATION), {"ceo", "klicnik", "pravni-specialista", "normovac", "zakazky", "ai-provoz"})
        for sysid, pairs in sync_prompt_core.PERSONALIZATION.items():
            personal = "\n".join(sync_prompt_core.personalize_core(core, agents[sysid]))
            self.assertNotEqual(personal, generic, sysid)
            for old, new in pairs:
                self.assertEqual(generic.count(old), 1, f"{sysid}: {old}")   # the phrase exists exactly once in the shared core
                self.assertNotIn(old, personal, sysid)                          # ... is gone from the personal core
                self.assertIn(new, personal, sysid)                             # ... and replaced by the personal wording
            card = sync_prompt_core.card_path(agents[sysid]).read_text(encoding="utf-8")
            for old, new in pairs:
                self.assertIn(new, card, f"card of {sysid} does not carry the personal wording (run sync_prompt_core.py)")
        # EN: An agent never escalates to itself or asks itself. / CZ: Agent nikdy neeskaluje sám sobě ani se neptá sám sebe.
        self.assertNotIn("eskaluj agentovi ceo", "\n".join(sync_prompt_core.personalize_core(core, agents["ceo"])))
        self.assertNotIn("nahlas agentovi klicnik", "\n".join(sync_prompt_core.personalize_core(core, agents["klicnik"])))
        self.assertNotIn("pravni-specialista /", "\n".join(sync_prompt_core.personalize_core(core, agents["pravni-specialista"])))
        self.assertNotIn("/ normovac", "\n".join(sync_prompt_core.personalize_core(core, agents["normovac"])))
        self.assertNotIn("agenta ceo", "\n".join(line for line in sync_prompt_core.personalize_core(core, agents["ceo"]) if "KDYŽ SELŽE KONTROLA" in line))
        self.assertNotIn("klicnik", "\n".join(line for line in sync_prompt_core.personalize_core(core, agents["klicnik"]) if "NEDŮVĚRYHODNÝ VSTUP" in line))
        # EN: No agent is told about itself in the third person. / CZ: Žádný agent o sobě nečte ve třetí osobě.
        for sysid in sync_prompt_core.PERSONALIZATION:
            personal = "\n".join(sync_prompt_core.personalize_core(core, agents[sysid]))
            self.assertNotRegex(personal, rf"agent\w* {re.escape(sysid)}(?![\w-])", sysid)
        # EN: Everybody else gets the shared core unchanged. / CZ: Všichni ostatní dostanou společné jádro beze změny.
        self.assertEqual(sync_prompt_core.personalize_core(core, agents["marketing"]), core)

    def test_identity_line_splits_the_share_into_quota_and_reserve(self) -> None:
        total = self.canon["budget_total_usd"]
        line = sync_prompt_core.identity_line({"id": "11001", "sysid": "ceo", "budget_usd": 35}, total)
        self.assertIn("podíl v rozpočtu je 35 USD, z toho provozní kvóta 85 % = 29,75 USD", line)
        self.assertIn("15 % jde do sdílené rezervy P1", line)
        self.assertIn(f"celofiremního stropu {total} USD", line)
        self.assertIn("= 17,00 USD", sync_prompt_core.identity_line({"id": "1", "sysid": "x", "budget_usd": 20}, total))
        self.assertIn("= 8,93 USD", sync_prompt_core.identity_line({"id": "1", "sysid": "x", "budget_usd": 10.5}, total))
        # EN: Quotas and reserve of all agents add up to the company-wide cap. / CZ: Kvóty a rezerva všech agentů dají celofiremní strop.
        shares = [sync_prompt_core.Decimal(str(agent["budget_usd"])) for agent in self.canon["agents"]]
        quotas = sum(share * sync_prompt_core.OPERATING_QUOTA_PCT / 100 for share in shares)
        reserve = sum(share * sync_prompt_core.RESERVE_PCT / 100 for share in shares)
        self.assertEqual(quotas + reserve, total)
        for agent in self.canon["agents"]:
            card = sync_prompt_core.card_path(agent).read_text(encoding="utf-8")
            self.assertIn(sync_prompt_core.identity_line(agent, total), card, agent["id"])
            self.assertEqual(self.errors(cc.check_company, sync_prompt_core.identity_line(agent, total)), [])

    def test_core_is_the_last_section_and_nothing_before_it_is_lost(self) -> None:
        core = sync_prompt_core.load_core()
        total = self.canon["budget_total_usd"]
        for agent in self.canon["agents"]:
            card = sync_prompt_core.card_path(agent).read_text(encoding="utf-8")
            rendered = sync_prompt_core.render(card, agent, core, total).split("\n")
            start = next(i for i, line in enumerate(rendered) if sync_prompt_core.CHAPTER4_RE.match(line))
            start = next(i for i in range(start, len(rendered)) if rendered[i].strip() == "```text")
            end = next(i for i in range(start + 1, len(rendered)) if rendered[i].strip() == "```")
            numbers = [int(m.group(1)) for m in map(sync_prompt_core.TOP_SECTION_RE.match, rendered[start:end]) if m]
            self.assertEqual(numbers, list(range(1, len(numbers) + 1)), agent["id"])       # 1..n without a gap or a repeat
            sections = [line for line in rendered[start:end] if sync_prompt_core.TOP_SECTION_RE.match(line)]
            self.assertRegex(sections[-1], sync_prompt_core.SECTION_RE, agent["id"])         # the core is last
            self.assertTrue(any("SMÍŠ BEZ DECISIONS" in line for line in sections[:-1]), agent["id"])
            before_core = card.split("\n")
            cut = next(i for i, line in enumerate(before_core) if sync_prompt_core.SECTION_RE.match(line))
            for line in before_core[:cut]:
                if line.strip() and not sync_prompt_core.LEGACY_RE.match(line):
                    self.assertIn(line, rendered, agent["id"])                               # nothing above the core is deleted
        # EN: A section after the core stops the run instead of being deleted.
        # CZ: Oddíl za jádrem běh zastaví, místo aby byl smazán.
        agent = self.canon["agents"][1]
        lines = sync_prompt_core.card_path(agent).read_text(encoding="utf-8").split("\n")
        cut = next(i for i, line in enumerate(lines) if sync_prompt_core.SECTION_RE.match(line))
        end = next(i for i in range(cut, len(lines)) if lines[i].strip() == "```")
        with_section_after = "\n".join(lines[:end] + ["", "99. DALŠÍ ODDÍL", "- pravidlo"] + lines[end:])
        with self.assertRaises(ValueError):
            sync_prompt_core.render(with_section_after, agent, core, total)

    def test_missing_personalization_phrase_is_a_clear_error(self) -> None:
        core = sync_prompt_core.load_core()
        for sysid, pairs in sync_prompt_core.PERSONALIZATION.items():
            for old, _ in pairs:
                damaged = [line.replace(old, "jiná formulace") for line in core]
                with self.assertRaises(ValueError) as raised:
                    sync_prompt_core.validate_personalization(damaged)
                self.assertIn(old, str(raised.exception))
                doubled = core + [f"- {old}"]
                with self.assertRaises(ValueError):
                    sync_prompt_core.validate_personalization(doubled)

    def test_sync_keeps_examples_and_refuses_to_delete_foreign_content(self) -> None:
        core = sync_prompt_core.load_core()
        ceo = next(a for a in self.canon["agents"] if a["sysid"] == "ceo")
        card = sync_prompt_core.card_path(ceo).read_text(encoding="utf-8")
        total = self.canon["budget_total_usd"]
        with_example_above = card.replace("## 4.", "## 3.5 Ukázka\n\n```text\nukázka\n```\n\n## 4.", 1)
        self.assertIn("```text\nukázka\n```", sync_prompt_core.render(with_example_above, ceo, core, total))
        # EN: A hand-written paragraph inside the generated section would be deleted silently - refuse instead.
        # CZ: Ručně psaný odstavec uvnitř generované sekce by se potichu smazal - místo toho odmítni.
        lines = card.split("\n")
        index = next(i for i, line in enumerate(lines) if sync_prompt_core.SECTION_RE.match(line))
        damaged = "\n".join(lines[:index + 2] + ["Ručně dopsaný odstavec, který není odrážkou jádra."] + lines[index + 2:])
        with self.assertRaises(ValueError):
            sync_prompt_core.render(damaged, ceo, core, total)

    def test_prompt_core_drift_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(cc.ROOT / "agenti-a-prompty", root / "agenti-a-prompty")
            agent = self.canon["agents"][5]
            card = sync_prompt_core.card_path(agent, root)
            core = sync_prompt_core.load_core(root)
            card.write_text(card.read_text(encoding="utf-8").replace(core[2], core[2] + " A něco navíc.", 1), encoding="utf-8")
            with mock.patch.object(cc, "ROOT", root):
                report = cc.Report()
                cc.check_prompt_core(self.canon, report)
            self.assertTrue(any(card.name in e and "shared prompt core differs" in e for e in report.errors), report.errors)

    # --- version bump / zvýšení verze ---

    def test_bump_canon_updates_uniquely(self) -> None:
        raw = '{"version": "2.7", "release_tag": "Polarita-2.7"}'
        updated = bump_version.bump_canon(raw, "2.7", "2.8")
        self.assertEqual(json.loads(updated), {"version": "2.8", "release_tag": "Polarita-2.8"})
        with self.assertRaises(RuntimeError):
            bump_version.bump_canon('{"version": "2.6"}', "2.7", "2.8")

    def test_bump_text_rewrites_exactly_what_the_check_recognises(self) -> None:
        text = (f"# Dokument · Verze 2.7\nve verzi **2.7**, Verze{NBSP}2.7, Version 2.7, tag Polarita-2.7, blueprint v2.7\r\n"
                "Python 2.7, TLS 2.7, Verze 12.7, Verze 2.70, Verze 2.7.1, cena 2.7 Kč\n")
        updated, count = bump_version.bump_text(text, "2.7", "3.0")
        self.assertEqual(count, 6)
        self.assertEqual(updated, (f"# Dokument · Verze 3.0\nve verzi **3.0**, Verze{NBSP}3.0, Version 3.0, tag Polarita-3.0, blueprint v3.0\r\n"
                                   "Python 2.7, TLS 2.7, Verze 12.7, Verze 2.70, Verze 2.7.1, cena 2.7 Kč\n"))
        self.assertEqual(self.errors(cc.check_versions, updated.replace("3.0", self.canon["version"]).split("Python")[0]), [])

    def test_bump_version_refuses_malformed_numbers(self) -> None:
        with mock.patch.object(bump_version, "bump_text", side_effect=AssertionError("must not rewrite anything")), \
                contextlib.redirect_stderr(io.StringIO()):
            for bad in ("02.9", "2.09", "2", "2.9.01", "2.9.1.2", "v2.9", "2,9", "", "2.9 "):
                self.assertEqual(bump_version.main([bad]), 2, bad)
            self.assertEqual(bump_version.main([]), 2)
            self.assertEqual(bump_version.main(["2.9", "3.0"]), 2)

    # --- Markdown structure / struktura Markdownu ---

    def structure_errors(self, text: str, name: str = "planted.md") -> list[str]:
        report = cc.Report()
        cc.check_structure(cc.ROOT / "oddeleni" / name, text, report)
        return report.errors

    def test_markdown_structure_defects_are_caught(self) -> None:
        for planted in ("| a | b |\n| :--- | :--- |\n| jen jeden sloupec |\n",
                        "a | b\n--- | ---\n1 | 2 | 3\n",                       # table without leading pipes / tabulka bez úvodních svislítek
                        "| a | b |\n|---|---|\n| 1 | 2 |\n| 1 |\n",
                        "```text\nneuzavřený blok\n", "~~~\nneuzavřený blok\n", "```\nkód\n~~~\n",
                        "první řádek\r\ndruhý řádek\n"):
            self.assertTrue(self.structure_errors(planted), repr(planted))
        for clean in ("| a | b |\n| :--- | :--- |\n| 1 | 2 |\n\n[web](https://example.org)\n", "a | b\n--- | ---\n1 | 2\n",
                      "| a | b |\n| --- | --- |\n| x \\| y | 2 |\n", "~~~\n| a |\n```\n~~~\n", "```\n[x](./neexistuje.md)\n```\n",
                      "řádek\r\nřádek\r\n", "text se svislítkem a | b bez tabulky\n"):
            self.assertEqual(self.structure_errors(clean), [], repr(clean))

    def test_broken_links_anchors_and_pdf_links_are_caught(self) -> None:
        charter = sorted((cc.ROOT / "oddeleni").glob("*.md"))[0].name
        pdfs = sorted(cc.known_pdfs())
        self.assertTrue(pdfs)
        root_pdf = next(name for name in pdfs if "/" not in name)
        for planted in ("[odkaz](./neexistuje.md)", '[odkaz](./neexistuje.md "titulek")', "[odkaz](<./neexistuje.md>)",
                        "[odkaz]: ./neexistuje.md", '<a href="./neexistuje.md">odkaz</a>', '<img src="./neexistuje.png">',
                        "![obrázek](./neexistuje.png)", "[odkaz](../readme.md)", f"[odkaz](./{charter.upper()})",
                        "[odkaz](../README.md#tato-kotva-neexistuje)", f"[odkaz](./{charter}#tato-kotva-neexistuje)",
                        "[odkaz](#tato-kotva-neexistuje)", "[odkaz](../neexistujici-kniha.pdf)", f"[odkaz](./{root_pdf})",
                        "[odkaz](../balicky/S1-generator-cistopisu/vystup/99-neexistuje.pdf)"):
            self.assertTrue(self.structure_errors(planted + "\n"), planted)
        for clean in (f"[odkaz](./{charter})", f'[odkaz](./{charter} "titulek")', "[odkaz](../README.md)", f"[odkaz](../{root_pdf})",
                      "[odkaz](https://example.org/neexistuje.md)", "[odkaz](mailto:info@example.org)", "[odkaz](../nastroje/)",
                      "[odkaz](../balicky/S1-generator-cistopisu/vystup/07-predzalobni-vyzva.pdf)"):
            self.assertEqual(self.structure_errors(clean + "\n"), [], clean)
        # EN: An anchor of a real heading of another file works; the same heading twice gets the suffix -1.
        # CZ: Kotva skutečného nadpisu jiného souboru funguje; tentýž nadpis podruhé dostane příponu -1.
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(cc, "ROOT", Path(tmp)):
            def own_anchor_errors(name: str, text: str) -> list[str]:
                path = Path(tmp) / name
                path.write_text(text, encoding="utf-8")
                report = cc.Report()
                cc.check_structure(path, text, report)
                return report.errors

            self.assertEqual(own_anchor_errors("a.md", "# A\n\n# A\n\n## Řízení `Decisions`\n\n[x](#a) [y](#a-1) [z](#řízení-decisions)\n"), [])
            self.assertTrue(own_anchor_errors("b.md", "# A\n\n[y](#a-1)\n"))
            self.assertTrue(own_anchor_errors("c.md", "```\n# Jen v kódu\n```\n\n[y](#jen-v-kódu)\n"))
            self.assertEqual(own_anchor_errors("d.md", '<a id="Vlastni-Kotva"></a>\n\n[y](#vlastni-kotva) [z](./a.md#a-1)\n'), [])
            self.assertTrue(own_anchor_errors("e.md", "[z](./a.md#a-2)\n"))
        self.assertEqual(cc.github_slug("3. Řízení `Decisions` – přehled (N8)"), "3-řízení-decisions--přehled-n8")

    # --- wiring / zapojení ---

    def test_check_file_runs_every_per_file_rule(self) -> None:
        total = self.canon["budget_total_usd"]
        text = ("# Podstrčeno · Verze 0.9\n\nmontér § 6\n\nkontroluje `15001` `normovac`\n\ntabulka `db_sklad`\n\nIČO: 12345678\n\n"
                f"strop {total + 10} USD\n\n`1` servisních databází\n\n[odkaz](./neexistuje.md)\n")
        report = cc.Report()
        cc.check_file(self.path, text, self.canon, True, report)
        for expected in ("version 0.9 differs", "forbidden term", "agent 15001 paired", "unknown database db_sklad", "company id 12345678",
                         "budget cap", "servisních databases", "broken relative link"):
            self.assertTrue(any(expected in e for e in report.errors), expected)
        # EN: Markdown structure is checked only in Markdown; the canon rules everywhere.
        # CZ: Struktura Markdownu se kontroluje jen v Markdownu; pravidla kanonu všude.
        report = cc.Report()
        cc.check_file(cc.ROOT / "balicky/x/skript.py", text, self.canon, False, report)
        self.assertFalse(any("broken relative link" in e for e in report.errors))
        self.assertTrue(any("forbidden term" in e for e in report.errors))

    def test_crowdsec_yaml_database_keys(self) -> None:
        report = cc.Report()
        path = cc.ROOT / "nasazeni/test/ochrana/config.yaml"
        cc.check_names(path, "db_config:\n  db_path: /var/db_sklad.sqlite", self.canon, report)
        self.assertEqual(len(report.errors), 1)
        self.assertIn("unknown database db_sklad", report.errors[0])

    def test_garage_storage_setting_and_database_values(self) -> None:
        report = cc.Report()
        path = cc.ROOT / "nasazeni/test/objekty/garage.toml"
        cc.check_names(path, 'db_engine = "sqlite"\ndata_dir = "/db_sklad"', self.canon, report)
        self.assertEqual(len(report.errors), 1)
        self.assertIn("unknown database db_sklad", report.errors[0])

    def test_main_exit_codes(self) -> None:
        clean, dirty = cc.Report(), cc.Report()
        dirty.error("x.md:1", "planted")
        dirty.warn("x.md", "warned")
        for report, arguments, code, shown in ((clean, [], 0, "0 errors"), (dirty, [], 1, "ERROR   x.md:1: planted"),
                                               (dirty, ["--warnings"], 1, "WARNING x.md: warned")):
            out = io.StringIO()
            with mock.patch.object(cc, "run", return_value=report), contextlib.redirect_stdout(out):
                self.assertEqual(cc.main(arguments), code)
            self.assertIn(shown, out.getvalue())
        with mock.patch.object(cc, "run", side_effect=AssertionError("must not run")), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cc.main(["--fix"]), 2)


class FullRunTests(unittest.TestCase):
    """The whole program on a temporary copy of the folder. / Celý program nad dočasnou kopií složky."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.copy = Path(cls.tmp.name) / "kopie"
        for path in cc._walk_files() if os.environ.get(cc.NO_GIT_ENV) == "1" else (cc._git_files() or cc._walk_files()):
            if path.is_file():
                target = cls.copy / cc.rel(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        # EN: The copy gets its agent cards synchronised with the shared prompt core, so that the planted
        #     drift of one card is told apart from cards that are waiting for a sync in the folder itself
        #     (that state is the business of RepositoryTests).
        # CZ: Kopie dostane karty agentů synchronizované se společným jádrem promptu, aby se podstrčená
        #     odchylka jedné karty odlišila od karet, které ve složce samotné čekají na synchronizaci
        #     (tento stav hlídají RepositoryTests).
        subprocess.run([sys.executable, str(cls.copy / "nastroje" / "sync_prompt_core.py")], capture_output=True, timeout=300,
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}, check=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def program(self, *arguments: str) -> tuple[int, str]:
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", cc.NO_GIT_ENV: "1"}
        done = subprocess.run([sys.executable, str(self.copy / "nastroje" / "check_consistency.py"), *arguments],
                              capture_output=True, text=True, encoding="utf-8", env=environment, cwd=self.tmp.name, timeout=300)
        return done.returncode, done.stdout + done.stderr

    def test_1_clean_copy_gives_the_same_result_as_the_folder(self) -> None:
        code, output = self.program()
        drift = "shared prompt core differs"
        expected = sorted(error for error in cc.run().errors if drift not in error)
        self.assertEqual(sorted(line[8:] for line in output.splitlines() if line.startswith("ERROR") and drift not in line), expected)
        self.assertNotIn(drift, output)
        self.assertEqual(code, 1 if expected else 0)
        self.assertIn(f"consistency check: {len(expected)} errors", output)
        self.assertEqual(self.program("--bogus")[0], 2)

    def test_2_planted_defects_end_with_exit_code_one_and_are_all_named(self) -> None:
        _, baseline = self.program()
        canon = load_canon()
        total = canon["budget_total_usd"]
        folder = self.copy / "balicky" / "podstrcene-vady"
        folder.mkdir()
        (folder / "vady.md").write_text(
            f"# Podstrčené vady · Verze{NBSP}0.9\n\n"
            f"montér §{NBSP}6 a `15001` (`normovac`), tabulka `db_sklad2`, kanál #14-zakazky, zóna app_interal.\n\n"
            f"IČO: 12345678, DIČ: CZ12345678, datová schránka `abc1234`, celofiremní strop `{total + 10} USD`.\n\n"
            "Celkem `1` servisních databází.\n\n"
            '[a](./neexistuje.md "titulek") [b](../../readme.md) [c](../../README.md#tato-kotva-neexistuje) [d](../../neexistuje.pdf)\n\n'
            "a | b\n--- | ---\n1 | 2 | 3\n\n~~~\nneuzavřený blok\n", encoding="utf-8")
        (folder / "skript.py").write_text("# Polarita-0.9\nDSN = 'db_sklad3'\nOWNER = '17003 · Roman Hájek'\n", encoding="utf-8")
        (folder / "schema.sql").write_text("-- podle zák. č. 250/2021 Sb.\n", encoding="utf-8")
        (folder / "konfigurace.yaml").write_text("zone: data_vaults\n", encoding="utf-8")
        (folder / "LICENSE").write_text("spusť docker run nginx\n", encoding="utf-8")
        (folder / "binarni.txt").write_bytes(b"\xff\xfe\x00 not utf-8")
        (self.copy / "oddeleni" / "navic.md").write_text(f"# Listina navíc · Verze {canon['version']}\n", encoding="utf-8")

        builder = self.copy / "nastroje" / "build_org_pdfs.py"
        agent = canon["agents"][0]
        heading = f"(ai · {agent['sysid']} · {agent['budget_usd']} USD)"
        builder_text = builder.read_text(encoding="utf-8")
        self.assertEqual(builder_text.count(heading), 1)
        builder.write_text(builder_text.replace(heading, f"(ai · {agent['sysid']} · {agent['budget_usd'] + 5} USD)"), encoding="utf-8")

        other = canon["agents"][7]
        card = next((self.copy / "agenti-a-prompty").glob(f"{other['id']}-*.md"))
        card_lines = card.read_text(encoding="utf-8").split("\n")
        core_line = next(i for i, line in enumerate(card_lines) if sync_prompt_core.SECTION_RE.match(line))
        card_lines[core_line + 1] += " A něco navíc."
        card.write_text("\n".join(card_lines), encoding="utf-8")

        canon_path = self.copy / "nastroje" / "kanon.json"
        damaged = copy.deepcopy(canon)
        damaged["budget_total_usd"] = total + 1
        damaged["release_tag"] = "Polarita-0.1"
        canon_path.write_text(json.dumps(damaged, ensure_ascii=False, indent=2), encoding="utf-8")

        code, output = self.program("--warnings")
        self.assertEqual(code, 1)
        new = [line for line in output.splitlines() if line.startswith("ERROR") and line not in baseline.splitlines()]
        where = "balicky/podstrcene-vady/"
        expected = (
            f"{where}vady.md:1: version 0.9 differs",
            f"{where}vady.md:3: forbidden term",
            f"{where}vady.md:3: agent 15001 paired with system id normovac",
            f"{where}vady.md:3: unknown database db_sklad2",
            f"{where}vady.md:3: unknown Zulip channel #14-zakazky",
            f"{where}vady.md:3: unknown network zone app_interal",
            f"{where}vady.md:5: company id 12345678 differs",
            f"{where}vady.md:5: VAT id CZ12345678 differs",
            f"{where}vady.md:5: data box id abc1234 differs",
            f"{where}vady.md:5: budget cap {total + 10} USD differs",
            f"{where}vady.md:7: states 1 servisních databases",
            f"{where}vady.md:9: broken relative link ./neexistuje.md",
            f"{where}vady.md:9: broken relative link ../../readme.md",
            f"{where}vady.md:9: broken anchor #tato-kotva-neexistuje",
            f"{where}vady.md:9: link to a PDF that no builder produces",
            f"{where}vady.md:13: table row has 3 columns, header has 2",
            f"{where}vady.md: unclosed code fence",
            f"{where}skript.py:1: version 0.9 differs",
            f"{where}skript.py:2: unknown database db_sklad3",
            f"{where}skript.py:3: name Roman Hájek paired with agent 17003",
            f"{where}schema.sql:1: forbidden term",
            f"{where}konfigurace.yaml:1: unknown network zone data_vaults",
            f"{where}LICENSE:1: forbidden term",
            f"{where}binarni.txt: file is not valid UTF-8",
            "nastroje/kanon.json: release_tag Polarita-0.1 differs",
            "nastroje/kanon.json: agent budgets sum to",
            "nastroje/kanon.json: documents.core_markdown",
            "nastroje/kanon.json: documents.department_charters",
            f"nastroje/build_org_pdfs.py:{builder_text[:builder_text.index(heading)].count(chr(10)) + 1}: heading of agent {agent['id']} does not match",
            f"agenti-a-prompty/{card.name}: shared prompt core differs",
        )
        for message in expected:
            self.assertTrue(any(message in line for line in new), f"not reported: {message}\n" + "\n".join(new))
        self.assertIn("WARNING", output)


if __name__ == "__main__":
    unittest.main()
