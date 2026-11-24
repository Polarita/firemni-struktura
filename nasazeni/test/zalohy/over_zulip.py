"""Porovná logicky obnovený chat s přílohami z téhož snímku Restic."""
import configparser
import json
import os
from pathlib import Path
import re
import socket
import subprocess


def query(sql):
    result = subprocess.run(
        ["runuser", "-u", "postgres", "--", "psql", "-XqAt", "-v", "ON_ERROR_STOP=1",
         "-U", "obnova_test", "-d", "zulip"],
        input=sql, text=True, capture_output=True, check=True,
    )
    return result.stdout.splitlines()


def verify(root):
    data = root / "zulip"
    if not data.exists() and query("SELECT to_regclass('public.zerver_realm') IS NULL") == ["t"]:
        return  # Vydání před instalací chatu.
    secrets = configparser.RawConfigParser()
    with (data / "zulip-secrets.conf").open() as stream:
        secrets.read_file(stream)
    if not all(secrets.get("secrets", key) for key in ("secret_key", "avatar_salt")):
        raise RuntimeError("Chybí nativní konfigurace obnoveného Zulipu")
    expected = json.loads((data / "pozice.json").read_bytes())
    if len(expected) != 20 or any(not re.fullmatch(r"1[1-8]\d{3}", code) for code in expected):
        raise RuntimeError("Neplatné karty pozic v obnově Zulipu")
    subscriptions = query("""
        SELECT DISTINCT json_build_array(u.delivery_email, u.full_name, s.name)::text
        FROM zerver_userprofile u
        JOIN zerver_realm r ON r.id=u.realm_id
        JOIN zerver_userprofile owner ON owner.id=u.bot_owner_id AND owner.realm_id=r.id
        JOIN zerver_subscription sub ON sub.user_profile_id=u.id AND sub.active
        JOIN zerver_stream s ON s.recipient_id=sub.recipient_id AND s.realm_id=r.id
        WHERE r.string_id='' AND r.name='Ředitelství Polarity' AND r.invite_required
          AND NOT r.enable_spectator_access AND owner.is_active AND owner.role=100
          AND owner.delivery_email='spravce@polarita.test' AND u.is_bot AND u.is_active
          AND s.invite_only AND NOT s.is_web_public AND NOT s.deactivated
    """)
    channels = dict(zip(("11","12","13","14","15","16","17","18"), (
        "11-vedeni","12-marketing","13-eshop-a-nakup","14-elektro-a-zakazky",
        "15-pravo-a-normy","16-finance-a-kancelar","17-it-secops","18-hr-a-teren",
    )))
    actual = {tuple(json.loads(row)) for row in subscriptions}
    for code, display in expected.items():
        if (f"ai-{code}-bot@polarita.test", display, channels[code[:2]]) not in actual:
            raise RuntimeError("Obnovený Zulip postrádá odběr účtu " + code)
    uploads = (data / "uploads/files").resolve(strict=True)
    rows = query("SELECT json_build_array(path_id, size) FROM zerver_attachment")
    for row in rows:
        name, size = json.loads(row)
        path = (uploads / name).resolve(strict=True)
        if not path.is_relative_to(uploads) or not path.is_file() or path.stat().st_size != size:
            raise RuntimeError("Příloha nesouhlasí s obnovenou databází Zulipu")
    sample = query("""
        SELECT a.path_id FROM zerver_attachment a
        JOIN zerver_attachment_messages am ON am.attachment_id=a.id
        JOIN zerver_message m ON m.id=am.message_id
        JOIN zerver_stream s ON s.recipient_id=m.recipient_id AND s.realm_id=a.realm_id
        JOIN zerver_userprofile u ON u.id=a.owner_id AND u.id=m.sender_id
        WHERE a.file_name='polarita-obnova-zulip-test-v1.txt' AND m.subject='POL-2026-00000'
          AND s.name='17-it-secops' AND u.delivery_email='spravce@polarita.test'
    """)
    if len(sample) != 1 or (uploads / sample[0]).read_bytes() != b"Polarita TEST Zulip 1\n":
        raise RuntimeError("Zpráva a obsah kontrolní přílohy se po obnově Zulipu liší")
    print(f"Obnova Zulipu ověřila správce, osm oddělení a dvacet odběrů botů. Počet ověřených příloh včetně souboru z testovací zprávy: {len(rows)}.")


if __name__ == "__main__":
    if not re.fullmatch("restic-obnova-[a-f0-9]{12}", socket.gethostname().split(".")[0]) or os.listdir("/sys/class/net") != ["lo"]:
        raise SystemExit("Kontrola vyžaduje izolovanou obnovu")
    verify(Path("/var/tmp/obnova-polarita"))
