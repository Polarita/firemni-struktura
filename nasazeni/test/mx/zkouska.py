"""Zkouška SMTP na vyhrazené testovací bráně uvnitř polarita-hq."""
import smtplib
import ssl
import subprocess
import time
import uuid

IP = "10.239.31.12"
HOST = "mx.polarita.test"
INSTANCE = "stalwart-mx-test"


def check():
    cert = subprocess.check_output(
        ["incus", "exec", INSTANCE, "--", "cat", "/var/lib/stalwart/tls/mx.crt"],
        text=True,
    )
    context = ssl.create_default_context(cadata=cert)
    marker = "zkouska-" + uuid.uuid4().hex[:12]
    recipients = [f"{marker}@polarita.cz", f"{marker}@example.invalid"]
    with smtplib.SMTP(local_hostname="zkouska.polarita.test", timeout=15) as client:
        assert client.connect(IP, 25)[0] == 220
        assert client.ehlo()[0] == 250 and client.has_extn("starttls")
        # SNI a kontrola jména dle SAN při přímém připojení na interní adresu.
        client._host = HOST
        assert client.starttls(context=context)[0] == 220
        assert client.ehlo()[0] == 250 and not client.has_extn("auth")
        print("STARTTLS s ověřeným jménem:", client.sock.version(), flush=True)
        assert client.mail("")[0] == 250
        for recipient in recipients:
            code, reply = client.rcpt(recipient)
            if not 500 <= code < 600:
                raise RuntimeError(f"RCPT {recipient}: {code} {reply!r}")
            print(f"Příjemce {recipient} odmítnut ({code})", flush=True)

    for attempt in range(10):
        recent = subprocess.check_output(
            ["incus", "exec", INSTANCE, "--", "sh", "-ec",
             'latest=$(ls -t /var/lib/stalwart/log/smtp.* | head -1); tail -n 100 "$latest"'],
            text=True,
        )
        denials = [line for line in recent.splitlines() if "(smtp.relay-not-allowed)" in line]
        if all(any(recipient in line for line in denials) for recipient in recipients):
            break
        if attempt == 9:
            raise RuntimeError("Chybí odpovídající záznamy o odmítnutí SMTP")
        time.sleep(1)

    print("Obě odmítnutí jsou zaznamenaná v protokolu Stalwart.")
    ports = subprocess.check_output(
        ["incus", "exec", INSTANCE, "--", "cat", "/proc/net/tcp", "/proc/net/tcp6"],
        text=True,
    )
    listeners = {(address,int(port,16)) for line in ports.splitlines()
                 if len(cols := line.split()) > 3 and cols[3]=="0A"
                 for address,port in [cols[1].split(":")]}
    # /proc/net/tcp uvádí IPv4 oktety v opačném pořadí. Na síti smí být pouze SMTP.
    if listeners != {("00000000",25),("0100007F",19090)}:
        raise RuntimeError(f"Neočekávaná vazba TCP služby MX: {sorted(listeners)}")
    print("SMTP je dostupné na portu 25 a telemetrie výhradně na místním loopbacku.")



if __name__ == "__main__":
    for attempt in range(50):
        try:
            check()
            break
        except (ConnectionRefusedError, subprocess.CalledProcessError):
            if attempt == 49:
                raise
            time.sleep(1)
