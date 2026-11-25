"""Otevře starší schéma v QElectroTech a ověří spoje po grafickém Uložit jako."""
from collections import Counter
from pathlib import Path
import os
import shutil
import subprocess
import time
from xml.etree import ElementTree as ET

SAMPLE = Path("/usr/share/qelectrotech/examples/741.qet")


def obvod(path):
    root = ET.parse(path).getroot()
    if root.tag != "project":
        raise ValueError("Soubor není projekt QElectroTech.")
    sheets = []
    for diagram in root.findall("diagram"):
        elements = {}
        terminals = {}
        for element in diagram.findall("elements/element"):
            uid = element.attrib["uuid"].lower()
            if uid in elements:
                raise ValueError("Dvě značky mají stejné UUID.")
            elements[uid] = (float(element.attrib["x"]), float(element.attrib["y"]))
            for pin in element.findall("terminals/terminal"):
                index = pin.attrib["id"]
                if index in terminals:
                    raise ValueError("Duplicitní číslo svorky.")
                terminals[index] = (uid, float(pin.attrib["x"]), float(pin.attrib["y"]))
        wires = Counter(tuple(sorted((terminals[w.attrib["terminal1"]], terminals[w.attrib["terminal2"]])))
                        for w in diagram.findall("conductors/conductor"))
        if not elements or not wires:
            raise ValueError("Vzor vyžaduje značky i spoje.")
        sheets.append((elements, wires))
    if not sheets:
        raise ValueError("Projekt nemá žádné schéma.")
    return sheets


def window(pattern, app, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if app.poll() is not None:
            raise RuntimeError("Editor skončil před uložením projektu.")
        windows = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", pattern],
                                 capture_output=True, text=True, check=False)
        if windows.returncode == 0 and windows.stdout.strip():
            return windows.stdout.splitlines()[-1]
        time.sleep(0.5)
    raise TimeoutError(f"Editor neotevřel očekávané okno ({pattern}).")


def key(*args):
    subprocess.run(["xdotool", *args], check=True, timeout=15)


def main():
    if os.getuid() == 0 or os.listdir("/sys/class/net") != ["lo"]:
        raise RuntimeError("Zkouška vyžaduje běžný účet a odpojenou síť.")
    project = Path.cwd() / "vstup.qet"
    result = Path.cwd() / "ulozeno.qet"
    shutil.copyfile(SAMPLE, project)
    expected = obvod(project)
    with Path("editor.log").open("w") as log:
        app = subprocess.Popen(["/opt/polarita/qet/AppRun", str(project)], stdout=log, stderr=log)
        try:
            main_window = window("QElectroTech", app, 240)
            key("windowfocus", "--sync", main_window)
            # Během načítání může být už vidět úvodní obrazovka.
            for attempt in range(8):
                key("key", "--clearmodifiers", "ctrl+shift+s")
                try:
                    dialog = window("Save|Enregistrer|Uložit", app, 15)
                    break
                except TimeoutError:
                    if attempt == 7:
                        raise
                    key("windowfocus", "--sync", window("QElectroTech", app, 30))
            key("windowfocus", "--sync", dialog)
            key("key", "ctrl+a")
            key("type", "--clearmodifiers", str(result))
            key("key", "Return")
            end = time.monotonic() + 90
            while time.monotonic() < end and not result.is_file():
                time.sleep(0.5)
            if not result.is_file() or obvod(result) != expected:
                raise ValueError("Po uložení se liší značky, jejich umístění nebo zapojení svorek.")
            print(f"QElectroTech otevřel a uložil vzor 741.qet. Listů {len(expected)}, "
                  f"značek {sum(len(e) for e, _ in expected)}, spojů {sum(w.total() for _, w in expected)}.",
                  flush=True)
        finally:
            if app.poll() is None:
                app.terminate()
                try:
                    app.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    app.kill()
                    app.wait()


if __name__ == "__main__":
    main()
