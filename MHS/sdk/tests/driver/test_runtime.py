"""A Driver served by the strict runtime: async methods, outputs, limits, e-stop, interlocks, failures."""

from __future__ import annotations

import time
import unittest

from mhs.driver import (
    FAKE_FIDELITY,
    Driver,
    DriverFailed,
    Field,
    Limit,
    action,
    build_manifest,
    build_server,
    close_server,
    estop,
    read,
    write,
)

from tests.driver import support
from tests.driver.support import code


class BathRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.driver = support.Bath(backend="fake")
        self.server, self.client = support.serve(self.driver)
        self.native = self.driver.native
        self.addCleanup(close_server, self.server)

    def test_served_strict_and_as_a_fake(self) -> None:
        self.assertIs(self.server.strict, True)
        device = self.client.device()
        self.assertEqual(device["device_id"], "mhs://localhost/lab/bath/fake")
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["models"], ["mhs://localhost/lab/bath"])
        self.assertEqual(device["fidelity"], FAKE_FIDELITY)
        verbs = {item["capability_id"]: (item.get("verb"), item.get("x-mhs-name")) for item in device["capabilities"]}
        self.assertEqual(verbs["cap.thermal.setpoint.v1"], ("write", "ramp_to"))
        self.assertEqual(verbs["cap.device.configure.v1"], ("write", None))
        self.assertEqual(verbs["x-cap.julabo.heater_off.v1"], ("invoke", "heater_off"))
        self.assertNotIn("x-mhs-reference-error", device)
        self.assertEqual(device["reference"]["safety"]["estop"]["native"], "stop")

    def test_async_read_runs_on_one_loop(self) -> None:
        first = self.client.read()
        second = self.client.read()
        self.assertEqual(first["state"]["temperature"], 21.5)
        self.assertEqual(first["state"]["setpoint"], 20.0)
        self.assertEqual(first["revision"], second["revision"])
        self.assertEqual(len(self.native.loops), 1)

    def test_async_write_reaches_the_native_and_is_read_back(self) -> None:
        receipt = self.client.write({"setpoint": 37.5})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["applied"], {"setpoint": 37.5})
        self.assertEqual(self.native.actuations, [("set_setpoint", 37.5)])
        self.assertEqual(self.client.read()["state"]["setpoint"], 37.5)
        self.assertEqual(receipt["capability_id"], "cap.device.configure.v1")

    def test_setter_return_value_is_the_applied_value(self) -> None:
        overlay = {"openmhs": "0.9", "site": "t", "issued_by": {"id": "operator:t"}, "issued_at": "2026-10-22T09:00:00Z",
                   "devices": {"mhs://localhost/lab/bath/fake": {
                       "pump_speed": {"min": 0, "max": 100, "unit": "/min", "source": "operator"}}}}
        server, client = support.serve(support.Bath(backend="fake"), site_limits=overlay)
        self.addCleanup(close_server, server)
        receipt = client.write({"pump_speed": 12.34})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["applied"], {"pump_speed": 12.3})

    def test_write_outside_the_limit_is_refused_before_the_native(self) -> None:
        for value in (-20.5, 150.01, 1e6):
            receipt = self.client.write({"setpoint": value})
            self.assertEqual(receipt["status"], "rejected")
            self.assertEqual(code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION")
            self.assertEqual(receipt["error"]["details"]["path"], "setpoint")
        self.assertEqual(self.native.actuations, [])

    def test_read_only_parameter_is_not_writable(self) -> None:
        receipt = self.client.write({"temperature": 30})
        self.assertNotEqual(receipt["status"], "completed")
        self.assertEqual(self.native.actuations, [])

    def test_operator_required_is_limits_unset_without_an_overlay(self) -> None:
        receipt = self.client.write({"pump_speed": 10})
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(code(receipt), "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(self.native.actuations, [])

    def test_operator_required_works_with_an_overlay_for_the_hardware_id(self) -> None:
        overlay = {"openmhs": "0.9", "site": "t", "issued_by": {"id": "operator:t"}, "issued_at": "2026-10-22T09:00:00Z",
                   "devices": {"mhs://localhost/lab/bath": {
                       "pump_speed": {"min": 0, "max": 50, "unit": "/min", "source": "operator"}}}}
        server, client = support.serve(support.Bath(backend="fake"), site_limits=overlay)
        self.addCleanup(close_server, server)
        self.assertEqual(client.write({"pump_speed": 10})["status"], "completed")
        refused = client.write({"pump_speed": 60})
        self.assertEqual(code(refused), "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_action_output_and_limits(self) -> None:
        receipt = self.client.command("cap.thermal.setpoint.v1", {"target_temperature": 40})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"setpoint": 40.0, "reached": True})
        refused = self.client.command("cap.thermal.setpoint.v1", {"target_temperature": 151})
        self.assertEqual(code(refused), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual([item for item in self.native.actuations if item[0] == "ramp"], [("ramp", 40)])

    def test_scalar_return_is_wrapped_into_the_single_output_field(self) -> None:
        receipt = self.client.command("x-cap.julabo.heater_off.v1", {})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"heater_off": True})

    def test_native_exception_is_a_redacted_failure(self) -> None:
        receipt = self.client.command("x-cap.julabo.explode.v1", {})
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(code(receipt), "MHS.ADAPTER.SHIM_FAILED")
        self.assertNotIn("secret", str(receipt))

    def test_estop_latches_calls_the_native_stop_and_the_safe_state(self) -> None:
        receipt = self.client.estop()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["latched"])
        self.assertEqual(receipt["output"]["estop"], "engaged")
        self.assertEqual(self.native.actuations, [("stop",), ("heater_off",)])
        refused = self.client.command("cap.thermal.setpoint.v1", {"target_temperature": 30})
        self.assertEqual(code(refused), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(code(self.client.write({"setpoint": 30})), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertNotIn(("set_setpoint", 30), self.native.actuations)

    def test_estop_during_a_running_action_cancels_it(self) -> None:
        driver = support.Bath(backend="fake", options={"ramp_s": 5.0})
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        started = client.command("cap.thermal.setpoint.v1", {"target_temperature": 45}, deadline_ms=200)
        self.assertEqual(started["status"], "running", started)
        self.assertTrue(driver.native.ramp_started.wait(2))
        client.estop()
        self.assertTrue(driver.native.ramp_cancelled.wait(3), "the running ramp was not cancelled")
        self.assertIn(("stop",), driver.native.actuations)
        deadline = time.monotonic() + 3
        state = None
        while time.monotonic() < deadline:
            state = client.operation(started["operation_id"]).get("status")
            if state in ("cancelled", "failed", "completed", "rejected"):
                break
            time.sleep(0.01)
        self.assertEqual(state, "cancelled")

    def test_reset_runs_the_native_recovery(self) -> None:
        self.client.estop()
        response = self.client.reset()
        self.assertIn("result", response, response)
        self.assertEqual(response["result"]["status"], "completed")
        self.assertEqual(self.native.reset_calls, 1)
        self.assertEqual(self.client.command("cap.thermal.setpoint.v1", {"target_temperature": 30})["status"],
                         "completed")

    def test_open_or_unreadable_interlock_blocks_the_gated_action(self) -> None:
        for value in (False, "garbage", None):
            self.native.lid_closed = value
            receipt = self.client.command("cap.thermal.setpoint.v1", {"target_temperature": 30})
            self.assertEqual(code(receipt), "MHS.SAFETY.INTERLOCK_OPEN", (value, receipt))
        self.assertEqual(self.driver.interlocks()[0]["state"], "unknown")
        self.native.lid_closed = True
        self.assertEqual(self.client.command("cap.thermal.setpoint.v1", {"target_temperature": 30})["status"],
                         "completed")
        self.assertEqual(self.driver.interlocks(), [{"id": "lid_closed", "state": "closed",
                                                     "description": "Bath lid closed"}])


class ArmRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.driver = support.Arm(backend="fake")
        self.server, self.client = support.serve(self.driver)
        self.addCleanup(close_server, self.server)

    def test_every_joint_element_is_bounded_per_element(self) -> None:
        good = [0.0, 0.5, 1.0, 0.0, 0.0, 0.0]
        self.assertEqual(self.client.command("cap.motion.joint_position.v1", {"joint_positions": good})["status"],
                         "completed")
        lows = [-6.28, -2.0, -0.1, -6.28, -1.7, -6.28]
        highs = [6.28, 2.0, 3.8, 6.28, 3.1, 6.28]
        before = len(self.driver.native.actuations)
        for index in range(6):
            for bad in (lows[index] - 0.01, highs[index] + 0.01):
                joints = list(good)
                joints[index] = bad
                receipt = self.client.command("cap.motion.joint_position.v1", {"joint_positions": joints})
                self.assertEqual(code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION", (index, bad, receipt))
                self.assertEqual(receipt["error"]["details"]["path"], f"joint_positions[{index}]")
                self.assertEqual(receipt["error"]["details"].get("element_name"), support.JOINTS[index])
        self.assertEqual(len(self.driver.native.actuations), before)

    def test_a_scalar_bound_on_an_array_bounds_every_element(self) -> None:
        class Dosing(Driver):
            device_id, device_kind, mode, risk = "dosing", "instrument", "hardware", "R1"
            backends = {"fake": list}

            @action(name="x-cap.example.dose.v1", input={"volumes": Field(
                "array", items="number", length=3, unit="uL",
                limit=Limit(min=0, max=10, source="vendor_doc", ref="pump.pdf:7"))})
            def dose(self, volumes):
                self.native.append(list(volumes))

        driver = Dosing(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        self.assertEqual(client.command("x-cap.example.dose.v1", {"volumes": [0, 5, 10]})["status"], "completed")
        for index in range(3):
            volumes = [1.0, 1.0, 1.0]
            volumes[index] = 10.5
            receipt = client.command("x-cap.example.dose.v1", {"volumes": volumes})
            self.assertEqual(code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION")
            self.assertEqual(receipt["error"]["details"]["path"], f"volumes[{index}]")
        self.assertEqual(driver.native, [[0, 5, 10]])

    def test_wrong_length_is_refused(self) -> None:
        receipt = self.client.command("cap.motion.joint_position.v1", {"joint_positions": [0.0] * 5})
        self.assertNotEqual(receipt["status"], "completed")
        self.assertEqual(self.driver.native.actuations, [])

    def test_nested_cartesian_limits(self) -> None:
        ok = self.client.command("cap.motion.cartesian_pose.v1", {"position": {"x": 100, "y": 0, "z": 300}})
        self.assertEqual(ok["status"], "completed", ok)
        for axis, value in (("x", 701), ("y", -701), ("z", -101), ("z", 901)):
            position = {"x": 0, "y": 0, "z": 300}
            position[axis] = value
            receipt = self.client.command("cap.motion.cartesian_pose.v1", {"position": position})
            self.assertEqual(code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION", (axis, value))
            self.assertEqual(receipt["error"]["details"]["path"], f"position.{axis}")
        self.assertEqual(len(self.driver.native.actuations), 1)

    def test_return_code_failure_is_a_failed_receipt_with_the_code(self) -> None:
        self.driver.native.code = 9
        receipt = self.client.command("cap.motion.joint_position.v1", {"joint_positions": [0.0] * 6})
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(code(receipt), "MHS.DEVICE.FAULTED")

    def test_estop_calls_the_named_native(self) -> None:
        self.client.estop()
        self.assertEqual(self.driver.native.actuations, [("emergency_stop",)])


class OutputContractTests(unittest.TestCase):
    def test_sampled_at_is_stamped_and_scalars_need_a_single_output(self) -> None:
        class Meter(Driver):
            device_id, device_kind, mode = "meter", "instrument.dmm", "hardware"
            backends = {"fake": dict}

            @action(cap="cap.measure.voltage.v1")
            def measure(self):
                return 1.25

            @action(name="x-cap.example.pair.v1", output={"a": Field("number"), "b": Field("number")})
            def pair(self):
                return 3.0

            @action(name="x-cap.example.garbage.v1", output={"ok": Field("boolean")})
            def garbage(self):
                return {"ok": "yes", "extra": 1}

        server, client = support.serve(Meter(backend="fake"))
        self.addCleanup(close_server, server)
        receipt = client.command("cap.measure.voltage.v1", {})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["voltage"], 1.25)
        self.assertRegex(receipt["output"]["sampled_at"], r"^\d{4}-\d\d-\d\dT")
        refused = client.command("cap.measure.voltage.v1", {"channel": "ch1"})
        self.assertNotEqual(refused["status"], "completed")  # the method takes no channel
        pair = client.command("x-cap.example.pair.v1", {})
        self.assertEqual((pair["status"], code(pair)), ("failed", "MHS.CAPABILITY.OUTPUT_INVALID"))
        garbage = client.command("x-cap.example.garbage.v1", {})
        self.assertEqual((garbage["status"], code(garbage)), ("failed", "MHS.CAPABILITY.OUTPUT_INVALID"))

    def test_native_units_are_converted_both_ways(self) -> None:
        class Native:
            def __init__(self) -> None:
                self.kelvin = 300.0
                self.calls: list[float] = []

            def set_kelvin(self, value: float) -> None:
                self.calls.append(value)
                self.kelvin = value

        class Oven(Driver):
            device_id, device_kind, mode, risk = "oven", "thermal.zone", "hardware", "R1"
            backends = {"fake": Native}

            @read("setpoint", unit="Cel", native_unit="K")
            def get(self):
                return self.native.kelvin

            @write("setpoint", unit="Cel", native_unit="K",
                   limit=Limit(min=0, max=200, source="vendor_doc", ref="oven.pdf:1"))
            def put(self, value):
                self.native.set_kelvin(value)

        server, client = support.serve(Oven(backend="fake"))
        self.addCleanup(close_server, server)
        self.assertAlmostEqual(client.read()["state"]["setpoint"], 26.85)
        receipt = client.write({"setpoint": 100})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertAlmostEqual(server.devices[client.device_id].bridge.native.calls[0], 373.15)

    def test_driver_failed_and_cancellation_signals(self) -> None:
        class Device(Driver):
            device_id, device_kind, mode = "dev", "instrument", "hardware"
            backends = {"fake": dict}

            @action(name="x-cap.example.refuse.v1")
            def refuse(self):
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "not homed")

            @action(name="x-cap.example.loop.v1", long_running=True, max_duration_ms=10000, cancellable=True)
            def loop(self):
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    self.check_cancelled()
                    time.sleep(0.005)

        driver = Device(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        refused = client.command("x-cap.example.refuse.v1", {})
        self.assertEqual((refused["status"], code(refused)), ("failed", "MHS.DEVICE.PRECONDITION_UNMET"))
        started = client.command("x-cap.example.loop.v1", {}, deadline_ms=100)
        self.assertEqual(started["status"], "running", started)
        client.rpc("mhs.operations.cancel", {"session_id": client.session_id,
                                             "operation_id": started["operation_id"], "deadline_ms": 2000})
        deadline = time.monotonic() + 3
        state = None
        while time.monotonic() < deadline:
            state = client.operation(started["operation_id"]).get("status")
            if state not in ("accepted", "running"):
                break
            time.sleep(0.01)
        self.assertEqual(state, "cancelled")

    def test_a_driver_without_estop_reports_a_software_only_stop(self) -> None:
        class Sim(Driver):
            device_id, device_kind, mode = "sim", "instrument", "simulated"
            fidelity = dict(FAKE_FIDELITY, engine="analytic")
            backends = {"fake": dict}

            @read("level", unit="1")
            def level(self):
                return 0.5

            @action(name="x-cap.example.noop.v1")
            def noop(self):
                return None

        server, client = support.serve(Sim(backend="fake"))
        self.addCleanup(close_server, server)
        receipt = client.estop()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "software_only")
        status = client.rpc("mhs.safety.status", {"session_id": client.session_id, "device_id": client.device_id,
                                                  "deadline_ms": 2000})
        self.assertIsNone(status["estop"]["native"])


class EstopResolutionTests(unittest.TestCase):
    """The e-stop the runtime reports follows the resolved model (verifier probe_estop_override)."""

    def estop(self, driver: Driver) -> tuple[dict, support.Client]:
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        return client.estop(), client

    def test_an_undecorated_override_of_the_estop_method_is_software_only(self) -> None:
        class Overridden(support.Bath):
            async def stop(self):  # no @estop: the subclass definition wins, so no native stop
                self.native.actuations.append(("sub-stop",))

        class Removed(support.Bath):
            stop = None

        for cls in (Overridden, Removed):
            with self.subTest(driver=cls.__name__):
                self.assertIsNone(cls.driver_model().estop)
                driver = cls(backend="fake")
                self.assertIsNone(build_manifest(driver)["safety"]["estop"]["native"])
                receipt, client = self.estop(driver)
                self.assertEqual(receipt["status"], "completed", receipt)
                self.assertEqual(receipt["output"]["estop"], "software_only")
                self.assertTrue(receipt["output"]["latched"])
                self.assertFalse({("stop",), ("sub-stop",)} & set(driver.native.actuations))
                self.assertEqual(code(client.write({"setpoint": 30})), "MHS.SAFETY.ESTOP_ENGAGED")

    def test_a_redecorated_override_is_the_native_stop(self) -> None:
        class Redecorated(support.Bath):
            @estop(native="panic")
            def stop(self):
                self.native.actuations.append(("panic",))

        driver = Redecorated(backend="fake")
        self.assertEqual(build_manifest(driver)["safety"]["estop"]["native"], "panic")
        receipt, _client = self.estop(driver)
        self.assertEqual(receipt["output"]["estop"], "engaged", receipt)
        self.assertIn(("panic",), driver.native.actuations)
        self.assertNotIn(("stop",), driver.native.actuations)


class HardwareRuntimeTests(unittest.TestCase):
    def test_hardware_view_and_operator_only_reset(self) -> None:
        state_dir = support.temp_dir(self)
        tokens = {"agent-token": {"id": "agent", "kind": "agent"}, "op-token": {"id": "op", "kind": "operator"}}
        driver = support.Bath(backend="hardware", native=support.FakeBath())
        with self.assertRaises(PermissionError):
            build_server(driver)
        with self.assertRaises(PermissionError):
            build_server(driver, allow_hardware=True)
        server = build_server(driver, allow_hardware=True, state_dir=state_dir, auth_tokens=tokens,
                              armed=["mhs://localhost/lab/bath"])
        self.addCleanup(close_server, server)
        device = server.devices["mhs://localhost/lab/bath"]
        self.assertEqual(device.mode, "hardware")
        self.assertIsNone(device.fidelity)
        self.assertIsNone(device.models)
        agent = support.Client(server, token="agent-token")
        self.assertEqual(agent.command("cap.thermal.setpoint.v1", {"target_temperature": 30})["status"], "completed")
        agent.estop()
        refused = agent.reset()
        self.assertNotEqual(refused.get("result", {}).get("status"), "completed", refused)
        operator = support.Client(server, token="op-token", principal={"id": "op", "kind": "human"})
        accepted = operator.reset()
        self.assertEqual(accepted["result"]["status"], "completed", accepted)


if __name__ == "__main__":
    unittest.main()
