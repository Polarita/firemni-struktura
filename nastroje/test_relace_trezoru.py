import importlib.util
from contextlib import ExitStack
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError

cesta = Path(__file__).resolve().parents[1] / "nasazeni/test/trezor/pristupy.py"
spec = importlib.util.spec_from_file_location("pristupy", cesta)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class RelaceTrezoru(TestCase):
    def test_pomala_kontrola_dokoncena_s_kratkymi_relacemi(self):
        cas = 0
        platne = {}
        prihlaseni = []
        hodnoty = {}

        def login(role):
            token = f"{role}-{len(prihlaseni)}"
            prihlaseni.append(role)
            platne[token] = (role, cas + (240 if role == "sprava" else 120))
            return token

        def over(token):
            role, konec = platne[token]
            self.assertLess(cas, konec)
            return role

        def credentials(role, manager):
            self.assertEqual(over(manager), "sprava")
            return role

        def inicializace(manager):
            nonlocal cas
            cas += 65
            self.assertEqual(over(manager), "sprava")

        def request(method, path, body=None, token=None):
            role = over(token)
            if path == "auth/token/revoke-self":
                del platne[token]
            elif role == "sprava" and method == "POST":
                hodnoty[path] = body
            elif role != "sprava" and method == "GET" and path == "test/data/" + role:
                return {"data": hodnoty[path]}
            else:
                raise HTTPError("TEST", 403, "Forbidden", {}, None)

        with ExitStack() as mocks:
            for name, value in (("login", login), ("credentials", credentials), ("request", request),
                                ("recover", lambda _: "sprava"), ("FIXTURES", {"a": ["a"], "b": ["b"]}),
                                ("DENIED", ["c"])):
                mocks.enter_context(patch.object(p, name, value))
            for name in ("database_passwords", "seal", "cache", "objects", "grade_token", "protocol_key"):
                mocks.enter_context(patch.object(p, "initialize_" + name, inicializace))
            p.verify_roles()
        self.assertGreater(cas, 240)
        self.assertFalse(platne)
        self.assertIn("a", prihlaseni)
        self.assertIn("b", prihlaseni)

    def test_vyjimka_ukonci_relaci(self):
        with patch.object(p, "login", return_value="relace"), patch.object(p, "request") as volani:
            with self.assertRaisesRegex(ValueError, "kontrola"):
                with p.relace("udaje"):
                    raise ValueError("kontrola")
        volani.assert_called_once_with("POST", "auth/token/revoke-self", {}, "relace")
