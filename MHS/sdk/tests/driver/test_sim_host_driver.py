"""GymnasiumDriver backends in an isolated simulator host: definition, the stock server and the gate (G6, G7).

A synthetic package (a copy of the tutorial with a gymnasium card, a small upstream world in its vendor clone and a
fake) runs its fake in a real child process; nothing here runs a simulator.
"""
from __future__ import annotations

import copy
import threading
import time
import unittest

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverDefinitionError, GymnasiumDriver, build_manifest
from mhs.testing import client_for
from tests.driver import gate_support as gs

STEP, RESET = "cap.world.step.v1", "cap.world.reset.v1"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"

UPSTREAM = (
    "class Link:\n"
    "    def __init__(self):\n"
    "        self.paused = True\n\n"
    "    def pause(self):\n"
    "        self.paused = True\n\n"
    "    def properties(self):\n"
    "        return self\n\n\n"
    "class World:\n"
    "    def __init__(self):\n"
    "        self.action_space = self.observation_space = None\n"
    "        self.link = Link()\n\n"
    "    def reset(self, seed=None, options=None):\n"
    "        return [0.0], {}\n\n"
    "    def step(self, action):\n"
    "        self.link.paused = False\n"
    "        return [0.0], 0.0, False, False, {}\n\n"
    "    def close(self):\n"
    "        pass\n")
FAKE = (
    "import time\n\n\n"
    "class Box:\n"
    "    def __init__(self, low, high):\n"
    "        self.low, self.high, self.shape, self.dtype = list(low), list(high), (len(low),), 'float64'\n\n\n"
    "class FakeLink:\n"
    "    def __init__(self, ignore_stop):\n"
    "        self.paused = True\n"
    "        self._ignore_stop = ignore_stop\n\n"
    "    def pause(self):\n"
    "        if not self._ignore_stop:\n"
    "            self.paused = True\n\n"
    "    def properties(self):\n"
    "        return self\n\n\n"
    "class FakeWorld:\n"
    "    def __init__(self, ignore_stop=False, step_delay=0.0, unpause_at_end=False):\n"
    "        self.action_space = Box([-1.0, -1.0], [1.0, 1.0])\n"
    "        self.observation_space = Box([-100.0], [100.0])\n"
    "        self.link = FakeLink(ignore_stop)\n"
    "        self._delay, self._unpause_at_end, self._x = step_delay, unpause_at_end, 0.0\n\n"
    "    def reset(self, seed=None, options=None):\n"
    "        self._x = 0.0\n"
    "        return [self._x], {}\n\n"
    "    def step(self, action):\n"
    "        self.link.paused = False\n"
    "        if self._delay:\n"
    "            time.sleep(self._delay)\n"
    "        self._x += float(action[0])\n"
    "        self.link.paused = not self._unpause_at_end\n"
    "        return [self._x], -abs(self._x), False, False, {}\n\n"
    "    def close(self):\n"
    "        pass\n")
HOST = {"mode": "isolated_process_v1", "reset_kwargs": ["seed", "options"], "start_timeout_s": 20.0,
        "step_timeout_s": 5.0, "reset_timeout_s": 5.0, "close_timeout_s": 5.0, "stop": "link.pause",
        "readback": {"path": "link.properties", "field": "paused", "equals": True}, "stop_timeout_s": 2.0,
        "settle_timeout_s": 5.0}


def driver_source(host=None, extra=""):
    return ("from mhs.driver import GymnasiumDriver\n\n"
            f"HOST = {repr(host or HOST)}\n\n\n"
            "class Hosted(GymnasiumDriver):\n"
            "    device_id = 'hosted'\n"
            "    env_id = 'Hosted-v0'\n"
            "    native = 'thermo.hosted:World'\n"
            "    backends = {'fake': '.fake:FakeWorld'}\n"
            "    process_by_backend = {'fake': HOST}\n"
            "    safe_state = 'the world is paused, confirmed by its paused read-back'\n" + extra)


def package(test, host=None, extra=""):
    directory = gs.copy_tutorial(test)
    (directory / "vendor" / "thermo" / "hosted.py").write_text(UPSTREAM, encoding="utf-8")
    (directory / "fake.py").write_text(FAKE, encoding="utf-8")
    (directory / "driver.py").write_text(driver_source(host, extra), encoding="utf-8")
    gs.edit_json(directory, "task.json", family="gymnasium", helper="GymnasiumDriver", decision="family-config",
                 safety={"expected_mode": "simulated", "risk_floor": "R0", "limit_hints": []},
                 entry_symbols=[{"symbol": "thermo.hosted:World", "file": "thermo/hosted.py", "line": 12,
                                 "confidence": "override"}])
    gs.edit_json(directory, "driver.lock.json", backends={"fake": ".fake:FakeWorld"})
    gs.regenerate(directory)
    return directory


def serve(test, directory, **options):
    server = load(directory, backend="fake", options=options or None)
    test.addCleanup(close_server, server)
    client = client_for(server)
    device = client.hello()["devices"][0]["device_id"]
    session = client.open_session(device_ids=[device])["session_id"]
    return client, {"device_id": device, "session_id": session}


class HostedGateTests(unittest.TestCase):
    def test_a_hosted_package_passes_g1_to_g8_with_its_fake_in_a_child_process(self):
        directory = package(self)
        report = gs.check(directory)
        self.assertEqual(report["failed"], [], gs.findings(report))
        self.assertEqual([code for code in gs.findings(report, "G7", severity=None)], [])
        self.assertNotIn("G6.HOST_FAIL_OPEN", gs.findings(report, "G6"))

    def test_a_package_that_skips_the_readback_fails_host_fail_open(self):
        # A driver that stops but never reads back (here by replacing the bridge's hosted e-stop) confirms a stop the
        # simulator may not have made: only HOST_FAIL_OPEN catches it (the stop itself is still called).
        bypass = ("\n    def make_bridge(self, native):\n"
                  "        bridge = super().make_bridge(native)\n"
                  "        bridge._estop_hosted = lambda: (bridge._env.stop(), {})[1]\n"
                  "        return bridge\n")
        report = gs.check(package(self, extra=bypass), gates=["G6"])
        self.assertEqual(report["failed"], ["G6"])
        self.assertEqual(gs.findings(report, "G6"), ["G6.HOST_FAIL_OPEN"])

    def test_g7_checks_the_declared_stop_and_readback_against_the_clone(self):
        for stop, readback, culprit in (("link.halt", "link.properties", "halt"),
                                        ("lever.pause", "link.properties", "lever"),
                                        ("link.pause", "link.status_report", "status_report")):
            directory = package(self, host={**HOST, "stop": stop,
                                            "readback": {**HOST["readback"], "path": readback}})
            report = gs.check(directory, gates=["G7"])
            self.assertEqual(report["failed"], ["G7"], (stop, readback))
            messages = [finding["message"] for gate in report["gates"] if gate["id"] == "G7"
                        for finding in gate["findings"] if finding["code"] == "G7.HOST_PATH"]
            self.assertTrue(any(repr(culprit) in message for message in messages), messages)


class HostedServerTests(unittest.TestCase):
    def test_the_stock_server_confirms_the_stop_through_the_host(self):
        client, ids = serve(self, package(self))
        self.assertEqual(client.invoke(STEP, {"ticks": 2, "action": {"values": [0.5, 0.0]}}, **ids)["status"],
                         "completed")
        stop = client.estop("test", **ids)
        self.assertEqual((stop["status"], stop["output"]["estop"], stop["output"]["safe_state_achieved"]),
                         ("completed", "engaged", True), stop)
        latched = client.invoke(STEP, {"ticks": 1, "action": {"values": [0.5, 0.0]}}, **ids)
        self.assertEqual(latched["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(client.reset(**ids)["status"], "completed")
        self.assertEqual(client.invoke(STEP, {"ticks": 1, "action": {"values": [0.5, 0.0]}}, **ids)["status"],
                         "completed")

    def test_a_stop_that_does_not_take_effect_is_unreached_latched_and_retried(self):
        client, ids = serve(self, package(self), ignore_stop=True, unpause_at_end=True)
        client.invoke(STEP, {"ticks": 1, "action": {"values": [0.5, 0.0]}}, **ids)
        stop = client.estop("ignored", **ids)
        self.assertEqual((stop["status"], stop["error"]["mhs_code"]), ("failed", UNREACHED), stop)
        self.assertTrue(stop["error"]["details"]["retrying"])
        self.assertEqual((stop["output"]["latched"], stop["output"]["safe_state_achieved"]), (True, False))
        status = client.safety_status(device_id=ids["device_id"])
        self.assertFalse(status["estop"]["confirmed"])

    def test_an_estop_during_a_step_is_confirmed_by_the_stop_sent_after_it(self):
        client, ids = serve(self, package(self), step_delay=0.4, unpause_at_end=True)
        client.invoke(RESET, {}, **ids)
        outcome = {}
        worker = threading.Thread(target=lambda: outcome.update(receipt=client.invoke(
            STEP, {"ticks": 1, "action": {"values": [0.1, 0.0]}}, **ids)), daemon=True)
        worker.start()
        time.sleep(0.1)
        stop = client.estop("during a step", **ids)
        worker.join(5.0)
        self.assertEqual(stop["status"], "completed", stop)
        self.assertTrue(stop["output"]["safe_state_achieved"])

    def test_manifest_and_projection(self):
        directory = package(self)
        driver = load_driver(directory, backend="fake")
        self.addCleanup(driver.close)
        manifest = build_manifest(driver)
        self.assertEqual(manifest["safety"]["estop"]["native"], "link.pause")
        self.assertIn("isolated_process_v1", " ".join(manifest["profile"]["operating_notes"]))
        step = next(item for item in manifest["capabilities"] if item["capability_id"] == STEP)
        self.assertEqual(step["limits"]["action.values"]["max"], [1.0, 1.0])
        host = driver.inner.host_status()
        self.assertEqual((host["state"], host["entry"]), ("ready", ".fake:FakeWorld"))


class DefinitionTests(unittest.TestCase):
    def build(self, **attributes):
        namespace = {"device_id": "hosted-definition", "backends": {"fake": ".fake:FakeWorld"},
                     "process_by_backend": {"fake": copy.deepcopy(HOST)}, **attributes}
        cls = type("Definition", (GymnasiumDriver,), namespace)
        return cls(backend="fake")

    def test_refused_declarations(self):
        cases = [
            {"backends": {"fake": lambda: None}},                              # not a package entry the host imports
            {"process_by_backend": {"hardware": copy.deepcopy(HOST)}},
            {"process_by_backend": {"fake": {**HOST, "stop": "link.pause()"}}},
            {"process_by_backend": {"fake": {**HOST, "mode": "subprocess"}}},
            {"async_by_backend": {"fake": {"mode": "asyncio_owned_loop_v1", "step": "sync", "reset": "sync",
                                           "reset_kwargs": [], "step_timeout_s": 1, "reset_timeout_s": 1,
                                           "close_timeout_s": 1}}},
        ]
        for attributes in cases:
            with self.assertRaises(DriverDefinitionError, msg=attributes):
                self.build(**attributes)

    def test_the_class_declaration_is_checked_without_an_instance(self):
        # Projection checks and the manifest read the declaration from the class; a backend the host cannot import is
        # refused there, before any instance or process exists.
        cls = type("Callable", (GymnasiumDriver,), {"device_id": "hosted-callable", "backends": {"fake": lambda: None},
                                                     "process_by_backend": {"fake": copy.deepcopy(HOST)}})
        with self.assertRaisesRegex(DriverDefinitionError, "package-relative"):
            cls._process_configs()


if __name__ == "__main__":
    unittest.main()
