"""Živá zkouška přenosu dvou zvukových kanálů s přepisem z účelového koše do WORM."""
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import wave

import hovory
import uloz
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"objekty"))
import provoz


def main():
    uloz.check_host()
    captured = "2026-01-05T10:00:00+00:00"
    with TemporaryDirectory(dir="/run") as tmp:
        audio = Path(tmp)/"zvuk.wav"
        transcript = Path(tmp)/"prepis.txt"
        with wave.open(str(audio),"wb") as writer:
            writer.setparams((2,2,8000,0,"NONE","not compressed"))
            writer.writeframes(struct.pack("<hh",100,-100)*800)
        transcript.write_text("Kanál L a kanál R. Syntetický test předání.\n")
        metadata = {"legal-hold":"true","spis":"TEST-PRIJEM-0001","retence-let":"3","porizeno":captured,
                    "zvuk-sha256":hashlib.sha256(audio.read_bytes()).hexdigest(),
                    "prepis-sha256":hashlib.sha256(transcript.read_bytes()).hexdigest()}
        record,encoded,receipt,paths,year = hovory.reference(metadata,None)
        with provoz.manager() as admin:
            key = provoz.key_for("hovory",admin)
        with closing(provoz.client(key)) as s3:
            # Zkouší časovač s oběma původními S3 objekty včetně jejich času pořízení.
            for part,file in (("zvuk",audio),("prepis",transcript)):
                s3.put_object(Bucket="hovory",Key=paths[part],Body=file.read_bytes(),Metadata=metadata)
            provoz.expire(s3,datetime.now(timezone.utc))
            for path in paths.values():
                provoz.rejected(s3.head_object,404,Bucket="hovory",Key=path)
            if hovory.handover(s3,metadata["spis"],3,captured,audio,transcript)!=receipt:
                raise RuntimeError("Opakované předání stejného hovoru vytvořilo jiný spis")
            # Opakování po přerušení mezi dvěma výmazy již převzaté dvojice.
            s3.put_object(Bucket="hovory",Key=paths["prepis"],Body=transcript.read_bytes(),Metadata=metadata)
            provoz.expire(s3,datetime.now(timezone.utc))
            provoz.rejected(s3.head_object,404,Bucket="hovory",Key=paths["prepis"])
        for part,ext in hovory.PARTS:
            assert hovory.verified_copy(year,metadata[part+"-sha256"],ext)
        manifest = uloz.DATA/hovory.AREA/str(year)/receipt/"dokument.json"
        if manifest.read_bytes()!=encoded or not hovory.verified_copy(year,receipt,"json"):
            raise RuntimeError("Chybí neměnný předávací záznam")
        if json.loads(manifest.read_bytes())["uchovat_do"]!="2029-01-05":
            raise RuntimeError("Neplatná lhůta spisu")
    print("Garage předala stereo WAV a doslovný přepis spisu do WORM. Tři chráněné snímky souhlasí s originály.")
    print("Opakované předání i dokončení po přerušení mají stejnou účtenku a zdroje v provozním koši byly odstraněny.")


if __name__=="__main__":
    main()
