"""G7 for a native class that the upstream exposes only through pybind11 binding source (``pybind:`` selectors)."""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from mhs.driver import Driver
from mhs.driver.check import Gate, _g7
from mhs.driver.model import check_class_attributes
from mhs.driver.pybind_surface import pybind_surface
from mhs.driver.source_selector import parse_pybind_selector, parse_selector
from mhs.testing.recorder import RecordLog
from tests.driver import gate_support as gs
from tests.driver.test_upstream import tree_with

BINDER = '''#include <mvsim/Comms/Client.h>
// cl.def("commented", ...) in a line comment is not a member
void bind_mvsim_Comms_Client(std::function<pybind11::module&(std::string const& namespace_)>& M)
{
	{  // mvsim::Client file:mvsim/Comms/Client.h line:48
		pybind11::class_<mvsim::Client, std::shared_ptr<mvsim::Client>> cl(
			M("mvsim"), "Client",
			"Doc string with cl.def(\\"quoted\\") inside");
		cl.def(pybind11::init([]() { return new mvsim::Client(); }));
		// cl.def("ghost", ...) in a line comment inside the block is not a member
		cl.def("setName", (void(mvsim::Client::*)(const std::string&)) & mvsim::Client::setName);
		/* cl.def("blocked", ...) in a block comment */
		cl.def(
			"callService",
			[](mvsim::Client& self, const std::string& name, const pybind11::bytes& in) -> pybind11::bytes
			{
				return pybind11::bytes(self.callService(name, std::string(in)));
			},
			pybind11::arg("serviceName"), pybind11::arg("inputSerializedMsg"));
		cl.def_static("make", &mvsim::Client::make);
		cl.def_readwrite("name", &mvsim::Client::name);
		cl.def_property_readonly("port", &mvsim::Client::serverPort);
		{  // mvsim::Client::InfoPerNode
			auto& enclosing_class = cl;
			pybind11::class_<mvsim::Client::InfoPerNode, std::shared_ptr<mvsim::Client::InfoPerNode>>
				cl(enclosing_class, "InfoPerNode", "");
			cl.def("assign", &mvsim::Client::InfoPerNode::operator=);
		}
	}
	{
		pybind11::class_<mvsim::Other> cl(M("mvsim"), "Other", "");
		cl.def("afterwards", &mvsim::Other::afterwards);
	}
}
'''

PLAIN = '''PYBIND11_MODULE(example, m) {
    py::class_<Pet>(m, "Pet");
    py::class_<Dog> dog(m, "Dog");
    dog.def("bark", &Dog::bark);
}
'''

SELECTOR = "pybind:bind/Client.cpp#mvsim.Client"


class PybindSelectorTests(unittest.TestCase):
    def test_forms(self) -> None:
        selector = parse_pybind_selector(SELECTOR)
        self.assertEqual((selector.path, selector.scope, selector.name), ("bind/Client.cpp", "mvsim", "Client"))
        nested = parse_pybind_selector("pybind:a/b.cc#outer.inner.Name")
        self.assertEqual((nested.scope, nested.name), ("outer::inner", "Name"))
        self.assertEqual(parse_pybind_selector("pybind:b.cxx#Dog").scope, "")
        self.assertIsNone(parse_selector(SELECTOR), "pybind selectors are not Python selectors")

    def test_unsafe_or_malformed_selectors(self) -> None:
        for value in ("pybind:../a.cpp#x.Y", "pybind:/a.cpp#x.Y", "pybind:a//b.cpp#x.Y", "pybind:a.py#x.Y",
                      "pybind:a.h#x.Y", "pybind:a.cpp", "pybind:a.cpp#", "pybind:a.cpp#x.", "pybind:a.cpp#x.Y()",
                      "pybind:a.cpp#x#Y", "pyfile:a.py#X", "a.b:C", None, 3):
            with self.subTest(value=value):
                self.assertIsNone(parse_pybind_selector(value))

    def test_model_accepts_a_pybind_native(self) -> None:
        class Bound(Driver):
            device_id, device_kind = "probe", "robot.mobile_base"
            native = SELECTOR
        problems = []
        attrs = check_class_attributes(Bound, problems, native_symbol=Bound.native, safe_state=None)
        self.assertEqual(attrs["native_symbol"], SELECTOR)
        self.assertFalse(any("native must" in problem for problem in problems), problems)
        problems = []
        check_class_attributes(Bound, problems, native_symbol="pybind:../x.cpp#a.B", safe_state=None)
        self.assertTrue(any("native must" in problem for problem in problems), problems)


class PybindSurfaceTests(unittest.TestCase):
    def surface(self, value=SELECTOR, files=None):
        return pybind_surface(tree_with(self, files or {"bind/Client.cpp": BINDER}), parse_pybind_selector(value))

    def test_members_at_the_declaration_depth_only(self) -> None:
        surface = self.surface()
        self.assertTrue(surface.found, surface.problems)
        self.assertEqual(surface.names, {"setName", "callService", "make", "name", "port"})
        for commented in ("commented", "ghost", "blocked", "quoted"):
            self.assertNotIn(commented, surface.names)
        self.assertEqual((surface.file, surface.line), ("bind/Client.cpp", 6))

    def test_a_nested_class_is_selected_by_its_own_name(self) -> None:
        surface = self.surface("pybind:bind/Client.cpp#InfoPerNode")
        self.assertEqual(surface.names, {"assign"})

    def test_plain_module_form(self) -> None:
        surface = self.surface("pybind:pet.cpp#Dog", {"pet.cpp": PLAIN})
        self.assertEqual(surface.names, {"bark"})
        chained = self.surface("pybind:pet.cpp#Pet", {"pet.cpp": PLAIN})
        self.assertFalse(chained.found)
        self.assertIn("without a variable name", chained.problems[0])
        empty = self.surface("pybind:pet.cpp#Cat", {"pet.cpp": PLAIN + 'py::class_<Cat> cat(m, "Cat");\n'})
        self.assertFalse(empty.found)
        self.assertIn("binds no named member", empty.problems[0])

    def test_missing_ambiguous_or_unreadable_declarations_fail(self) -> None:
        for value, files, text in (
            ("pybind:bind/Client.cpp#mvsim.Missing", None, "has no pybind11 class_ declaration"),
            ("pybind:bind/Client.cpp#other.Client", None, "has no pybind11 class_ declaration"),
            (SELECTOR, {"bind/Client.cpp": BINDER + BINDER}, "has 2 pybind11 class_ declaration"),
            (SELECTOR, {"other.cpp": BINDER}, "unavailable"),
        ):
            with self.subTest(value=value, text=text):
                surface = self.surface(value, files)
                self.assertFalse(surface.found)
                self.assertTrue(any(text in problem for problem in surface.problems), surface.problems)


class Fake:
    def callService(self, serviceName, inputSerializedMsg):
        return b""

    def setName(self, nodeName):
        return None


class PybindGateTests(unittest.TestCase):
    def gate(self, *, fake=Fake, family="direct", calls=(), card=None, native=SELECTOR, records_native=True,
             clone=True):
        log = RecordLog("pybind fake")
        for name in calls:
            log.record(name, "call", (), {})
            log.found.add(name)
        ctx = SimpleNamespace(cls=SimpleNamespace(native=native), family=family, records_native=records_native,
                              tree=tree_with(self, {"bind/Client.cpp": BINDER}) if clone else None, card=card or {},
                              logs=[log],
                              transport_family=family in ("serial", "scpi", "ros", "http", "mcp-client", "sila2"))
        members = {name for name in vars(fake) if not name.startswith("_")}
        gate = Gate("G7", "Native surface")
        with patch("mhs.driver.check._fake_members", return_value=members):
            _g7(ctx, gate)
        return [(finding.code, finding.severity) for finding in gate.findings]

    def test_fake_members_and_used_names_must_be_bound(self) -> None:
        self.assertEqual(self.gate(calls=["callService"]), [])

        class Invented(Fake):
            def close(self):
                return None
        self.assertIn(("G7.NOT_UPSTREAM", "error"), self.gate(fake=Invented))
        self.assertIn(("G7.NOT_UPSTREAM", "error"), self.gate(calls=["assign"]))

    def test_only_direct_and_python_object_drivers_may_name_one(self) -> None:
        self.assertEqual(self.gate(family="python-object"), [])
        for family in ("ros", "serial", "gymnasium"):
            with self.subTest(family=family):
                self.assertIn(("G7.NATIVE_NOT_FOUND", "error"), self.gate(family=family))

    def test_an_upstream_simulator_fake_does_not_exempt_other_families(self) -> None:
        # A Gymnasium or MuJoCo driver whose fake backend is the upstream simulator (records_native false) skips the
        # fake-surface check, but its pybind11 selector is still refused.
        for family in ("gymnasium", "mujoco"):
            with self.subTest(family=family):
                findings = self.gate(family=family, records_native=False)
                self.assertIn(("G7.NATIVE_NOT_FOUND", "error"), findings)
                self.assertNotIn(("G7.UPSTREAM_BACKEND", "warning"), findings)
        # Without a pybind11 selector the upstream-simulator shortcut is unchanged.
        self.assertEqual(self.gate(family="gymnasium", records_native=False, native="gymnasium.envs:Env"),
                         [("G7.UPSTREAM_BACKEND", "warning")])

    def test_a_pybind_native_without_a_clone_is_reported(self) -> None:
        self.assertEqual(self.gate(clone=False), [("G7.NO_CLONE", "error")])
        self.assertEqual(self.gate(family="ros", clone=False), [("G7.NATIVE_NOT_FOUND", "error")])

    def test_card_entry_symbols_constrain_it(self) -> None:
        other = {"entry_symbols": [{"symbol": "client:Other", "file": "client.py", "line": 1, "confidence": "ast"}]}
        self.assertIn(("G7.NOT_AN_ENTRY_SYMBOL", "error"), self.gate(card=other))
        guessed = {"entry_symbols": [{"symbol": "client:Other", "file": "client.py", "line": 1}]}
        self.assertIn(("G7.NOT_AN_ENTRY_SYMBOL", "warning"), self.gate(card=guessed))
        listed = {"entry_symbols": [{"symbol": SELECTOR, "file": "bind/Client.cpp", "line": 6}]}
        self.assertEqual(self.gate(card=listed), [])

    def test_an_unresolvable_selector_is_reported(self) -> None:
        self.assertIn(("G7.NATIVE_NOT_FOUND", "error"), self.gate(native="pybind:bind/Client.cpp#mvsim.Gone"))
        self.assertIn(("G7.NO_NATIVE", "error"), self.gate(native="pybind:../Client.cpp#mvsim.Client"))

    def test_real_gate_context_on_a_tutorial_copy(self) -> None:
        directory = gs.copy_tutorial(self)
        (directory / "vendor" / "bind").mkdir()
        (directory / "vendor" / "bind" / "Controller.cpp").write_text(
            'void bind(M) {\n  pybind11::class_<thermo::Controller> cl(M("thermo"), "Controller");\n'
            + "".join(f'  cl.def("{name}", &thermo::Controller::{name});\n'
                      for name in ("read_temperature", "get_setpoint", "set_setpoint", "set_zone_trim",
                                   "set_fan_speed", "heater_off", "emergency_off", "lid_is_closed", "close"))
            + "}\n")
        gs.edit(directory, "driver.py", 'native = "thermo.controller:Controller"',
                'native = "pybind:bind/Controller.cpp#thermo.Controller"')
        report = gs.check(directory, gates=["G3", "G7"])
        # The tutorial card confirms its Python entry class: another native is refused until the card names it.
        self.assertIn("G7.NOT_AN_ENTRY_SYMBOL", gs.findings(report))
        card = json.loads((directory / "task.json").read_text())
        card["entry_symbols"] = [{"symbol": "pybind:bind/Controller.cpp#thermo.Controller",
                                  "file": "bind/Controller.cpp", "line": 2, "confidence": "override"}]
        (directory / "task.json").write_text(json.dumps(card))
        report = gs.check(directory, gates=["G3", "G7"])
        self.assertEqual(gs.findings(report), [], json.dumps(gs.findings(report))[:2000])


if __name__ == "__main__":
    unittest.main()
