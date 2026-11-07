"""Acceptance run of the RoboPianist package: the gate plus local cases.

Add cases, never remove the check_driver call. The cases run on the fake backend (fake.py), an analytic dm_env
stand-in for the environment robopianist.suite.load returns; no robopianist, dm_control or MuJoCo code is imported.
"""

import importlib
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverDefinitionError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
STEP, RESET, SEED = "cap.world.step.v1", "cap.world.reset.v1", "cap.world.seed.v1"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ZERO = [0.0] * 45


def package_module(driver, name):
    """The package's own module ``name`` (fake or sim), imported beside driver.py."""
    return importlib.import_module(type(driver).__module__.rsplit(".", 1)[0] + "." + name)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RoboPianistCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_action_envelope_is_two_hands_and_the_sustain_pedal(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        fake = package_module(driver, "fake")
        spec = fake.FakePianoEnvironment().action_spec()
        self.assertEqual(spec.shape, (45,))
        # right hand: 20 XML actuators then forearm_tx and forearm_ty; the left hand likewise; then the sustain
        self.assertEqual((spec.minimum[0], spec.maximum[0]), (-0.523599, 0.174533))      # wrist_y
        self.assertEqual((spec.minimum[9], spec.maximum[9]), (0.0, 3.1415))              # middle_distal (FF)
        self.assertAlmostEqual(spec.minimum[20], -0.7605)                                # forearm_tx, right
        self.assertAlmostEqual(spec.maximum[20], 0.4605)
        self.assertEqual((spec.minimum[21], spec.maximum[21]), (0.0, 0.06))              # forearm_ty
        self.assertAlmostEqual(spec.minimum[42], -0.4605)                                # forearm_tx, left
        self.assertAlmostEqual(spec.maximum[42], 0.7605)
        self.assertEqual((spec.minimum[44], spec.maximum[44]), (0.0, 1.0))               # sustain
        self.assertEqual(spec.minimum[:20], spec.minimum[22:42])
        self.assertEqual(spec.maximum[:20], spec.maximum[22:42])

    def test_step_runs_a_placeholder_episode_through_the_dm_env_adapter(self) -> None:
        client = self.serve()
        reset = client.invoke(RESET, {}, **self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        receipt = client.invoke(STEP, {"ticks": 3, "action": {"values": ZERO}}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        # The fake's eighth step is LAST with discount 1.0: the adapter reports the end of the piece as truncated.
        receipt = client.invoke(STEP, {"ticks": 5, "action": {"values": ZERO}}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["truncated"], receipt)
        self.assertFalse(receipt["output"]["terminated"], receipt)

    def test_an_action_outside_a_cited_bound_is_refused_before_the_native_call(self) -> None:
        client = self.serve()
        client.invoke(RESET, {}, **self.ids)
        for index, value in ((44, 1.5), (21, 0.07), (0, -0.6)):
            action = list(ZERO)
            action[index] = value
            receipt = client.invoke(STEP, {"ticks": 1, "action": {"values": action}}, **self.ids)
            self.assertEqual(receipt["status"], "rejected", (index, receipt))
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_no_seed_capability_is_served(self) -> None:
        client = self.serve()
        capabilities = [item["capability_id"] for item in client.hello()["devices"][0]["capabilities"]]
        self.assertNotIn(SEED, capabilities)
        self.assertIn(STEP, capabilities)
        self.assertIn(RESET, capabilities)

    def test_the_estop_latches_and_reset_releases(self) -> None:
        client = self.serve()
        client.invoke(RESET, {}, **self.ids)
        stop = client.estop("test", device_id=self.ids["device_id"])
        self.assertEqual(stop["status"], "completed", stop)
        # No native stop exists or is needed: the latch is the stop of a synchronous simulator.
        self.assertEqual((stop["output"]["estop"], stop["output"]["latched"]), ("software_only", True), stop)
        self.assertTrue(stop["output"]["safe_state_achieved"], stop)
        latched = client.invoke(STEP, {"ticks": 1, "action": {"values": ZERO}}, **self.ids)
        self.assertEqual(latched["status"], "rejected", latched)
        self.assertEqual(client.reset(device_id=self.ids["device_id"])["status"], "completed")
        self.assertEqual(client.invoke(RESET, {}, **self.ids)["status"], "completed")

    def test_the_fake_keeps_only_the_dm_env_calls_of_the_adapter(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        fake = package_module(driver, "fake")
        public = {name for name in vars(fake.FakePianoEnvironment) if not name.startswith("_")}
        self.assertEqual(public, {"reset", "step", "action_spec", "observation_spec", "control_timestep", "close"})

    def test_live_factory_imports_nothing_until_it_opens_and_refuses_other_options(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        sim = package_module(driver, "sim")
        self.assertFalse({"suite", "robopianist"} & set(vars(sim)), "nothing of robopianist at module import")
        # Every refusal comes before the import: robopianist is not installed here, so a factory that imported
        # first would raise ModuleNotFoundError instead.
        for options in ({"midi_file": "x.mid"}, {"task_kwargs": {}}, {"environment_name": "NotARoboPianistName-v0"},
                        {"seed": -1}, {"seed": True}):
            with self.subTest(options=options), self.assertRaises(DriverDefinitionError):
                sim.make_env(**options)
        self.assertEqual(sim.DEFAULT_ENVIRONMENT, "RoboPianist-debug-TwinkleTwinkleLittleStar-v0")


if __name__ == "__main__":
    unittest.main()
