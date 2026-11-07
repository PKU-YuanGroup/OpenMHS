"""Timing is resolved from the selected backend; legacy declarations stay unchanged."""
import copy
import json
from pathlib import Path
import unittest
from mhs.driver import Action, GymnasiumDriver, DriverDefinitionError, build_manifest, build_reference
from mhs.schema.store import default_store
from tests.bridges.test_gymnasium_timing import ClockEnv, CONFIG, CHECKPOINT


def timed_driver(env=None, *, autoreset=False, long_running=False, decimation=5,
                 backend="sim", checkpoint=False):
    native = env or ClockEnv()
    class Timed(GymnasiumDriver):
        device_id = "timing/clock"
        backends = {"sim": lambda: native, "fake": (lambda: native) if backend == "fake" else ClockEnv}
        timing_by_backend = {backend: {**copy.deepcopy(CONFIG), "control_decimation": decimation}}
        checkpoint_by_backend = {backend: copy.deepcopy(CHECKPOINT)} if checkpoint else {}
        safe_state = "software-only simulation pause"
    Timed.autoreset = autoreset
    if long_running:
        Timed.actions = {"cap.world.step.v1": Action(name="step", long_running=True,
                                                   cancellable=True, max_duration_ms=1500)}
    return Timed(backend=backend)


class DriverTimingTests(unittest.TestCase):
    def test_manifest_has_both_periods_and_binding_notes(self):
        driver = timed_driver()
        self.addCleanup(driver.close)
        manifest = build_manifest(driver)
        self.assertEqual(default_store().validate(manifest, "device.schema.json"), [])
        self.assertEqual(manifest["fidelity"]["timestep_ms"], 2)
        self.assertIn("no wall-clock pacing", manifest["fidelity"]["gaps"])
        step = next(x for x in manifest["capabilities"] if x["capability_id"] == "cap.world.step.v1")
        desc = step["x-vendor"]["openmhs_simulation_timing"]
        self.assertEqual((desc["physics_timestep_ms"], desc["control_period_ms"]), (2, 10))
        self.assertIn("ticks", step["input_schema"]["required"])
        self.assertEqual(step["input_schema"]["properties"]["ticks"]["multipleOf"], 5)
        self.assertIn("Physics timestep 2 ms; control period 10 ms", manifest["profile"]["operating_notes"][0])
        reference = build_reference(driver)
        self.assertEqual(default_store().validate(reference, "reference.schema.json"), [])
        action = next(x for x in reference["actions"] if x["cap_id"] == "cap.world.step.v1")
        ticks = next(x for x in action["inputs"] if x["name"] == "ticks")
        self.assertIn("Physics timestep 2 ms; control period 10 ms", ticks["description"])

    def test_nonselected_sim_config_does_not_open_sim_and_fake_keeps_legacy(self):
        calls = []
        class Split(GymnasiumDriver):
            device_id = "timing/split"
            backends = {"fake": ClockEnv, "sim": lambda: calls.append("opened")}
            timing_by_backend = {"sim": CONFIG}
        fake = Split(backend="fake")
        self.addCleanup(fake.close)
        manifest = build_manifest(fake)
        self.assertEqual(calls, [])
        self.assertEqual(manifest["fidelity"]["timestep_ms"], 10)
        self.assertNotIn("operating_notes", manifest.get("profile", {}))
        step = next(x for x in manifest["capabilities"] if x["capability_id"] == "cap.world.step.v1")
        self.assertNotIn("x-vendor", step)
        with self.assertRaises(DriverDefinitionError):
            build_manifest(fake, backend="sim")
        self.assertEqual(calls, [])

    def test_backend_projection_and_conflicting_fidelity_are_refused(self):
        driver = timed_driver()
        self.addCleanup(driver.close)
        with self.assertRaises(DriverDefinitionError):
            build_manifest(driver, backend="fake")
        class Bad(GymnasiumDriver):
            device_id = "timing/bad"
            backends = {"sim": ClockEnv}
            timing_by_backend = {"sim": CONFIG}
            fidelity_by_backend = {"sim": {"timestep_ms": 10}}
        with self.assertRaises(DriverDefinitionError):
            Bad(backend="sim")

    def test_empty_config_reference_matches_inherited_default(self):
        class Plain(GymnasiumDriver):
            device_id = "timing/plain"
            display_name = "Unconfigured clock peer"
            backends = {"fake": ClockEnv}
        class Empty(Plain):
            timing_by_backend = {}
        plain, empty = Plain(backend="fake"), Empty(backend="fake")
        self.addCleanup(plain.close)
        self.addCleanup(empty.close)
        self.assertEqual(build_reference(plain), build_reference(empty))

    def test_legacy_manifest_reference_state_and_digests_match_captured_baseline(self):
        from tests.driver.test_families import CartPole, Pendulums
        result = {}
        for cls in (CartPole, Pendulums):
            driver = cls(backend="fake")
            self.addCleanup(driver.close)
            manifest = build_manifest(driver)
            manifest.pop("instance_id", None)
            result[cls.__name__] = {"manifest": manifest, "reference": build_reference(driver)}
            if cls is CartPole:
                driver.inner.call("cap.world.reset.v1", {"seed": 7})
                result[cls.__name__]["step"] = driver.inner.call(
                    "cap.world.step.v1", {"ticks": 3, "action": {"index": 1}})
                with self.assertRaises(Exception):
                    driver.inner.snapshot()  # implicit native-only snapshots are no longer supported
        actual = (json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        fixture = Path(__file__).parents[1] / "fixtures/simulation-timing-legacy.json"
        # Preserve the original golden bytes. Enumerate only the approved Gym
        # and MuJoCo checkpoint migrations; all other bytes must remain equal.
        # The old native-only Gym checkpoint is not served wire state.
        from mhs import canonical
        expected = json.loads(fixture.read_bytes())
        cart = expected["CartPole"]
        cart.pop("snapshot")
        for document in (cart["manifest"], cart["reference"]):
            document["fidelity"]["snapshot_restore"] = False
            document["fidelity"]["determinism"]["kind"] = "seeded"
        for binding in cart["manifest"]["capabilities"]:
            binding["determinism"] = "seeded"
        cart["reference"]["provenance"]["manifest_digest"] = canonical.digest(cart["manifest"])
        pendulums = expected["Pendulums"]
        for document in (pendulums["manifest"], pendulums["reference"]):
            self.assertEqual(document["fidelity"]["determinism"]["kind"], "exact")
            document["fidelity"]["determinism"]["kind"] = "none"
        for binding in pendulums["manifest"]["capabilities"]:
            self.assertEqual(binding["determinism"], "exact")
            self.assertNotIn("exclusive", binding)
            binding["determinism"] = "none"
            binding["exclusive"] = True
        # An explicit expected schema, not copied from the implementation or
        # current output: an unrelated schema/limit/description drift still fails.
        description = (
            "Declared native checkpoint. Integration profile restores the full native input vector; "
            "basic profile restores only advertised state plus actuator activation and exact native time. "
            "Neither profile certifies external callbacks, plugins, RNG or hardware fidelity.")
        properties = pendulums["manifest"]["resources"][0]["state_schema"]["properties"]
        self.assertNotIn("native_checkpoint", properties)
        properties["native_checkpoint"] = {
            "type": "object", "readOnly": True, "description": description,
            "properties": {
                "profile": {"type": "string", "enum": ["mujoco_integration_v1", "mujoco_basic_v1"]},
                "engine_version": {"type": "string", "maxLength": 100},
                "signature": {"type": "integer"}, "state_size": {"type": "integer"},
                "dimensions": {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4},
                "values": {"type": "array", "items": {"type": "number"}, "maxItems": 32768},
                "time": {"type": "number"},
                "act": {"type": "array", "items": {"type": "number"}, "maxItems": 32768},
            },
            "required": ["profile", "engine_version", "signature", "state_size", "dimensions"],
            "additionalProperties": False,
        }
        pendulums["reference"]["measures"].append({
            "name": "native_checkpoint", "type": "object", "description": description, "resource": "world"})
        pendulums["reference"]["provenance"]["manifest_digest"] = canonical.digest(pendulums["manifest"])
        expected_bytes = (json.dumps(expected, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        self.assertEqual(actual, expected_bytes)

    def test_timing_mode_does_not_claim_unimplemented_wall_clock_pacing(self):
        class Paced(GymnasiumDriver):
            device_id = "timing/paced"
            backends = {"sim": ClockEnv}
            timing_by_backend = {"sim": CONFIG}
            fidelity = {"realtime_factor": 1}
        with self.assertRaises(DriverDefinitionError):
            Paced(backend="sim")


if __name__ == "__main__":
    unittest.main()
