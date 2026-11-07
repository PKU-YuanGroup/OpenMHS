"""Fake mode must not invent a missing stop in a hardware driver's contract."""
from __future__ import annotations

import threading
import time
import unittest

from mhs.driver import Driver, FAKE_FIDELITY, Field, action, close_server, estop, read, write
from tests.driver import support

SET = "x-cap.test.unbound-hardware-set.v1"
STOP = "x-cap.test.unbound-hardware-stop.v1"


class RetainedTarget:
    def __init__(self):
        self.target = 0.0
        self.started = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.finished = threading.Event()
        self.stops = 0


class HardwareControl(Driver):
    device_id, device_kind, mode, risk = "unbound-hardware", "instrument", "hardware", "R2"
    backends = {"fake": RetainedTarget}

    @action(name=SET, input={"target": Field("number")}, long_running=True,
            cancellable=False, max_duration_ms=1000)
    def set_target(self, target):
        self.native.started.set()
        if not self.native.release.wait(2):
            raise RuntimeError("test peer was not released")
        self.native.target = target
        self.native.finished.set()


class UnboundHardwareSafetyTests(unittest.TestCase):
    def serve(self, cls=HardwareControl):
        driver = cls(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        return driver, client

    def status(self, client):
        return client.rpc("mhs.safety.status", {"session_id": client.session_id,
                                               "device_id": client.device_id, "deadline_ms": 1000})

    def test_completed_or_pending_external_effect_is_never_certified_by_a_local_latch(self):
        for pending in (False, True):
            with self.subTest(pending=pending):
                driver, client = self.serve()
                peer = driver.native
                if pending:
                    peer.release.clear()
                self.addCleanup(peer.release.set)
                receipt = client.command(SET, {"target": 3.25}, deadline_ms=10 if pending else 1000)
                def retire(peer=peer, client=client, receipt=receipt):
                    peer.release.set()
                    peer.finished.wait(1)
                    deadline = time.monotonic() + 1
                    while receipt.get("operation_id") and time.monotonic() < deadline:
                        if client.operation(receipt["operation_id"]).get("status") not in ("accepted", "running"):
                            break
                        time.sleep(0.002)
                self.addCleanup(retire)
                self.assertTrue(peer.started.wait(1))
                if not pending:
                    self.assertEqual(receipt["status"], "completed", receipt)
                stop = client.estop()
                self.assertEqual(stop["status"], "failed", stop)
                self.assertEqual(support.code(stop), "MHS.SAFETY.SAFE_STATE_UNREACHED")
                self.assertEqual(stop["output"]["estop"], "software_only")
                self.assertFalse(stop["output"]["safe_state_achieved"])
                self.assertTrue(stop["output"]["latched"])
                self.assertFalse(self.status(client)["estop"]["confirmed"])
                peer.release.set()
                self.assertTrue(peer.finished.wait(1))
                self.assertEqual(peer.target, 3.25)
                self.assertEqual(peer.stops, 0)
                self.assertFalse(self.status(client)["estop"]["confirmed"])
                self.assertFalse(driver.safety_status()["safe_state"]["achieved"])
                refused = client.command(SET, {"target": 8.0})
                self.assertEqual(support.code(refused), "MHS.SAFETY.ESTOP_ENGAGED", refused)
                self.assertEqual(peer.target, 3.25)

    def test_mutating_hardware_contract_is_unconfirmed_before_native_construction(self):
        driver = HardwareControl(backend="fake")
        self.addCleanup(driver.close)
        self.assertFalse(driver.safety_status()["safe_state"]["achieved"])
        self.assertFalse(driver._native_ready)

    def test_readonly_hardware_and_declared_local_simulation_keep_software_latch(self):
        class Observation(Driver):
            device_id, device_kind, mode = "unbound-observation", "instrument", "hardware"
            backends = {"fake": RetainedTarget}

            @action(name="x-cap.test.unbound-observe.v1", verb="read", output={"value": Field("number")})
            def observe(self):
                return {"value": self.native.target}

        class LocalSimulation(HardwareControl):
            mode = "simulated"
            risk = "R0"
            fidelity = FAKE_FIDELITY

        for cls in (Observation, LocalSimulation):
            with self.subTest(cls=cls.__name__):
                driver, client = self.serve(cls)
                receipt = client.estop()
                self.assertEqual(receipt["status"], "completed", receipt)
                self.assertEqual(receipt["output"]["estop"], "software_only")
                self.assertNotIn("safe_state", driver.safety_status())

    def test_native_stop_and_safe_state_action_paths_remain_available(self):
        class NativeStop(HardwareControl):
            @estop
            def halt(self):
                self.native.target = 0.0
                self.native.stops += 1

        class ActionStop(HardwareControl):
            @action(name=STOP, safe_state=True)
            def halt(self):
                self.native.target = 0.0
                self.native.stops += 1

        for cls in (NativeStop, ActionStop):
            with self.subTest(cls=cls.__name__):
                driver, client = self.serve(cls)
                self.assertEqual(client.command(SET, {"target": 3.25})["status"], "completed")
                receipt = client.estop()
                self.assertEqual(receipt["status"], "completed", receipt)
                self.assertTrue(receipt["output"]["safe_state_achieved"])
                self.assertEqual(driver.native.target, 0.0)
                self.assertEqual(driver.native.stops, 1)

    def test_write_only_hardware_contract_is_not_treated_as_observation(self):
        class WriteOnly(Driver):
            device_id, device_kind, mode = "unbound-write", "instrument", "hardware"
            risk = "R1"
            backends = {"fake": RetainedTarget}

            @read("target")
            def target(self):
                return self.native.target

            @write("target")
            def set_target(self, value):
                self.native.target = value

        driver, client = self.serve(WriteOnly)
        receipt = client.estop()
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertFalse(driver.safety_status()["safe_state"]["achieved"])

    def test_r0_measurement_invocation_does_not_imply_physical_control(self):
        class Measurement(Driver):
            device_id, device_kind, mode, risk = "unbound-measurement", "instrument", "hardware", "R0"
            backends = {"fake": RetainedTarget}

            @action(name="x-cap.test.start_measurement.v1", output={"value": Field("number")})
            def acquire(self):
                self.native.target += 1  # Measurement counter, not a physical output.
                return {"value": self.native.target}

        driver, client = self.serve(Measurement)
        self.assertEqual(client.command("x-cap.test.start_measurement.v1")["status"], "completed")
        self.assertEqual(driver.native.target, 1)
        receipt = client.estop()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "software_only")
        self.assertNotIn("safe_state", driver.safety_status())

    def test_catalogue_risk_floor_cannot_be_hidden_by_a_declared_r0_label(self):
        class PhysicalClassFloor(Driver):
            device_id, device_kind, mode, risk = "unbound-class-floor", "robot.arm", "hardware", "R0"
            backends = {"fake": RetainedTarget}

            @action(cap="cap.motion.joint_position.v1")
            def move(self, joint_positions, duration_s=None):
                return {"joint_positions": joint_positions, "reached": True}

        driver = PhysicalClassFloor(backend="fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver._model.declared_risk, "R0")
        self.assertNotEqual(driver._model.risk, "R0")
        self.assertFalse(driver.safety_status()["safe_state"]["achieved"])
        self.assertFalse(driver._native_ready)


if __name__ == "__main__":
    unittest.main()
