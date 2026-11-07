"""The four exemplar driver packages behave as their READMEs claim when served: limits, operator bounds, e-stop, review gate.

These are runtime checks of the shipped packages in MHS/drivers (the gate G1 to G9 is a separate, stricter check that needs the
upstream clones). They run on the fake backends, so they need neither the corpus nor hardware.
"""

import tempfile
import unittest
import warnings
from pathlib import Path

from mhs.adapter import LoadError, load
from mhs.testing import client_for

REPO = Path(__file__).resolve().parents[4]
DRIVERS = REPO / "MHS" / "drivers"
JULABO = DRIVERS / "labs" / "tiagocoutinho__julabo"
SR860 = DRIVERS / "labs" / "thinksrs__srsinst.sr860"
XARM = DRIVERS / "robots" / "xarm-developer__xarm-python-sdk"
GYM = DRIVERS / "robots" / "farama-foundation__gymnasium"


class Bench:
    """A served exemplar with one open session."""

    def __init__(self, path, **options):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.server = load(path, "fake", **options)
        self.client = client_for(self.server)
        self.device = self.client.hello()["devices"][0]["device_id"]
        self.session = self.client.open_session(device_ids=[self.device])["session_id"]

    def invoke(self, capability, payload):
        return self.client.invoke(capability, payload, device_id=self.device, session_id=self.session)

    def write(self, patch):
        return self.client.write("main", patch, device_id=self.device, session_id=self.session)

    def state(self):
        return self.client.read("main", device_id=self.device)["state"]

    def estop(self):
        return self.client.estop("test", device_id=self.device, session_id=self.session)


def code(receipt):
    return (receipt.get("error") or {}).get("mhs_code")


class ExemplarRuntimeTests(unittest.TestCase):
    def test_xarm_refuses_a_joint_outside_its_own_range_and_does_not_move(self):
        bench = Bench(XARM)
        good = [0.1] * 7
        self.assertEqual(bench.invoke("cap.motion.joint_position.v1", {"joint_positions": good})["status"], "completed")
        bad = list(good)
        bad[3] = -1.0  # joint 4 of this robot type starts at -0.19 rad
        receipt = bench.invoke("cap.motion.joint_position.v1", {"joint_positions": bad})
        self.assertEqual((receipt["status"], code(receipt)), ("rejected", "MHS.SAFETY.ENVELOPE_VIOLATION"))
        self.assertEqual(bench.state()["joint_positions"], good, "a refused command must not reach the arm")

    def test_xarm_nested_position_limit_and_operator_required_orientation(self):
        bench = Bench(XARM)
        receipt = bench.invoke("cap.motion.cartesian_pose.v1", {"position": {"x": 0.0, "y": 0.0, "z": 5000.0}})
        self.assertEqual(code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION")
        receipt = bench.invoke("cap.motion.cartesian_pose.v1", {
            "position": {"x": 100.0, "y": 0.0, "z": 200.0}, "orientation": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}})
        self.assertEqual(code(receipt), "MHS.SAFETY.LIMITS_UNSET", "no source states an orientation bound: the operator supplies it")

    def test_an_estop_latches_and_refuses_everything_that_moves(self):
        for path, refused in ((XARM, lambda b: b.invoke("cap.motion.joint_position.v1", {"joint_positions": [0.1] * 7})),
                              (JULABO, lambda b: b.write({"setpoint": 30.0}))):
            with self.subTest(path.name):
                bench = Bench(path, site_limits=f"{JULABO}/site-limits.example.json") if path == JULABO else Bench(path)
                self.assertEqual(bench.estop()["status"], "completed")
                self.assertEqual(code(refused(bench)), "MHS.SAFETY.ESTOP_ENGAGED")

    def test_julabo_setpoint_is_refused_until_the_operator_supplies_a_range(self):
        bench = Bench(JULABO)
        self.assertEqual(code(bench.write({"setpoint": 30.0})), "MHS.SAFETY.LIMITS_UNSET")
        bench = Bench(JULABO, site_limits=f"{JULABO}/site-limits.example.json")
        self.assertEqual(bench.write({"setpoint": 30.0})["status"], "completed")
        self.assertEqual(code(bench.write({"setpoint": 90.0})), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(bench.state()["setpoint"], 30.0)

    def test_sr860_limits_come_from_the_upstream_code(self):
        bench = Bench(SR860)
        for name, ok, bad in (("frequency", 1000.0, 600000.0), ("amplitude", 1.0, 3.0), ("time_constant", 1e-3, 0.5)):
            with self.subTest(name):
                self.assertEqual(bench.write({name: ok})["status"], "completed")
                self.assertEqual(code(bench.write({name: bad})), "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_gymnasium_action_space_is_enforced(self):
        bench = Bench(GYM)
        self.assertEqual(bench.invoke("cap.world.step.v1", {"ticks": 3, "action": {"index": 1}})["status"], "completed")
        self.assertEqual(code(bench.invoke("cap.world.step.v1", {"ticks": 3, "action": {"index": 5}})),
                         "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_model_written_r2_hardware_drivers_never_start_a_hardware_backend_unreviewed(self):
        for path in (JULABO, XARM):
            with self.subTest(path.name), tempfile.TemporaryDirectory() as state_dir:
                with self.assertRaises(LoadError) as raised:
                    load(path, "hardware", allow_hardware=True, state_dir=state_dir)
                self.assertEqual(raised.exception.reason, "review_required")

    def test_a_hardware_backend_is_never_started_without_the_operator_flag(self):
        with self.assertRaises(LoadError) as raised:
            load(XARM, "hardware")
        self.assertEqual(raised.exception.reason, "hardware_not_allowed")


if __name__ == "__main__":
    unittest.main()
