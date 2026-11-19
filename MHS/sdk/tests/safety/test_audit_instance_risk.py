"""Instance-derived hardware contracts are admitted at the resolved risk.

SAFE-007: a device's risk is the maximum over its bindings, so an action risk
raises a lower class attribute. DRV-040 and CORE-154: a hardware backend at
R2 or above needs ``driver.lock.json`` and, when a model wrote the driver, a
human ``reviewed_by`` before the hardware factory runs. A contract that cannot
be resolved without opening that factory is refused.
"""

from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from mhs.adapter import LoadError, load_driver
from mhs.driver import DriverDefinitionError
from mhs.driver.loader import import_driver_module

_MOVE = "x-cap.sdk.probe_move.v1"

_OPHYD = textwrap.dedent(
    """
    from mhs.driver import Action, Field, OphydDriver

    MOVE = "x-cap.sdk.probe_move.v1"
    calls = []

    def connect_hardware(**options):
        calls.append("hardware")
        return object()

    def connect_fake(**options):
        calls.append("fake")
        return object()

    class Probe(OphydDriver):
        _needs_instance = True
        device_id = "probe"
        device_kind = "motion.axis"
        mode = "hardware"
        risk = "R0"
        native = "probe.device:Probe"
        safe_state = "The controlled axis is idle."
        estop_physical_ref = "front panel stop switch"
        backends = {"hardware": ".driver:connect_hardware", "fake": ".driver:connect_fake"}
        parameters = {"position": Field("number")}
        signal_bindings = {
            "position": {
                "signal": "user_readback",
                "get": True,
                "set": False,
                "profile": "classic_epics_ro_v1",
                "get_kwargs": {"use_monitor": False},
                "timeout_ms": 1000,
                "source_ref": "fixture_source.py:4",
            }
        }
        commands = {
            MOVE: {
                "concurrency": "exclusive",
                "native": "move",
                "invoke": "call",
                "timeout_ms": 1000,
                "result": {"map": {"done": "output.done"}},
            }
        }
        actions = {
            MOVE: Action(
                name="move_absolute",
                verb="invoke",
                risk="R2",
                input={"position": Field("number")},
                output={"done": Field("boolean")},
            )
        }
        safety_bindings = {"estop": {"native": "stop", "invoke": "call", "timeout_ms": 1000}}
    """
)

_GYM = textwrap.dedent(
    """
    from mhs.driver import GymnasiumDriver

    calls = []

    def connect(**options):
        calls.append("hardware")
        return object()

    class Scene(GymnasiumDriver):
        device_id = "scene"
        mode = "hardware"
        risk = "R0"
        env_id = "CartPole-v1"
        safe_state = "simulation paused"
        backends = {"hardware": ".driver:connect"}
    """
)


_BACKEND_DERIVED = textwrap.dedent(
    """
    import copy
    from types import SimpleNamespace
    from mhs.driver import Driver, Field, action

    calls = []

    def connect(**options):
        calls.append("hardware")
        return SimpleNamespace(risk="R2")

    class Probe(Driver):
        _needs_instance = True
        device_id = "probe"
        device_kind = "sensor"
        mode = "hardware"
        risk = "R0"
        native = "probe.device:Probe"
        safe_state = "idle"
        backends = {"hardware": ".driver:connect"}

        @action(name="x-cap.sdk.probe_read.v1", verb="read", output={"value": Field("number")})
        def value(self):
            return {"value": 0.0}

        def _driver_model(self):
            native = self.native
            model = copy.deepcopy(super()._driver_model())
            model.risk = native.risk
            return model
    """
)


def _lock(*, reviewed: bool) -> dict:
    return {
        "openmhs": "0.9",
        "package_id": "gh.example/probe",
        "upstream": {
            "repo_url": "https://github.com/example/probe",
            "commit": "a" * 40,
            "license_spdx": "MIT",
        },
        "backends": {"hardware": ".driver:connect_hardware", "fake": ".driver:connect_fake"},
        "sdk_version": "0.9.0.dev0",
        "authored_by": {
            "kind": "model",
            "model_id": "example-model",
            "run_id": "run-1",
            "date": "2026-10-22",
        },
        "reviewed_by": (
            {"reviewer": "R. Viewer", "date": "2026-10-22", "scope": "hardware"} if reviewed else None
        ),
    }


class InstanceRiskAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        holder = tempfile.TemporaryDirectory(prefix="mhs-instance-risk-")
        self.addCleanup(holder.cleanup)
        self.root = Path(holder.name)

    def _package(self, source: str, *, lock: dict | None = None) -> tuple[Path, object]:
        directory = self.root / "driver"
        directory.mkdir()
        (directory / "driver.py").write_text(source, encoding="utf-8")
        if lock is not None:
            (directory / "driver.lock.json").write_text(json.dumps(lock), encoding="utf-8")
        return directory, import_driver_module(directory)

    def test_r0_class_with_r2_action_does_not_open_hardware_without_a_lock(self) -> None:
        # The served model is R2 (SAFE-007). Admission must use that risk, not the class attribute R0.
        directory, module = self._package(_OPHYD)
        instance = module.Probe(backend="fake", base_dir=directory)
        self.addCleanup(instance.close)
        self.assertEqual(module.Probe.risk, "R0")
        self.assertEqual(instance._model.risk, "R2")
        self.assertFalse(instance._native_ready)
        self.assertEqual(module.calls, [])

        state = self.root / "state"
        state.mkdir()
        driver = None
        try:
            with self.assertRaises(LoadError) as caught:
                driver = load_driver(directory, backend="hardware", allow_hardware=True, state_dir=state)
            self.assertEqual(caught.exception.reason, "review_required")
            self.assertIn("R2", str(caught.exception))
            self.assertIn("driver.lock.json", str(caught.exception))
        finally:
            if driver is not None:
                driver.close()
        self.assertEqual(module.calls, [])

    def test_model_lock_without_a_signature_is_the_same_refusal(self) -> None:
        directory, module = self._package(_OPHYD, lock=_lock(reviewed=False))
        state = self.root / "state"
        state.mkdir()
        with self.assertRaises(LoadError) as caught:
            load_driver(directory, backend="hardware", allow_hardware=True, state_dir=state)
        self.assertEqual(caught.exception.reason, "review_required")
        self.assertIn("reviewed_by", str(caught.exception))
        self.assertEqual(module.calls, [])

    def test_a_reviewed_lock_admits_the_resolved_r2_contract(self) -> None:
        directory, module = self._package(_OPHYD, lock=_lock(reviewed=True))
        state = self.root / "state"
        state.mkdir()
        driver = load_driver(directory, backend="hardware", allow_hardware=True, state_dir=state)
        self.addCleanup(driver.close)
        self.assertEqual(driver._model.risk, "R2")
        self.assertEqual(module.calls, ["hardware"])

    def test_fake_backend_does_not_use_the_hardware_factory(self) -> None:
        directory, module = self._package(_OPHYD)
        driver = load_driver(directory, backend="fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver._model.risk, "R2")
        self.assertEqual(module.calls, ["fake"])

    def test_hardware_is_refused_when_the_contract_needs_the_open_backend(self) -> None:
        # Simulator families derive the contract from the opened backend. Declaring mode hardware
        # must not run that factory in order to discover whether the review gate applies.
        directory, module = self._package(_GYM)
        state = self.root / "state"
        state.mkdir()
        with self.assertRaises(LoadError) as caught:
            load_driver(directory, backend="hardware", allow_hardware=True, state_dir=state)
        self.assertEqual(caught.exception.reason, "review_required")
        self.assertIn("cannot be resolved", str(caught.exception))
        self.assertEqual(module.calls, [])

    def test_a_decorated_class_model_does_not_resolve_its_instance_contract(self) -> None:
        directory, module = self._package(_BACKEND_DERIVED)
        self.assertEqual(module.Probe.driver_model().risk, "R0")
        with self.assertRaises(LoadError) as caught:
            load_driver(directory, backend="hardware", allow_hardware=True, state_dir=self.root)
        self.assertEqual(caught.exception.reason, "review_required")
        self.assertEqual(module.calls, [])

    def test_a_family_model_hook_does_not_authorize_an_unknown_instance_hook(self) -> None:
        source = _BACKEND_DERIVED + (
            "\n    @classmethod\n"
            "    def _family_model(cls, instance):\n"
            "        return cls.driver_model()\n"
        )
        directory, module = self._package(source)
        with self.assertRaises(LoadError) as caught:
            load_driver(directory, backend="hardware", allow_hardware=True, state_dir=self.root)
        self.assertEqual(caught.exception.reason, "review_required")
        self.assertEqual(module.calls, [])

    def test_ophyd_admission_uses_the_declared_contract_despite_candidate_hooks(self) -> None:
        source = _OPHYD + (
            "\n    @classmethod\n"
            "    def _family_model(cls, instance):\n"
            "        model = super()._family_model(instance)\n"
            "        if not isinstance(instance, cls):\n"
            "            model.risk = 'R0'\n"
            "        return model\n"
        )
        directory, module = self._package(source)
        with self.assertRaises(LoadError) as caught:
            load_driver(directory, backend="hardware", allow_hardware=True, state_dir=self.root)
        self.assertEqual(caught.exception.reason, "review_required")
        self.assertEqual(module.calls, [])

    def test_hardware_prerequisites_are_checked_before_an_unresolved_contract(self) -> None:
        directory, module = self._package(_GYM)
        for kwargs, reason in (({}, "hardware_not_allowed"),
                               ({"allow_hardware": True}, "state_dir_required")):
            with self.subTest(reason=reason):
                with self.assertRaises(LoadError) as caught:
                    load_driver(directory, backend="hardware", **kwargs)
                self.assertEqual(caught.exception.reason, reason)
                self.assertEqual(module.calls, [])

    def test_an_instance_contract_below_r2_still_needs_no_lock(self) -> None:
        directory, module = self._package(_OPHYD.replace('risk="R2"', 'risk="R1"'))
        driver = load_driver(directory, backend="hardware", allow_hardware=True, state_dir=self.root)
        self.addCleanup(driver.close)
        self.assertEqual(driver._model.risk, "R1")
        self.assertEqual(module.calls, ["hardware"])

    def test_strict_refusal_of_an_instance_contract_precedes_the_factory(self) -> None:
        directory, module = self._package(
            _OPHYD.replace('estop_physical_ref = "front panel stop switch"', 'estop_physical_ref = None'),
            lock=_lock(reviewed=True),
        )
        with self.assertRaises(DriverDefinitionError) as caught:
            load_driver(directory, backend="hardware", allow_hardware=True, state_dir=self.root)
        self.assertIn("SAFE-045", str(caught.exception))
        self.assertEqual(module.calls, [])


if __name__ == "__main__":
    unittest.main()
