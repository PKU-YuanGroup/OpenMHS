"""Unit tests for the in-process harness and the input synthesis (CONF-01, CONF-08, CONF-09)."""

from __future__ import annotations

import threading
import unittest

from mhs.conformance.inprocess import Harness, Loopback, run_suite_inprocess
from mhs.conformance.synth import (
    Fixtures,
    Unsynthesizable,
    alternate_input,
    bindings_for,
    envelope_probes,
    valid_input,
)
from mhs.errors import MHSError

from tests.conformance import support


def _manifest(server, device_id):
    return server.devices[device_id].manifest()


def _binding(manifest, capability_id):
    return next(item for item in bindings_for(manifest) if item.capability_id == capability_id)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.server, self.backend = support.heater_server(interlock=True)
        self.harness = Harness(self.server)
        self.bridge = self.server.devices[support.HEATER_ID].bridge

    def tearDown(self):
        self.harness.restore()

    def test_calls_are_recorded(self):
        self.bridge.call("cap.thermal.setpoint.v1", {"target_temperature": 30})
        self.bridge.read("heater")
        self.assertEqual([item.method for item in self.harness.records], ["call", "read"])
        self.assertEqual(len(self.harness.actuations(support.HEATER_ID)), 1)

    def test_interlocks_can_be_forced(self):
        self.assertEqual(self.bridge.interlocks()[0]["state"], "closed")
        with self.harness.force_interlocks(support.HEATER_ID, "unknown"):
            self.assertEqual(self.bridge.interlocks()[0]["state"], "unknown")
        self.assertEqual(self.bridge.interlocks()[0]["state"], "closed")

    def test_delay_ends_cancelled_on_request(self):
        event = threading.Event()
        ctx = type("Ctx", (), {"cancel_event": event, "cancelled": lambda self: event.is_set()})()
        event.set()
        with self.harness.delay_calls(support.HEATER_ID, "cap.thermal.setpoint.v1", 5.0):
            result = self.bridge.call("cap.thermal.setpoint.v1", {"target_temperature": 30}, ctx)
        self.assertEqual(result.get("status"), "cancelled")
        self.assertEqual(self.backend.actuations(), [])

    def test_dropped_response_is_an_unknown_outcome_after_the_effect(self):
        with self.harness.drop_responses(support.HEATER_ID, "cap.thermal.setpoint.v1"):
            with self.assertRaises(MHSError) as raised:
                self.bridge.call("cap.thermal.setpoint.v1", {"target_temperature": 30})
        self.assertEqual(raised.exception.code, "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(self.backend.actuations(), [("set_setpoint", 30.0)])

    def test_restore_removes_the_wrappers(self):
        self.harness.restore()
        self.bridge.call("cap.thermal.setpoint.v1", {"target_temperature": 30})
        self.assertEqual(self.harness.records, [])

    def test_loopback_round_trip(self):
        transport = Loopback(self.server)
        response = transport.request({"jsonrpc": "2.0", "id": 1, "method": "mhs.hello", "params": {}})
        self.assertIn("result", response)
        self.assertEqual(transport.methods, ["mhs.hello"])


class HardwareBlockTests(unittest.TestCase):
    """CON-031: without allow_actuation the harness refuses write/invoke calls on hardware at the bridge."""

    def test_hardware_calls_are_blocked_and_recorded(self):
        server, backend = support.hardware_heater()
        harness = Harness(server)
        bridge = server.devices[support.HEATER_ID].bridge
        try:
            harness.current_test = "SAFE-014"
            with self.assertRaises(MHSError) as raised:
                bridge.call("cap.thermal.setpoint.v1", {"target_temperature": 30})
            self.assertEqual(raised.exception.code, "MHS.AUTH.HARDWARE_DISABLED")
            bridge.read("heater")
        finally:
            harness.restore()
        self.assertEqual(backend.actuations(), [])
        record = harness.actuations(support.HEATER_ID)[0]
        self.assertEqual((record.faulted, record.test_id, record.ok), ("blocked", "SAFE-014", False))
        self.assertTrue(harness.blocks(support.HEATER_ID))

    def test_allow_actuation_lets_calls_through(self):
        server, backend = support.hardware_heater()
        harness = Harness(server, allow_actuation=True)
        try:
            server.devices[support.HEATER_ID].bridge.call("cap.thermal.setpoint.v1", {"target_temperature": 30})
        finally:
            harness.restore()
        self.assertEqual(backend.actuations(), [("set_setpoint", 30.0)])
        self.assertFalse(harness.blocks(support.HEATER_ID))

    def test_read_capabilities_are_not_blocked(self):
        server, _backend = support.hardware_heater()
        harness = Harness(server)
        try:
            harness.gate([support.HEATER_ID], allow_actuation=False,
                         read_capabilities={support.HEATER_ID: ["cap.measure.temperature.v1"]})
            result = server.devices[support.HEATER_ID].bridge.call("cap.measure.temperature.v1", {})
        finally:
            harness.restore()
        self.assertIn("temperature", result)

    def test_simulated_devices_are_never_blocked(self):
        server, backend = support.heater_server()
        harness = Harness(server)
        try:
            server.devices[support.HEATER_ID].bridge.call("cap.thermal.setpoint.v1", {"target_temperature": 30})
        finally:
            harness.restore()
        self.assertEqual(backend.actuations(), [("set_setpoint", 30.0)])


class SynthesisTests(unittest.TestCase):
    def setUp(self):
        server, _backend = support.heater_server()
        self.binding = _binding(_manifest(server, support.HEATER_ID), "cap.thermal.setpoint.v1")

    def test_effective_limits_are_resolved_like_the_runtime(self):
        bounds = {bound.path: (bound.min, bound.max) for bound in self.binding.bounds}
        self.assertEqual(bounds["target_temperature"], (0, 80))
        self.assertEqual(self.binding.verb, "write")

    def test_fixture_then_class_example_then_synthesis(self):
        fixtures = Fixtures({"cap.thermal.setpoint.v1": {"valid": {"target_temperature": 12}}})
        self.assertEqual(valid_input(self.binding, fixtures), ({"target_temperature": 12}, "fixture"))
        payload, source = valid_input(self.binding)
        self.assertEqual((payload, source), ({"target_temperature": 37}, "class example"))

    def test_alternate_is_valid_and_distinct(self):
        alternate = alternate_input(self.binding, {"target_temperature": 80})
        self.assertIsNotNone(alternate)
        self.assertNotEqual(alternate, {"target_temperature": 80})
        self.assertTrue(self.binding.valid(alternate))

    def test_envelope_probes_stay_inside_the_schema_when_possible(self):
        probes = envelope_probes(self.binding, {"target_temperature": 37})
        by_kind = {probe.kind: probe for probe in probes}
        self.assertEqual(by_kind["max"].value, 81.0)
        self.assertTrue(by_kind["max"].in_schema)
        self.assertFalse(by_kind["min"].in_schema)

    def test_pattern_strings_are_never_invented(self):
        server, _bridge = support.pattern_server()
        binding = _binding(_manifest(server, support.WORLD_ID), "cap.world.step.v1")
        with self.assertRaises(Unsynthesizable) as raised:
            valid_input(binding)
        self.assertIn("fixture", str(raised.exception))

    def test_no_distinct_alternate_returns_none(self):
        server, _bridge = support.class_faithful_server(
            "cap.world.step.v1",
            {"type": "object", "required": ["mode"], "properties": {"mode": {"type": "string", "enum": ["auto"]}},
             "additionalProperties": False})
        binding = _binding(_manifest(server, support.WORLD_ID), "cap.world.step.v1")
        payload, _source = valid_input(binding)
        self.assertEqual(payload, {"mode": "auto"})
        self.assertIsNone(alternate_input(binding, payload))

    def test_class_default_bounds_are_probed(self):
        """07b: the runtime enforces class-default limits (plan 3.5), so SAFE-014 probes them."""

        server = support.thermostat_server(variant="plain")
        binding = _binding(_manifest(server, support.THERMO_ID), "cap.thermal.setpoint.v1")
        self.assertTrue(binding.bounds)
        probes = envelope_probes(binding, {"target_temperature": 37})
        self.assertEqual(sorted((probe.kind, probe.value) for probe in probes), [("max", 301.0), ("min", -51.0)])


class UninstrumentedBridgeTests(unittest.TestCase):
    """A bridge method the recorder cannot shadow makes its zero-call evidence fail closed."""

    def test_sealed_methods_are_reported(self):
        server, _backend = support.heater_server(bridge_class=support.SealedHeaterBridge)
        harness = Harness(server)
        try:
            self.assertIn(f"{support.HEATER_ID}:call", harness.uninstrumented)
            self.assertEqual(harness.uninstrumented_for(support.HEATER_ID), ["call", "write", "restore"])
            self.assertNotIn(f"{support.HEATER_ID}:interlocks", harness.uninstrumented)
        finally:
            harness.restore()

    def test_con031_is_not_proven_for_an_uninstrumented_hardware_bridge(self):
        backends = []

        def factory():
            server, backend = support.hardware_heater(bridge_class=support.SealedHeaterBridge,
                                                      capability_limits={"target_temperature": {"min": 10,
                                                                                                "max": 60}})
            backends.append(backend)
            return server

        report = run_suite_inprocess(factory, profile="MHS-Device", level="CL3")
        case = support.entry(report, "CON-031")
        self.assertNotEqual(case["status"], "pass", case)
        self.assertIn("call", case["detail"])
        self.assertTrue(case["required"])
        # The harness cannot block an uninstrumented bridge, so the negative tests are not sent either.
        self.assertEqual([call for backend in backends for call in backend.actuations()], [])
        for test_id in ("OP-005", "PROTO-027", "SAFE-014"):
            self.assertEqual(support.entry(report, test_id)["status"], "skip", support.entry(report, test_id))

    def test_zero_call_checks_fail_closed(self):
        report = run_suite_inprocess(
            lambda: support.heater_server(bridge_class=support.SealedHeaterBridge, interlock=True)[0],
            profile="MHS-Sim", level="CL3")
        for test_id in ("SAFE-011", "SAFE-012", "SAFE-014"):
            with self.subTest(test=test_id):
                case = support.entry(report, test_id)
                self.assertEqual(case["status"], "fail", case)
                self.assertIn("not instrumented", case["detail"])


if __name__ == "__main__":
    unittest.main()
