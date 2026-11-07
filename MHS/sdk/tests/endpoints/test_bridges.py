"""Unit tests for the MHS bridge families (stdlib only; optional deps skip)."""

from __future__ import annotations

import unittest
import warnings

from tests.endpoints import support  # noqa: F401 - ensures the SDK src path is on sys.path

from mhs import signals
from mhs.bridge import available_bridges
from mhs.bridge.base import (
    BridgeContext,
    ErrorMap,
    FieldMapping,
    MappingError,
    convert_unit,
    jsonable,
    make_mhs_error,
)
from mhs.bridge.python import PythonObjectBridge
from mhs.bridge.replay import ReplayBridge
from mhs.bridge.serial import FakeSerial, SerialBridge


def error_code(exc: BaseException) -> str | None:
    return getattr(exc, "code", None)


class MappingEngineTests(unittest.TestCase):
    def test_unit_conversion_is_dimension_checked(self) -> None:
        self.assertAlmostEqual(convert_unit(2.5, "uL", "mL"), 0.0025)
        self.assertAlmostEqual(convert_unit(1000, "ms", "s"), 1.0)
        self.assertAlmostEqual(convert_unit(180, "deg", "rad"), 3.141592653589793)
        self.assertEqual(convert_unit(25, "Cel", "K"), 298.15)
        self.assertEqual(convert_unit(0, "m", "m"), 0)
        # mhs.units: % is a ratio of 0.01 and compound codes are derived (FIT-08)
        self.assertEqual(convert_unit(50, "%", "1"), 0.5)
        self.assertEqual(convert_unit(1, "m/s", "mm/s"), 1000)
        with self.assertRaises(Exception):
            convert_unit(1, "mm", "s")

    def test_input_mapping_applies_from_const_enum_unit_scale_clamp(self) -> None:
        mapping = FieldMapping(
            {
                "ticks": {"from": "input.count", "required": True, "clamp": {"min": 0, "max": 10}},
                "speed": {"from": "input.speed_mm_s", "unit": ["mm", "m"]},
                "gate": {"from": "input.gate", "enum": {"main": 0, "divert": 1}},
                "mode": {"const": "auto"},
                "gain": {"default": 1, "scale": 2.0},
            },
            direction="input",
        )
        mapped = mapping.map({"count": 5, "speed_mm_s": 250, "gate": "divert"})
        self.assertEqual(mapped["ticks"], 5)
        # a clamp is a rejection, never a silent truncation (ADPT-024, plan 3.5)
        with self.assertRaises(Exception) as caught:
            mapping.map({"count": 50, "speed_mm_s": 250, "gate": "divert"})
        self.assertEqual(error_code(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertAlmostEqual(mapped["speed"], 0.25)
        self.assertEqual(mapped["gate"], 1)
        self.assertEqual(mapped["mode"], "auto")
        self.assertEqual(mapped["gain"], 2.0)

    def test_input_mapping_requires_declared_fields(self) -> None:
        mapping = FieldMapping({"ticks": {"from": "input.ticks", "required": True}}, direction="input")
        with self.assertRaises(MappingError):
            mapping.map({})

    def test_output_mapping_and_enum(self) -> None:
        mapping = FieldMapping(
            {"temperature_c": {"from": "temp", "scale": 0.5}, "state": {"from": "mode", "enum": {0: "idle"}}},
            direction="output",
        )
        self.assertEqual(mapping.map({"temp": 21, "mode": 0}), {"temperature_c": 10.5, "state": "idle"})

    def test_error_map_prefers_class_then_message_then_default(self) -> None:
        errors = ErrorMap({"ValueError": "MHS.SAFETY.ENVELOPE_VIOLATION", "RuntimeError:busy": "MHS.DEVICE.BUSY"})
        self.assertEqual(errors.translate(ValueError("nope"))[0], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(errors.translate(RuntimeError("device busy now"))[0], "MHS.DEVICE.BUSY")
        # plan 3.7: an unmapped native exception is SHIM_FAILED unless "*" says otherwise
        self.assertEqual(errors.translate(OSError("x"))[0], "MHS.ADAPTER.SHIM_FAILED")
        fallback = ErrorMap({"ValueError": "MHS.SAFETY.ENVELOPE_VIOLATION", "*": "MHS.DEVICE.FAULTED"})
        self.assertEqual(fallback.translate(OSError("x"))[0], "MHS.DEVICE.FAULTED")

    def test_jsonable_refuses_non_json_values(self) -> None:
        class Opaque:
            pass

        self.assertEqual(jsonable({"a": (1, 2), "b": None}), {"a": [1, 2], "b": None})
        with self.assertRaises(MappingError):
            jsonable({"bad": Opaque()})

    def test_make_mhs_error_carries_code_message_and_data(self) -> None:
        exc = make_mhs_error("MHS.SAFETY.INTERLOCK_OPEN", "door open", {"retryable": False})
        self.assertEqual(error_code(exc), "MHS.SAFETY.INTERLOCK_OPEN")
        self.assertEqual(getattr(exc, "data", {}).get("retryable"), False)


class PythonObjectBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        # THERMO_CONFIG uses the deprecated in-process grammar: it needs the marker.
        with self.assertWarns(DeprecationWarning):
            self.bridge = PythonObjectBridge(
                dict(support.THERMO_CONFIG, grammar="legacy"), device_id="mhs://localhost:7400/lab/thermo"
            )

    def tearDown(self) -> None:
        self.bridge.close()

    def test_capabilities_are_declared_and_resources_listed(self) -> None:
        ids = {item["capability_id"] for item in self.bridge.capabilities()}
        self.assertIn("cap.measure.temperature.v1", ids)
        self.assertEqual(self.bridge.resources()[0]["resource_id"], "thermo")

    def test_call_maps_arguments_and_result(self) -> None:
        result = self.bridge.call("cap.measure.temperature.v1", {"channel": 3}, BridgeContext())
        self.assertEqual(result["temperature_c"], 24)
        self.assertEqual(result["serial"], 1)

    def test_call_clamps_and_maps_inputs(self) -> None:
        result = self.bridge.call("cap.thermal.setpoint.v1", {"target_c": 27}, BridgeContext())
        self.assertEqual(result["temperature_c"], 27)

    def test_read_and_snapshot_restore(self) -> None:
        self.bridge.call("cap.thermal.setpoint.v1", {"target_c": 22}, BridgeContext())
        self.assertEqual(self.bridge.read("thermo")["temperature_c"], 22)
        snapshot = self.bridge.snapshot()
        self.bridge.call("cap.thermal.setpoint.v1", {"target_c": 32}, BridgeContext())
        self.bridge.restore(snapshot)
        self.assertEqual(self.bridge.read("thermo")["temperature_c"], 22)

    def test_undeclared_capability_is_refused(self) -> None:
        with self.assertRaises(Exception) as caught:
            self.bridge.call("cap.world.step.v1", {"ticks": 1}, BridgeContext())
        self.assertIn(error_code(caught.exception) or "", ("MHS.CAPABILITY.NOT_BOUND", "MHS.DEVICE.UNSUPPORTED"))

    def test_native_error_is_mapped(self) -> None:
        with self.assertRaises(Exception) as caught:
            self.bridge.call("cap.thermal.setpoint.v1", {"target_c": 1201}, BridgeContext())
        self.assertIn(error_code(caught.exception) or "", ("MHS.SAFETY.ENVELOPE_VIOLATION",))

    def test_close_is_idempotent_and_refuses_further_calls(self) -> None:
        self.bridge.close()
        self.bridge.close()
        with self.assertRaises(Exception):
            self.bridge.call("cap.measure.temperature.v1", {}, BridgeContext())


class SerialBridgeTests(unittest.TestCase):
    def test_bounded_transaction_with_injected_serial(self) -> None:
        bridge = SerialBridge(
            {
                "port": "/dev/fake",
                "timeout_s": 0.2,
                "capabilities": {
                    "cap.measure.voltage.v1": {
                        "resource": "psu",
                        "native": "serial:VOLT?",
                        "command": "MEAS:VOLT?",
                        "args": {},
                        "parse": {"kind": "float", "field": "voltage_v"},
                    }
                },
                "reads": {
                    "instrument": {
                        "command": "MEAS:VOLT?",
                        "parse": {"kind": "float", "field": "voltage_v"},
                    }
                },
            },
            serial_factory=lambda **kwargs: FakeSerial({"MEAS:VOLT?": "1.234\\n"}),
        )
        try:
            result = bridge.call("cap.measure.voltage.v1", {}, BridgeContext())
            self.assertAlmostEqual(result["voltage_v"], 1.234)
            self.assertEqual(bridge.read("instrument")["voltage_v"], 1.234)
            with self.assertRaises(Exception):
                bridge.write("instrument", {"voltage_v": 1})
        finally:
            bridge.close()

    def test_missing_response_is_a_bounded_unknown_outcome(self) -> None:
        bridge = SerialBridge(
            {
                "port": "/dev/fake",
                "timeout_s": 0.02,
                "capabilities": {
                    "cap.measure.voltage.v1": {
                        "resource": "psu",
                        "command": "MEAS:VOLT?",
                        "args": {},
                        "parse": {"kind": "float"},
                    }
                },
            },
            serial_factory=lambda **kwargs: FakeSerial(default=""),
        )
        try:
            with self.assertRaises(signals.OutcomeUnknown) as caught:
                bridge.call("cap.measure.voltage.v1", {}, BridgeContext())
            self.assertEqual(error_code(caught.exception), "MHS.OUTCOME.UNKNOWN")
            self.assertFalse(caught.exception.retryable)
        finally:
            bridge.close()


class LazyBridgeTests(unittest.TestCase):
    def test_available_bridges_reports_optional_dependencies(self) -> None:
        status = available_bridges()
        self.assertTrue(status["python-object"])
        self.assertTrue(status["replay"])
        self.assertIn("gymnasium", status)
        self.assertIn("mujoco", status)
        self.assertIn("serial", status)
        self.assertTrue(status["scpi"])

    def test_gymnasium_bridge_skips_cleanly_when_absent(self) -> None:
        try:
            from mhs.bridge.gymnasium import GymnasiumBridge
        except ImportError:  # pragma: no cover - import-safe module is required
            self.fail("gymnasium bridge module must be import-safe without gymnasium")
        if not GymnasiumBridge.available():
            self.skipTest("gymnasium is not installed")
        self.assertTrue(GymnasiumBridge.available())

    def test_mujoco_bridge_skips_cleanly_when_absent(self) -> None:
        from mhs.bridge.mujoco import MujocoBridge

        if not MujocoBridge.available():
            self.skipTest("mujoco is not installed")
        bridge = MujocoBridge(model_xml="<mujoco/>")
        self.assertIn("world", [item["resource_id"] for item in bridge.resources()])

    def test_serial_bridge_skips_cleanly_without_pyserial(self) -> None:
        from mhs.bridge.serial import SerialBridge as Bridge

        if not Bridge.available():
            self.skipTest("pyserial is not installed")
        self.assertTrue(Bridge.available())


class ReplayBridgeTests(unittest.TestCase):
    def _bridge(self) -> ReplayBridge:
        frames = [
            {"revision": 0, "state": {"arm": {"q": 0}}, "state_hash": "sha256:" + "1" * 64},
            {"revision": 1, "state": {"arm": {"q": 10}}, "state_hash": "sha256:" + "2" * 64},
            {"revision": 2, "state": {"arm": {"q": 20}}, "state_hash": "sha256:" + "3" * 64},
        ]
        return ReplayBridge(
            frames=frames,
            receipts=[{"receipt_id": "x", "evidence": {"seq": 1, "digest": "sha256:" + "4" * 64}}],
            head_digest="sha256:" + "4" * 64,
            primary_resource="arm",
            capabilities=[{"capability_id": "cap.motion.joint_position.v1", "resource": "arm"}],
        )

    def test_reads_current_frame_and_recording_metadata(self) -> None:
        bridge = self._bridge()
        try:
            self.assertEqual(bridge.read("arm"), {"q": 20})
            recording = bridge.read("recording")
            self.assertTrue(recording["read_only"])
            self.assertEqual(recording["revisions"], [0, 1, 2])
        finally:
            bridge.close()

    def test_restore_seeks_by_recorded_revision(self) -> None:
        bridge = self._bridge()
        try:
            bridge.restore({"revision": 1})
            self.assertEqual(bridge.read("arm"), {"q": 10})
            bridge.restore({"state_hash": "sha256:" + "1" * 64})
            self.assertEqual(bridge.read("arm"), {"q": 0})
        finally:
            bridge.close()

    def test_mutations_are_refused_read_only(self) -> None:
        bridge = self._bridge()
        try:
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.motion.joint_position.v1", {"joint_positions_deg": [0, 0]}, BridgeContext())
            self.assertEqual(error_code(caught.exception), "MHS.MODE.READ_ONLY")
            with self.assertRaises(Exception):
                bridge.write("arm", {"q": 1})
        finally:
            bridge.close()


if __name__ == "__main__":
    unittest.main()
