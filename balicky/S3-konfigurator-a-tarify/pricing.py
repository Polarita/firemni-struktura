# -*- coding: utf-8 -*-
"""
Deterministic pricing kernel of package S3 (Version 2.8): MRR tariffs, turnkey packages,
labour rates, margin Hard-Stop and the partner commission matrix (N8).
Deterministické cenové jádro balíčku S3 (Verze 2.8): tarify MRR, balíčky na klíč,
hodinové sazby, Hard-Stop marže a provizní matice partnerů (N8).

EN: All amounts come from cenik.json (single source of truth; meta.approved tells whether 1001
    approved it). No ai agent computes prices from memory — it calls these functions.
CZ: Všechny částky pocházejí z cenik.json (jediný zdroj pravdy; meta.approved říká, zda jej
    jednatel 1001 schválil). Žádný ai agent nepočítá ceny zpaměti — volá tyto funkce.

Usage / Použití:
    python pricing.py --overview          # Markdown overview of the price list / přehled hodnot ceníku
    python pricing.py --build             # regenerate konfigurator.html and prehled-cen.md
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PRICE_LIST_PATH = HERE / "cenik.json"
TEMPLATE_PATH = HERE / "konfigurator.template.html"
CONFIGURATOR_PATH = HERE / "konfigurator.html"
OVERVIEW_PATH = HERE / "prehled-cen.md"

CENT = Decimal("0.01")


class PricingError(ValueError):
    """Invalid pricing input. / Neplatný vstup cenového výpočtu."""


def load_price_list(path: Path = PRICE_LIST_PATH) -> dict[str, Any]:
    """Load the price list. / Načte ceník."""
    return json.loads(path.read_text(encoding="utf-8"))


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _require_int(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise PricingError(f"{name} must be an integer >= {minimum}")
    return value


def _require_nonneg_decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise PricingError(f"{name} must be a non-negative finite number")
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PricingError(f"{name} must be a non-negative finite number") from exc
    if not dec.is_finite() or dec < 0:
        raise PricingError(f"{name} must be a non-negative finite number")
    return dec


def _tariff(price_list: dict[str, Any], code: str) -> dict[str, Any]:
    for tariff in price_list["mrr_tariffs"]:
        if tariff["code"] == code:
            return tariff
    raise PricingError(f"unknown tariff: {code}")


def monthly_fee(price_list: dict[str, Any], tariff_code: str, objects: int, extra_entrances: int = 0) -> Decimal:
    """
    EN: Monthly MRR fee without VAT. No surcharge per committee member or portal user.
    CZ: Měsíční paušál MRR bez DPH. Žádný příplatek za člena výboru ani uživatele portálu.
    """
    objects = _require_int(objects, "objects", 1)
    extra_entrances = _require_int(extra_entrances, "extra_entrances", 0)
    tariff = _tariff(price_list, tariff_code)
    total = Decimal(tariff["base_monthly_per_object"]) * objects + Decimal(tariff["extra_entrance_monthly"]) * extra_entrances
    return _money(total)


def annual_fee(price_list: dict[str, Any], tariff_code: str, objects: int, extra_entrances: int = 0) -> Decimal:
    """Twelve monthly fees. / Dvanáct měsíčních paušálů."""
    return _money(monthly_fee(price_list, tariff_code, objects, extra_entrances) * 12)


def package_range(price_list: dict[str, Any], package_code: str, quantity: int, month: int | None = None) -> tuple[Decimal, Decimal]:
    """
    EN: Transparent "from–to" price of a turnkey package, optionally with the seasonal coefficient.
    CZ: Transparentní cena „od–do“ balíčku na klíč, volitelně se sezónním koeficientem.
    """
    quantity = _require_int(quantity, "quantity", 1)
    for package in price_list["turnkey_packages"]:
        if package["code"] == package_code:
            coefficient = seasonal_coefficient(price_list, month) if month is not None else Decimal(1)
            return (_money(Decimal(package["price_from"]) * quantity * coefficient),
                    _money(Decimal(package["price_to"]) * quantity * coefficient))
    raise PricingError(f"unknown package: {package_code}")


def seasonal_coefficient(price_list: dict[str, Any], month: int) -> Decimal:
    """Seasonal coefficient for a calendar month. / Sezónní koeficient pro kalendářní měsíc."""
    month = _require_int(month, "month", 1)
    if month > 12:
        raise PricingError(f"no seasonal coefficient for month {month}")
    for band in price_list["seasonal_coefficients"]:
        if month in band["months"]:
            return Decimal(str(band["coefficient"]))
    raise PricingError(f"no seasonal coefficient for month {month}")


def labour_price(price_list: dict[str, Any], hours_by_role: dict[str, float], tariff_code: str | None = None) -> Decimal:
    """
    EN: Labour price from hourly rates; a tariff may grant a discount on labour.
    CZ: Cena práce z hodinových zúčtovacích sazeb; tarif může poskytnout slevu na práci.
    """
    if not isinstance(hours_by_role, dict):
        raise PricingError("hours_by_role must be a mapping")
    total = Decimal(0)
    for role, hours in hours_by_role.items():
        if role not in price_list["hourly_rates"]:
            raise PricingError(f"unknown role: {role}")
        hours_dec = _require_nonneg_decimal(hours, f"hours[{role}]")
        total += Decimal(price_list["hourly_rates"][role]["rate"]) * hours_dec
    if tariff_code is not None:
        discount = Decimal(_tariff(price_list, tariff_code)["labour_discount_pct"]) / 100
        total *= (Decimal(1) - discount)
    return _money(total)


def material_price(price_list: dict[str, Any], purchase_cost: Decimal | int | float) -> Decimal:
    """Material sale price = purchase cost + markup. / Prodejní cena materiálu = nákup + přirážka."""
    cost_dec = _require_nonneg_decimal(purchase_cost, "purchase_cost")
    return _money(cost_dec * (Decimal(100 + price_list["material_markup_pct"]) / 100))


def margin_check(price_list: dict[str, Any], price_without_vat: Decimal | int | float, direct_costs: Decimal | int | float) -> dict[str, Any]:
    """
    EN: Contribution margin check. Below the minimum the offer is Hard-Stopped until signed by 1001.
    CZ: Kontrola krycího příspěvku. Pod minimem je nabídka zastavena (Hard-Stop) do podpisu 1001.
    """
    price = _require_nonneg_decimal(price_without_vat, "price_without_vat")
    costs = _require_nonneg_decimal(direct_costs, "direct_costs")
    if price <= 0:
        raise PricingError("price must be > 0")
    raw_margin_pct = (price - costs) / price * 100
    margin_pct = raw_margin_pct.quantize(CENT, rounding=ROUND_HALF_UP)
    minimum = Decimal(price_list["minimum_contribution_margin_pct"])
    return {"contribution_margin_pct": margin_pct, "minimum_pct": minimum, "hard_stop": raw_margin_pct < minimum}


def partner_commission_pct(price_list: dict[str, Any], active_objects: int) -> Decimal:
    """Commission tier by number of referred active objects. / Stupeň provize dle počtu přivedených aktivních objektů."""
    active_objects = _require_int(active_objects, "active_objects", 0)
    if active_objects < 1:
        return Decimal(0)
    pct = Decimal(0)
    for tier in sorted(price_list["partner_commission"]["tiers"], key=lambda item: item["min_objects"]):
        if active_objects >= tier["min_objects"]:
            pct = Decimal(str(tier["pct"]))
    return pct


def partner_commission(price_list: dict[str, Any], paid_monthly_mrr: Decimal | int | float, active_objects: int) -> Decimal:
    """
    EN: Permanent monthly commission from PAID monthly MRR of referred objects (10–15 %).
    CZ: Trvalá měsíční provize z UHRAZENÉHO měsíčního MRR přivedených objektů (10–15 %).
    """
    paid = _require_nonneg_decimal(paid_monthly_mrr, "paid_monthly_mrr")
    return _money(paid * partner_commission_pct(price_list, active_objects) / 100)


def with_vat(price_list: dict[str, Any], net_amount: Decimal | int | float, *, reduced_residential: bool = False) -> Decimal:
    """
    EN: Informational price including VAT (21% standard, 12% reduced residential rate).
    CZ: Orientační cena včetně DPH (21 % základní sazba, 12 % snížená sazba pro bydlení).
    """
    amount = _require_nonneg_decimal(net_amount, "net_amount")
    rates = price_list["meta"]["vat_rates"]
    pct = rates["residential_reduced_pct"] if reduced_residential else rates["standard_pct"]
    return _money(amount * (Decimal(100 + pct) / 100))


def public_price_list(price_list: dict[str, Any]) -> dict[str, Any]:
    """
    EN: Return public subset for the standalone web configurator (excludes internal rates, margins and commissions).
    CZ: Vrátí veřejný výřez ceníku pro webový konfigurátor (bez interních hodinových sazeb, marží a provizí).
    """
    public_meta_keys = (
        "name", "version", "status", "approved", "approved_by",
        "approved_on", "valid_from", "currency", "prices_exclude_vat", "vat_rates",
    )
    return {
        "meta": {k: price_list["meta"][k] for k in public_meta_keys},
        "mrr_tariffs": price_list["mrr_tariffs"],
        "turnkey_packages": price_list["turnkey_packages"],
        "seasonal_coefficients": price_list["seasonal_coefficients"],
        "indexation": price_list["indexation"],
    }


def _czk(value: Decimal | int) -> str:
    # EN: Whole crowns, half up - the same rule as the configurator page.
    # CZ: Celé koruny, polovina nahoru - stejné pravidlo jako stránka konfigurátoru.
    whole = Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return f"{whole:,}".replace(",", " ") + " Kč"


def render_overview(price_list: dict[str, Any]) -> str:
    """Markdown overview generated from cenik.json. / Markdown přehled generovaný z cenik.json."""
    meta = price_list["meta"]
    lines = [
        "# Přehled cen a sazeb (generováno z `cenik.json`)",
        "",
        f"> **Stav: `{meta['status']}`** — {meta['note']}",
        "> Tento soubor se neupravuje ručně; vzniká příkazem `python pricing.py --build`.",
        "",
        "## Tarify paušálu „Elektro Správa SVJ a Firem“ (MRR, bez DPH)",
        "",
        "| Tarif | Měsíčně za objekt | Další vchod / měsíc | SLA odezva | Sleva na práci |",
        "| :--- | ---: | ---: | :--- | ---: |",
    ]
    for tariff in price_list["mrr_tariffs"]:
        lines.append(f"| **{tariff['label']}** | {_czk(tariff['base_monthly_per_object'])} | {_czk(tariff['extra_entrance_monthly'])} | {tariff['sla_response']} | {tariff['labour_discount_pct']} % |")
    lines += ["", "## Balíčky na klíč (cena od–do, bez DPH)", "", "| Balíček | Jednotka | Od | Do |", "| :--- | :--- | ---: | ---: |"]
    for package in price_list["turnkey_packages"]:
        lines.append(f"| {package['label']} | {package['unit']} | {_czk(package['price_from'])} | {_czk(package['price_to'])} |")
    lines += ["", "## Hodinové zúčtovací sazby (HZS, bez DPH)", "", "| Role | Kč / h |", "| :--- | ---: |"]
    for role in price_list["hourly_rates"].values():
        lines.append(f"| {role['label']} | {_czk(role['rate'])} |")
    lines += [
        "",
        "## Přirážky, minimální marže a provize",
        "",
        f"- Přirážka na materiál z `Elektro WMS`: **{price_list['material_markup_pct']} %**",
        f"- Minimální krycí příspěvek zakázky (`Hard-Stop` bez podpisu `1001`): **{price_list['minimum_contribution_margin_pct']} %**",
        f"- Zádržné: **{price_list['retention_pct']['min']}–{price_list['retention_pct']['max']} %** (dáno návrhem firmy)",
        "",
        "| Přivedených aktivních objektů | Trvalá provize z uhrazeného MRR |",
        "| ---: | ---: |",
    ]
    for tier in price_list["partner_commission"]["tiers"]:
        lines.append(f"| od {tier['min_objects']} | {str(tier['pct']).replace('.', ',')} % |")
    lines += ["", "## Sezónní koeficienty balíčků na klíč", "", "| Měsíce | Koeficient | Období |", "| :--- | ---: | :--- |"]
    for band in price_list["seasonal_coefficients"]:
        lines.append(f"| {', '.join(str(m) for m in band['months'])} | {str(band['coefficient']).replace('.', ',')} | {band['label']} |")
    lines += ["", f"**Indexace:** {price_list['indexation']}", ""]
    return "\n".join(lines)


def build(price_list: dict[str, Any]) -> list[Path]:
    """
    EN: Regenerate the self-contained configurator page and the Markdown overview from cenik.json.
    CZ: Přegeneruje samostatnou stránku konfigurátoru a Markdown přehled z cenik.json.
    """
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    marker = "/*__PRICE_LIST_JSON__*/"
    if template.count(marker) != 1:
        raise PricingError("template must contain exactly one price list marker")
    embedded = json.dumps(public_price_list(price_list), ensure_ascii=False).replace("</", "<\\/")
    CONFIGURATOR_PATH.write_text(template.replace(marker, embedded), encoding="utf-8", newline="\n")
    OVERVIEW_PATH.write_text(render_overview(price_list), encoding="utf-8", newline="\n")
    return [CONFIGURATOR_PATH, OVERVIEW_PATH]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Polarita pricing kernel (package S3)")
    parser.add_argument("--overview", action="store_true", help="print the Markdown overview")
    parser.add_argument("--build", action="store_true", help="regenerate konfigurator.html and prehled-cen.md")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    price_list = load_price_list()
    if args.build:
        for path in build(price_list):
            print("written", path.name)
    if args.overview or not args.build:
        print(render_overview(price_list))
    return 0


if __name__ == "__main__":
    sys.exit(main())
