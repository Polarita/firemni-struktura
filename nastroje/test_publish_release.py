import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import publish_release as release


class PublikaceTest(unittest.TestCase):
    def setUp(self):
        self.tag = "test-vydani"
        self.repo = "firma/projekt"
        self.expected = {"a.pdf":"sha256:a", "SHA256SUMS":"sha256:m"}
        self.draft = {"tag_name":self.tag,"id":11,"author":{"login":"github-actions[bot]"},"draft":True}
        self.uploaded = {"a.pdf":"sha256:a"}
        self.writes = []

    def gh(self,*args):
        if args[0] == "api":
            if "/assets?" in args[-1]:
                return json.dumps([[{"name":n,"digest":h,"state":"uploaded"} for n,h in self.uploaded.items()]])
            return json.dumps([[self.draft]])
        self.writes.append(args[:2])
        if args[:2] == ("release","upload"):
            self.assertIn("balik/SHA256SUMS",args)
            self.assertNotIn("balik/a.pdf",args)
            self.uploaded.update(self.expected)
            raise subprocess.CalledProcessError(1,["gh","release","upload"])
        if args[:2] == ("release","edit"):
            self.draft["draft"] = False
            return ""
        self.fail(args[:2])

    def dokonci(self):
        with patch.object(release,"gh",side_effect=self.gh):
            release.dokonci(self.repo,self.tag,Path("balik"),self.expected)

    def test_navazani_po_chybejici_odpovedi(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.dokonci()
        self.dokonci()
        self.dokonci()
        self.assertEqual(self.writes,[("release","upload"),("release","edit")])

    def test_odlisne_zverejnene_prilohy(self):
        self.draft["draft"] = False
        with self.assertRaises(ValueError):
            self.dokonci()
        self.assertEqual(self.writes,[])

    def test_neznama_priloha_konceptu(self):
        self.uploaded["jina.pdf"] = "sha256:x"
        with self.assertRaises(ValueError):
            self.dokonci()
        self.assertEqual(self.writes,[])
