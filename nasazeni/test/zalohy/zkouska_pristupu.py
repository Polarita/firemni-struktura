"""Ověří skutečný zákaz výmazu v odděleném testovacím repozitáři a připraví kontrolní objekt Garage."""
import base64
from contextlib import closing
import hashlib
import json
import ssl
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from sber import CA,REPO,ensure_repo,provoz,rest,rest_env

SAMPLE_KEY = "zkouska/obnova-zalohy-test-v1.pgm"
SAMPLE = b"P2\n2 2\n255\n0 85\n170 255\n"


def main():
    env=rest_env(REPO.replace("/firma/","/zkouska-vymazu/"))
    ensure_repo(env)
    rows=json.loads(rest(env,"snapshots","--no-lock","--json",capture_output=True).stdout)
    if rows:
        snap=rows[0]["id"]
    else:
        run=rest(env,"backup","--json","--host","polarita-hq","--tag","zkouska-vymazu","--stdin",
                 "--stdin-filename","zkusebni-soubor.txt",input=b"Polarita TEST\n",stdout=-1)
        snap=next(x["snapshot_id"] for x in map(json.loads,run.stdout.splitlines()) if x["message_type"]=="summary")
    web=build_opener(ProxyHandler({}),HTTPSHandler(context=ssl.create_default_context(cafile=CA)))
    auth=base64.b64encode(("polarita-test:"+env["RESTIC_REST_PASSWORD"]).encode()).decode()
    url=env["RESTIC_REPOSITORY"].removeprefix("rest:")+"snapshots/"+snap
    def request(method):
        return web.open(Request(url,method=method,headers={"Authorization":"Basic "+auth}),timeout=10)
    with request("GET") as res:
        digest=hashlib.sha256(res.read()).digest()
    try:
        with request("DELETE"):
            raise RuntimeError("Klient vymazal zkušební snímek")
    except HTTPError as e:
        if e.code!=403:
            raise
    with request("GET") as res:
        if hashlib.sha256(res.read()).digest()!=digest:
            raise RuntimeError("Změna zkušebního snímku po odmítnutém výmazu")
    with provoz.manager() as admin:
        key=provoz.key_for("foto-staveb",admin)
    with closing(provoz.client(key)) as s3:
        try:
            obj=s3.get_object(Bucket="foto-staveb",Key=SAMPLE_KEY)
        except provoz.ClientError as error:
            if error.response["ResponseMetadata"]["HTTPStatusCode"]!=404:
                raise
            s3.put_object(Bucket="foto-staveb",Key=SAMPLE_KEY,Body=SAMPLE,ContentType="image/x-portable-graymap")
            obj=s3.get_object(Bucket="foto-staveb",Key=SAMPLE_KEY)
        with closing(obj["Body"]) as body:
            if body.read()!=SAMPLE:
                raise RuntimeError("Kolize názvu zkušební fotografie")
    print("Restic odmítl klientovi výmaz HTTP 403. Celý zkušební snapshot je po odmítnutí čitelný.")
    print("V samostatném koši Garage je pro kontrolu obnovy známý obrazový vzorek TEST.")


if __name__=="__main__":
    main()
