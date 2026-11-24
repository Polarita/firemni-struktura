# -*- coding: utf-8 -*-
"""
Tests of the pricing kernel of package S3 (Version 3.2.2).
Testy cenového jádra balíčku S3 (Verze 3.2.2).

Usage / Použití:  python -m unittest -v test_pricing

EN: The test of the JavaScript kernel of the configurator runs it in Node.js or, if Node.js is missing,
    in a headless Chromium browser (variable POLARITA_PDF_BROWSER or a browser on the PATH). Without
    both it is skipped - unless POLARITA_REQUIRE_BROWSER=1 is set (CI), then it fails.
CZ: Test javascriptového jádra konfigurátoru je spouští v Node.js, nebo - chybí-li Node.js - v bezhlavém
    prohlížeči Chromium (proměnná POLARITA_PDF_BROWSER nebo prohlížeč na PATH). Bez obojího se přeskočí -
    pokud není nastaveno POLARITA_REQUIRE_BROWSER=1 (CI), pak selže.
"""

from __future__ import annotations

import contextlib
import copy
import html
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

import pricing


class PricingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.price_list = pricing.load_price_list()

    def test_price_list_approval_state_is_consistent(self) -> None:
        # EN: Either a proposal with no approver, or approved by 1001 with both dates filled in.
        # CZ: Buď návrh bez schvalovatele, nebo schváleno 1001 s vyplněnými oběma daty.
        meta = self.price_list["meta"]
        if meta["approved"]:
            self.assertEqual(meta["status"], "SCHVALENO_1001")
            self.assertEqual(meta["approved_by"], "1001")
            for key in ("approved_on", "valid_from"):
                self.assertRegex(meta[key] or "", r"^\d{4}-\d{2}-\d{2}$")
        else:
            self.assertEqual(meta["status"], "NAVRH_KE_SCHVALENI_1001")
            self.assertIsNone(meta["approved_by"])
            self.assertIsNone(meta["valid_from"])

    def test_whole_crowns_round_half_up_like_the_configurator(self) -> None:
        self.assertEqual(pricing._czk(Decimal("1415.5")), "1 416 Kč")
        self.assertEqual(pricing._czk(Decimal("1416.5")), "1 417 Kč")
        self.assertEqual(pricing._czk(Decimal("1415.49")), "1 415 Kč")
        template = pricing.TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertIn("const shifted = safe(safe(numerator) + divisor / 2);", template)
        self.assertIn("return (shifted - shifted % divisor) / divisor;", template)
        self.assertIn("const wholeCrowns = (hellers) => halfUp(hellers, 100);", template)

    def test_three_tariffs_and_three_turnkey_packages(self) -> None:
        self.assertEqual([t["code"] for t in self.price_list["mrr_tariffs"]], ["START_SVJ", "STANDARD_OBJEKT", "MAXI_AREAL_B2B"])
        self.assertEqual(len(self.price_list["turnkey_packages"]), 3)

    def test_monthly_fee_has_no_per_user_surcharge(self) -> None:
        tariff = self.price_list["mrr_tariffs"][0]
        expected = Decimal(tariff["base_monthly_per_object"]) * 2 + Decimal(tariff["extra_entrance_monthly"]) * 3
        self.assertEqual(pricing.monthly_fee(self.price_list, "START_SVJ", 2, 3), expected)
        self.assertEqual(pricing.annual_fee(self.price_list, "START_SVJ", 2, 3), expected * 12)

    def test_invalid_inputs_are_rejected(self) -> None:
        with self.assertRaises(pricing.PricingError):
            pricing.monthly_fee(self.price_list, "START_SVJ", 0)
        with self.assertRaises(pricing.PricingError):
            pricing.monthly_fee(self.price_list, "NEEXISTUJE", 1)
        with self.assertRaises(pricing.PricingError):
            pricing.package_range(self.price_list, "EV_WALLBOX", 0)
        with self.assertRaises(pricing.PricingError):
            pricing.labour_price(self.price_list, {"unknown_role": 1})

    def test_package_range_with_seasonal_coefficient(self) -> None:
        package = self.price_list["turnkey_packages"][0]
        low, high = pricing.package_range(self.price_list, package["code"], 2)
        self.assertEqual((low, high), (Decimal(package["price_from"]) * 2, Decimal(package["price_to"]) * 2))
        seasonal_low, _ = pricing.package_range(self.price_list, package["code"], 2, month=7)
        self.assertEqual(seasonal_low, (low * pricing.seasonal_coefficient(self.price_list, 7)).quantize(Decimal("0.01")))
        covered = sorted(m for band in self.price_list["seasonal_coefficients"] for m in band["months"])
        self.assertEqual(covered, list(range(1, 13)))  # every month exactly once / každý měsíc právě jednou

    def test_labour_price_applies_tariff_discount(self) -> None:
        hours = {"electrotechnician": 10, "revision_technician": 2}
        full = pricing.labour_price(self.price_list, hours)
        discounted = pricing.labour_price(self.price_list, hours, "MAXI_AREAL_B2B")
        discount = Decimal(self.price_list["mrr_tariffs"][2]["labour_discount_pct"]) / 100
        self.assertEqual(discounted, (full * (1 - discount)).quantize(Decimal("0.01")))

    def test_margin_hard_stop_below_minimum(self) -> None:
        minimum = Decimal(self.price_list["minimum_contribution_margin_pct"])
        below = pricing.margin_check(self.price_list, 100_000, 100_000 * (1 - (minimum - 1) / 100))
        border_below = pricing.margin_check(self.price_list, 100_000, 78_004)  # 21.996 % is shown as 21.99 %, never as 22.00 %
        at_minimum = pricing.margin_check(self.price_list, 100_000, 100_000 * (1 - minimum / 100))
        self.assertTrue(below["hard_stop"])
        self.assertEqual(border_below["contribution_margin_pct"], Decimal("21.99"))
        self.assertTrue(border_below["hard_stop"])
        self.assertFalse(at_minimum["hard_stop"])

    def test_partner_commission_stays_within_10_to_15_percent(self) -> None:
        for objects in (1, 4, 5, 9, 10, 250):
            pct = pricing.partner_commission_pct(self.price_list, objects)
            self.assertTrue(Decimal(10) <= pct <= Decimal(15), objects)
        self.assertEqual(pricing.partner_commission_pct(self.price_list, 0), Decimal(0))
        self.assertEqual(pricing.partner_commission(self.price_list, 20_000, 1), Decimal("2000.00"))

    def test_material_markup(self) -> None:
        markup = Decimal(100 + self.price_list["material_markup_pct"]) / 100
        self.assertEqual(pricing.material_price(self.price_list, 1000), (Decimal(1000) * markup).quantize(Decimal("0.01")))

    def test_public_price_list_excludes_internal_fields(self) -> None:
        pub = pricing.public_price_list(self.price_list)
        for secret_key in ("hourly_rates", "material_markup_pct", "minimum_contribution_margin_pct", "retention_pct", "partner_commission"):
            self.assertNotIn(secret_key, pub)
        self.assertNotIn("note", pub["meta"])
        self.assertIn("vat_rates", pub["meta"])

    def test_public_price_list_is_an_allowlist_on_every_level(self) -> None:
        # EN: A field added later to a tariff, package, season or the VAT block must not leak to the public page.
        # CZ: Pole později přidané k tarifu, balíčku, sezóně nebo bloku DPH nesmí uniknout na veřejnou stránku.
        tampered = copy.deepcopy(self.price_list)
        tampered["mrr_tariffs"][0]["internal_cost_monthly"] = 777123
        tampered["turnkey_packages"][0]["purchase_cost"] = 777124
        tampered["seasonal_coefficients"][0]["internal_note"] = "tajne-777125"
        tampered["meta"]["vat_rates"]["internal"] = 777126
        tampered["secret_block"] = {"x": 777127}
        public = json.dumps(pricing.public_price_list(tampered), ensure_ascii=False)
        for leaked in ("777123", "777124", "777125", "777126", "777127", "internal", "purchase_cost"):
            self.assertNotIn(leaked, public)
        self.assertEqual(pricing.public_price_list(tampered), pricing.public_price_list(self.price_list))

    def test_embedded_json_cannot_break_out_of_the_script_element(self) -> None:
        for text in ("</script><script>alert(1)</script>", "<!--<script>", "a & b > c", "x\u2028y\u2029z"):
            embedded = pricing.embed_json({"label": text})
            for char in ("<", ">", "&", "\u2028", "\u2029"):
                self.assertNotIn(char, embedded, text)
            self.assertEqual(json.loads(embedded), {"label": text})

    def test_invalid_price_list_is_rejected_when_loaded(self) -> None:
        def broken(change) -> bool:
            document = copy.deepcopy(self.price_list)
            change(document)
            try:
                pricing.validate_price_list(document)
            except pricing.PricingError:
                return True
            return False

        defects = {
            "negative base": lambda d: d["mrr_tariffs"][0].__setitem__("base_monthly_per_object", -1490),
            "text price": lambda d: d["mrr_tariffs"][0].__setitem__("base_monthly_per_object", "1490"),
            "bool price": lambda d: d["mrr_tariffs"][0].__setitem__("extra_entrance_monthly", True),
            "discount 150": lambda d: d["mrr_tariffs"][1].__setitem__("labour_discount_pct", 150),
            "discount negative": lambda d: d["mrr_tariffs"][1].__setitem__("labour_discount_pct", -5),
            "duplicate tariff": lambda d: d["mrr_tariffs"][1].__setitem__("code", "START_SVJ"),
            "package code __proto__": lambda d: d["turnkey_packages"][0].__setitem__("code", "__proto__"),
            "tariff code __proto__": lambda d: d["mrr_tariffs"][0].__setitem__("code", "__proto__"),
            "code with a space": lambda d: d["turnkey_packages"][0].__setitem__("code", "EV WALLBOX"),
            "code with a dot": lambda d: d["mrr_tariffs"][0].__setitem__("code", "START.SVJ"),
            "code starting with a digit": lambda d: d["turnkey_packages"][0].__setitem__("code", "1EV"),
            "code with a trailing newline": lambda d: d["turnkey_packages"][0].__setitem__("code", "EV_WALLBOX\n"),
            "code with a diacritic": lambda d: d["turnkey_packages"][0].__setitem__("code", "STOUPAČKY"),
            "code too long": lambda d: d["turnkey_packages"][0].__setitem__("code", "A" * 65),
            "no tariffs": lambda d: d.__setitem__("mrr_tariffs", []),
            "from above to": lambda d: d["turnkey_packages"][0].__setitem__("price_from", 96000),
            "zero package": lambda d: d["turnkey_packages"][0].__setitem__("price_from", 0),
            "three decimals": lambda d: d["turnkey_packages"][0].__setitem__("price_to", 95000.005),
            "month twice": lambda d: d["seasonal_coefficients"][1]["months"].append(1),
            "month missing": lambda d: d["seasonal_coefficients"][0]["months"].remove(2),
            "month 13": lambda d: d["seasonal_coefficients"][3]["months"].append(13),
            "zero coefficient": lambda d: d["seasonal_coefficients"][0].__setitem__("coefficient", 0),
            "negative coefficient": lambda d: d["seasonal_coefficients"][0].__setitem__("coefficient", -1.0),
            "nan coefficient": lambda d: d["seasonal_coefficients"][0].__setitem__("coefficient", float("nan")),
            "negative rate": lambda d: d["hourly_rates"]["designer"].__setitem__("rate", -1),
            "negative markup": lambda d: d.__setitem__("material_markup_pct", -15),
            "margin 122": lambda d: d.__setitem__("minimum_contribution_margin_pct", 122),
            "margin missing": lambda d: d.pop("minimum_contribution_margin_pct"),
            "retention swapped": lambda d: d.__setitem__("retention_pct", {"min": 10, "max": 5}),
            "tiers out of order": lambda d: d["partner_commission"]["tiers"].reverse(),
            "tier pct falls": lambda d: d["partner_commission"]["tiers"][2].__setitem__("pct", 5.0),
            "vat 121": lambda d: d["meta"]["vat_rates"].__setitem__("standard_pct", 121),
            "vat missing": lambda d: d["meta"]["vat_rates"].pop("residential_reduced_pct"),
            "approved without approver": lambda d: d["meta"].__setitem__("approved_by", None),
            "approved as text": lambda d: d["meta"].__setitem__("approved", "true"),
            "proposal with approver": lambda d: d["meta"].update(approved=False, status="NAVRH_KE_SCHVALENI_1001"),
            "prices with vat": lambda d: d["meta"].__setitem__("prices_exclude_vat", False),
            # EN: Dates are real calendar dates in the right order. / CZ: Data jsou skutečná kalendářní data ve správném pořadí.
            "month 99": lambda d: d["meta"].__setitem__("approved_on", "2026-99-99"),
            "30 February": lambda d: d["meta"].__setitem__("valid_from", "2027-02-30"),
            "date with time": lambda d: d["meta"].__setitem__("valid_from", "2026-11-15T00:00"),
            "date as number": lambda d: d["meta"].__setitem__("valid_from", 20261115),
            "valid before approval": lambda d: d["meta"].update(approved_on="2026-11-15", valid_from="2026-11-14"),
            "proposal with approval date": lambda d: d["meta"].update(approved=False, status="NAVRH_KE_SCHVALENI_1001",
                                                                       approved_by=None, valid_from=None),
            # EN: Domain bounds - checked before rounding, always a PricingError. / CZ: Doménové meze - před zaokrouhlením, vždy PricingError.
            "huge price": lambda d: d["turnkey_packages"][0].__setitem__("price_to", 10 ** 40),
            "huge float": lambda d: d["mrr_tariffs"][0].__setitem__("base_monthly_per_object", 1e300),
            "infinite rate": lambda d: d["hourly_rates"]["designer"].__setitem__("rate", float("inf")),
            "price above bound": lambda d: d["turnkey_packages"][0].__setitem__("price_to", 100_000_000.01),
            "coefficient above bound": lambda d: d["seasonal_coefficients"][0].__setitem__("coefficient", 10.5),
            "markup above bound": lambda d: d.__setitem__("material_markup_pct", 1001),
            # EN: Inside the bounds, but the public page could not compute it exactly in whole hellers.
            # CZ: Uvnitř mezí, ale veřejná stránka by to v celých haléřích nespočítala přesně.
            "unsafe package arithmetic": lambda d: (d["turnkey_packages"][0].update(price_to=99_000_000),
                                                    d["seasonal_coefficients"][0].__setitem__("coefficient", 9.5)),
            "not an object": lambda d: d.clear(),
        }
        for name, change in defects.items():
            self.assertTrue(broken(change), name)
        self.assertFalse(broken(lambda d: None))
        self.assertFalse(broken(lambda d: d["meta"].update(approved=False, status="NAVRH_KE_SCHVALENI_1001", approved_by=None,
                                                           approved_on=None, valid_from=None)))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cenik.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(pricing.PricingError):
                pricing.load_price_list(path)
            document = copy.deepcopy(self.price_list)
            document["material_markup_pct"] = -1
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(pricing.PricingError):
                pricing.load_price_list(path)
            with mock.patch.object(pricing, "PRICE_LIST_PATH", path), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(pricing.main(["--overview"]), 1)

    def test_fractional_values_are_exact_decimals(self) -> None:
        # EN: 22.1 as a binary float is 22.10000000000000142...; the limit must be exactly 22.1.
        # CZ: 22.1 jako dvojkové číslo je 22,10000000000000142...; mez musí být přesně 22,1.
        document = copy.deepcopy(self.price_list)
        document["minimum_contribution_margin_pct"] = 22.1
        document["material_markup_pct"] = 15.5
        document["meta"]["vat_rates"]["standard_pct"] = 21.5
        document["mrr_tariffs"][0]["base_monthly_per_object"] = 1490.1
        document["hourly_rates"]["designer"]["rate"] = 1190.1
        pricing.validate_price_list(document)
        at_limit = pricing.margin_check(document, 1000, 779)
        self.assertEqual((at_limit["minimum_pct"], at_limit["hard_stop"]), (Decimal("22.1"), False))
        self.assertTrue(pricing.margin_check(document, 100000, Decimal("77900.01"))["hard_stop"])
        self.assertEqual(pricing.material_price(document, 1000), Decimal("1155.00"))
        self.assertEqual(pricing.with_vat(document, 1000), Decimal("1215.00"))
        self.assertEqual(pricing.monthly_fee(document, "START_SVJ", 3), Decimal("4470.30"))
        self.assertEqual(pricing.labour_price(document, {"designer": 3}), Decimal("3570.30"))

    def test_offer_margin_is_checked_for_the_whole_offer(self) -> None:
        # EN: Labour 10 000 + material 11 500 (cost 10 000, markup 15 %), labour cost 5 000: the material
        #     line alone is below the minimum, the offer as a whole is above it.
        # CZ: Práce 10 000 + materiál 11 500 (nákup 10 000, přirážka 15 %), náklad práce 5 000: materiálový
        #     řádek sám je pod minimem, nabídka jako celek nad ním.
        material = pricing.material_price(self.price_list, 10_000)
        self.assertTrue(pricing.margin_check(self.price_list, material, 10_000)["hard_stop"])
        whole = pricing.offer_margin_check(self.price_list, 10_000, material, 15_000)
        self.assertEqual((whole["hard_stop"], whole["price_without_vat"], whole["contribution_margin_pct"]),
                         (False, Decimal("21500.00"), Decimal("30.23")))
        self.assertTrue(pricing.offer_margin_check(self.price_list, 2_000, material, 11_000)["hard_stop"])
        # EN: A pure material delivery is not priced by this matrix (e-shop price list).
        # CZ: Čistě materiálová dodávka se touto maticí nenaceňuje (ceník e-shopu).
        with self.assertRaises(pricing.PricingError):
            pricing.offer_margin_check(self.price_list, 0, material, 10_000)

    def test_extreme_values_end_as_pricing_error_naming_the_field(self) -> None:
        for value in (10 ** 40, -10 ** 40, 1e300, float("inf"), float("nan"), 10 ** 400):
            with self.assertRaises(pricing.PricingError) as caught:
                pricing._number(value, "turnkey_packages[X].price_to")
            self.assertIn("turnkey_packages[X].price_to", str(caught.exception), value)
        self.assertEqual(pricing._number(100_000_000, "x"), Decimal("100000000"))
        # EN: The command line prints the error and returns 1 - no traceback. / CZ: Příkazová řádka chybu vypíše a vrátí 1 - žádný traceback.
        with tempfile.TemporaryDirectory() as tmp:
            document = copy.deepcopy(self.price_list)
            document["hourly_rates"]["designer"]["rate"] = 10 ** 40
            path = Path(tmp) / "cenik.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            errors = io.StringIO()
            with mock.patch.object(pricing, "PRICE_LIST_PATH", path), contextlib.redirect_stderr(errors):
                self.assertEqual(pricing.main(["--overview"]), 1)
            self.assertIn("hourly_rates[designer].rate", errors.getvalue())

    def test_public_arithmetic_stays_inside_exact_integers(self) -> None:
        # EN: The fields of the page may not multiply by more than the kernel was checked for.
        # CZ: Pole stránky nesmějí násobit víc, než pro kolik bylo jádro ověřeno.
        template = pricing.TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertIn(f'id="objects" type="number" min="1" max="{pricing.PUBLIC_MAX_OBJECTS}"', template)
        self.assertIn(f'id="entrances" type="number" min="0" max="{pricing.PUBLIC_MAX_ENTRANCES}"', template)
        self.assertIn(f'quantity.max = "{pricing.PUBLIC_MAX_QUANTITY}"', template)
        self.assertEqual(len(re.findall(r'\bmax\s*=\s*"', template)), 3)
        public = pricing.public_price_list(self.price_list)
        for entry in public["mrr_tariffs"] + public["turnkey_packages"] + public["seasonal_coefficients"]:
            for key, value in entry.items():
                if key.endswith(("_hellers", "_e4")):
                    self.assertIs(type(value), int, key)
                else:
                    self.assertNotIsInstance(value, float, key)
        self.assertEqual(public["meta"]["vat_rates"]["standard_bp"], int(Decimal(str(self.price_list["meta"]["vat_rates"]["standard_pct"])) * 100))
        self.assertEqual(public["mrr_tariffs"][0]["base_monthly_per_object_hellers"],
                         int(Decimal(str(self.price_list["mrr_tariffs"][0]["base_monthly_per_object"])) * 100))

    def test_offer_margin_is_judged_over_the_amounts_of_the_offer(self) -> None:
        # EN: 100.004 + 0 is offered as 100.00; with costs 78.003 that is 21.997 % - below the minimum of 22 %.
        # CZ: 100,004 + 0 se nabízí jako 100,00; s náklady 78,003 je to 21,997 % - pod minimem 22 %.
        day = date(2026, 12, 1)
        result = pricing.offer_margin_check(self.price_list, Decimal("100.004"), 0, Decimal("78.003"), day)
        self.assertEqual((result["price_without_vat"], result["hard_stop"], result["contribution_margin_pct"]),
                         (Decimal("100.00"), True, Decimal("21.99")))
        # EN: The price is the sum of the two rounded lines, exactly as they stand in the offer.
        # CZ: Cena je součet dvou zaokrouhlených řádků, přesně jak stojí v nabídce.
        lines = pricing.offer_margin_check(self.price_list, Decimal("100.004"), Decimal("50.004"), 100, day)
        self.assertEqual(lines["price_without_vat"], Decimal("150.00"))
        self.assertFalse(pricing.offer_margin_check(self.price_list, 100, 0, 78, day)["hard_stop"])
        with self.assertRaises(pricing.PricingError):
            pricing.offer_margin_check(self.price_list, Decimal("0.004"), 0, 0, day)
        # EN: Labour that rounds to 0.00 is no labour: the offer is a pure material delivery.
        # CZ: Práce, která se zaokrouhlí na 0,00, není práce: nabídka je čistě materiálová dodávka.
        for labour in (Decimal("0.001"), Decimal("0.004"), Decimal("0.0049")):
            with self.assertRaises(pricing.PricingError) as caught:
                pricing.offer_margin_check(self.price_list, labour, 100, 75, day)
            self.assertIn("without labour", str(caught.exception))
        self.assertEqual(pricing.offer_margin_check(self.price_list, Decimal("0.005"), 100, 75, day)["price_without_vat"], Decimal("100.01"))

    def test_binding_offer_requires_a_price_list_in_effect_on_the_offer_date(self) -> None:
        valid_from = date.fromisoformat(self.price_list["meta"]["valid_from"])
        pricing.require_approved(self.price_list, valid_from)
        pricing.offer_margin_check(self.price_list, 10_000, 0, 5_000, valid_from)
        for call in (lambda: pricing.require_approved(self.price_list, valid_from - timedelta(days=1)),
                     lambda: pricing.offer_margin_check(self.price_list, 10_000, 0, 5_000, valid_from - timedelta(days=1)),
                     lambda: pricing.require_approved(self.price_list, "2027-01-01"),
                     # EN: A date with time is refused as a PricingError, never a TypeError. / CZ: Datum s časem se odmítne jako PricingError, nikdy TypeError.
                     lambda: pricing.require_approved(self.price_list, datetime.combine(valid_from, datetime.min.time())),
                     lambda: pricing.offer_margin_check(self.price_list, 10_000, 0, 5_000, datetime(2027, 1, 1, 12, 0))):
            with self.assertRaises(pricing.PricingError):
                call()
        # EN: Approved today, valid from a future day: not usable today (the default offer date).
        # CZ: Schváleno dnes, platné od budoucího dne: dnes (výchozí datum nabídky) nepoužitelné.
        future = copy.deepcopy(self.price_list)
        future["meta"].update(approved_on=date.today().isoformat(), valid_from=(date.today() + timedelta(days=30)).isoformat())
        pricing.validate_price_list(future)
        with self.assertRaises(pricing.PricingError):
            pricing.require_approved(future)
        with self.assertRaises(pricing.PricingError):
            pricing.offer_margin_check(future, 10_000, 0, 5_000)
        pricing.offer_margin_check(future, 10_000, 0, 5_000, date.today() + timedelta(days=30))
        # EN: A document that skipped validation is still checked. / CZ: Dokument, který minul validaci, se přesto kontroluje.
        future["meta"]["valid_from"] = "2026-99-99"
        with self.assertRaises(pricing.PricingError):
            pricing.require_approved(future, date(2099, 1, 1))

    def test_binding_offer_requires_an_approved_price_list(self) -> None:
        pricing.require_approved(self.price_list)
        proposal = copy.deepcopy(self.price_list)
        proposal["meta"].update(approved=False, status="NAVRH_KE_SCHVALENI_1001", approved_by=None, approved_on=None, valid_from=None)
        pricing.validate_price_list(proposal)
        with self.assertRaises(pricing.PricingError):
            pricing.require_approved(proposal)
        with self.assertRaises(pricing.PricingError):
            pricing.offer_margin_check(proposal, 10_000, 0, 5_000)

    def test_with_vat_rates(self) -> None:
        self.assertEqual(pricing.with_vat(self.price_list, 1000), Decimal("1210.00"))
        self.assertEqual(pricing.with_vat(self.price_list, 1000, reduced_residential=True), Decimal("1120.00"))

    def test_month_zero_and_out_of_range_are_rejected(self) -> None:
        for bad_month in (0, 13, -1):
            with self.assertRaises(pricing.PricingError):
                pricing.package_range(self.price_list, "EV_WALLBOX", 1, month=bad_month)
        with self.assertRaises(pricing.PricingError):
            pricing.material_price(self.price_list, -1)
        with self.assertRaises(pricing.PricingError):
            pricing.margin_check(self.price_list, 1000, -1)

    def test_boolean_and_nan_inputs_are_rejected(self) -> None:
        with self.assertRaises(pricing.PricingError):
            pricing.monthly_fee(self.price_list, "START_SVJ", True)  # type: ignore[arg-type]
        with self.assertRaises(pricing.PricingError):
            pricing.labour_price(self.price_list, {"electrotechnician": True})  # type: ignore[dict-item]
        with self.assertRaises(pricing.PricingError):
            pricing.material_price(self.price_list, float("nan"))

    def test_built_configurator_embeds_current_price_list(self) -> None:
        # konfigurator.html must be regenerated after every change of cenik.json and embed only public_price_list.
        # konfigurator.html se musí přegenerovat po každé změně cenik.json a smí obsahovat jen public_price_list.
        page = pricing.CONFIGURATOR_PATH.read_text(encoding="utf-8")
        pub = pricing.public_price_list(self.price_list)
        expected_embedded = pricing.embed_json(pub)
        self.assertEqual(page, pricing.TEMPLATE_PATH.read_text(encoding="utf-8").replace("/*__PRICE_LIST_JSON__*/", expected_embedded))
        match = re.search(r"const PRICE_LIST = (\{.*?\});\n", page, flags=re.DOTALL)
        self.assertIsNotNone(match)
        self.assertEqual(json.loads(match.group(1)), pub)
        self.assertEqual(page.count("<script"), 1)
        for forbidden in ("hourly_rates", "material_markup_pct", "minimum_contribution_margin_pct", "retention_pct", "partner_commission", "14005"):
            self.assertNotIn(forbidden, page)
        self.assertEqual(pricing.OVERVIEW_PATH.read_text(encoding="utf-8"), pricing.render_overview(self.price_list))


def _run_javascript(script: str) -> str | None:
    """
    EN: Run a script that ends by calling emit(text) and return the text; None when neither Node.js nor
        a Chromium browser is available.
    CZ: Spustí skript, který končí voláním emit(text), a vrátí ten text; None, když není k dispozici
        Node.js ani prohlížeč Chromium.
    """
    node = shutil.which("node") or shutil.which("nodejs")
    with tempfile.TemporaryDirectory() as tmp:
        if node:
            path = Path(tmp) / "kernel.js"
            path.write_text("const emit = (text) => console.log(text);\n" + script, encoding="utf-8")
            return subprocess.run([node, str(path)], capture_output=True, text=True, timeout=60, check=True).stdout.strip()
        candidates = [os.environ.get("POLARITA_PDF_BROWSER", ""), "chromium", "chromium-browser", "google-chrome",
                      "google-chrome-stable", "chrome", "msedge", "microsoft-edge"]
        browser = next((found for found in (shutil.which(name) for name in candidates if name) if found), None)
        if not browser:
            return None
        page = Path(tmp) / "kernel.html"
        page.write_text('<!DOCTYPE html><meta charset="utf-8"><pre id="out"></pre><script>\n'
                        'const emit = (text) => { document.getElementById("out").textContent = text; };\n'
                        + script + "\n</script>", encoding="utf-8")
        command = [browser, "--headless=new", "--disable-gpu", "--disable-extensions", "--host-resolver-rules=MAP * ~NOTFOUND",
                   f"--user-data-dir={Path(tmp) / 'profile'}", "--dump-dom", page.as_uri()]
        dom = subprocess.run(command, capture_output=True, text=True, timeout=120, check=True).stdout
        match = re.search(r'<pre id="out">(.*?)</pre>', dom, flags=re.DOTALL)
        return html.unescape(match.group(1)) if match else ""


class ConfiguratorKernelTests(unittest.TestCase):
    """The JavaScript of the public page must compute exactly like pricing.py. / JavaScript veřejné stránky musí počítat přesně jako pricing.py."""

    def setUp(self) -> None:
        self.price_list = pricing.load_price_list()
        self.template = pricing.TEMPLATE_PATH.read_text(encoding="utf-8")

    def kernel(self) -> str:
        match = re.search(r"// KERNEL-START\n(.*?)// KERNEL-END", self.template, flags=re.DOTALL)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_kernel_is_free_of_page_access_and_fixed_rates(self) -> None:
        kernel = self.kernel()
        for forbidden in ("document", "byId(", "PRICE_LIST", "window", "fetch"):
            self.assertNotIn(forbidden, kernel)
        # EN: VAT labels come from vat_rates; no rate is written into the page by hand.
        # CZ: Popisky DPH vycházejí z vat_rates; žádná sazba není do stránky vepsána ručně.
        script = self.template[self.template.index("<script>"):]
        self.assertNotRegex(script, r"\d\s*%")
        self.assertNotRegex(self.template, r"\d\s*%\s*(?:DPH|\))")
        self.assertEqual(self.template.count("pctLabel(vat."), 4)
        # EN: The value used in the calculation is written back to the field; nothing is sent anywhere.
        # CZ: Hodnota použitá ve výpočtu se zapisuje zpět do pole; nic se nikam neodesílá.
        self.assertIn("input.value = String(clampInt(input))", self.template)
        for forbidden in ("fetch(", "XMLHttpRequest", "sendBeacon", "<form", "localStorage", "innerHTML", "eval("):
            self.assertNotIn(forbidden, self.template)

    def test_codes_named_like_object_members_keep_parity_with_pricing_py(self) -> None:
        # EN: Codes that are members of every plain JavaScript object ("constructor", "toString", ...) pass the
        #     safe pattern; the page keeps quantities in a Map, so their totals equal pricing.py - also when
        #     nothing is chosen. A code outside the pattern ("__proto__") is refused on both sides.
        # CZ: Kódy, které jsou členy každého obyčejného objektu JavaScriptu („constructor“, „toString“, ...),
        #     bezpečným vzorem projdou; stránka drží množství v Map, takže jejich součty odpovídají pricing.py -
        #     i když není vybráno nic. Kód mimo vzor („__proto__“) se odmítne na obou stranách.
        kernel = self.kernel()
        self.assertIn("/^" + pricing.SAFE_CODE_PATTERN + "$/", kernel)
        self.assertIn("packages: new Map()", self.template)
        self.assertNotIn("packages: {}", self.template)
        self.assertNotRegex(self.template, r"state\.packages\[")
        document = copy.deepcopy(self.price_list)
        codes = ["constructor", "toString", "hasOwnProperty"]
        for package, code in zip(document["turnkey_packages"], codes):
            package["code"] = code
        pricing.validate_price_list(document)
        public = pricing.public_price_list(document)
        month = 7
        selections = [[], [["constructor", 3]], [["toString", 1], ["hasOwnProperty", 200]],
                      [["constructor", 2], ["toString", 5], ["hasOwnProperty", 7]], [["constructor", 4], ["constructor", 0]]]
        expected_totals = []
        for selection in selections:
            final = dict(selection)   # the last quantity of a code wins / platí poslední množství kódu
            ranges = [pricing.package_range(document, code, quantity, month) for code, quantity in final.items() if quantity > 0]
            expected_totals.append({"from": str(int(sum((r[0] for r in ranges), Decimal(0)) * 100)),
                                    "to": str(int(sum((r[1] for r in ranges), Decimal(0)) * 100)),
                                    "chosen": [[code, final[code]] for code in codes if final.get(code, 0) > 0]})
        for bad in ("__proto__", "", "a b", "1A", "A" * 65, "EV-WALLBOX"):
            broken = copy.deepcopy(self.price_list)
            broken["turnkey_packages"][0]["code"] = bad
            with self.assertRaises(pricing.PricingError, msg=bad):
                pricing.validate_price_list(broken)
        expected = {"totals": expected_totals, "refused": ["RangeError"] * 8, "accepted": ["ok"] * 3,
                    "prototype_untouched": True}
        script = (
            f"const P = {json.dumps(public)};\n" + kernel +
            f"const selections = {json.dumps(selections)};\n"
            "const kind = (run) => { try { run(); return 'ok'; } catch (e) { return e.name; } };\n"
            "const forged = JSON.parse(JSON.stringify(P)); forged.turnkey_packages[0].code = '__proto__';\n"
            "const refused = [() => setQuantity(new Map(), '__proto__', 1), () => setQuantity(new Map(), '', 1),\n"
            "  () => setQuantity(new Map(), 'a b', 1), () => setQuantity(new Map(), '1A', 1), () => setQuantity(new Map(), 'A'.repeat(65), 1),\n"
            "  () => setQuantity(new Map(), 'EV-WALLBOX', 1), () => setQuantity(new Map(), 7, 1),\n"
            "  () => packagesTotal(forged, new Map(), 7)].map(kind);\n"
            "const accepted = ['constructor', 'A'.repeat(64), 'a_1'].map((code) => kind(() => setQuantity(new Map(), code, 1)));\n"
            "emit(JSON.stringify({\n"
            "  totals: selections.map((selection) => {\n"
            "    const quantities = new Map(); selection.forEach(([code, quantity]) => setQuantity(quantities, code, quantity));\n"
            f"    const total = packagesTotal(P, quantities, {month});\n"
            "    return { from: String(total.from), to: String(total.to), chosen: total.chosen };\n"
            "  }),\n"
            "  refused: refused, accepted: accepted,\n"
            "  prototype_untouched: Object.getPrototypeOf({}) === Object.prototype && typeof ({}).toString === 'function',\n"
            "}));\n")
        output = _run_javascript(script)
        if output is None:
            if os.environ.get("POLARITA_REQUIRE_BROWSER") == "1":
                self.fail("POLARITA_REQUIRE_BROWSER=1 and neither Node.js nor a Chromium browser found")
            self.skipTest("neither Node.js nor a Chromium browser available / není dostupný Node.js ani prohlížeč Chromium")
        self.assertEqual(json.loads(output), expected)

    def test_kernel_computes_like_pricing_py(self) -> None:
        document = copy.deepcopy(self.price_list)
        # EN: Values that expose float arithmetic (1003.50 x 1.21 = 1214.235) and fractional rates.
        # CZ: Hodnoty, které odhalí dvojkovou aritmetiku (1003,50 x 1,21 = 1214,235) i desetinné sazby.
        document["mrr_tariffs"][0].update(base_monthly_per_object=1003.5, extra_entrance_monthly=0.07)
        document["turnkey_packages"][0].update(price_from=38000.33, price_to=95000.55)
        document["seasonal_coefficients"][0]["coefficient"] = 0.9333
        document["meta"]["vat_rates"].update(standard_pct=21, residential_reduced_pct=12.5)
        # EN: The largest amounts the validation still lets through at the largest multipliers of the page.
        # CZ: Největší částky, které validace ještě pustí, při největších násobitelích stránky.
        document["mrr_tariffs"][2].update(base_monthly_per_object=9_999_999.99, extra_entrance_monthly=9_999_999.99)
        document["turnkey_packages"][2].update(price_from=30_000_000.01, price_to=30_000_000.03)
        pricing.validate_price_list(document)
        public = pricing.public_price_list(document)
        fee_cases = [(code, objects, entrances) for code in ("START_SVJ", "STANDARD_OBJEKT", "MAXI_AREAL_B2B")
                     for objects, entrances in ((1, 0), (3, 4), (7, 13), (200, 500))]
        package_cases = [(code, quantity, month) for code in ("EV_WALLBOX", "STOUPACKY_HER", "FVE_BESS")
                         for quantity in (1, 3, 200) for month in (1, 2, 5, 7, 12)]
        vat_amounts = ["1003.50", "0.01", "0.05", "1415.50", "33.33", "999999.99", "12130.00", "1.15", "2.68", "1214.24",
                       "6999999999.93"]
        vat_hellers = [int(Decimal(amount) * 100) for amount in vat_amounts]
        clamp_cases = [["5", 1, 200], ["0", 1, 200], ["-3", 0, 500], ["999", 1, 200], ["2.9", 1, 200], ["", 1, 200], ["abc", 0, 500],
                       ["1e3", 1, 200], ["Infinity", 1, 200]]

        expected = {
            "fees": [str(int(pricing.monthly_fee(document, *case) * 100)) for case in fee_cases],
            "packages": [[str(int(v * 100)) for v in pricing.package_range(document, code, quantity, month)]
                         for code, quantity, month in package_cases],
            "vat": [[str(int(pricing.with_vat(document, Decimal(amount), reduced_residential=reduced) * 100)) for reduced in (False, True)]
                    for amount in vat_amounts],
            "annual": [str(int(pricing.annual_fee(document, *case) * 100)) for case in fee_cases],
            "crowns": [pricing._czk(Decimal(amount)).replace(" Kč", "").replace(" ", "") for amount in vat_amounts],
            "clamp": [5, 1, 0, 200, 2, 1, 0, 200, 1],
            "labels": ["21 %", "12,5 %"],
            "missing_month": "error",
            # EN: Anything outside the exact integers stops the kernel instead of being rounded silently.
            # CZ: Cokoli mimo přesná celá čísla jádro zastaví, místo aby se to potichu zaokrouhlilo.
            "unsafe": ["RangeError"] * 8,
            "half_up_exact": [str((2 ** 53 - 1 - 5000 + 5000) // 10000), "1", "0", "900719925474"],
        }
        script = (
            f"const P = {json.dumps(public)};\n" + self.kernel() +
            f"const feeCases = {json.dumps(fee_cases)}, packageCases = {json.dumps(package_cases)};\n"
            f"const amounts = {json.dumps(vat_hellers)}, clampCases = {json.dumps(clamp_cases)};\n"
            "const tariff = (code) => P.mrr_tariffs.find((t) => t.code === code);\n"
            "const pkg = (code) => P.turnkey_packages.find((t) => t.code === code);\n"
            "const hellers = (value) => value;\n"
            "const kind = (run) => { try { run(); return 'ok'; } catch (e) { return e.name; } };\n"
            "const big = 2 ** 53;\n"
            "const unsafe = [() => safe(big), () => safe(1.5), () => safe(-1), () => safe('5'), () => withVat(big - 1, 2100),\n"
            "  () => monthlyFee({base_monthly_per_object_hellers: big - 1, extra_entrance_monthly_hellers: 1}, 1, 1),\n"
            "  () => packageRange(P, {price_from_hellers: 1, price_to_hellers: big / 2}, 200, 1), () => annualFee(big / 4)].map(kind);\n"
            "let missing = 'ok'; try { seasonalCoefficient({seasonal_coefficients: []}, 3); } catch (e) { missing = 'error'; }\n"
            "emit(JSON.stringify({\n"
            "  fees: feeCases.map(([c, o, e]) => String(monthlyFee(tariff(c), o, e))),\n"
            "  packages: packageCases.map(([c, q, m]) => packageRange(P, pkg(c), q, m).map(String)),\n"
            "  vat: amounts.map((a) => [String(withVat(hellers(a), P.meta.vat_rates.standard_bp)),"
            " String(withVat(hellers(a), P.meta.vat_rates.residential_reduced_bp))]),\n"
            "  annual: feeCases.map(([c, o, e]) => String(annualFee(monthlyFee(tariff(c), o, e)))),\n"
            "  unsafe: unsafe,\n"
            "  half_up_exact: [halfUp(big - 1 - 5000, 10000), halfUp(5000, 10000), halfUp(4999, 10000), halfUp(9007199254735000, 10000)].map(String),\n"
            "  crowns: amounts.map((a) => String(wholeCrowns(hellers(a)))),\n"
            "  clamp: clampCases.map(([raw, min, max]) => clampValue(raw, min, max)),\n"
            "  labels: [pctLabel(P.meta.vat_rates.standard_pct), pctLabel(P.meta.vat_rates.residential_reduced_pct)],\n"
            "  missing_month: missing,\n"
            "}));\n")
        output = _run_javascript(script)
        if output is None:
            if os.environ.get("POLARITA_REQUIRE_BROWSER") == "1":
                self.fail("POLARITA_REQUIRE_BROWSER=1 and neither Node.js nor a Chromium browser found")
            self.skipTest("neither Node.js nor a Chromium browser available / není dostupný Node.js ani prohlížeč Chromium")
        self.assertEqual(json.loads(output), expected)


if __name__ == "__main__":
    unittest.main()
