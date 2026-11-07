"""Explicit source metadata never imports upstream or weakens legacy G7."""
from __future__ import annotations

import inspect
import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from mhs.driver import Driver
from mhs.driver.check import Gate, _g7
from mhs.driver.model import check_class_attributes
from mhs.driver.source_gate import check_explicit_source
from mhs.driver.source_selector import entry_shape, parse_selector, source_path
from mhs.driver.source_surface import explicit_surface, regular_source
from mhs.driver.upstream import UpstreamTree, class_surface
from mhs.testing.recorder import RecordLog
from tests.driver import gate_support as gs
from tests.driver.test_upstream import tree_with


class SelectorTests(unittest.TestCase):
    def test_explicit_forms_and_legacy_names(self):
        for symbol, kind in [("spectrometer:init", "class"), ("pkg.mod:Outer.Inner", "class"),
                             ("pyfile:spectrometer.py#*", "module"), ("pyfile:2230G.py#KEI2230G", "class"),
                             ("pyfile:2220 Programmable DC Power Supplies.py#KEI2220S", "class")]:
            self.assertEqual(parse_selector(symbol).kind, kind)
        self.assertTrue(entry_shape("TLBC2:TLBC2", "Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py", 156))
        self.assertTrue(entry_shape("pyfile:spectrometer.py#*", "spectrometer.py", 1))
        self.assertFalse(entry_shape("pyfile:spectrometer.py#*", "spectrometer.py", 2))
        self.assertFalse(entry_shape("pyfile:a.py#X", "b.py", 1))
        self.assertFalse(entry_shape("pyfile:a.py#X", "a.py", True))

    def test_unsafe_paths_and_invalid_selectors(self):
        for path in ("../a.py", "x/../a.py", "./a.py", "/a.py", "x//a.py", "x/./a.py",
                     "a\\b.py", "a.py\n", "a:1.py", "a#b.py", "a*.py", "a.py/"):
            self.assertIsNone(source_path(path), path)
            self.assertIsNone(parse_selector(f"pyfile:{path}#X"), path)
        for selector in ("pyfile:a.py", "pyfile:a.txt#X", "pyfile:a.py#X()", "pyfile:a.py#X#Y",
                         "pyfile:a.py#", "pyfile:a.py#**", "2230G:X", None):
            self.assertIsNone(parse_selector(selector), selector)

    def test_model_accepts_source_only_native_metadata(self):
        class Source(Driver):
            device_id, device_kind = "probe", "instrument.spectrometer"
            native = "pyfile:spectrometer.py#*"
        problems = []
        attrs = check_class_attributes(Source, problems, native_symbol=Source.native, safe_state=None)
        self.assertEqual(attrs["native_symbol"], Source.native)
        self.assertFalse(any("native must" in problem for problem in problems), problems)


class SourceTests(unittest.TestCase):
    def surface(self, source, symbol="pyfile:module.py#*"):
        selected = parse_selector(symbol)
        return explicit_surface(tree_with(self, {selected.path: source}), selected)

    def test_only_direct_functions_with_precise_signatures(self):
        surface = self.surface("def read(a, /, b=1, *rest, flag, gain=2, **opts):\n    return a\n")
        self.assertTrue(surface.found, surface.problems)
        sig = surface.signatures["read"]
        sig.bind(1, flag=True)
        sig.bind(1, 2, 3, flag=True, extra=4)
        with self.assertRaises(TypeError):
            sig.bind(a=1, flag=True)
        with self.assertRaises(TypeError):
            sig.bind(1)

    def test_nonexecution_and_defaults_are_never_evaluated(self):
        marker = gs.temp_root(self) / "executed"
        before = set(sys.modules)
        surface = self.surface(f"raise RuntimeError('never import')\n"
                               f"def read(value=open({str(marker)!r}, 'w')):\n    return value\n")
        self.assertTrue(surface.found, surface.problems)
        self.assertFalse(marker.exists())
        self.assertEqual(set(sys.modules), before)

    def test_python2_prints_preserve_source_lines(self):
        surface = self.surface("from smbus import SMBus\ni2c=SMBus(1)\n"
                               "def init():\n    print 'reset'\n"
                               "def readRAW():\n    print output\n    return output\n")
        self.assertTrue(surface.found, surface.problems)
        self.assertEqual(surface.names, {"init", "readRAW"})
        self.assertEqual(surface.legacy, {"module.py": 2})

    def test_legacy_header_rewrites_do_not_establish_signatures(self):
        surface = self.surface("def broken((x, y)):\n    return x\n")
        self.assertFalse(surface.found)

    def test_imported_conditional_redefined_decorated_async_are_not_functions(self):
        cases = ["from other import read\n", "if True:\n    def read(): pass\n",
                 "def read(): pass\nread=other\n", "def read(): pass\ndef read(): pass\n",
                 "def read(): pass\ndel read\n", "@dec\ndef read(): pass\n", "async def read(): pass\n"]
        for source in cases:
            with self.subTest(source=source):
                surface = self.surface(source + "\ndef known(): pass\n")
                self.assertNotIn("read", surface.names)
                self.assertIn("known", surface.names)
        self.assertFalse(self.surface("answer=1\n").found)

    def test_dynamic_namespace_is_not_approved(self):
        for text in ("globals()['read']=other", "exec('read = other')", "from other import *",
                     "def replace():\n    global read\n    read=other", "read.__defaults__=(1,)",
                     "import sys\nsys.modules[__name__].read = other", "setattr(module, 'read', other)"):
            self.assertFalse(self.surface("def read(): pass\n" + text + "\n").found)

    def test_exact_class_does_not_follow_alias_or_wrong_file(self):
        tree = tree_with(self, {"2230G.py": "class KEI2230G:\n    def read(self): pass\n",
                               "alias.py": "from elsewhere import KEI2230G\n"})
        found = explicit_surface(tree, parse_selector("pyfile:2230G.py#KEI2230G"))
        self.assertEqual((found.file, found.line, found.names), ("2230G.py", 1, {"read"}))
        self.assertFalse(explicit_surface(tree, parse_selector("pyfile:alias.py#KEI2230G")).found)
        self.assertFalse(explicit_surface(tree, parse_selector("pyfile:missing.py#KEI2230G")).found)
        self.assertFalse(explicit_surface(tree, parse_selector("pyfile:2230G.py#Wrong")).found)

    def test_same_file_base_supported_but_external_members_not_guessed(self):
        surface = self.surface("class Base:\n    def read(self): pass\n"
                               "class Device(Base):\n    def stop(self): pass\n", "pyfile:module.py#Device")
        self.assertEqual(surface.names, {"read", "stop"})
        tree = tree_with(self, {"pkg.py": "from other import Base\nclass Device(Base): pass\n",
                               "other.py": "class Base:\n    def guessed(self): pass\n"})
        strict = explicit_surface(tree, parse_selector("pyfile:pkg.py#Device"))
        self.assertNotIn("guessed", strict.names)
        # Existing class behavior still follows this in-clone base.
        self.assertIn("guessed", class_surface(tree, "pkg:Device").names)

    def test_reassigned_base_does_not_contribute_invented_members(self):
        surface = self.surface("class Base:\n    def invented(self): pass\n"
                               "Base = object\nclass Device(Base):\n    def read(self): pass\n",
                               "pyfile:module.py#Device")
        self.assertTrue(surface.found)
        self.assertNotIn("invented", surface.names)

    def test_git_pin_wins_over_worktree_and_head(self):
        root = gs.temp_root(self)
        gs.git(root, "init", "-q")
        (root / "module.py").write_text("def read(): pass\n")
        gs.git(root, "add", ".")
        gs.git(root, "commit", "-qm", "pinned")
        pin = gs.git(root, "rev-parse", "HEAD")
        (root / "module.py").write_text("def invented(): pass\n")
        gs.git(root, "add", ".")
        gs.git(root, "commit", "-qm", "later")
        tree = UpstreamTree(root, pin)
        self.assertEqual(explicit_surface(tree, parse_selector("pyfile:module.py#*")).names, {"read"})
        (root / "untracked.py").write_text("def invented(): pass\n")
        with self.assertRaises(ValueError):
            regular_source(tree, "untracked.py")
        with self.assertRaises(ValueError):
            regular_source(UpstreamTree(root, "0" * 40), "module.py")
        with self.assertRaises(ValueError):
            regular_source(UpstreamTree(root), "module.py")

    def test_no_pin_fallback_or_symlink_source(self):
        tree = tree_with(self, {"module.py": "def read(): pass\n"})
        (tree.root / "alias.py").symlink_to("module.py")
        with self.assertRaises(ValueError):
            regular_source(tree, "alias.py")
        with self.assertRaises(ValueError):
            regular_source(UpstreamTree(tree.root, "a" * 40, use_git=False), "module.py")
        gs.git(tree.root, "init", "-q")
        gs.git(tree.root, "add", ".")
        gs.git(tree.root, "commit", "-qm", "symlink")
        pinned = UpstreamTree(tree.root, gs.git(tree.root, "rev-parse", "HEAD"))
        with self.assertRaises(ValueError):
            regular_source(pinned, "alias.py")

    def test_parent_symlink_and_gitlink_never_fall_back_to_worktree(self):
        tree = tree_with(self, {"module.py": "def read(): pass\n"})
        outside = tree_with(self, {"module.py": "def invented(): pass\n"})
        (tree.root / "escape").symlink_to(outside.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            regular_source(tree, "escape/module.py")
        gs.git(tree.root, "init", "-q")
        gs.git(tree.root, "add", "module.py")
        gs.git(tree.root, "commit", "-qm", "root")
        child_pin = gs.git(tree.root, "rev-parse", "HEAD")
        gs.git(tree.root, "update-index", "--add", "--cacheinfo", f"160000,{child_pin},child")
        gs.git(tree.root, "commit", "-qm", "gitlink")
        (tree.root / "child").mkdir()
        (tree.root / "child/module.py").write_text("def invented(): pass\n")
        pinned = UpstreamTree(tree.root, gs.git(tree.root, "rev-parse", "HEAD"))
        with self.assertRaises(ValueError):
            regular_source(pinned, "child/module.py")


class ModuleGateTests(unittest.TestCase):
    def gate(self, source="def read(value, *, flag=False): pass\n", fake=None, calls=(), entry=None):
        if fake is None:
            class Fake:
                def read(self, value, *, flag=False): pass
            fake = Fake
        selected = parse_selector("pyfile:module.py#*")
        tree = tree_with(self, {"module.py": source})
        log = RecordLog("source fake")
        for name, args, kwargs in calls:
            log.record(name, "call", args, kwargs)
        card = {"entry_symbols": [entry or {"symbol": selected.value, "file": "module.py", "line": 1}]}
        ctx = SimpleNamespace(tree=tree, card=card, logs=[log])
        gate = Gate("G7", "Native surface")
        members = {name for klass in fake.__mro__ for name in vars(klass) if not name.startswith("_")}
        check_explicit_source(ctx, gate, selected, fake, members)
        return [finding.code for finding in gate.findings if finding.severity == "error"]

    def test_valid_calls_and_keyword_binding(self):
        self.assertEqual(self.gate(calls=[("read", (3,), {"flag": True})]), [])

    def test_bad_recorded_arguments_are_rejected(self):
        for args, kwargs in [((), {}), ((1, 2), {}), ((1,), {"unknown": 2}), ((1,), {"value": 2})]:
            self.assertIn("G7.CALL_SIGNATURE", self.gate(calls=[("read", args, kwargs)]))

    def test_fake_catchall_and_wrong_defaults_are_rejected(self):
        class Catchall:
            def read(self, *args, **kwargs): pass
        class Required:
            def read(self, value, *, flag): pass
        self.assertIn("G7.FAKE_SIGNATURE", self.gate(fake=Catchall))
        self.assertIn("G7.FAKE_SIGNATURE", self.gate(fake=Required))

    def test_missing_member_in_fake_or_recording_fails(self):
        class Fake:
            def read(self, value, *, flag=False): pass
            def invented(self): pass
        self.assertIn("G7.NOT_UPSTREAM", self.gate(fake=Fake))
        self.assertIn("G7.NOT_UPSTREAM", self.gate(calls=[("invented", (), {})]))
        self.assertIn("G7.NOT_UPSTREAM", self.gate(calls=[("read.nested", (), {})]))

    def test_dynamic_fake_is_rejected(self):
        class Fake:
            def read(self, value, *, flag=False): pass
            def __getattr__(self, name): return lambda *args: None
        self.assertIn("G7.FAKE_SIGNATURE", self.gate(fake=Fake))

    def test_callable_fake_cannot_bypass_module_members(self):
        class Fake:
            def read(self, value, *, flag=False): pass
            def __call__(self, payload): pass
        self.assertIn("G7.FAKE_SIGNATURE", self.gate(fake=Fake))
        self.assertIn("G7.NOT_UPSTREAM", self.gate(calls=[("__call__", ({"anything": 1},), {})]))

    def test_staticmethod_does_not_drop_first_argument(self):
        class Fake:
            @staticmethod
            def read(value, *, flag=False): pass
        self.assertEqual(self.gate(fake=Fake), [])

    def test_fake_signature_metadata_cannot_mask_a_catchall(self):
        class Fake:
            def read(self, *args, **kwargs): pass
        def declared(self, value, *, flag=False): pass
        Fake.read.__signature__ = inspect.signature(declared)
        self.assertIn("G7.FAKE_SIGNATURE", self.gate(fake=Fake))

    def test_class_entry_requires_actual_definition_line(self):
        selected = parse_selector("pyfile:2230G.py#KEI2230G")
        ctx = SimpleNamespace(tree=tree_with(self, {"2230G.py": "# header\nclass KEI2230G: pass\n"}),
                              card={"entry_symbols": [{"symbol": selected.value, "file": "2230G.py", "line": 1}]},
                              logs=[])
        gate = Gate("G7", "Native surface")
        check_explicit_source(ctx, gate, selected, None, set(), check_members=False)
        self.assertIn("G7.ENTRY_SOURCE", [finding.code for finding in gate.findings])

    def test_real_gate_context_resolves_explicit_class_without_importing_source(self):
        directory = gs.copy_tutorial(self)
        gs.edit(directory, "driver.py", 'native = "thermo.controller:Controller"',
                'native = "pyfile:thermo/controller.py#Controller"')
        card = json.loads((directory / "task.json").read_text())
        source = class_surface(UpstreamTree(directory / "vendor", use_git=False), "thermo.controller:Controller")
        card["entry_symbols"] = [{"symbol": "pyfile:thermo/controller.py#Controller",
                                 "file": source.file, "line": source.line, "confidence": "override"}]
        (directory / "task.json").write_text(json.dumps(card))
        report = gs.check(directory, gates=["G3", "G7"])
        self.assertEqual(gs.findings(report), [])

    def test_wrong_card_file_line_or_symbol_is_not_accepted(self):
        for entry in [dict(symbol="pyfile:other.py#*", file="other.py", line=1),
                      dict(symbol="pyfile:module.py#*", file="other.py", line=1),
                      dict(symbol="pyfile:module.py#*", file="module.py", line=2)]:
            self.assertTrue(self.gate(entry=entry))

    def test_transport_gate_does_not_skip_explicit_source_identity(self):
        tree = tree_with(self, {"2230G.py": "class KEI2230G: pass\n"})
        ctx = SimpleNamespace(cls=SimpleNamespace(native="pyfile:2230G.py#Wrong"), family="scpi",
                              tree=tree, card={}, logs=[], transport_family=True)
        gate = Gate("G7", "Native surface")
        with patch("mhs.driver.check._fake_target", return_value=None), \
             patch("mhs.driver.check._fake_members", return_value=set()), \
             patch("mhs.driver.check._g7_transport") as transport:
            _g7(ctx, gate)
        transport.assert_called_once()
        self.assertIn("G7.NATIVE_NOT_FOUND", [finding.code for finding in gate.findings])


if __name__ == "__main__":
    unittest.main()
