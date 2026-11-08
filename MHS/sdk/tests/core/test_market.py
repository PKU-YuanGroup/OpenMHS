"""The device market index (MHS/drivers/market.json) and `mhs serve <market id>`."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from mhs import market
from mhs.cli import main as cli_main

REPO = Path(__file__).resolve().parents[4]
DRIVERS = REPO / "MHS" / "drivers"


class MarketTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = market.load(DRIVERS)

    def test_committed_index_matches_the_drivers(self):
        self.assertEqual((DRIVERS / market.MARKET_FILE).read_text(encoding="utf-8"),
                         market.render(market.build(DRIVERS)),
                         "MHS/drivers/market.json is stale: run `python3 -m mhs market build`")

    def test_every_entry_passed_its_gate_and_says_how_to_serve_it(self):
        passing = sorted(p.parent.relative_to(DRIVERS).as_posix() for p in DRIVERS.glob("*/*/RESULT.json")
                         if json.loads(p.read_text(encoding="utf-8")).get("status") == "pass")
        self.assertEqual([e["id"] for e in self.document["packages"]], passing)
        self.assertEqual(self.document["count"], len(passing))
        for entry in self.document["packages"]:
            self.assertTrue(entry["intro"] and entry["category"] and entry["name"], entry["id"])
            self.assertEqual(entry["install"]["openai4s"], f"openai4s lab add {entry['id']}")
            self.assertEqual(entry["served_backend"], "fake")
            self.assertIn(entry["mode"], ("hardware", "simulated"))

    def test_find_accepts_ids_folders_and_unique_repository_names(self):
        julabo = "labs/tiagocoutinho__julabo"
        for name in (julabo, "tiagocoutinho__julabo", "julabo", "tiagocoutinho/julabo", "gh.tiagocoutinho/julabo",
                     "MHS/drivers/" + julabo):
            self.assertEqual(market.find(name, document=self.document)["id"], julabo, name)
        self.assertIsNone(market.find("no-such-device", document=self.document))
        self.assertEqual(market.resolve_package("julabo", DRIVERS), DRIVERS / julabo)

    def test_search_matches_every_word(self):
        hits = market.search("temperature controller", document=self.document)
        self.assertTrue(hits)
        for entry in hits:
            text = json.dumps(entry).lower()
            self.assertIn("temperature", text)
            self.assertIn("controller", text)
        self.assertTrue(all(e["track"] == "robots" for e in market.search("", track="robots", document=self.document)))

    def test_cli_show_and_unknown_serve_target(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli_main(["market", "show", "julabo"]), 0)
        self.assertIn("openai4s lab add labs/tiagocoutinho__julabo", out.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(cli_main(["serve", "definitely-not-a-package", "--stdio"]), 2)
        self.assertIn("market package", err.getvalue())


if __name__ == "__main__":
    unittest.main()
