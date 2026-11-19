# -*- coding: utf-8 -*-
"""
Tests of the pricing kernel of package S3 (Version 2.8).
Testy cenového jádra balíčku S3 (Verze 2.8).

Usage / Použití:  python -m unittest -v test_pricing
"""

from __future__ import annotations

import json
import re
import unittest
from decimal import Decimal

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
        self.assertIn("Math.round(Math.round(value * 100) / 100)", template)

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
        border_below = pricing.margin_check(self.price_list, 100_000, 78_004)  # 21.996% rounds to 22.00%
        at_minimum = pricing.margin_check(self.price_list, 100_000, 100_000 * (1 - minimum / 100))
        self.assertTrue(below["hard_stop"])
        self.assertEqual(border_below["contribution_margin_pct"], Decimal("22.00"))
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
        expected_embedded = json.dumps(pub, ensure_ascii=False).replace("</", "<\\/")
        self.assertEqual(page, pricing.TEMPLATE_PATH.read_text(encoding="utf-8").replace("/*__PRICE_LIST_JSON__*/", expected_embedded))
        match = re.search(r"const PRICE_LIST = (\{.*?\});\n", page, flags=re.DOTALL)
        self.assertIsNotNone(match)
        self.assertEqual(json.loads(match.group(1).replace("<\\/", "</")), pub)
        for forbidden in ("hourly_rates", "material_markup_pct", "minimum_contribution_margin_pct", "retention_pct", "partner_commission", "14005"):
            self.assertNotIn(forbidden, page)
        self.assertEqual(pricing.OVERVIEW_PATH.read_text(encoding="utf-8"), pricing.render_overview(self.price_list))


if __name__ == "__main__":
    unittest.main()
