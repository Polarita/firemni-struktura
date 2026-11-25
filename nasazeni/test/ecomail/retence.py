"""Místní protějšek retenčního seznamu a schránka doručených zpráv v TEST."""
import argparse
import base64
from contextlib import closing
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formatdate, make_msgid
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys

import dkim

STATE = Path("/srv/polarita/workspace/ecomail-test")
KEY = Path("/etc/polarita-ecomail-test")
PREFIX = "/ecomail-test/odhlaseni/"
ONE_CLICK = "List-Unsubscribe=One-Click"
HEADERS = [b"From", b"To", b"Subject", b"Date", b"Message-ID", b"List-Unsubscribe", b"List-Unsubscribe-Post"]
SCHEMA = """
CREATE TABLE IF NOT EXISTS kontakty (
    seznam TEXT, email TEXT, titul TEXT NOT NULL CHECK(titul IN ('souhlas','zakaznik','zadny')),
    odhlaseno INTEGER NOT NULL DEFAULT 0 CHECK(odhlaseno IN (0,1)), PRIMARY KEY(seznam,email)
) STRICT;
CREATE TABLE IF NOT EXISTS kampane (
    seznam TEXT, kolo INTEGER, PRIMARY KEY(seznam,kolo)
) STRICT;
CREATE TABLE IF NOT EXISTS schranka (
    seznam TEXT, kolo INTEGER, email TEXT, titul TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
    eml BLOB NOT NULL, PRIMARY KEY(seznam,kolo,email),
    FOREIGN KEY(seznam,email) REFERENCES kontakty, FOREIGN KEY(seznam,kolo) REFERENCES kampane
) STRICT;
"""

def titul(souhlas, prodej, obdobna_sluzba, moznost_odmitnout):
    if souhlas:
        return "souhlas"
    if prodej and obdobna_sluzba and moznost_odmitnout:
        return "zakaznik"
    return "zadny"


def importuj(db, seznam, email, duvod):
    if not re.fullmatch(r"[a-z0-9-]{1,48}@polarita\.test", email):
        raise ValueError("TEST přijímá pouze syntetické kontakty.")
    db.execute("""INSERT INTO kontakty(seznam,email,titul) VALUES(?,?,?)
        ON CONFLICT(seznam,email) DO UPDATE SET titul=excluded.titul""", (seznam,email,duvod))


def zprava(email, host, secret):
    url = "https://" + host + PREFIX + secret
    msg = EmailMessage(policy=SMTP.clone(max_line_length=998))
    msg["From"] = "Polarita TEST <retence@polarita.test>"
    msg["To"] = email
    msg["Subject"] = "Obchodní sdělení TEST – servis elektroinstalace"
    msg["Date"] = formatdate(localtime=False, usegmt=True)
    msg["Message-ID"] = make_msgid(domain="polarita.test")
    msg["List-Unsubscribe"] = "<" + url + ">"
    msg["List-Unsubscribe-Post"] = ONE_CLICK
    msg.set_content("Modelová nabídka servisu Polarita TEST.\nOdhlášení z odběru: " + url)
    raw = msg.as_bytes()
    signature = dkim.sign(raw, b"retence", b"polarita.test", (KEY/"test.key").read_bytes(), include_headers=HEADERS)
    return signature + raw


def kampan(db, seznam, kolo, host):
    if not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+\.ts\.net", host):
        raise ValueError("Odkaz musí vést na TEST v tailnetu.")
    # Zámek zahrnuje výběr příjemců i doručení do místní schránky.
    with db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("INSERT OR IGNORE INTO kampane VALUES(?,?)", (seznam,kolo)).rowcount:
            return
        for email, duvod in db.execute("SELECT email,titul FROM kontakty WHERE seznam=? AND titul!='zadny' AND odhlaseno=0", (seznam,)):
            token = secrets.token_urlsafe(32)
            db.execute("INSERT INTO schranka VALUES (?,?,?,?,?,?)", (
                seznam,kolo,email,duvod,hashlib.sha256(token.encode()).hexdigest(),zprava(email,host,token)))


def prihlas_vzory(db, seznam):
    rows = [("souhlas", True,False,False,False), ("zakaznik", False,True,True,True),
            ("cizi", False,False,True,True), ("bez-volby", False,True,True,False),
            ("jiny-produkt",False,True,False,True)]
    with db:
        for jmeno,*evidence in rows:
            importuj(db, seznam, jmeno+"@polarita.test", titul(*evidence))


def odhlaseni(db):
    raw = sys.stdin.buffer.readline(56)
    match = re.fullmatch(rb"(GET|POST) ([A-Za-z0-9_-]{43})\n", raw)
    if not match:
        print(400)
        return
    with db:
        db.execute("BEGIN IMMEDIATE" if match[1] == b"POST" else "BEGIN")
        kontakt = db.execute("SELECT seznam,email FROM schranka WHERE token_hash=?", (hashlib.sha256(match[2]).hexdigest(),)).fetchone()
        if kontakt and match[1] == b"POST":
            db.execute("UPDATE kontakty SET odhlaseno=1 WHERE seznam=? AND email=? AND odhlaseno=0", kontakt)
    print(200 if kontakt else 404)


def prehled(db):
    return [{"seznam": seznam, "kolo": kolo, "souhlas": s, "zakaznik": z} for seznam,kolo,s,z in
            db.execute("""SELECT k.seznam,k.kolo,count(s.email) FILTER (WHERE titul='souhlas'),
            count(s.email) FILTER (WHERE titul='zakaznik') FROM kampane k LEFT JOIN schranka s USING(seznam,kolo)
            GROUP BY k.seznam,k.kolo ORDER BY k.rowid DESC LIMIT 50""")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["init","request","prvni","druha","prehled","zprava"])
    parser.add_argument("--seznam", default="servis-test")
    parser.add_argument("--host")
    parser.add_argument("--kontrola-zakaznika", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,64}", args.seznam):
        parser.error("Neplatný seznam")
    os.umask(0o077)
    with closing(sqlite3.connect(STATE/"retence.sqlite3",timeout=12)) as db:
        db.execute("PRAGMA foreign_keys=ON")
        if args.action == "init":
            db.executescript(SCHEMA)
        elif args.action == "request":
            odhlaseni(db)
        elif args.action == "prehled":
            print(json.dumps({"available": True, "campaigns": prehled(db)}))
        elif args.action == "zprava":
            adresa = "zakaznik@polarita.test" if args.kontrola_zakaznika else "souhlas@polarita.test"
            raw, = db.execute("SELECT eml FROM schranka WHERE seznam=? AND kolo=1 AND email=?", (args.seznam,adresa)).fetchone()
            public = b"v=DKIM1; k=rsa; p="+base64.b64encode((KEY/"test.der").read_bytes())
            if not dkim.verify(raw, dnsfunc=lambda n,**kw: public if n.rstrip(b".")==b"retence._domainkey.polarita.test" else None):
                raise ValueError("Podpis zprávy nesouhlasí.")
            sys.stdout.buffer.write(raw)
        else:
            prihlas_vzory(db, args.seznam)
            kolo = 1 if args.action == "prvni" else 2
            kampan(db,args.seznam,kolo,args.host)
            prijemci = set(db.execute("SELECT email,titul FROM schranka WHERE seznam=? AND kolo=?", (args.seznam,kolo)))
            expected = {("zakaznik@polarita.test","zakaznik")}
            if kolo == 1:
                expected.add(("souhlas@polarita.test","souhlas"))
            if prijemci != expected:
                raise RuntimeError("Nesouhlasí skuteční příjemci testovací kampaně.")
            print(f"Kampaň {kolo} · ověřeno příjemců v místní schránce: {len(prijemci)}.")

if __name__ == "__main__":
    main()
