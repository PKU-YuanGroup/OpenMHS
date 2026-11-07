"""Gate G7 for environments a factory function of the clone builds (``native_factory``, FACTORY-ENVIRONMENTS).

The clone is a plain directory (nothing is imported from it); the environment classes are synthetic.
"""

from __future__ import annotations

import types
import unittest

from mhs.driver import DriverDefinitionError, GymnasiumDriver, build_manifest
from mhs.driver.check import _GYMNASIUM_ENV_API, Gate
from mhs.driver.factory_check import DM_ENV_INTERFACE, check_factory_surface, declaration_problems
from mhs.driver.upstream import UpstreamTree

from tests.bridges.test_gym_dm_env import DM, PianoLike
from tests.driver import gate_support as gs

SUITE = (
    "from extlib import envs\n"            # 1
    "from . import tasks\n"                # 2
    "import extlib.wrappers as wrap\n"     # 3
    "\n"                                   # 4
    "def load(name, seed=None):\n"         # 5
    "    task = tasks.Task(name)\n"        # 6
    "    return envs.Environment(\n"       # 7
    "        task=task,\n"                 # 8
    "        random_state=seed,\n"         # 9
    "    )\n"                              # 10
    "\n"                                   # 11
    "def wrapped(name):\n"                 # 12
    "    if name:\n"                       # 13
    "        return wrap.Gym(name)\n"      # 14
    "    return wrap.Gym(None)\n"          # 15
    "\n"                                   # 16
    "def shadowed(name):\n"                # 17
    "    envs = tasks\n"                   # 18
    "    return envs.Environment(name)\n"  # 19
    "\n"                                   # 20
    "def relative(name):\n"                # 21
    "    return tasks.Task(name)\n"        # 22
    "\n"                                   # 23
    "def nothing(name):\n"                 # 24
    "    return None\n"                    # 25
    "\n"                                   # 26
    "@staticmethod\n"                      # 27
    "def decorated(name):\n"               # 28
    "    return envs.Environment(name)\n"  # 29
    "\n"                                   # 30
    "class Suite:\n"                       # 31
    "    pass\n"                           # 32
    "\n"                                   # 33
    "def own(name):\n"                     # 34
    "    return owned.Env(name)\n"         # 35
    "\n"                                   # 36
    "from suite import owned\n"            # 37
    "\n"                                   # 38
    "def maybe(name):\n"                   # 39
    "    if name:\n"                       # 40
    "        return envs.Environment(name)\n"  # 41
    "\n"                                   # 42
    "def generated(name):\n"               # 43
    "    yield None\n"                     # 44
    "    return envs.Environment(name)\n"  # 45
)
FACTORY = {"returns": "extlib.envs.Environment", "ref": "suite/__init__.py:7-10"}


def tree_for(test: unittest.TestCase) -> UpstreamTree:
    root = gs.temp_root(test)
    for name, text in {"suite/__init__.py": SUITE, "suite/tasks.py": "class Task:\n    pass\n",
                       "suite/owned.py": "class Env:\n    def reset(self):\n        pass\n"}.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return UpstreamTree(root, None, use_git=False)


def run(test: unittest.TestCase, symbol: str = "suite:load", factory=None, members=("reset", "step", "action_spec",
        "observation_spec", "close"), *, dm_env: bool = True, family: str = "gymnasium", used=()) -> list[tuple[str, str]]:
    cls = types.SimpleNamespace(dm_env_by_backend={"fake": dict(DM)} if dm_env else {})
    log = types.SimpleNamespace(found=set(used))
    ctx = types.SimpleNamespace(family=family, tree=tree_for(test), cls=cls, backend="fake", logs=[log])
    gate = Gate("G7", "Native surface")
    check_factory_surface(ctx, gate, symbol, None, FACTORY if factory is None else factory, set(members),
                          _GYMNASIUM_ENV_API)
    return [(item.code, item.message) for item in gate.findings]


def codes(findings: list[tuple[str, str]]) -> list[str]:
    return [code for code, _message in findings]


class FactoryRuleTests(unittest.TestCase):
    def test_a_factory_returning_the_declared_external_class_passes(self) -> None:
        self.assertEqual(run(self), [])
        self.assertEqual(run(self, used=["control_timestep", "reward_spec"]), [])

    def test_the_fake_is_held_to_the_profiles_interface(self) -> None:
        found = run(self, members=("reset", "step", "action_spec", "observation_spec", "render"))
        self.assertEqual(codes(found), ["G7.NOT_UPSTREAM"])
        self.assertIn("'render' (defined by the fake)", found[0][1])
        self.assertIn("dm_env environment", found[0][1])
        found = run(self, used=["physics"])
        self.assertEqual(codes(found), ["G7.NOT_UPSTREAM"])
        # Without the dm_env profile the Gymnasium interface applies: action_spec is not part of it.
        found = run(self, dm_env=False, members=("reset", "step", "action_space", "observation_space", "close",
                                                   "action_spec"))
        self.assertEqual(codes(found), ["G7.NOT_UPSTREAM"])
        self.assertIn("'action_spec'", found[0][1])
        self.assertTrue(DM_ENV_INTERFACE.isdisjoint({"render", "physics", "task"}))

    def test_every_return_must_build_the_declared_class(self) -> None:
        found = run(self, "suite:wrapped", {"returns": "extlib.wrappers.Gym", "ref": "suite/__init__.py:13-15"})
        self.assertEqual(found, [])
        found = run(self, "suite:load", {"returns": "extlib.envs.Other", "ref": "suite/__init__.py:7-10"})
        self.assertEqual(codes(found), ["G7.FACTORY_RETURN"])
        self.assertIn("returns extlib.envs.Environment(...), not extlib.envs.Other", found[0][1])
        for symbol, why in (("suite:shadowed", "bound inside the factory"), ("suite:relative", "relative import"),
                            ("suite:nothing", "something other than a call")):
            with self.subTest(symbol):
                found = run(self, symbol, {"returns": "extlib.envs.Environment", "ref": "suite/__init__.py:1-40"})
                self.assertIn("G7.FACTORY_RETURN", codes(found))
                self.assertIn(why, " ".join(message for _code, message in found))

    def test_a_factory_that_can_return_none_or_is_a_generator_is_refused(self) -> None:
        found = run(self, "suite:maybe", {"returns": "extlib.envs.Environment", "ref": "suite/__init__.py:41"})
        self.assertEqual(codes(found), ["G7.FACTORY_RETURN"])
        self.assertIn("returns None", found[0][1])
        found = run(self, "suite:generated", {"returns": "extlib.envs.Environment", "ref": "suite/__init__.py:45"})
        self.assertEqual(codes(found), ["G7.FACTORY_NOT_FUNCTION"])
        self.assertIn("generator", found[0][1])

    def test_the_ref_must_cover_each_return(self) -> None:
        found = run(self, factory={"returns": "extlib.envs.Environment", "ref": "suite/__init__.py:7"})
        self.assertEqual(codes(found), ["G7.FACTORY_REF"])
        found = run(self, factory={"returns": "extlib.envs.Environment", "ref": "suite/tasks.py:1"})
        self.assertEqual(codes(found), ["G7.FACTORY_REF"])

    def test_classes_decorated_functions_and_missing_names_are_refused(self) -> None:
        self.assertEqual(codes(run(self, "suite:Suite")), ["G7.FACTORY_NOT_FUNCTION"])
        self.assertEqual(codes(run(self, "suite:decorated")), ["G7.FACTORY_NOT_FUNCTION"])
        self.assertEqual(codes(run(self, "suite:absent")), ["G7.NATIVE_NOT_FOUND"])
        self.assertEqual(codes(run(self, "nowhere:load")), ["G7.NATIVE_NOT_FOUND"])
        self.assertEqual(codes(run(self, "suite:load.inner")), ["G7.FACTORY_DECLARATION"])

    def test_a_class_of_the_clone_is_named_as_native_instead(self) -> None:
        found = run(self, "suite:own", {"returns": "suite.owned.Env", "ref": "suite/__init__.py:35"})
        self.assertEqual(codes(found), ["G7.FACTORY_IN_CLONE"])

    def test_other_families_and_malformed_declarations(self) -> None:
        self.assertEqual(codes(run(self, family="mujoco")), ["G7.FACTORY_FAMILY"])
        self.assertEqual(codes(run(self, factory={"returns": "Environment", "ref": "suite/__init__.py:7"})),
                         ["G7.FACTORY_DECLARATION"])
        for bad in (None, {}, {"returns": "a.B"}, {"returns": "a.B", "ref": "x.py:1", "extra": 1},
                    {"returns": "a.B", "ref": "/abs.py:1"}, {"returns": "a B.C", "ref": "x.py:1"},
                    {"returns": "a.B", "ref": "x.py"}):
            with self.subTest(bad=bad):
                self.assertTrue(declaration_problems(bad))
        self.assertEqual(declaration_problems(FACTORY), [])


class FactoryDefinitionTests(unittest.TestCase):
    def test_a_malformed_declaration_is_a_definition_error(self) -> None:
        native = PianoLike(horizon=2, final_discount=1.0)

        class Composer(GymnasiumDriver):
            device_id = "factory/composer"
            backends = {"fake": lambda: native}
            dm_env_by_backend = {"fake": dict(DM)}
            native_factory = {"returns": "Environment", "ref": "suite/__init__.py:7"}
            safe_state = "software latch; the synthetic composer task does not advance without a step"
        with self.assertRaises(DriverDefinitionError) as caught:
            Composer(backend="fake")
        self.assertIn("native_factory.returns", str(caught.exception))

    def test_a_well_formed_declaration_changes_no_manifest(self) -> None:
        native = PianoLike(horizon=2, final_discount=1.0)

        class Composer(GymnasiumDriver):
            device_id = "factory/composer"
            display_name = "Composer"
            backends = {"fake": lambda: native}
            dm_env_by_backend = {"fake": dict(DM)}
            safe_state = "software latch; the synthetic composer task does not advance without a step"

        class Declared(Composer):
            native_factory = dict(FACTORY)
        plain, declared = Composer(backend="fake"), Declared(backend="fake")
        self.addCleanup(plain.close)
        self.addCleanup(declared.close)
        manifests = [build_manifest(driver) for driver in (plain, declared)]
        for manifest in manifests:
            manifest.pop("instance_id")   # a fresh ULID per manifest
        self.assertEqual(manifests[0], manifests[1])


if __name__ == "__main__":
    unittest.main()
