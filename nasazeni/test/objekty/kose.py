"""Založí omezené přístupy v lokálním správním API Garage. Vstup obsahuje klíče jen v paměti."""
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

LOCAL = build_opener(ProxyHandler({}))
URL = "http://127.0.0.1:3903/v2/"


def main():
    token = Path("/run/secrets/garage-admin").read_text().strip()
    def api(action, query=None, body=None, optional=False):
        endpoint = URL + action + ("?" + urlencode(query) if query else "")
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
        data = json.dumps(body).encode() if body is not None else None
        try:
            with LOCAL.open(Request(endpoint, headers=headers, data=data), timeout=15) as result:
                return json.load(result)
        except HTTPError as error:
            if optional and error.code == 404:
                return None
            raise RuntimeError(f"Garage {action} vrátil HTTP {error.code}") from None

    for bucket, key in json.load(sys.stdin).items():
        info = api("GetBucketInfo", {"globalAlias": bucket}, optional=True)
        if info is None:
            info = api("CreateBucket", body={"globalAlias": bucket})
        identity = {"id": key["id"]}
        account = api("GetKeyInfo", identity, optional=True)
        if account is None:
            account = api("ImportKey", body={"accessKeyId": key["id"], "secretAccessKey": key["tajemstvi"],
                                             "name": "polarita-test-" + bucket})
        if account["name"] != "polarita-test-" + bucket or account["permissions"].get("createBucket"):
            raise RuntimeError("Neočekávaná identita nebo práva přístupu S3")
        perm = {"read": True, "write": True, "owner": False}
        if not account["buckets"]:
            api("AllowBucketKey", body={"bucketId": info["id"], "accessKeyId": key["id"], "permissions": perm})
        linked = api("GetKeyInfo", identity)["buckets"]
        if len(linked) != 1 or linked[0]["id"] != info["id"] or linked[0]["permissions"] != perm:
            raise RuntimeError("Rozsah práv ke koši neodpovídá jeho účelu")
    print("Osm košů má každý vlastní omezený přístup.")


if __name__ == "__main__":
    main()
