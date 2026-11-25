"""Převod XC4 NZ do upravitelného sešitu a zpět se zachováním stromu stavby."""
import base64
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

from lxml import etree as ET
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Protection
from openpyxl.worksheet.datavalidation import DataValidation

from nabidka import LIMIT, MARK, VRSTVY, cislo, over_xml, polozky, souhrn, xml_bytes

HEAD = ("ID", "Objekt", "Díl", "Kód", "Název", "MJ", "Množství", "Jednotková cena", "Skupina", "Celkem bez DPH")
FIXED = ("objekt", "dil", "kod", "nazev", "mj")
MAX_ROWS = 50000


def text(cell, value):
    cell.value = value
    cell.data_type = "s"


def number(value):
    # Excel ukládá nejvýše 15 platných číslic. Přesnější hodnoty se přenášejí textem.
    return value if len(value.as_tuple().digits) <= 15 and value.adjusted() < 15 else format(value, "f")


def do_xlsx(raw, schema):
    root = over_xml(raw, schema)
    rows = polozky(root)
    if len(rows) > MAX_ROWS:
        raise ValueError("Příliš mnoho položek pro sešit.")
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Položky"
    sheet.append(HEAD)
    for i, (key, row) in enumerate(rows.items(), 2):
        for col, value in enumerate((key, *(row[k] for k in FIXED)), 1):
            text(sheet.cell(i, col), value)
        for col, value in enumerate((number(row["mnozstvi"]), number(row["cena"]), row["vrstva"]), 7):
            cell = sheet.cell(i, col, value)
            cell.protection = Protection(locked=False)
        sheet.cell(i, 10, f"=ROUND(G{i}*H{i},2)").number_format = "#,##0.00"
    sheet.protection.sheet = True
    sheet.freeze_panes = "G2"
    sheet.auto_filter.ref = sheet.dimensions
    for column, width in zip("ABCDEFGHIJ", (18,14,14,22,55,10,18,18,12,20)):
        sheet.column_dimensions[column].width = width
    valid = DataValidation(type="whole", operator="between", formula1=1, formula2=9, showErrorMessage=True)
    sheet.add_data_validation(valid)
    valid.add(f"I2:I{len(rows)+1}")
    check = wb.create_sheet("Kontrola")
    check.append(("Skupina", "Druh práce", "Počet položek", "Cena bez DPH", "Měna"))
    for i, name in enumerate(VRSTVY, 2):
        check.append((i-1, name, f"=COUNTIF('Položky'!I$2:I${len(rows)+1},A{i})",
                      f"=SUMIF('Položky'!I$2:I${len(rows)+1},A{i},'Položky'!J$2:J${len(rows)+1})"))
        text(check.cell(i, 5), root.findtext("mena") or "")
    check.append((None, "Celkem", "=SUM(C2:C10)", "=SUM(D2:D10)"))
    for column, width in zip("ABCDE", (12,40,18,20,12)):
        check.column_dimensions[column].width = width
    for page in (sheet, check):
        for cell in page[1]:
            cell.font = Font(bold=True)
    source = wb.create_sheet("Zdroj XC4")
    source.sheet_state = "veryHidden"
    encoded = base64.b64encode(raw).decode("ascii")
    for start in range(0, len(encoded), 24000):
        source.append((encoded[start:start+24000],))
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


def over_zip(raw):
    if len(raw) > 2 * LIMIT:
        raise ValueError("Sešit překračuje limit velikosti.")
    with ZipFile(BytesIO(raw)) as zipped:
        infos = zipped.infolist()
        names = {entry.filename for entry in infos}
        if (len(infos) > 128 or len(names) != len(infos) or sum(i.file_size for i in infos) > 4 * LIMIT
                or any("externallinks/" in n.lower() or n.lower().endswith(".bin") for n in names)):
            raise ValueError("Nepodporovaný obsah sešitu.")


def do_xc4(raw, schema):
    over_zip(raw)
    wb = load_workbook(BytesIO(raw), read_only=True, data_only=False, keep_links=False)
    try:
        sheet = wb["Položky"]
        source = wb["Zdroj XC4"]
        # Skutečné počty řádků se určují čtením, metadata rozměrů dodává editor.
        source.reset_dimensions()
        chunks = []
        for i, (value,) in enumerate(source.values, 1):
            if i > 1000 or not isinstance(value, str) or len(value) > 24000:
                raise ValueError("Vadná vložená data XC4.")
            chunks.append(value)
        root = over_xml(base64.b64decode("".join(chunks), validate=True), schema)
        rows = polozky(root)
        sheet.reset_dimensions()
        records = iter(sheet.rows)
        if tuple(cell.value for cell in next(records, ())) != HEAD:
            raise ValueError("Nepodporované sloupce rozpočtu.")
        seen = set()
        for i, record in enumerate(records, 1):
            if i > MAX_ROWS or len(record) != len(HEAD):
                raise ValueError("Vadný rozsah položek v sešitu.")
            key, *rest = [cell.value for cell in record]
            if key not in rows or key in seen:
                raise ValueError("Neznámá nebo duplicitní položka v sešitu.")
            seen.add(key)
            row = rows[key]
            if rest[:5] != [row[k] for k in FIXED] or any(cell.data_type == "f" for cell in record[:9]):
                raise ValueError("Nelze změnit identitu položky nebo vložit vzorec do vstupních polí.")
            qty, price, group = rest[5:8]
            if type(group) is not int or not 1 <= group <= len(VRSTVY):
                raise ValueError("Každá položka potřebuje skupinu od 1 do 9.")
            el = row["xml"]
            for field, value, precision in (("mnozstvi", qty, 6), ("joc", price, 4)):
                if isinstance(value, float):
                    value = format(Decimal(str(value)), "f")
                parsed = cislo(value, precision)
                if parsed != Decimal(el.findtext(field)):
                    el.find(field).text = format(parsed, "f")
            if group != row["vrstva"]:
                desc = el.find("popis")
                if desc is None:
                    desc = ET.Element("popis")
                    el.find("por_cislo").addnext(desc)
                notes = [line for line in (desc.text or "").splitlines() if not line.startswith(MARK)]
                desc.text = "\n".join([*notes, MARK + str(group)])
        if seen != rows.keys():
            raise ValueError("V sešitu chybí původní položky.")
        result = xml_bytes(root)
        souhrn(polozky(over_xml(result, schema)))
        return result
    finally:
        wb.close()
