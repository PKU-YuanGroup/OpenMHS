"""GymnasiumDriver.env_module: the module whose import registers env_id is imported before gymnasium.make.

Without it a sim backend could not open any environment registered at import time (gym_pusht/PushT-v0, rware-*,
ur5-v0): gymnasium.make raised NameNotFound or NamespaceNotFound.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from mhs.bridge.gymnasium import GymnasiumBridge
from mhs.driver import GymnasiumDriver
from mhs.errors import MHSError

from . import support

REGISTRY: set[str] = set()


def _fake_gymnasium() -> types.ModuleType:
    gym = types.ModuleType("gymnasium")

    def make(env_id: str, **kwargs: object) -> object:
        if env_id not in REGISTRY:
            raise LookupError(f"NameNotFound: {env_id}")
        return support.FakeCartPole()

    gym.make = make  # type: ignore[attr-defined]
    return gym


class EnvModuleBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        REGISTRY.clear()
        self.tmp = tempfile.TemporaryDirectory()
        Path(self.tmp.name, "ai4s_registering_env.py").write_text(
            f"import {__name__} as t\nt.REGISTRY.add('ns/Fake-v0')\n")
        Path(self.tmp.name, "ai4s_broken_env.py").write_text("raise ImportError('missing dependency')\n")
        sys.path.insert(0, self.tmp.name)
        self.patch = mock.patch.dict(sys.modules, {"gymnasium": _fake_gymnasium()})
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        sys.path.remove(self.tmp.name)
        for name in ("ai4s_registering_env", "ai4s_broken_env"):
            sys.modules.pop(name, None)
        self.tmp.cleanup()

    def _env(self, bridge: GymnasiumBridge) -> object:
        try:
            return bridge._ensure_env()
        finally:
            bridge.close()

    def test_without_env_module_the_unregistered_id_is_not_found(self) -> None:
        with self.assertRaises(MHSError) as caught:
            self._env(GymnasiumBridge(env_id="ns/Fake-v0"))
        self.assertIn("gym.make('ns/Fake-v0') failed", str(caught.exception))

    def test_env_module_is_imported_before_make(self) -> None:
        env = self._env(GymnasiumBridge(env_id="ns/Fake-v0", env_spec={"env_module": "ai4s_registering_env"}))
        self.assertIsInstance(env, support.FakeCartPole)

    def test_a_failing_env_module_is_not_ready(self) -> None:
        with self.assertRaises(MHSError) as caught:
            self._env(GymnasiumBridge(env_id="ns/Fake-v0", env_spec={"env_module": "ai4s_broken_env"}))
        self.assertIn("import of env_module 'ai4s_broken_env' failed (ImportError)", str(caught.exception))


LEGACY: set[str] = set()


def _legacy_gym() -> types.ModuleType:
    """A legacy gym (<= 0.21) whose registry keeps its specs in EnvRegistry.env_specs."""
    gym = types.ModuleType("gym")
    gym.envs = types.SimpleNamespace(registry=types.SimpleNamespace(env_specs={}))  # type: ignore[attr-defined]

    def make(env_id: str, **kwargs: object) -> object:
        if env_id not in gym.envs.registry.env_specs:  # type: ignore[attr-defined]
            raise LookupError(f"UnregisteredEnv: {env_id}")
        env = support.FakeCartPole()
        env.made_by = "gym"  # type: ignore[attr-defined]
        return env

    gym.make = make  # type: ignore[attr-defined]
    return gym


class LegacyRegistryTests(unittest.TestCase):
    """An env_module that registers in the legacy gym registry is made with gym.make, not gymnasium.make."""

    def setUp(self) -> None:
        REGISTRY.clear()
        self.tmp = tempfile.TemporaryDirectory()
        Path(self.tmp.name, "ai4s_legacy_env.py").write_text(
            "import gym\ngym.envs.registry.env_specs['Legacy-v0'] = object()\n")
        Path(self.tmp.name, "ai4s_both_env.py").write_text(
            f"import gym\nimport {__name__} as t\ngym.envs.registry.env_specs['Both-v0'] = object()\n"
            "t.REGISTRY.add('Both-v0')\n")
        sys.path.insert(0, self.tmp.name)
        gymnasium = _fake_gymnasium()
        gymnasium.envs = types.SimpleNamespace(registry=REGISTRY)  # type: ignore[attr-defined]
        self.patch = mock.patch.dict(sys.modules, {"gymnasium": gymnasium, "gym": _legacy_gym()})
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        sys.path.remove(self.tmp.name)
        for name in ("ai4s_legacy_env", "ai4s_both_env"):
            sys.modules.pop(name, None)
        self.tmp.cleanup()

    def _env(self, env_id: str, module: str) -> object:
        bridge = GymnasiumBridge(env_id=env_id, env_spec={"env_module": module})
        try:
            return bridge._ensure_env()
        finally:
            bridge.close()

    def test_a_legacy_registration_is_made_with_gym(self) -> None:
        self.assertEqual(getattr(self._env("Legacy-v0", "ai4s_legacy_env"), "made_by", None), "gym")

    def test_gymnasium_wins_when_both_registries_hold_the_id(self) -> None:
        self.assertIsNone(getattr(self._env("Both-v0", "ai4s_both_env"), "made_by", None))

    def test_an_id_in_neither_registry_still_fails_as_before(self) -> None:
        with self.assertRaises(MHSError) as caught:
            self._env("Missing-v0", "ai4s_legacy_env")
        self.assertIn("gym.make('Missing-v0') failed", str(caught.exception))


class EnvModuleDeclarationTests(unittest.TestCase):
    def test_a_dotted_module_name_is_accepted(self) -> None:
        problems: list[str] = []

        class Good(GymnasiumDriver):
            env_id = "ns/Fake-v0"
            env_module = "pkg.envs"

        Good._fill_model(mock.Mock(), None, problems)
        self.assertEqual([p for p in problems if "env_module" in p], [])

    def test_a_path_is_rejected(self) -> None:
        problems: list[str] = []

        class Bad(GymnasiumDriver):
            env_id = "ns/Fake-v0"
            env_module = "pkg/envs.py"

        Bad._fill_model(mock.Mock(), None, problems)
        self.assertTrue(any("env_module must be a dotted module name" in p for p in problems), problems)

    def test_make_bridge_passes_env_module_only_for_gymnasium_make(self) -> None:
        class Driver(GymnasiumDriver):
            env_id = "ns/Fake-v0"
            env_module = "ai4s_registering_env"

        instance = Driver.__new__(Driver)
        instance.__dict__.update(backend="sim", device_id="mhs://localhost/fake")
        with mock.patch("mhs.bridge.gymnasium.GymnasiumBridge") as bridge:
            Driver.make_bridge(instance, None)
            self.assertEqual(bridge.call_args.kwargs["env_spec"], {"env_module": "ai4s_registering_env"})
            Driver.make_bridge(instance, support.FakeCartPole())
            self.assertIsNone(bridge.call_args.kwargs["env_spec"])


if __name__ == "__main__":
    unittest.main()
