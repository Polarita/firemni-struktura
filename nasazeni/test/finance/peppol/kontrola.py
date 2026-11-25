"""Kontrola jedné faktury UBL podle XSD a obou připnutých sad Schematron."""
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from lxml import etree

SVRL = "{http://purl.oclc.org/dsdl/svrl}"


def over(raw, adresar):
    parser = etree.XMLParser(no_network=True, resolve_entities=False)
    schema = etree.XMLSchema(etree.parse(str(adresar/"xsd/maindoc/UBL-Invoice-2.1.xsd"), parser))
    schema.assertValid(etree.fromstring(raw, parser))
    problemy = []
    with TemporaryDirectory() as tmp:
        source = Path(tmp)/"faktura.xml"
        source.write_bytes(raw)
        report = Path(tmp)/"kontrola.xml"
        for sada in ("cen","peppol"):
            subprocess.run(["java","-Xmx256m","-cp",str(adresar/"saxon.jar"),"net.sf.saxon.Transform",
                            "-dtd:off","-s:"+str(source),"-xsl:"+str(adresar/(sada+".xsl")),"-o:"+str(report)],
                           check=True, timeout=180)
            svrl = etree.parse(str(report), parser)
            if svrl.getroot().tag != SVRL+"schematron-output" or not svrl.findall(".//"+SVRL+"fired-rule"):
                raise ValueError("Validátor neprovedl pravidla sady " + sada)
            problemy.extend(f.get("id") for f in svrl.iter(SVRL+"failed-assert"))
    if problemy:
        raise ValueError("Faktura porušuje pravidla UBL: " + ", ".join(problemy))
