"""Převzetí označeného spisového hovoru z Garage. Zdroje se uvolní až po ověření všech tří zápisů."""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
import wave
from tempfile import TemporaryDirectory

from botocore.exceptions import ClientError
import uloz

AREA = "hovory-legal-hold-10let"
PARTS = (("zvuk", "wav"), ("prepis", "txt"))


def reference(metadata, key):
    case = metadata["spis"]
    years = metadata["retence-let"]
    captured = datetime.fromisoformat(metadata["porizeno"])
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", case)
            or years not in {str(n) for n in range(3, 11)}
            or not 2000 <= captured.year <= 9988 or captured.tzinfo is None or captured > datetime.now(timezone.utc)):
        raise ValueError("Neplatný spis, doba nebo čas pořízení hovoru")
    captured = captured.astimezone(timezone.utc)
    try:
        until = captured.date().replace(year=captured.year+int(years))
    except ValueError:
        until = captured.date().replace(year=captured.year+int(years), day=28)
    record = {"rezim":"TEST", "agenda":AREA, "spis":case, "porizeno":captured.isoformat(),
              "retence_let":int(years), "uchovat_do":until.isoformat(), "casti":{}}
    for part,ext in PARTS:
        digest = metadata[part+"-sha256"]
        if not re.fullmatch("[a-f0-9]{64}",digest):
            raise ValueError("Chybný otisk části spisového hovoru")
        record["casti"][part] = {"sha256":digest,"format":ext}
    encoded = json.dumps(record,sort_keys=True,separators=(",",":")).encode()
    record_id = hashlib.sha256(encoded).hexdigest()
    paths = {part:f"legal-hold/{record_id}/{part}.{ext}" for part,ext in PARTS}
    if key is not None and key not in paths.values():
        raise ValueError("Název předmětu nesouhlasí s předávacím záznamem hovoru")
    return record, encoded, record_id, paths, captured.year


def verified_copy(year, digest, ext):
    final = uloz.DATA / AREA / str(year) / digest / ("dokument."+ext)
    token = hashlib.sha256(str(final.relative_to(uloz.DATA)).encode()).hexdigest()
    name = "zapis-"+token
    saved = uloz.DATA / ".zfs/snapshot" / name / final.relative_to(uloz.DATA)
    if not saved.is_file():
        return False
    snap = uloz.DATASET+"@"+name
    held = any(line.split()[1]=="polarita-test" for line in uloz.run("zfs","holds","-H",snap).splitlines())
    if not held:
        return False
    with saved.open("rb") as stream:
        if hashlib.file_digest(stream,"sha256").hexdigest()!=digest:
            raise RuntimeError("Porušený kontrolní součet spisového hovoru ve snímku")
    return True


def missing(error):
    return error.response["ResponseMetadata"]["HTTPStatusCode"] == 404


def transfer(s3, key, metadata):
    uloz.check_host()
    record, encoded, record_id, paths, year = reference(metadata,key)
    with TemporaryDirectory(dir="/run") as directory:
        tmp = Path(directory)
        for part,ext in PARTS:
            digest = record["casti"][part]["sha256"]
            if verified_copy(year,digest,ext):
                continue
            try:
                obj = s3.get_object(Bucket="hovory",Key=paths[part])
            except ClientError as e:
                if missing(e):
                    return False
                raise
            with obj["Body"] as body:
                if ({k.lower():v for k,v in obj["Metadata"].items()} != metadata or not 0 < obj["ContentLength"] <= 128*1024*1024):
                    raise ValueError("Části hovoru nemají shodné předávací údaje nebo přípustnou délku")
                file = tmp/part
                with file.open("xb") as out:
                    for chunk in body.iter_chunks(1024*1024):
                        out.write(chunk)
            uloz.store(file,AREA,ext,digest,year)
            file.unlink()
        manifest = tmp/"predani.json"
        manifest.write_bytes(encoded)
        uloz.store(manifest,AREA,"json",record_id,year)
    if (not verified_copy(year,record_id,"json") or not all(
        verified_copy(year,record["casti"][p]["sha256"],ext) for p,ext in PARTS)):
        raise RuntimeError("Převzetí hovoru dosud nepotvrdil chráněný snímek")
    # Klíče obsahují otisk předání, takže různá verze hovoru má nový pár klíčů.
    # Neúplný nebo cizí pár se nikdy nepotvrdí jako převzatý.
    for part,ext in PARTS:
        try:
            obj = s3.get_object(Bucket="hovory",Key=paths[part])
        except ClientError as e:
            if missing(e):
                continue
            raise
        with obj["Body"] as stream:
            if {k.lower():v for k,v in obj["Metadata"].items()} != metadata or hashlib.file_digest(stream,"sha256").hexdigest()!=record["casti"][part]["sha256"]:
                raise ValueError("Obsah se po předání změnil")
    for source_key in paths.values():
        s3.delete_object(Bucket="hovory",Key=source_key)
    return True


def handover(s3,case,years,captured,audio,transcript):
    """Příjem uzavřených souborů od lokální testovací telefonní služby."""
    uloz.check_host()
    with wave.open(str(audio),"rb") as wav:
        if wav.getnchannels()!=2 or wav.getnframes()==0:
            raise ValueError("Spisová nahrávka musí mít dva kanály")
    files = {"zvuk":audio,"prepis":transcript}
    metadata = {"legal-hold":"true","spis":case,"retence-let":str(years),"porizeno":captured}
    for part,file in files.items():
        if not file.is_file() or file.is_symlink() or not 0 < file.stat().st_size <= 128*1024*1024:
            raise ValueError("Neplatná velikost nebo typ předávané části")
        with file.open("rb") as stream:
            metadata[part+"-sha256"] = hashlib.file_digest(stream,"sha256").hexdigest()
    with transcript.open("r",encoding="utf-8") as stream:
        while stream.read(1024*1024):
            pass
    _,_,record_id,paths,year = reference(metadata,None)
    with Path("/run/polarita-hovory-retence.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if verified_copy(year,record_id,"json") and all(
                verified_copy(year,metadata[p+"-sha256"],ext) for p,ext in PARTS):
            transfer(s3,paths["zvuk"],metadata)
            return record_id
        for part,path in files.items():
            with path.open("rb") as stream:
                s3.put_object(Bucket="hovory",Key=paths[part],Body=stream,Metadata=metadata)
        if not transfer(s3,paths["zvuk"],metadata):
            raise RuntimeError("Chybí část předávaného spisového hovoru")
    return record_id
