"""QCoDeS-shaped native objects through the real retained bridge and stock server."""
from __future__ import annotations

import copy
import threading
import types
import unittest

from mhs.driver import QcodesDriver, Field, Action, DriverDefinitionError, build_manifest, close_server
from tests.driver.support import serve

FIDELITY = {"engine": "controlled Parameter double", "fidelity_level": "F0",
            "determinism": {"kind": "none", "seed_control": "none"}, "timestep_ms": 0,
            "realtime_factor": 0, "clock": "lockstep", "reset": "partial", "snapshot_restore": False,
            "gaps": ["No VISA, instrument, RF output or upstream import"]}


class Parameter:
    """A whole QCoDeS set can contain several native steps before returning None."""
    def __init__(self):
        self.value = 1.
        self.cache = types.SimpleNamespace(value=-100.)
        self.gets, self.steps = 0, []
        self.entered, self.release = threading.Event(), threading.Event()
        self.release.set()

    def get(self):
        self.gets += 1
        return self.value

    def set(self, value):
        self.steps.append(value / 2)
        self.value = value / 2
        self.entered.set()
        if not self.release.wait(3):
            raise RuntimeError("test release missing")
        self.steps.append(value)
        self.value = value


class Native:
    def __init__(self):
        self.channel = types.SimpleNamespace(frequency=Parameter())
        self.off_count = 0

    def off(self):
        self.off_count += 1
        self.channel.frequency.value = 0.


class Fixture(QcodesDriver):
    device_id, device_kind, mode, risk = "qcodes-test", "world.sim", "simulated", "R0"
    fidelity = FIDELITY
    native = "tests.driver.test_qcodes_family:Native"
    parameters = {"frequency": Field("number", unit="Hz", writable=True)}
    parameter_bindings = {"frequency": {"parameter": "channel.frequency", "get": True, "set": True,
                                       "timeout_ms": 40, "source_ref": "native.py:1"}}
    safe_state = "Native output off after all setters have settled"
    safety_bindings = {"estop": {"native": "off", "timeout_ms": 40},
                       "safe_state": {"native": "off", "timeout_ms": 40},
                       "reset": {"native": "off", "timeout_ms": 40}}


class QcodesFamilyTests(unittest.TestCase):
    def attach(self, cls=Fixture):
        raw = Native()
        driver = cls(native=raw)
        server, client = serve(driver)
        self.addCleanup(close_server, server)
        self.addCleanup(raw.channel.frequency.release.set)
        return raw, driver, client

    def test_definition_and_constructor_have_zero_native_calls(self):
        calls = []
        class Lazy(Fixture):
            backends = {"fake": lambda: calls.append("factory")}
        Lazy.driver_model()
        build_manifest(Lazy)
        driver = Lazy(backend="fake")
        self.assertEqual(calls, [])
        driver.close()
        self.assertEqual(calls, [])

    def test_nested_get_is_measurement_and_set_waits_whole_ramp(self):
        raw, driver, client = self.attach()
        self.assertEqual(client.read()["state"]["frequency"], 1.)
        self.assertGreater(raw.channel.frequency.gets, 0)
        self.assertEqual(raw.channel.frequency.cache.value, -100.)
        self.assertEqual(client.write({"frequency": 8.})["status"], "completed")
        self.assertEqual(raw.channel.frequency.steps, [4., 8.])
        self.assertEqual(client.read()["state"]["frequency"], 8.)

    def test_timeout_retains_late_step_and_refuses_stop_reset_and_new_write(self):
        raw, driver, client = self.attach()
        raw.channel.frequency.release.clear()
        result = client.write({"frequency": 8.})
        self.assertEqual(result["status"], "unknown", result)
        self.assertTrue(raw.channel.frequency.entered.is_set())
        stopped = client.estop()
        self.assertFalse(stopped["output"]["safe_state_achieved"], stopped)
        self.assertNotEqual(client.reset().get("result", {}).get("status"), "completed")
        self.assertNotEqual(client.write({"frequency": 9.})["status"], "completed")
        self.assertEqual(raw.channel.frequency.steps, [4.])
        raw.channel.frequency.release.set()
        with driver.inner._activity:
            self.assertTrue(driver.inner._activity.wait_for(lambda: not driver.inner._executions, 2))
        self.assertEqual(raw.channel.frequency.value, 8.)
        self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
        self.assertTrue(client.estop()["output"]["safe_state_achieved"])
        self.assertEqual(client.reset()["result"]["status"], "completed")
        self.assertEqual(client.write({"frequency": 10.})["status"], "completed")

    def test_config_copied_before_first_native_open_and_model_not_aliased(self):
        config = copy.deepcopy(Fixture.parameter_bindings)
        class Owned(Fixture):
            parameter_bindings = config
            parameters = copy.deepcopy(Fixture.parameters)
        raw = Native()
        driver = Owned(native=raw)
        config["frequency"]["parameter"] = "cache"
        Owned.parameters["frequency"].unit = "V"
        server, client = serve(driver)
        self.addCleanup(close_server, server)
        self.assertEqual(client.read()["state"]["frequency"], 1.)
        self.assertEqual(driver._model.param("frequency").field.unit, "Hz")
        first, second = Fixture.driver_model(), Fixture.driver_model()
        first.param("frequency").field.unit = "V"
        self.assertEqual(second.param("frequency").field.unit, "Hz")
        self.assertEqual(Fixture.parameters["frequency"].unit, "Hz")

    def test_backend_map_and_nested_options_are_owned_before_open(self):
        calls=[]
        def original(**options):
            calls.append(options)
            return Native()
        config={"fake":original}
        class Lazy(Fixture):
            backends=config
        options={"nested":{"value":1}}
        driver=Lazy(backend="fake",options=options)
        config["fake"]=lambda **options: self.fail("mutated backend was called")
        options["nested"]["value"]=2
        driver.open();self.addCleanup(driver.close)
        self.assertEqual(calls,[{"nested":{"value":1}}])

    def test_bad_configs_fail_before_backend_factory(self):
        changes = [{"parameter": "channel.__dict__"}, {"parameter": "channel[0]"},
                   {"parameter": ".frequency"}, {"get": False}, {"get": 1}, {"set": False},
                   {"timeout_ms": True}, {"timeout_ms": 0}, {"timeout_ms": 60001},
                   {"source_ref": "../bad.py:1"}, {"source_ref": "bad.py:1-999"},
                   {"cache": True}, {"factory_ref": "/tmp/native.py:1"}]
        for change in changes:
            with self.subTest(change=change):
                entries = copy.deepcopy(Fixture.parameter_bindings)
                entries["frequency"].update(change)
                calls = []
                class Bad(Fixture):
                    parameter_bindings = entries
                    backends = {"fake": lambda: calls.append("called")}
                with self.assertRaises(DriverDefinitionError):
                    Bad(backend="fake")
                self.assertEqual(calls, [])

    def test_conflicting_explicit_map_is_not_a_silent_override(self):
        class Bad(Fixture):
            reads = {"frequency": "channel.frequency.cache"}
        with self.assertRaisesRegex(DriverDefinitionError, "overlap"):
            Bad.driver_model()

    def test_duplicate_selector_and_empty_or_oversized_maps_are_refused(self):
        for config in ({}, {str(i): {} for i in range(129)}):
            class Bad(Fixture):
                parameter_bindings = config
            with self.assertRaises(DriverDefinitionError):
                Bad.driver_model()
        class Alias(Fixture):
            parameters = {**Fixture.parameters, "alias": Field("number", writable=True)}
            parameter_bindings = {**Fixture.parameter_bindings, "alias": Fixture.parameter_bindings["frequency"]}
        with self.assertRaisesRegex(DriverDefinitionError, "duplicate"):
            Alias.driver_model()

    def test_missing_native_method_never_substitutes_cache(self):
        raw, driver, client = self.attach()
        raw.channel.frequency.get = None
        result = client.read()
        self.assertNotIn("frequency", result["state"])
        with self.assertRaises(Exception):
            driver.inner._resolve("channel.frequency.get")
        self.assertEqual(raw.channel.frequency.gets, 0)
        self.assertEqual(raw.channel.frequency.steps, [])


if __name__ == "__main__":
    unittest.main()
