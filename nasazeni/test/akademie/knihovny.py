"""Ověří shodu distribučních archivů se zámkem Composeru z vydání Moodle."""
import json
from pathlib import Path
import re
import sys

from podklady import CACHE, prepare


def archives(lock, pins):
    packages = {}
    urls = {}
    for package in lock["packages"]:
        name = package["name"]
        dist = package["dist"]
        url = re.fullmatch(r"https://api\.github\.com/repos/([\w.-]+/[\w.-]+)/zipball/([a-f0-9]{40})",
                           dist["url"])
        if (not url or dist["type"] != "zip" or package["type"] != "library"
                or url[2] != dist["reference"] or url[2] != package["source"]["reference"]
                or url[2] != pins[name]["reference"]):
            raise ValueError(f"Distribuce neodpovídá uzamčenému zdroji {name}")
        filename = url[2] + ".zip"
        packages[filename] = {"url": f"https://codeload.github.com/{url[1]}/legacy.zip/{url[2]}",
                              "sha256": pins[name]["sha256"]}
        urls[name] = filename
    if set(pins) != set(urls):
        raise ValueError("Nesouhlasí seznam provozních závislostí Moodle")
    return packages, urls


if __name__ == "__main__":
    original, output = map(Path, sys.argv[1:])
    lock = json.loads(original.read_text())
    pins = json.loads(Path(__file__).with_name("knihovny.lock.json").read_text())
    packages, urls = archives(lock, pins)
    prepare(CACHE / "composer", packages)
    # Do pracovního zámku Composeru vstupují jen ověřené místní ZIPy. Aplikace
    # si ponechá původní composer.lock dodaný Moodlem.
    for package in lock["packages"]:
        package["dist"]["url"] = "file:///opt/polarita-composer/" + urls[package["name"]]
    output.write_text(json.dumps(lock))
