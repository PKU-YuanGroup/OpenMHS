"""mhs.driver.upstream: references, the read-only upstream tree and the AST surface of a class (G4, G7)."""

from __future__ import annotations

import os
import sys
import unittest

from mhs.driver.upstream import UpstreamTree, class_surface, parse_ref, safe_relpath

from tests.driver import gate_support as gs


def tree_with(test: unittest.TestCase, files: dict[str, str]) -> UpstreamTree:
    root = gs.temp_root(test)
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return UpstreamTree(root, None, use_git=False)


class RefTests(unittest.TestCase):
    def test_parse_ref(self) -> None:
        self.assertEqual(str(parse_ref("pkg/mod.py:12")), "pkg/mod.py:12")
        ref = parse_ref("README.md:3-5")
        self.assertEqual((ref.path, ref.line, ref.end), ("README.md", 3, 5))
        for text in ("README.md", "README.md:0", "a.py:5-3", "https://example.com/x", "", None, "a.py:x"):
            self.assertIsNone(parse_ref(text), text)

    def test_safe_relpath(self) -> None:
        self.assertEqual(safe_relpath("./a/b.py"), "a/b.py")
        for text in ("/etc/passwd", "../x.py", "a/../../x", "a\\b.py", ""):
            self.assertIsNone(safe_relpath(text), text)


class TreeTests(unittest.TestCase):
    def test_worktree_reads_and_greps(self) -> None:
        tree = tree_with(self, {"docs/MANUAL.md": "Set FREQ to 10 Hz\n", "bin.dat": "\0binary"})
        self.assertFalse(tree.is_git)
        self.assertEqual(tree.read_text("docs/MANUAL.md"), "Set FREQ to 10 Hz\n")
        self.assertIsNone(tree.read_text("bin.dat"))
        self.assertIsNone(tree.read_bytes("../outside"))
        self.assertTrue(tree.grep("freq"))
        self.assertFalse(tree.grep("AMPL"))
        self.assertEqual(sorted(tree.files()), ["bin.dat", "docs/MANUAL.md"])

    def test_symlinks_out_of_the_tree_are_not_read(self) -> None:
        outside = gs.temp_root(self) / "secret.txt"
        outside.write_text("secret", encoding="utf-8")
        tree = tree_with(self, {"a.txt": "a"})
        try:
            (tree.root / "link.txt").symlink_to(outside)
        except (OSError, NotImplementedError):  # pragma: no cover - platforms without symlinks
            self.skipTest("no symlinks")
        self.assertIsNone(tree.read_text("link.txt"))

    def test_a_filter_of_the_clone_installs_no_hook_into_it(self) -> None:
        # Wave D: the gate's git status over a Git LFS file ran git-lfs, which installed its hooks in .git/hooks.
        root = gs.temp_root(self)
        gs.git(root, "init", "-q")
        (root / ".gitattributes").write_text("*.bin filter=probe\n", encoding="utf-8")
        (root / "data.bin").write_bytes(b"payload\n")
        install = 'd=$(git rev-parse --git-path hooks) && mkdir -p "$d" && touch "$d/post-checkout"; cat'
        gs.git(root, "config", "filter.probe.clean", f"sh -c '{install}'")
        gs.git(root, "add", "-A")
        gs.git(root, "commit", "-q", "-m", "data")
        later = (root / "data.bin").stat().st_mtime + 10
        os.utime(root / "data.bin", (later, later))  # stat-dirty: git status runs the clean filter again
        tree = UpstreamTree(root, gs.git(root, "rev-parse", "HEAD"))
        self.assertTrue(tree.is_git, tree.notes)
        self.assertEqual(tree.modified(), [])
        self.assertFalse((root / ".git" / "hooks" / "post-checkout").exists())


class SurfaceTests(unittest.TestCase):
    def test_members_bases_and_instance_attributes(self) -> None:
        tree = tree_with(self, {
            "src/pkg/__init__.py": "",
            "src/pkg/base.py": "class Base:\n    timeout = 1\n    def ping(self):\n        pass\n",
            "src/pkg/dev.py": (
                "from .base import Base\n\n"
                "class Device(Base):\n"
                "    __slots__ = ('raw',)\n"
                "    def __init__(self, port):\n"
                "        self.port = port\n"
                "        self._link: object = None\n"
                "    @property\n"
                "    def temperature(self):\n"
                "        return 1\n"
                "    async def stop(self):\n"
                "        setattr(self, 'stopped', True)\n"
                "    class Error(Exception):\n"
                "        pass\n"),
        })
        surface = class_surface(tree, "pkg.dev:Device")
        self.assertTrue(surface.found, surface.problems)
        self.assertEqual(surface.file, "src/pkg/dev.py")
        self.assertEqual(surface.line, 3)
        for name in ("port", "_link", "temperature", "stop", "stopped", "Error", "raw", "ping", "timeout",
                     "__init__"):
            self.assertIn(name, surface.names)
        self.assertEqual(surface.open, [])

    def test_external_base_and_getattr_leave_the_surface_open(self) -> None:
        tree = tree_with(self, {"pkg/dev.py": (
            "import serial\n\n"
            "class Port(serial.Serial):\n    def ask(self):\n        pass\n\n"
            "class Dynamic:\n    def __getattr__(self, name):\n        return name\n")})
        port = class_surface(tree, "pkg.dev:Port")
        self.assertTrue(port.found)
        self.assertTrue(any("serial.Serial" in item for item in port.open), port.open)
        dynamic = class_surface(tree, "pkg.dev:Dynamic")
        self.assertTrue(any("__getattr__" in item for item in dynamic.open), dynamic.open)

    def test_reexported_and_missing_classes(self) -> None:
        tree = tree_with(self, {"pkg/__init__.py": "from .impl import Thing\n",
                                "pkg/impl.py": "class Thing:\n    def go(self):\n        pass\n"})
        surface = class_surface(tree, "pkg:Thing")
        self.assertEqual(surface.file, "pkg/impl.py")
        self.assertIn("go", surface.names)
        self.assertIn("is not defined", class_surface(tree, "pkg.impl:Other").problems[0])
        self.assertIn("is not in the clone", class_surface(tree, "nope.mod:X").problems[0])
        self.assertIn("package.module:Class", class_surface(tree, "no_colon").problems[0])

    def test_a_hint_file_that_only_registers_the_class(self) -> None:
        # A card's entry symbol may point at the gym register(...) call; the module path still finds the class.
        tree = tree_with(self, {"gym-x/gym_x/__init__.py": "from gymnasium.envs.registration import register\n"
                                                           "register(id='X-v0', entry_point='gym_x.env:XEnv')\n",
                                "gym-x/gym_x/env.py": "class XEnv:\n    def step(self, action):\n        pass\n"})
        surface = class_surface(tree, "gym_x.env:XEnv", hint_file="gym-x/gym_x/__init__.py")
        self.assertEqual(surface.problems, [])
        self.assertEqual((surface.file, surface.line), ("gym-x/gym_x/env.py", 1))
        self.assertIn("step", surface.names)
        self.assertIn("is not defined", class_surface(tree, "gym_x.env:YEnv",
                                                      hint_file="gym-x/gym_x/__init__.py").problems[0])

    def test_python_2_source_is_read_leniently(self) -> None:
        # Wave C: seven driver cards had Python 2 upstreams (print statements, except E, e:), which ast rejects.
        tree = tree_with(self, {"smc100.py": (
            "import serial\n\n"
            "class SMC100(object):\n"
            "\tdef __init__(self, port):\n"
            "\t\tself.port = port\n"
            "\t\tself.mode = 0777\n"
            "\tdef move(self, mm):\n"
            "\t\tprint 'moving', mm, \\\n"
            "\t\t      'mm'\n"
            "\t\ttry:\n"
            "\t\t\tself.port.write('PA%f' % mm)\n"
            "\t\texcept IOError, e:\n"
            "\t\t\tprint >>sys.stderr, e\n"
            "\tdef stop(self):\n"
            "\t\texec 'pass'\n")})
        surface = class_surface(tree, "smc100:SMC100")
        self.assertTrue(surface.found, surface.problems)
        self.assertEqual((surface.file, surface.line), ("smc100.py", 3))
        for name in ("__init__", "port", "mode", "move", "stop"):
            self.assertIn(name, surface.names)
        self.assertEqual(list(surface.legacy), ["smc100.py"])
        self.assertGreater(surface.legacy["smc100.py"], 0)
        modern = class_surface(tree_with(self, {"dev.py": "class Dev:\n    def go(self):\n        print('x')\n"}),
                               "dev:Dev")
        self.assertEqual(modern.legacy, {})

    def test_a_helper_that_sets_attributes_on_its_owner_leaves_the_surface_open(self) -> None:
        # rp2daq attaches the commands its firmware table names to the Rp2daq object from another class (wave C).
        tree = tree_with(self, {"rp2daq.py": (
            "class Rp2daq:\n"
            "    def __init__(self):\n"
            "        self._i = Internals(externals=self)\n\n"
            "class Internals:\n"
            "    def __init__(self, externals):\n"
            "        self._e = externals\n"
            "        for name in ('adc', 'gpio_out'):\n"
            "            setattr(self._e, name, print)\n\n"
            "class Plain:\n"
            "    def __init__(self):\n"
            "        self.log = Logger(self)\n\n"
            "class Logger:\n"
            "    def __init__(self, owner):\n"
            "        self.owner = owner\n")})
        surface = class_surface(tree, "rp2daq:Rp2daq")
        self.assertTrue(any(item.startswith("Internals sets attributes dynamically") for item in surface.open),
                        surface.open)
        self.assertEqual(class_surface(tree, "rp2daq:Plain").open, [])

    def test_the_tutorial_upstream(self) -> None:
        surface = class_surface(UpstreamTree(gs.TUTORIAL / "vendor", None, use_git=False),
                                "thermo.controller:Controller")
        self.assertEqual(surface.file, "thermo/controller.py")
        for name in ("read_temperature", "get_setpoint", "set_setpoint", "set_zone_trim", "set_fan_speed",
                     "heater_off", "emergency_off", "lid_is_closed"):
            self.assertIn(name, surface.names)

    def test_upstream_code_is_never_imported(self) -> None:
        tree = tree_with(self, {"boom/mod.py": "raise SystemExit('imported!')\nclass X:\n    pass\n"})
        before = set(sys.modules)
        surface = class_surface(tree, "boom.mod:X")
        self.assertTrue(surface.found)
        self.assertFalse({name for name in set(sys.modules) - before if name.startswith("boom")})


if __name__ == "__main__":
    unittest.main()
