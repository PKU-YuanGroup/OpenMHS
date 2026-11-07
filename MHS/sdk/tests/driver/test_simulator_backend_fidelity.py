"""Backend-specific simulator fidelity overrides preserve existing common declarations."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import Mock

from mhs.driver import DriverDefinitionError, build_manifest, build_reference

from tests.bridges import support as bridge_support
from tests.driver.test_families import CartPole, Pendulums, fake_mujoco_module


class SimulatorBackendFidelityTests(unittest.TestCase):
    def test_mujoco_fake_and_sim_metadata_are_distinct(self):
        class Split(Pendulums):
            backends = {"fake": fake_mujoco_module, "sim": fake_mujoco_module}
            fidelity = {"reset": "partial", "determinism": {"kind": "none"}}
            fidelity_by_backend = {
                "fake": {"engine": "analytic fake", "fidelity_level": "F0", "gaps": ["no dynamics"]},
                "sim": {"engine": "mujoco", "fidelity_level": "F1", "gaps": ["unvalidated contacts"]},
            }

        for backend, engine, level in (("fake", "analytic fake", "F0"), ("sim", "mujoco", "F1")):
            with self.subTest(backend=backend):
                driver = Split(backend=backend)
                self.addCleanup(driver.close)
                fidelity = build_manifest(driver)["fidelity"]
                self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), (engine, level))
                self.assertEqual(fidelity["reset"], "partial")
                self.assertEqual(fidelity["determinism"], {"kind": "none"})
                self.assertEqual(fidelity["timestep_ms"], 2.0)
                self.assertEqual(driver.fidelity_for(None), driver.fidelity_for(backend))

    def test_gymnasium_selected_override_wins_over_common_members(self):
        class Split(CartPole):
            backends = {
                "fake": lambda: bridge_support.FakeCartPole(),
                "sim": lambda: bridge_support.FakeCartPole(),
            }
            fidelity = {"engine": "common engine", "fidelity_level": "F0", "reset": "partial",
                        "determinism": {"kind": "none", "notes": "common notes"}}
            fidelity_by_backend = {
                "sim": {"engine": "sim engine", "determinism": {"kind": "statistical"}},
            }

        fake, sim = Split(backend="fake"), Split(backend="sim")
        self.addCleanup(fake.close)
        self.addCleanup(sim.close)
        self.assertEqual(fake.fidelity_for(None)["engine"], "common engine")
        self.assertEqual(sim.fidelity_for(None)["engine"], "sim engine")
        self.assertEqual(sim.fidelity_for(None)["determinism"], {"kind": "statistical"})
        self.assertEqual(sim.fidelity_for(None)["reset"], "partial")
        self.assertEqual(sim.fidelity_for(None)["fidelity_level"], "F0")
        self.assertEqual(sim.fidelity_for(None)["clock"], "lockstep")

    def test_empty_default_keeps_reference_and_fidelity_unchanged(self):
        driver = Pendulums(backend="fake")
        self.addCleanup(driver.close)
        derived = driver._derived_fidelity()
        self.assertEqual(driver.fidelity_for(None), derived)
        before = build_reference(driver)
        # The explicit empty declaration has exactly the inherited default's behavior.
        class Empty(Pendulums):
            fidelity_by_backend = {}

        other = Empty(backend="fake")
        self.addCleanup(other.close)
        self.assertEqual(build_manifest(other)["fidelity"], derived)
        self.assertEqual(build_reference(driver), before)

    def test_returned_fidelity_has_no_mutable_aliases_to_class_model_or_other_backend(self):
        common = {"determinism": {"kind": "none", "notes": "original"}}
        per_backend = {"fake": {"gaps": ["fake gap"]}, "sim": {"gaps": ["sim gap"]}}

        class Split(Pendulums):
            fidelity = common
            fidelity_by_backend = per_backend

        driver = Split(backend="fake")
        self.addCleanup(driver.close)
        expected_common, expected_backends = copy.deepcopy(common), copy.deepcopy(per_backend)
        first = driver.fidelity_for(None)
        first["gaps"].append("mutated return")
        first["determinism"]["notes"] = "mutated return"
        manifest = build_manifest(driver)
        manifest["fidelity"]["gaps"].append("mutated manifest")
        self.assertEqual(common, expected_common)
        self.assertEqual(per_backend, expected_backends)
        self.assertEqual(driver._model.fidelity["gaps"], ["fake gap"])
        self.assertEqual(driver.fidelity_for("sim")["gaps"], ["sim gap"])
        self.assertEqual(driver.fidelity_for(None)["determinism"]["notes"], "original")

    def test_invalid_config_or_entry_is_rejected_before_backend_factory(self):
        for invalid in (None, [], "fake", {"real": {}}, {None: {}}, {1: {}},
                        {"fake": None}, {"fake": []}, {"sim": "not an object"}):
            factory = Mock(side_effect=AssertionError("invalid metadata opened a backend"))
            cls = type("Invalid", (Pendulums,), {"backends": {"fake": factory},
                                                "fidelity_by_backend": invalid})
            with self.subTest(invalid=invalid), self.assertRaises(DriverDefinitionError) as caught:
                cls(backend="fake")
            self.assertIn("fidelity_by_backend", str(caught.exception))
            factory.assert_not_called()

    def test_invalid_later_config_cannot_be_emitted_in_a_manifest(self):
        class Mutable(Pendulums):
            fidelity_by_backend = {"fake": {"gaps": ["valid"]}}

        driver = Mutable(backend="fake")
        self.addCleanup(driver.close)
        Mutable.fidelity_by_backend["sim"] = None
        with self.assertRaises(DriverDefinitionError):
            build_manifest(driver)

    def test_explicit_unknown_projection_backend_is_rejected(self):
        driver = Pendulums(backend="fake")
        self.addCleanup(driver.close)
        for invalid in ("real", "", 1, False):
            with self.subTest(backend=invalid), self.assertRaises(DriverDefinitionError):
                driver.fidelity_for(invalid)


if __name__ == "__main__":
    unittest.main()
