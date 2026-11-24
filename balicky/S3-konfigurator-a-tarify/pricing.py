# -*- coding: utf-8 -*-
"""
Deterministic pricing kernel of package S3 (Version 3.12): MRR tariffs, turnkey packages,
labour rates, margin Hard-Stop and the partner commission matrix (N8).
Deterministické cenové jádro balíčku S3 (Verze 3.12): tarify MRR, balíčky na klíč,
hodinové sazby, Hard-Stop marže a provizní matice partnerů (N8).

EN: All amounts come from cenik.json (single source of truth; meta.approved tells whether 1001
    approved it). No ai agent computes prices from memory — it calls these functions.
    The price list is validated when loaded (load_price_list -> validate_price_list); a binding
    offer is checked as a whole by offer_margin_check, which refuses an unapproved price list.
CZ: Všechny částky pocházejí z cenik.json (jediný zdroj pravdy; meta.approved říká, zda jej
    jednatel 1001 schválil). Žádný ai agent nepočítá ceny zpaměti — volá tyto funkce.
    Ceník se při načtení validuje (load_price_list -> validate_price_list); závazná nabídka se
    kontroluje jako celek funkcí offer_margin_check, která neschválený ceník odmítne.

Usage / Použití:
    python pricing.py --overview          # Markdown overview of the price list / přehled hodnot ceníku
    python pricing.py --build             # regenerate konfigurator.html and prehled-cen.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PRICE_LIST_PATH = HERE / "cenik.json"
TEMPLATE_PATH = HERE / "konfigurator.template.html"
CONFIGURATOR_PATH = HERE / "konfigurator.html"
OVERVIEW_PATH = HERE / "prehled-cen.md"

CENT = Decimal("0.01")

# EN: Domain bounds of the price list. They are applied BEFORE any rounding, so an absurd value ends as
#     a PricingError naming the field, and they keep every intermediate result of the public page (whole
#     hellers in JavaScript) inside the exactly representable integers - see _check_public_arithmetic.
# CZ: Doménové meze ceníku. Uplatňují se PŘED jakýmkoli zaokrouhlením, takže nesmyslná hodnota skončí
#     jako PricingError se jménem pole, a drží každý mezivýsledek veřejné stránky (celé haléře
#     v JavaScriptu) uvnitř přesně zobrazitelných celých čísel - viz _check_public_arithmetic.
MAX_AMOUNT = Decimal("100000000")        # CZK per item / Kč za položku
MAX_COEFFICIENT = Decimal("10")
MAX_MARKUP_PCT = Decimal("1000")
MAX_SAFE_INTEGER = 2 ** 53 - 1           # Number.MAX_SAFE_INTEGER of JavaScript
# EN: Largest multipliers the public page may use (the "max" of its number fields must not exceed them).
# CZ: Největší násobitele, které smí veřejná stránka použít ("max" jejích číselných polí je nesmí překročit).
PUBLIC_MAX_OBJECTS = 200
PUBLIC_MAX_ENTRANCES = 500
PUBLIC_MAX_QUANTITY = 200


class PricingError(ValueError):
    """Invalid pricing input. / Neplatný vstup cenového výpočtu."""


def _dec(value: Any) -> Decimal:
    """Exact decimal of a JSON number (never Decimal(float)). / Přesné desetinné číslo z JSON (nikdy Decimal(float))."""
    return Decimal(str(value))


def _number(value: Any, name: str, *, minimum: Decimal | int = 0, maximum: Decimal | int = MAX_AMOUNT,
            positive: bool = False, places: int = 2) -> Decimal:
    """
    EN: Validate one number of the price list. The bounds are checked first; only a value inside them
        is compared with its rounded form, so no input can raise anything else than PricingError.
    CZ: Zvaliduje jedno číslo ceníku. Nejdřív se kontrolují meze; teprve hodnota uvnitř nich se porovnává
        se svým zaokrouhleným tvarem, takže žádný vstup nevyvolá nic jiného než PricingError.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PricingError(f"price list: {name} must be a number")
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PricingError(f"price list: {name} must be a number") from exc
    if not dec.is_finite() or dec < minimum or (positive and dec <= 0) or dec > maximum:
        raise PricingError(f"price list: {name} must be {'> 0' if positive else '>= ' + str(minimum)} and <= {maximum}")
    try:
        exact = dec == dec.quantize(Decimal(1).scaleb(-places))
    except InvalidOperation:
        exact = False
    if not exact:
        raise PricingError(f"price list: {name} may have at most {places} decimal places")
    return dec


def _calendar_date(value: Any, name: str) -> date:
    """A real calendar date YYYY-MM-DD. / Skutečné kalendářní datum RRRR-MM-DD."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise PricingError(f"price list: {name} must be a date YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise PricingError(f"price list: {name} is not an existing calendar date") from exc


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PricingError(f"price list: {name} must be a non-empty text")
    return value


def _items(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise PricingError(f"price list: {name} must be a non-empty list")
    return value


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PricingError(f"price list: {name} must be an object")
    return value


# EN: Codes of tariffs and packages are used as keys and identifiers by the public page as well. Only a
#     plain ASCII identifier is accepted (a letter, then letters, digits or underscores, at most 64
#     characters), so a code such as "__proto__" can never reach the page. The JavaScript kernel checks
#     the SAME pattern (SAFE_CODE in konfigurator.template.html) and keeps quantities in a Map.
# CZ: Kódy tarifů a balíčků používá jako klíče a identifikátory i veřejná stránka. Přijímá se jen prostý
#     ASCII identifikátor (písmeno, pak písmena, číslice nebo podtržítka, nejvýše 64 znaků), takže kód
#     typu „__proto__“ se na stránku nikdy nedostane. Jádro v JavaScriptu kontroluje TÝŽ vzor (SAFE_CODE
#     v konfigurator.template.html) a množství drží v Map.
SAFE_CODE_PATTERN = r"[A-Za-z][A-Za-z0-9_]{0,63}"
SAFE_CODE = re.compile(SAFE_CODE_PATTERN)


def _unique_codes(entries: list[Any], name: str) -> None:
    codes = [_text(_mapping(entry, name).get("code"), f"{name}.code") for entry in entries]
    for code in codes:
        if not SAFE_CODE.fullmatch(code):
            raise PricingError(f"price list: {name}.code must be a plain identifier (a letter, then letters, digits or "
                               f"underscores, at most 64 characters)")
    if len(set(codes)) != len(codes):
        raise PricingError(f"price list: {name} has a duplicate code")


def validate_price_list(price_list: Any) -> dict[str, Any]:
    """
    EN: Reject a price list that would silently produce wrong prices: missing parts, negative or
        non-numeric amounts, percentages outside 0-100, "from" above "to", a month without or with two
        seasonal coefficients, commission tiers out of order, inconsistent approval data.
    CZ: Odmítne ceník, který by potichu dával špatné ceny: chybějící části, záporné nebo nečíselné
        částky, procenta mimo 0-100, „od“ nad „do“, měsíc bez sezónního koeficientu nebo se dvěma,
        stupně provize mimo pořadí, nekonzistentní údaje o schválení.
    """
    root = _mapping(price_list, "root")
    meta = _mapping(root.get("meta"), "meta")
    for key in ("name", "version", "status", "currency", "note"):
        _text(meta.get(key), f"meta.{key}")
    if not isinstance(meta.get("approved"), bool) or meta.get("prices_exclude_vat") is not True:
        raise PricingError("price list: meta.approved must be a boolean and meta.prices_exclude_vat must be true")
    if meta["approved"]:
        if meta["status"] != "SCHVALENO_1001" or meta.get("approved_by") != "1001":
            raise PricingError("price list: an approved price list must have status SCHVALENO_1001 and approved_by 1001")
        # EN: Real calendar dates in the right order: a price list cannot take effect before it was approved.
        # CZ: Skutečná kalendářní data ve správném pořadí: ceník nemůže nabýt účinnosti dřív, než byl schválen.
        if _calendar_date(meta.get("approved_on"), "meta.approved_on") > _calendar_date(meta.get("valid_from"), "meta.valid_from"):
            raise PricingError("price list: meta.valid_from must not be earlier than meta.approved_on")
    elif (meta["status"] != "NAVRH_KE_SCHVALENI_1001" or meta.get("approved_by") is not None or meta.get("valid_from") is not None
          or meta.get("approved_on") is not None):
        raise PricingError("price list: a proposal must have status NAVRH_KE_SCHVALENI_1001 and no approver, approval date or validity date")
    vat = _mapping(meta.get("vat_rates"), "meta.vat_rates")
    for key in ("standard_pct", "residential_reduced_pct"):
        _number(vat.get(key), f"meta.vat_rates.{key}", maximum=100)

    tariffs = _items(root.get("mrr_tariffs"), "mrr_tariffs")
    _unique_codes(tariffs, "mrr_tariffs")
    for tariff in tariffs:
        code = tariff["code"]
        for key in ("label", "audience", "sla_response"):
            _text(tariff.get(key), f"mrr_tariffs[{code}].{key}")
        _number(tariff.get("base_monthly_per_object"), f"mrr_tariffs[{code}].base_monthly_per_object", positive=True)
        _number(tariff.get("extra_entrance_monthly"), f"mrr_tariffs[{code}].extra_entrance_monthly")
        _number(tariff.get("labour_discount_pct"), f"mrr_tariffs[{code}].labour_discount_pct", maximum=100)
        for item in _items(tariff.get("includes"), f"mrr_tariffs[{code}].includes"):
            _text(item, f"mrr_tariffs[{code}].includes")

    packages = _items(root.get("turnkey_packages"), "turnkey_packages")
    _unique_codes(packages, "turnkey_packages")
    for package in packages:
        code = package["code"]
        for key in ("label", "unit", "includes"):
            _text(package.get(key), f"turnkey_packages[{code}].{key}")
        low = _number(package.get("price_from"), f"turnkey_packages[{code}].price_from", positive=True)
        high = _number(package.get("price_to"), f"turnkey_packages[{code}].price_to", positive=True)
        if low > high:
            raise PricingError(f"price list: turnkey_packages[{code}].price_from is above price_to")

    rates = _mapping(root.get("hourly_rates"), "hourly_rates")
    if not rates:
        raise PricingError("price list: hourly_rates must not be empty")
    for role, entry in rates.items():
        _text(_mapping(entry, f"hourly_rates[{role}]").get("label"), f"hourly_rates[{role}].label")
        _number(entry.get("rate"), f"hourly_rates[{role}].rate", positive=True)

    _number(root.get("material_markup_pct"), "material_markup_pct", maximum=MAX_MARKUP_PCT)
    _number(root.get("minimum_contribution_margin_pct"), "minimum_contribution_margin_pct", maximum=100)
    retention = _mapping(root.get("retention_pct"), "retention_pct")
    if _number(retention.get("min"), "retention_pct.min", maximum=100) > _number(retention.get("max"), "retention_pct.max", maximum=100):
        raise PricingError("price list: retention_pct.min is above retention_pct.max")

    tiers = _items(_mapping(root.get("partner_commission"), "partner_commission").get("tiers"), "partner_commission.tiers")
    previous: tuple[int, Decimal] | None = None
    for tier in tiers:
        tier = _mapping(tier, "partner_commission.tiers")
        objects = tier.get("min_objects")
        if isinstance(objects, bool) or not isinstance(objects, int) or objects < 1:
            raise PricingError("price list: partner_commission.tiers.min_objects must be an integer >= 1")
        pct = _number(tier.get("pct"), "partner_commission.tiers.pct", maximum=100)
        if previous is not None and (objects <= previous[0] or pct < previous[1]):
            raise PricingError("price list: partner_commission.tiers must rise in min_objects and never fall in pct")
        previous = (objects, pct)

    months: list[int] = []
    for band in _items(root.get("seasonal_coefficients"), "seasonal_coefficients"):
        band = _mapping(band, "seasonal_coefficients")
        _text(band.get("label"), "seasonal_coefficients.label")
        _number(band.get("coefficient"), "seasonal_coefficients.coefficient", positive=True, places=4, maximum=MAX_COEFFICIENT)
        for month in _items(band.get("months"), "seasonal_coefficients.months"):
            if isinstance(month, bool) or not isinstance(month, int):
                raise PricingError("price list: seasonal_coefficients.months must be integers")
            months.append(month)
    if sorted(months) != list(range(1, 13)):
        raise PricingError("price list: seasonal_coefficients must cover every month 1-12 exactly once")
    _text(root.get("indexation"), "indexation")
    _check_public_arithmetic(root)
    return root


def _hellers(value: Any) -> int:
    """Whole hellers of a validated amount. / Celé haléře zvalidované částky."""
    return int(_dec(value) * 100)


def _check_public_arithmetic(root: dict[str, Any]) -> None:
    """
    EN: The public page computes in whole hellers with JavaScript numbers, which are exact only up to
        2^53 - 1. Take the worst case the page can reach (largest multipliers, highest coefficient,
        every package chosen, highest VAT rate) and refuse a price list whose intermediate result
        would leave that range - the page then never has to round an amount it cannot represent.
    CZ: Veřejná stránka počítá v celých haléřích čísly JavaScriptu, která jsou přesná jen do 2^53 - 1.
        Vezme se nejhorší případ, kterého stránka může dosáhnout (největší násobitele, nejvyšší
        koeficient, všechny balíčky vybrané, nejvyšší sazba DPH), a ceník, jehož mezivýsledek by ten
        rozsah opustil, se odmítne - stránka pak nikdy nezaokrouhluje částku, kterou neumí zobrazit.
    """
    vat = max(int(_dec(pct) * 100) for pct in root["meta"]["vat_rates"].values()) + 10000
    coefficient = max(int(_dec(band["coefficient"]) * 10000) for band in root["seasonal_coefficients"])
    fee = max(_hellers(t["base_monthly_per_object"]) * PUBLIC_MAX_OBJECTS + _hellers(t["extra_entrance_monthly"]) * PUBLIC_MAX_ENTRANCES
              for t in root["mrr_tariffs"])
    scaled_packages = [_hellers(p["price_to"]) * PUBLIC_MAX_QUANTITY * coefficient for p in root["turnkey_packages"]]
    packages = sum(-(-value // 10000) for value in scaled_packages)
    worst = max(fee * 12, fee * vat + 5000, max(scaled_packages) + 5000, packages * vat + 5000)
    if worst > MAX_SAFE_INTEGER:
        raise PricingError("price list: amounts are too large for the exact arithmetic of the public configurator "
                           "(an intermediate result in hellers would exceed 2^53 - 1)")


def load_price_list(path: Path | None = None) -> dict[str, Any]:
    """Load and validate the price list. / Načte a zvaliduje ceník."""
    path = PRICE_LIST_PATH if path is None else path
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:  # invalid JSON or invalid UTF-8 / neplatný JSON nebo neplatné UTF-8
        raise PricingError(f"price list {path.name} cannot be read: {exc}") from exc
    return validate_price_list(document)


def require_approved(price_list: dict[str, Any], offer_date: date | None = None) -> None:
    """
    EN: A binding offer may be based only on a price list approved by 1001 that is already in effect on
        the day of the offer (today when no date is given): approved and not yet valid is not enough.
    CZ: Závazná nabídka smí vycházet jen z ceníku schváleného jednatelem 1001, který je ke dni nabídky
        (dnes, když datum není zadáno) už účinný: schválený, ale dosud neplatný ceník nestačí.
    """
    meta = price_list.get("meta", {})
    if meta.get("approved") is not True or meta.get("approved_by") != "1001":
        raise PricingError("price list is not approved by 1001 - no binding offer may be based on it")
    if offer_date is None:
        offer_date = date.today()
    elif type(offer_date) is not date:
        # EN: Only a pure calendar date. A datetime is a subclass of date, but which day an instant
        #     belongs to depends on the time zone - the caller must decide that, not this function.
        # CZ: Jen čisté kalendářní datum. Datum s časem je podtřídou date, ale to, ke kterému dni okamžik
        #     patří, závisí na časovém pásmu - o tom musí rozhodnout volající, ne tato funkce.
        raise PricingError("offer_date must be a pure calendar date (datetime.date, not datetime.datetime)")
    approved_on = _calendar_date(meta.get("approved_on"), "meta.approved_on")
    valid_from = _calendar_date(meta.get("valid_from"), "meta.valid_from")
    if approved_on > valid_from:
        raise PricingError("price list: meta.valid_from must not be earlier than meta.approved_on")
    if offer_date < valid_from:
        raise PricingError(f"price list is approved but takes effect only on {valid_from.isoformat()} - "
                           f"no binding offer dated {offer_date.isoformat()} may be based on it")


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
    total = _dec(tariff["base_monthly_per_object"]) * objects + _dec(tariff["extra_entrance_monthly"]) * extra_entrances
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
            return (_money(_dec(package["price_from"]) * quantity * coefficient),
                    _money(_dec(package["price_to"]) * quantity * coefficient))
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
        total += _dec(price_list["hourly_rates"][role]["rate"]) * hours_dec
    if tariff_code is not None:
        discount = _dec(_tariff(price_list, tariff_code)["labour_discount_pct"]) / 100
        total *= (Decimal(1) - discount)
    return _money(total)


def material_price(price_list: dict[str, Any], purchase_cost: Decimal | int | float) -> Decimal:
    """Material sale price = purchase cost + markup. / Prodejní cena materiálu = nákup + přirážka."""
    cost_dec = _require_nonneg_decimal(purchase_cost, "purchase_cost")
    return _money(cost_dec * (100 + _dec(price_list["material_markup_pct"])) / 100)


def margin_check(price_list: dict[str, Any], price_without_vat: Decimal | int | float, direct_costs: Decimal | int | float) -> dict[str, Any]:
    """
    EN: Contribution margin check. Below the minimum the offer is Hard-Stopped until signed by 1001.
        The price and the costs are those of the WHOLE offer (labour + material) - see offer_margin_check.
    CZ: Kontrola krycího příspěvku. Pod minimem je nabídka zastavena (Hard-Stop) do podpisu 1001.
        Cena i náklady jsou za CELOU nabídku (práce + materiál) - viz offer_margin_check.
    """
    price = _require_nonneg_decimal(price_without_vat, "price_without_vat")
    costs = _require_nonneg_decimal(direct_costs, "direct_costs")
    if price <= 0:
        raise PricingError("price must be > 0")
    raw_margin_pct = (price - costs) / price * 100
    # EN: Shown rounded DOWN, so a margin below the minimum can never be displayed as reaching it.
    # CZ: Zobrazuje se zaokrouhlená DOLŮ, takže marže pod minimem se nikdy nezobrazí, jako by ho dosáhla.
    margin_pct = raw_margin_pct.quantize(CENT, rounding=ROUND_FLOOR)
    minimum = _dec(price_list["minimum_contribution_margin_pct"])
    return {"contribution_margin_pct": margin_pct, "minimum_pct": minimum, "hard_stop": raw_margin_pct < minimum}


def offer_margin_check(price_list: dict[str, Any], labour_without_vat: Decimal | int | float,
                       material_without_vat: Decimal | int | float, direct_costs: Decimal | int | float,
                       offer_date: date | None = None) -> dict[str, Any]:
    """
    EN: Hard-Stop of a binding offer, evaluated for the whole offer: price = labour + material, costs =
        all direct costs of both. The material markup alone is below the minimum margin by design, so
        a line-by-line check would stop every offer; a pure material delivery is not priced by this
        matrix at all (it goes through the e-shop price list). Refuses an unapproved price list.
        The key "hard_stop" is the value of below_minimum_margin for the guard MARGIN_HARD_STOP.
    CZ: Hard-Stop závazné nabídky hodnocený za celou nabídku: cena = práce + materiál, náklady = všechny
        přímé náklady obojího. Samotná přirážka na materiál je záměrně pod minimální marží, takže kontrola
        po řádcích by zastavila každou nabídku; čistě materiálová dodávka se touto maticí nenaceňuje
        vůbec (jde přes ceník e-shopu). Neschválený ceník odmítne. Klíč „hard_stop“ je hodnota
        below_minimum_margin pro pojistku MARGIN_HARD_STOP.
    EN: The margin is judged over exactly the amounts that go into the offer: both lines rounded to
        hellers and their sum, which is also returned as price_without_vat. The price list must be in
        effect on offer_date (today when not given).
    CZ: Marže se posuzuje nad přesně těmi částkami, které jdou do nabídky: oba řádky zaokrouhlené na
        haléře a jejich součet, který se také vrací jako price_without_vat. Ceník musí být ke dni
        offer_date (dnes, není-li zadán) účinný.
    """
    require_approved(price_list, offer_date)
    labour = _require_nonneg_decimal(labour_without_vat, "labour_without_vat")
    material = _require_nonneg_decimal(material_without_vat, "material_without_vat")
    # EN: The ban on an offer without labour applies to the labour line as it stands in the offer, i.e.
    #     rounded to hellers: 0.001 CZK of labour is invoiced as 0.00 and the offer is a pure material delivery.
    # CZ: Zákaz nabídky bez práce platí pro řádek práce tak, jak stojí v nabídce, tedy zaokrouhlený na
    #     haléře: 0,001 Kč práce se fakturuje jako 0,00 a nabídka je čistě materiálová dodávka.
    if _money(labour) <= 0:
        raise PricingError("an offer without labour is a pure material delivery - it is priced by the e-shop price list, not by this matrix")
    price = _money(labour) + _money(material)
    if price <= 0:
        raise PricingError("the offer price rounds to zero")
    result = margin_check(price_list, price, direct_costs)
    result["price_without_vat"] = price
    return result


def partner_commission_pct(price_list: dict[str, Any], active_objects: int) -> Decimal:
    """Commission tier by number of referred active objects. / Stupeň provize dle počtu přivedených aktivních objektů."""
    active_objects = _require_int(active_objects, "active_objects", 0)
    if active_objects < 1:
        return Decimal(0)
    pct = Decimal(0)
    for tier in sorted(price_list["partner_commission"]["tiers"], key=lambda item: item["min_objects"]):
        if active_objects >= tier["min_objects"]:
            pct = _dec(tier["pct"])
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
    EN: Informational price including VAT (standard or reduced residential rate from meta.vat_rates).
    CZ: Orientační cena včetně DPH (základní nebo snížená sazba pro bydlení z meta.vat_rates).
    """
    amount = _require_nonneg_decimal(net_amount, "net_amount")
    rates = price_list["meta"]["vat_rates"]
    pct = rates["residential_reduced_pct"] if reduced_residential else rates["standard_pct"]
    return _money(amount * (100 + _dec(pct)) / 100)


PUBLIC_META_KEYS = ("name", "version", "status", "approved", "approved_by", "approved_on", "valid_from", "currency",
                    "prices_exclude_vat")
PUBLIC_VAT_KEYS = ("standard_pct", "residential_reduced_pct")
PUBLIC_TARIFF_KEYS = ("code", "label", "audience", "sla_response", "labour_discount_pct", "includes")
PUBLIC_PACKAGE_KEYS = ("code", "label", "unit", "includes")
PUBLIC_SEASON_KEYS = ("months", "label")
# EN: Amounts leave Python already as integers: "<field>_hellers" (CZK x 100), "coefficient_e4"
#     (coefficient x 10 000) and "<rate>_bp" (per cent x 100). The page never parses a decimal number.
# CZ: Částky opouštějí Python už jako celá čísla: "<pole>_hellers" (Kč x 100), "coefficient_e4"
#     (koeficient x 10 000) a "<sazba>_bp" (procenta x 100). Stránka nikdy nepřevádí desetinné číslo.
PUBLIC_TARIFF_AMOUNTS = ("base_monthly_per_object", "extra_entrance_monthly")
PUBLIC_PACKAGE_AMOUNTS = ("price_from", "price_to")


def public_price_list(price_list: dict[str, Any]) -> dict[str, Any]:
    """
    EN: Public subset for the standalone web configurator. An allowlist on every level: a field that is
        not named here (internal rates, margins, commissions, a cost or note added to a tariff or package
        later) never reaches the public page.
    CZ: Veřejný výřez ceníku pro webový konfigurátor. Allowlist na každé úrovni: pole, které zde není
        vyjmenováno (interní sazby, marže, provize, později přidaný náklad či poznámka u tarifu nebo
        balíčku), se na veřejnou stránku nikdy nedostane.
    """
    def pick(entry: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
        return {key: (list(entry[key]) if isinstance(entry[key], list) else entry[key]) for key in keys}

    def amounts(entry: dict[str, Any], keys: tuple[str, ...], amount_keys: tuple[str, ...]) -> dict[str, Any]:
        return {**pick(entry, keys), **{f"{key}_hellers": _hellers(entry[key]) for key in amount_keys}}

    meta = pick(price_list["meta"], PUBLIC_META_KEYS)
    vat = price_list["meta"]["vat_rates"]
    meta["vat_rates"] = {**pick(vat, PUBLIC_VAT_KEYS), **{key[:-3] + "bp": int(_dec(vat[key]) * 100) for key in PUBLIC_VAT_KEYS}}
    return {
        "meta": meta,
        "mrr_tariffs": [amounts(item, PUBLIC_TARIFF_KEYS, PUBLIC_TARIFF_AMOUNTS) for item in price_list["mrr_tariffs"]],
        "turnkey_packages": [amounts(item, PUBLIC_PACKAGE_KEYS, PUBLIC_PACKAGE_AMOUNTS) for item in price_list["turnkey_packages"]],
        "seasonal_coefficients": [{**pick(item, PUBLIC_SEASON_KEYS), "coefficient_e4": int(_dec(item["coefficient"]) * 10000)}
                                  for item in price_list["seasonal_coefficients"]],
        "indexation": str(price_list["indexation"]),
    }


_SCRIPT_UNSAFE = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026", "\u2028": "\\u2028", "\u2029": "\\u2029"}


def embed_json(value: Any) -> str:
    """
    EN: JSON safe inside a <script> element: no "<" (so neither "</script>" nor "<!--<script>" can change
        how the browser reads the page), no line separators that end a JavaScript line.
    CZ: JSON bezpečný uvnitř prvku <script>: žádné „<“ (takže „</script>“ ani „<!--<script>“ nezmění, jak
        prohlížeč stránku čte), žádné oddělovače řádků, které ukončují řádek JavaScriptu.
    """
    text = json.dumps(value, ensure_ascii=False)
    return "".join(_SCRIPT_UNSAFE.get(char, char) for char in text)


def _czk(value: Decimal | int) -> str:
    # EN: Whole crowns, half up - the same rule as the configurator page.
    # CZ: Celé koruny, polovina nahoru - stejné pravidlo jako stránka konfigurátoru.
    whole = _dec(value).quantize(Decimal(1), rounding=ROUND_HALF_UP)
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
    CONFIGURATOR_PATH.write_text(template.replace(marker, embed_json(public_price_list(price_list))), encoding="utf-8", newline="\n")
    OVERVIEW_PATH.write_text(render_overview(price_list), encoding="utf-8", newline="\n")
    return [CONFIGURATOR_PATH, OVERVIEW_PATH]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Polarita pricing kernel (package S3)")
    parser.add_argument("--overview", action="store_true", help="print the Markdown overview")
    parser.add_argument("--build", action="store_true", help="regenerate konfigurator.html and prehled-cen.md")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        price_list = load_price_list()
        if args.build:
            for path in build(price_list):
                print("written", path.name)
        if args.overview or not args.build:
            print(render_overview(price_list))
    except (PricingError, OSError, ArithmeticError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
