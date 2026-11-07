"""G7 resolves a transport family's ``native`` in the clone (RUNTIME-AND-GATE-FIXES).

Before this change G7 checked a serial or SCPI driver's sent command tokens and never looked at ``native``, so an
invented symbol passed (moler-group/scanning-squid named ``scanning_squid.instruments.heater:EL320P``, a module path
the clone does not have).  A transport family's native is provenance and is never imported: a class, a module-level
function or a module-level name of the pinned clone.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from mhs.driver.check import Gate, _g7
from mhs.driver.upstream import definition_surface
from tests.driver.test_upstream import tree_with

FILES = {
    "keithley2400.py": "import pyvisa\n\ndef open_connection():\n    return pyvisa.ResourceManager().open_resource('X')\n",
    "AgilentControl.py": ("import pyvisa\nrm = pyvisa.ResourceManager()\n\nif __name__ == '__main__':\n"
                          "    inst = rm.open_resource('TCPIP::1::INSTR')\n    inst.write('*RST')\n"),
    "drivers/__init__.py": "from .supply import PowerSupply\n",
    "drivers/supply.py": "class PowerSupply:\n    def output(self, on):\n        pass\n",
    "scanning-squid/instruments/heater.py": "class EL320P:\n    pass\n",
    "tools.py": "def helper():\n    class Hidden:\n        pass\n    local_name = 1\n    return Hidden\n",
    "tricky.py": ("from typing import TYPE_CHECKING\nimport typing\n"
                  "Annotated: int\n"
                  "Augmented += 1\n"
                  "if False:\n    Dead = 1\nelse:\n    Alive = 1\n"
                  "if 0:\n    def dead_function():\n        pass\n"
                  "if TYPE_CHECKING:\n    from drivers.supply import PowerSupply as Typed\n    Checked = 1\n"
                  "if typing.TYPE_CHECKING:\n    Checked2 = 1\n"
                  "while False:\n    Looped = 1\n"
                  "Gone = 1\ndel Gone\n"
                  "class Vanished:\n    pass\n\ndel Vanished\n"
                  "Back = 1\ndel Back\nBack = 2\n"
                  "Valued: int = 3\n"),
}


def _g7_findings(test, tree, native, family="scpi", card=None):
    ctx = SimpleNamespace(cls=SimpleNamespace(native=native), family=family, tree=tree, card=card or {}, logs=[],
                          transport_family=True)
    gate = Gate("G7", "Native surface")
    with patch("mhs.driver.check._fake_target", return_value=None), \
         patch("mhs.driver.check._fake_members", return_value=set()), \
         patch("mhs.driver.check._g7_transport"), \
         patch("mhs.driver.ros_check.check_ros_surface"):
        _g7(ctx, gate)
    return [(finding.code, finding.message) for finding in gate.findings]


class DefinitionSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = tree_with(self, FILES)

    def test_a_class_a_function_and_a_module_level_name_resolve(self) -> None:
        for symbol, line in (("drivers.supply:PowerSupply", 1), ("keithley2400:open_connection", 3),
                             ("AgilentControl:rm", 2), ("AgilentControl:inst", 5), ("drivers:PowerSupply", 1)):
            with self.subTest(symbol=symbol):
                surface = definition_surface(self.tree, symbol)
                self.assertTrue(surface.found, surface.problems)
                self.assertEqual(surface.line, line)

    def test_an_invented_module_or_name_does_not_resolve(self) -> None:
        missing = definition_surface(self.tree, "scanning_squid.instruments.heater:EL320P")
        self.assertFalse(missing.found)
        self.assertIn("is not in the clone", missing.problems[0])
        absent = definition_surface(self.tree, "keithley2400:close_connection")
        self.assertFalse(absent.found)
        self.assertIn("close_connection is not defined in keithley2400.py", absent.problems[0])

    def test_names_inside_a_function_are_not_module_level(self) -> None:
        for symbol in ("tools:Hidden", "tools:local_name"):
            with self.subTest(symbol=symbol):
                self.assertFalse(definition_surface(self.tree, symbol).found)

    def test_only_what_the_module_binds_when_it_runs_counts(self) -> None:
        # S9-07: a bare annotation, an augmented assignment, a branch that never runs (if False / if 0 /
        # if TYPE_CHECKING / while False) and a deleted name bind nothing; the else branch and a re-binding do.
        for symbol in ("tricky:Annotated", "tricky:Augmented", "tricky:Dead", "tricky:dead_function", "tricky:Typed",
                       "tricky:Checked", "tricky:Checked2", "tricky:Looped", "tricky:Gone", "tricky:Vanished"):
            with self.subTest(symbol=symbol):
                self.assertFalse(definition_surface(self.tree, symbol).found)
        for symbol, line in (("tricky:Alive", 8), ("tricky:Back", 27), ("tricky:Valued", 28)):
            with self.subTest(symbol=symbol):
                surface = definition_surface(self.tree, symbol)
                self.assertTrue(surface.found, surface.problems)
                self.assertEqual(surface.line, line)

    def test_the_card_file_hint_finds_a_module_outside_the_import_path(self) -> None:
        # The clone's package directory has a hyphen, so no dotted path reaches it without the card's file.
        surface = definition_surface(self.tree, "instruments.heater:EL320P",
                                     hint_file="scanning-squid/instruments/heater.py")
        self.assertTrue(surface.found, surface.problems)


class TransportNativeGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = tree_with(self, FILES)

    def test_an_invented_native_fails_g7(self) -> None:
        findings = _g7_findings(self, self.tree, "scanning_squid.instruments.heater:EL320P")
        self.assertEqual([code for code, _message in findings], ["G7.NATIVE_NOT_FOUND"])
        self.assertIn("must exist in the clone", findings[0][1])

    def test_an_existing_class_function_or_name_passes(self) -> None:
        for native in ("drivers.supply:PowerSupply", "keithley2400:open_connection", "AgilentControl:inst"):
            with self.subTest(native=native):
                self.assertEqual(_g7_findings(self, self.tree, native), [])
        for family in ("serial", "http", "sila2", "mcp-client"):
            with self.subTest(family=family):
                with patch("mhs.driver.http_check.check_http_surface"), \
                     patch("mhs.driver.sila2_check.check_sila2_surface"), \
                     patch("mhs.driver.mcp_client_check.check_mcp_client_surface"):
                    self.assertEqual([code for code, _ in _g7_findings(self, self.tree, "nowhere:Thing", family)],
                                     ["G7.NATIVE_NOT_FOUND"])

    def test_the_card_file_hint_is_used(self) -> None:
        card = {"entry_symbols": [{"symbol": "instruments.heater:EL320P",
                                   "file": "scanning-squid/instruments/heater.py", "line": 1}]}
        self.assertEqual(_g7_findings(self, self.tree, "instruments.heater:EL320P", card=card), [])

    def test_a_ros_driver_without_a_native_class_has_nothing_to_resolve(self) -> None:
        self.assertEqual(_g7_findings(self, self.tree, None, family="ros"), [])
        self.assertEqual([code for code, _ in _g7_findings(self, self.tree, "nodes.invented:Node", family="ros")],
                         ["G7.NATIVE_NOT_FOUND"])


if __name__ == "__main__":
    unittest.main()
