"""Provede lokální PJSIP hovor mezi dvěma klapkami a ověří oba směry přenosu RTP."""
from array import array
import hashlib
import math
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import sysconfig
import tempfile
import time
import wave

VZORKY = 8000
SRC = Path(__file__).resolve().parent


def zapis_wav(path, pocet_kanalu, vzorky):
    if sys.byteorder != "little":
        vzorky.byteswap()
    with wave.open(str(path), "wb") as output:
        output.setparams((pocet_kanalu, 2, VZORKY, 0, "NONE", "not compressed"))
        output.writeframes(vzorky.tobytes())


def mono(path):
    with wave.open(str(path), "rb") as source:
        if source.getparams()[:3] != (1, 2, VZORKY):
            raise ValueError("MixMonitor nevrátil mono PCM 8 kHz.")
        vzorky = array("h", source.readframes(source.getnframes()))
    if sys.byteorder != "little":
        vzorky.byteswap()
    return vzorky


def over_ton(vzorky, hz):
    # Ve 400 vzorcích mají oba testovací tóny celý počet period.
    n = 400
    cos = [math.cos(2 * math.pi * hz * i / VZORKY) for i in range(n)]
    sin = [math.sin(2 * math.pi * hz * i / VZORKY) for i in range(n)]
    okna = 0
    for start in range(0, len(vzorky) - n + 1, n):
        okno = vzorky[start:start + n]
        energie = sum(x * x for x in okno)
        if energie < 1000 * 1000 * n:
            continue
        a = sum(x * y for x, y in zip(okno, cos))
        b = sum(x * y for x, y in zip(okno, sin))
        if 2 * (a * a + b * b) > 0.8 * n * energie:
            okna += 1
    if okna < 20:
        raise ValueError(f"V nahrávce chybí alespoň jedna sekunda tónu {hz} Hz.")


def konfigurace(d):
    (d / "pjsip.conf").write_text((SRC / "pjsip.conf").read_text().replace("@HESLO@", secrets.token_hex(24)))
    (d / "extensions.conf").write_text((SRC / "extensions.conf").read_text().replace("@ADRESAR@", str(d)))
    (d / "modules.conf").write_text("[modules]\nautoload=yes\nnoload=chan_iax2.so\nnoload=chan_skinny.so\n")
    (d / "rtp.conf").write_text("[general]\nrtpstart=12000\nrtpend=12020\nicesupport=no\n")
    (d / "logger.conf").write_text("[logfiles]\nconsole => error,warning\n")
    moduly = Path("/usr/lib") / sysconfig.get_config_var("MULTIARCH") / "asterisk/modules"
    if not (moduly / "chan_pjsip.so").is_file():
        raise RuntimeError("V balíčku Asterisk chybí modul PJSIP.")
    soukrome_adresare = ("astetcdir", "astvarlibdir", "astdbdir", "astkeydir",
                         "astspooldir", "astrundir", "astlogdir", "astcachedir")
    radky = ["[directories]", f"astmoddir => {moduly}", "astdatadir => /usr/share/asterisk"]
    radky.extend(f"{key} => {d}" for key in soukrome_adresare)
    radky.extend(["", "[options]", "nocolor=yes", "dontwarn=yes", "entityid=02:00:00:00:81:01", ""])
    (d / "asterisk.conf").write_text("\n".join(radky))
    for hz in (440, 880):
        ton = array("h", (round(8500 * math.sin(2 * math.pi * hz * i / VZORKY)) for i in range(3 * VZORKY)))
        zapis_wav(d / f"ton-{hz}.wav", 1, ton)


def proved(d, vystup):
    konfigurace(d)
    base = ["/usr/sbin/asterisk", "-C", str(d / "asterisk.conf")]

    def cli(prikaz):
        return subprocess.run(base + ["-rx", prikaz], cwd=d, capture_output=True, text=True, timeout=15)

    with (d / "daemon.log").open("wb") as log:
        daemon = subprocess.Popen(base + ["-f"], cwd=d, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(90):
                if daemon.poll() is not None:
                    raise RuntimeError("Testovací Asterisk se zastavil při startu.")
                if (d / "asterisk.ctl").is_socket():
                    napoveda = cli("core show help channel originate").stdout
                    if "extension" in napoveda and "prijem" in cli("pjsip show endpoints").stdout:
                        break
                time.sleep(1)
            else:
                raise RuntimeError("Ústředna nepřipravila místní koncové body.")
            pokyn = cli("channel originate PJSIP/volajici extension 8101@volajici")
            if pokyn.returncode or "No such command" in pokyn.stdout:
                raise RuntimeError("PJSIP hovor nelze zahájit.")
            for _ in range(60):
                if (d / "prijem.wav").exists() and "0 active channels" in cli("core show channels").stdout.splitlines():
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Hovor na klapku 8202 neskončil se záznamem MixMonitor.")
        finally:
            if daemon.poll() is None:
                try:
                    cli("core stop now")
                    daemon.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    daemon.kill()
                    daemon.wait()
    prijem, vysilani = mono(d / "prijem.wav"), mono(d / "vysilani.wav")
    if len(prijem) != len(vysilani):
        raise ValueError("Časová osa příjmu a vysílání má různou délku.")
    over_ton(prijem, 880)
    over_ton(vysilani, 440)
    stereo = array("h", [0]) * (2 * len(prijem))
    stereo[::2], stereo[1::2] = prijem, vysilani
    zapis_wav(vystup, 2, stereo)
    with vystup.open("rb") as f:
        otisk = hashlib.file_digest(f, "sha256").hexdigest()
    print(f"PJSIP 8101 → 8202, přenos RTP a MixMonitor ověřeny. Stereo PCM, 8000 Hz, {len(prijem)} vzorků na kanál.")
    print(f"Levý kanál příjem 880 Hz, pravý kanál vysílání 440 Hz. SHA-256 WAV {otisk}.")


if __name__ == "__main__":
    if os.geteuid() == 0 or socket.gethostname().split(".")[0] != "asterisk-test":
        sys.exit("Hovor TEST patří neprivilegovanému účtu v instanci asterisk-test.")
    if [name for _, name in socket.if_nameindex()] != ["lo"]:
        sys.exit("Test vyžaduje pouze lokální rozhraní.")
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="polarita-pbx-") as tmp:
        proved(Path(tmp), Path(sys.argv[1]))
