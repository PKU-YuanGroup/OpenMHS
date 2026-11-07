"""Pins from the Core and the Driver Profile to the behaviour of the reference implementation (WP-09 (6)).

Each test names the ``CORE-nnn`` / ``DRV-nnn`` rule it checks and exercises the SDK, so that a change of behaviour
that the specification states must change the specification (or the other way round).  They use the tutorial
thermostat driver (``MHS/sdk/examples/thermostat``) and the reference conveyor; no network beyond loopback.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import warnings
from pathlib import Path

from mhs import canonical
from mhs.adapter import LoadError, load, load_driver
from mhs.reference import build_endpoint, build_server
from mhs.testing import client_for

warnings.filterwarnings("ignore", category=ResourceWarning)
ROOT = Path(__file__).resolve().parents[4]
SPEC = ROOT / "MHS" / "spec"
THERMOSTAT = ROOT / "MHS" / "sdk" / "examples" / "thermostat"
CORE = (SPEC / "core.md").read_text(encoding="utf-8")


def thermostat(**options):
    options.setdefault("log_ready", False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load(str(THERMOSTAT), backend="fake", **options)


def conveyor():
    """The reference conveyor with the test hooks (a protocol fixture: it runs in compatibility mode and warns)."""

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return build_server(build_endpoint("conveyor", endpoint_id="mhs://localhost:7400", test_profile=True),
                            log_ready=False)


class Session:
    """A client, a device and a session on one in-process server."""

    def __init__(self, server, device_index: int = 0, capabilities=None):
        self.server = server
        self.client = client_for(server)
        self.device = self.client.hello()["devices"][device_index]["device_id"]
        self.session = self.client.open_session(device_ids=[self.device], capabilities=capabilities)["session_id"]

    def invoke(self, capability, payload, **options):
        return self.client.invoke(capability, payload, device_id=self.device, session_id=self.session, **options)

    def rpc(self, method, **params):
        response = self.server.handle({"jsonrpc": "2.0", "id": canonical.ulid(), "method": method, "params": params})
        return response.to_dict() if hasattr(response, "to_dict") else response


class PrimitiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = thermostat()
        self.addCleanup(self.server.close)
        self.s = Session(self.server)

    def test_core_021_a_read_never_advances_the_revision(self) -> None:
        first = self.s.client.read("main", device_id=self.s.device, session_id=self.s.session)
        second = self.s.client.read("main", device_id=self.s.device, session_id=self.s.session)
        self.assertEqual((first["revision"], second["revision"]), (0, 0))

    def test_core_022_a_write_is_a_configure_command(self) -> None:
        receipt = self.s.rpc("mhs.resource.write", session_id=self.s.session, device_id=self.s.device,
                             resource_id="main", patch={"setpoint": 42}, command_id=canonical.ulid(),
                             deadline_ms=5000)["result"]
        self.assertEqual(receipt["capability_id"], "cap.device.configure.v1")
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["applied"], {"setpoint": 42})
        self.assertNotIn("receipt", receipt)                                  # CORE-093: bare receipt
        self.assertEqual(receipt["state_revision_after"], receipt["state_revision_before"] + 1)

    def test_core_022_unknown_and_read_only_keys_are_refused_with_their_own_codes(self) -> None:
        unknown = self.s.invoke("cap.device.configure.v1", {"colour": 1})
        readonly = self.s.invoke("cap.device.configure.v1", {"temperature": 30.0})
        self.assertEqual(unknown["error"]["mhs_code"], "MHS.RESOURCE.FIELD_UNKNOWN")
        self.assertEqual(readonly["error"]["mhs_code"], "MHS.RESOURCE.NOT_WRITABLE")
        self.assertEqual(readonly["state_revision_after"], readonly["state_revision_before"])

    def test_core_023_resource_not_bound_is_a_rejected_receipt(self) -> None:
        receipt = self.s.invoke("cap.thermal.setpoint.v1", {"target_temperature": 30}, resource="nope")
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.NOT_BOUND")


class LimitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = thermostat()
        self.addCleanup(self.server.close)
        self.s = Session(self.server)

    def test_core_044_an_out_of_range_value_is_a_safety_refusal_with_details(self) -> None:
        receipt = self.s.invoke("cap.thermal.setpoint.v1", {"target_temperature": 400})
        self.assertEqual(receipt["status"], "rejected")
        error = receipt["error"]
        self.assertEqual(error["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")      # not INPUT_INVALID (CORE-045)
        for key in ("path", "kind", "bound", "value", "unit", "source"):
            self.assertIn(key, error["details"])
        self.assertEqual((error["details"]["kind"], error["details"]["bound"], error["details"]["value"]),
                         ("max", 80, 400))
        self.assertTrue(error["details"]["violations"])

    def test_core_044_every_array_element_is_checked(self) -> None:
        ok = self.s.invoke("cap.device.configure.v1", {"zone_trim": [5, -3]})
        bad = self.s.invoke("cap.device.configure.v1", {"zone_trim": [0, 4]})
        self.assertEqual(ok["status"], "completed")
        self.assertEqual(bad["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual((bad["error"]["details"]["path"], bad["error"]["details"]["element_name"]),
                         ("zone_trim[1]", "back"))

    def test_core_046_operator_required_is_refused_until_the_overlay_fills_it(self) -> None:
        refused = self.s.invoke("cap.device.configure.v1", {"fan_speed": 100})
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertIn("fan_speed", json.dumps(refused["error"]["details"]))
        overlay = {"openmhs": "0.9", "devices": {"mhs://localhost/tutorial-thermostat": {
            "fan_speed": {"min": 0, "max": 1200, "unit": "/min", "source": "operator", "reason": "test"}}}}
        server = thermostat(site_limits=overlay)
        self.addCleanup(server.close)
        s = Session(server)
        self.assertEqual(s.invoke("cap.device.configure.v1", {"fan_speed": 100})["status"], "completed")
        self.assertEqual(s.invoke("cap.device.configure.v1", {"fan_speed": 5000})["error"]["mhs_code"],
                         "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_core_042_an_overlay_cannot_widen(self) -> None:
        widening = {"openmhs": "0.9", "devices": {"mhs://localhost/tutorial-thermostat": {
            "setpoint": {"max": 500, "unit": "Cel", "source": "operator", "reason": "widen"}}}}
        with self.assertRaises(Exception) as caught:
            thermostat(site_limits=widening)
        self.assertIn("overlay", str(caught.exception).lower())

    def test_core_031_the_reference_file_shows_the_effective_limits(self) -> None:
        manifest = self.s.client.request("mhs.devices.get", {"device_id": self.s.device})
        self.assertIn("reference", manifest)
        self.assertIn("adjusts", manifest["reference"])
        by_name = {entry["name"]: entry for entry in manifest["reference"]["adjusts"]}
        self.assertEqual(by_name["fan_speed"]["limit"], "operator_required")
        self.assertEqual(by_name["setpoint"]["limit"]["max"], 80)


class EstopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = thermostat()
        self.addCleanup(self.server.close)
        self.s = Session(self.server)

    def test_core_076_the_estop_needs_no_session_hello_or_deadline(self) -> None:
        fresh = thermostat()
        self.addCleanup(fresh.close)
        device = client_for(fresh).hello()["devices"][0]["device_id"]
        response = fresh.handle({"jsonrpc": "2.0", "id": 1, "method": "mhs.safety.estop",
                                 "params": {"device_id": device, "reason": "no session"}})
        receipt = (response.to_dict() if hasattr(response, "to_dict") else response)["result"]
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(receipt["output"]["latched"])

    def test_core_075_a_latched_device_refuses_effectful_commands_but_not_reads(self) -> None:
        stop = self.s.client.estop("test", device_id=self.s.device, session_id=self.s.session)
        self.assertEqual(stop["status"], "completed")
        refused = self.s.invoke("cap.thermal.setpoint.v1", {"target_temperature": 30})
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(refused["state_revision_after"], refused["state_revision_before"])
        self.assertEqual(self.s.client.read("main", device_id=self.s.device, session_id=self.s.session)["revision"],
                         refused["state_revision_before"])
        status = self.s.client.safety_status(self.s.device)
        self.assertTrue(status["estop_engaged"])

    def test_core_075_the_safe_state_action_is_callable_while_latched(self) -> None:
        self.s.client.estop("test", device_id=self.s.device, session_id=self.s.session)
        done = self.s.invoke("x-cap.openmhs-tutorial.heater_off.v1", {})
        self.assertEqual(done["status"], "completed")

    def test_core_080_and_082_reset_releases_the_latch_and_resumes_nothing(self) -> None:
        nothing = self.s.client.reset(device_id=self.s.device, session_id=self.s.session)
        self.assertEqual(nothing["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED")
        self.assertEqual(nothing["error"]["details"]["reason"], "not_latched")
        self.s.client.estop("test", device_id=self.s.device, session_id=self.s.session)
        released = self.s.client.reset(device_id=self.s.device, session_id=self.s.session)
        self.assertEqual(released["status"], "completed")
        self.assertIs(released["output"]["resumed"], False)
        self.assertEqual(self.s.invoke("cap.thermal.setpoint.v1", {"target_temperature": 30})["status"], "completed")

    def test_core_074_the_estop_cancels_running_work_and_reports_it(self) -> None:
        server = conveyor()
        self.addCleanup(server.close)
        s = Session(server, capabilities=["cap.world.*", "cap.motion.*", "x-cap.mhs-test.*"])
        slow = {}

        def run():
            slow["receipt"] = s.invoke("x-cap.mhs-test.delay.v1", {"ms": 1500}, deadline_ms=5000)

        thread = threading.Thread(target=run)
        thread.start()
        time.sleep(0.3)
        stop = s.client.estop("cancel", device_id=s.device, session_id=s.session)
        thread.join(10)
        self.assertEqual(stop["status"], "completed")
        self.assertTrue(stop["output"]["cancelled_operations"], stop["output"])
        self.assertEqual(slow["receipt"]["status"], "cancelled")


class ReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = thermostat()
        self.addCleanup(self.server.close)
        self.s = Session(self.server)

    def test_core_090_replay_reuse_and_a_rejected_attempt_is_not_the_outcome(self) -> None:
        command_id = canonical.ulid()
        refused = self.s.invoke("cap.thermal.setpoint.v1", {"target_temperature": 400}, command_id=command_id)
        first = self.s.invoke("cap.thermal.setpoint.v1", {"target_temperature": 30}, command_id=command_id)
        replay = self.s.invoke("cap.thermal.setpoint.v1", {"target_temperature": 30}, command_id=command_id)
        reuse = self.s.invoke("cap.thermal.setpoint.v1", {"target_temperature": 31}, command_id=command_id)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(first["status"], "completed")
        self.assertIs(replay["replayed"], True)
        self.assertEqual(replay["receipt_id"], first["receipt_id"])
        self.assertEqual(reuse["error"]["mhs_code"], "MHS.CONFLICT.COMMAND_ID_REUSE")

    def test_core_095_the_revision_moves_only_for_a_state_change(self) -> None:
        before = self.s.invoke("cap.thermal.setpoint.v1", {"target_temperature": 30})
        rejected = self.s.invoke("cap.thermal.setpoint.v1", {"target_temperature": 400})
        self.assertEqual(before["state_revision_after"], before["state_revision_before"] + 1)
        self.assertEqual(rejected["state_revision_after"], before["state_revision_after"])
        stale = self.s.invoke("cap.thermal.setpoint.v1", {"target_temperature": 31}, expected_revision=0)
        self.assertEqual(stale["error"]["mhs_code"], "MHS.CONFLICT.REVISION")
        self.assertEqual(stale["error"]["current_revision"], before["state_revision_after"])

    def test_core_100_a_deadline_bounds_the_wait_not_the_execution(self) -> None:
        server = conveyor()
        self.addCleanup(server.close)
        s = Session(server, capabilities=["cap.world.*", "x-cap.mhs-test.*"])
        slow = s.invoke("x-cap.mhs-test.delay.v1", {"ms": 600}, deadline_ms=60)
        self.assertEqual(slow["status"], "unknown")
        self.assertEqual(slow["error"]["mhs_code"], "MHS.OUTCOME.TIMEOUT")
        self.assertIs(slow["error"]["retryable"], False)
        operation_id = slow["operation_id"]
        final = None
        for _ in range(60):
            final = s.rpc("mhs.operations.get", session_id=s.session, operation_id=operation_id, deadline_ms=2000)["result"]
            if final["status"] not in ("running", "accepted") and (final.get("x-vendor") or {}).get("reconciles"):
                break
            time.sleep(0.1)
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(final["x-vendor"]["reconciles"]["status"], "unknown")


class ModeAndDiscoveryTests(unittest.TestCase):
    def test_core_111_a_fake_backend_is_served_as_simulated_under_its_own_id(self) -> None:
        server = thermostat()
        self.addCleanup(server.close)
        hello = client_for(server).hello()
        device = hello["devices"][0]
        self.assertEqual(device["mode"], "simulated")
        self.assertTrue(device["device_id"].endswith("/tutorial-thermostat/fake"))
        manifest = client_for(server).request("mhs.devices.get", {"device_id": device["device_id"]})
        self.assertEqual(manifest["fidelity"]["fidelity_level"], "F0")
        self.assertTrue(manifest["fidelity"]["gaps"])

    def test_core_186_hello_fields_and_the_method_count(self) -> None:
        server = thermostat()
        self.addCleanup(server.close)
        hello = client_for(server).hello()
        self.assertEqual(hello["spec_version"], "0.9")
        self.assertEqual(hello["mhs_version"], "1.0")
        self.assertEqual(hello["implementation"]["name"], "openmhs")
        limits = hello["limits"]
        for key, value in (("max_request_bytes", 1048576), ("max_batch", 64), ("max_subscriptions", 64),
                           ("max_rate_per_s", 50), ("session_max_ttl_s", 86400), ("receipt_retention_days", 30),
                           ("max_command_deadline_ms", 600000)):
            self.assertEqual(limits[key], value, key)
        self.assertEqual(limits["receipt_store"], "memory")
        self.assertEqual(hello["conformance"], [])
        self.assertIn("MHS.SAFETY.NOT_CERTIFIED", hello["features"])
        from mhs.server import MHSServer
        methods = set(MHSServer._METHODS)
        self.assertEqual(len(methods), 24)
        self.assertNotIn("mhs.composition.run", methods)
        self.assertNotIn("mhs.registry.search", methods)

    def test_core_190_the_conformance_report_of_an_unrun_endpoint_is_a_cl0_not_run_report(self) -> None:
        server = thermostat()
        self.addCleanup(server.close)
        report = client_for(server).request("mhs.conformance.report", {})
        self.assertEqual(report["level_achieved"], "CL0")
        self.assertTrue(all(case["status"] == "skip" and "not_run" in case.get("detail", "") for case in report["tests"]))
        self.assertIn("not_certified", {item["id"] for item in report["disclaimers"]})


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = thermostat()
        cls.handle = cls.server.start_http("127.0.0.1", 0)
        cls.url = cls.handle.url

    @classmethod
    def tearDownClass(cls) -> None:
        cls.handle.shutdown()
        cls.server.close()

    def post(self, body: str, headers: dict | None = None):
        request = urllib.request.Request(self.url + "/mhs/v1/rpc", data=body.encode(),
                                         headers=headers if headers is not None else {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            raw = error.read()
            error.close()
            return error.code, (json.loads(raw) if raw else None)

    def test_core_120_the_descriptor_is_served_without_authentication(self) -> None:
        with urllib.request.urlopen(self.url + "/.well-known/mhs.json", timeout=10) as response:
            descriptor = json.loads(response.read())
        self.assertEqual(descriptor["mhs_version"], "1.0")
        self.assertEqual(descriptor["auth"], ["none"])
        self.assertTrue(descriptor["devices"])

    def test_core_182_content_type_and_get_are_enforced(self) -> None:
        status, _ = self.post('{"jsonrpc":"2.0","id":1,"method":"mhs.hello","params":{}}', headers={"Content-Type": "text/plain"})
        self.assertEqual(status, 415)
        status, _ = self.post('{"jsonrpc":"2.0","id":1,"method":"mhs.hello","params":{}}', headers={})
        self.assertEqual(status, 415)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.url + "/mhs/v1/rpc", timeout=10)
        caught.exception.close()
        self.assertEqual(caught.exception.code, 405)

    def test_core_180_a_foreign_host_or_origin_is_refused(self) -> None:
        status, _ = self.post('{"jsonrpc":"2.0","id":1,"method":"mhs.hello","params":{}}',
                              headers={"Content-Type": "application/json", "Host": "evil.example"})
        self.assertEqual(status, 403)
        status, _ = self.post('{"jsonrpc":"2.0","id":1,"method":"mhs.hello","params":{}}',
                              headers={"Content-Type": "application/json", "Origin": "http://evil.example"})
        self.assertEqual(status, 403)

    def test_core_183_a_nan_literal_is_a_parse_error_with_status_400(self) -> None:
        status, body = self.post('{"jsonrpc":"2.0","id":1,"method":"mhs.hello","params":{"x":NaN}}')
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], -32700)

    def test_core_184_the_event_stream_needs_a_live_session(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(self.url + "/mhs/v1/events", timeout=10)
        missing.exception.close()
        self.assertEqual(missing.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError) as unknown:
            urllib.request.urlopen(self.url + "/mhs/v1/events?session_id=mhs_s_nope", timeout=10)
        unknown.exception.close()
        self.assertEqual(unknown.exception.code, 403)

    def test_core_152_a_non_loopback_bind_without_tokens_is_refused(self) -> None:
        server = thermostat()
        self.addCleanup(server.close)
        with self.assertRaises(Exception) as caught:
            server.start_http("0.0.0.0", 0)
        self.assertIn("MHS.AUTH.TRANSPORT_INSECURE", str(caught.exception))

    def test_core_181_with_tokens_every_route_needs_one_except_the_descriptor(self) -> None:
        server = thermostat(auth_tokens={"secret-token": {"id": "agent:test", "kind": "agent"}})
        handle = server.start_http("127.0.0.1", 0)
        self.addCleanup(server.close)
        self.addCleanup(handle.shutdown)
        request = urllib.request.Request(handle.url + "/mhs/v1/rpc", data=b'{"jsonrpc":"2.0","id":1,"method":"mhs.hello","params":{}}',
                                         headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=10)
        caught.exception.close()
        self.assertEqual(caught.exception.code, 401)
        self.assertIn("Bearer", caught.exception.headers.get("WWW-Authenticate", ""))
        with urllib.request.urlopen(handle.url + "/.well-known/mhs.json", timeout=10) as response:
            self.assertEqual(json.loads(response.read())["auth"], ["bearer"])


class PersistenceTests(unittest.TestCase):
    def test_core_171_and_172_a_latch_and_a_receipt_survive_a_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = thermostat(state_dir=directory)
            s = Session(first)
            command_id = canonical.ulid()
            done = s.invoke("cap.thermal.setpoint.v1", {"target_temperature": 30}, command_id=command_id)
            s.client.estop("persist", device_id=s.device, session_id=s.session)
            self.assertTrue((Path(directory) / "latch.json").is_file())
            self.assertTrue((Path(directory) / "journal.jsonl").is_file())
            first.close()
            second = thermostat(state_dir=directory)
            self.addCleanup(second.close)
            t = Session(second)
            self.assertEqual(client_for(second).hello()["limits"]["receipt_store"], "state_dir")
            status = t.client.safety_status(t.device)
            self.assertTrue(status["estop_engaged"])
            self.assertIs(status["estop"].get("restored"), True)
            self.assertIs(status["estop"].get("confirmed"), False)
            replay = t.invoke("cap.thermal.setpoint.v1", {"target_temperature": 30}, command_id=command_id)
            self.assertIs(replay["replayed"], True)
            self.assertEqual(replay["receipt_id"], done["receipt_id"])


class SurfaceTests(unittest.TestCase):
    def test_core_137_exit_codes_for_a_usage_error_and_an_unreachable_endpoint(self) -> None:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT / "MHS" / "sdk" / "src"))
        unreachable = subprocess.run([sys.executable, "-m", "mhs", "devices", "-e", "http://127.0.0.1:9", "--json"],
                                     cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(unreachable.returncode, 3, unreachable.stdout + unreachable.stderr)
        self.assertEqual(json.loads(unreachable.stdout)["error"]["mhs_code"], "MHS.TRANSPORT.UNAVAILABLE")
        usage = subprocess.run([sys.executable, "-m", "mhs", "call", "-e", "http://127.0.0.1:9", "-c", "cap.x.v1",
                                "-i", "[1]"], cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(usage.returncode, 2, usage.stdout + usage.stderr)

    def test_core_130_the_mcp_projection_hides_the_operator_tools_by_default(self) -> None:
        from mhs.mcp import MCPProjection
        server = thermostat()
        self.addCleanup(server.close)
        projection = MCPProjection(client_for(server))
        counter = [0]

        def call(method, params=None):
            counter[0] += 1
            message = {"jsonrpc": "2.0", "id": counter[0], "method": method}
            if params is not None:
                message["params"] = params
            return projection.handle_message(message)

        call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
        tools = {tool["name"]: tool for tool in call("tools/list")["result"]["tools"]}
        for name in ("mhs__devices", "mhs__inspect", "mhs__read", "mhs__safety", "mhs__operations", "mhs__evidence", "mhs__estop"):
            self.assertIn(name, tools)
        self.assertNotIn("mhs__reset", tools)
        self.assertNotIn("mhs__permit", tools)
        for tool in tools.values():
            self.assertLessEqual(len(tool["description"].encode("utf-8")), 2048, tool["name"])
        refused = call("tools/call", {"name": "mhs__reset", "arguments": {}})["result"]
        self.assertIs(refused["isError"], True)
        self.assertIn("MHS.AUTH.FORBIDDEN", refused["content"][0]["text"])
        setpoint = next(name for name in tools if name.endswith("thermal_setpoint"))
        rejected = call("tools/call", {"name": setpoint, "arguments": {"target_temperature": 400}})["result"]
        self.assertIs(rejected["isError"], False)                               # a rejected receipt is not a tool error
        self.assertEqual(rejected["structuredContent"]["receipt"]["status"], "rejected")

    def test_core_140_lab_raises_on_a_refusal_unless_check_is_false(self) -> None:
        from mhs.client import MHSRejected
        from mhs.run import lab
        server = thermostat()
        self.addCleanup(server.close)
        with lab(server, ledger=False) as bench:
            handle = bench["tutorial-thermostat"]
            with self.assertRaises(MHSRejected) as caught:
                handle.invoke("cap.thermal.setpoint.v1", {"target_temperature": 400})
            self.assertEqual(caught.exception.code, "MHS.SAFETY.ENVELOPE_VIOLATION")
        with lab(server, ledger=False, check=False) as bench:
            receipt = bench["tutorial-thermostat"].invoke("cap.thermal.setpoint.v1", {"target_temperature": 400})
            self.assertEqual(receipt["status"], "rejected")


class DriverProfileTests(unittest.TestCase):
    def test_drv_013_the_backend_names_are_fixed(self) -> None:
        with self.assertRaises(LoadError) as caught:
            load_driver(str(THERMOSTAT), backend="mock")
        self.assertEqual(caught.exception.reason, "backend_unknown")

    def test_core_154_a_hardware_backend_needs_the_operators_decisions(self) -> None:
        with self.assertRaises(LoadError) as caught:
            load_driver(str(THERMOSTAT), backend="hardware")
        self.assertEqual(caught.exception.reason, "hardware_not_allowed")
        with self.assertRaises(LoadError) as caught:
            load_driver(str(THERMOSTAT), backend="hardware", allow_hardware=True)
        self.assertEqual(caught.exception.reason, "state_dir_required")

    def test_drv_040_a_model_authored_r2_hardware_driver_needs_a_human_signature(self) -> None:
        from mhs.driver.loader import review_problem
        model = {"authored_by": {"kind": "model", "model_id": "m"}, "reviewed_by": None}
        human = {"authored_by": {"kind": "human"}, "reviewed_by": None}
        signed = {"authored_by": {"kind": "model", "model_id": "m"},
                  "reviewed_by": {"reviewer": "A", "date": "2026-11-02", "scope": "contract"}}
        self.assertIn("reviewed_by", review_problem(model, [], risk="R2"))
        self.assertIsNone(review_problem(model, [], risk="R1"))
        self.assertIsNone(review_problem(human, [], risk="R2"))
        self.assertIsNone(review_problem(signed, [], risk="R3"))

    def test_drv_060_the_gate_refuses_a_hardware_backend(self) -> None:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT / "MHS" / "sdk" / "src"))
        result = subprocess.run([sys.executable, "-m", "mhs.driver", "check", str(THERMOSTAT), "--backend", "hardware"],
                                cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_drv_061_the_gate_ids_of_the_profile_exist_in_the_schema(self) -> None:
        driver_profile = (SPEC / "driver-profile.md").read_text(encoding="utf-8")
        schema = json.loads((ROOT / "MHS/schema/defs.schema.json").read_text(encoding="utf-8"))["$defs"]
        self.assertEqual(schema["gateId"]["enum"], [f"G{n}" for n in range(1, 10)])
        for gate in schema["gateId"]["enum"]:
            self.assertIn(f"| {gate} ", driver_profile)
        for code in schema["blockedCode"]["enum"]:
            self.assertIn(f"`{code}`", driver_profile)


class DocumentConsistencyTests(unittest.TestCase):
    def test_every_mhs_error_code_named_in_the_core_is_registered(self) -> None:
        registered = {entry["code"] for entry in json.loads((SPEC / "errors.json").read_text(encoding="utf-8"))["errors"]}
        named = set(re.findall(r"\bMHS\.[A-Z]+\.[A-Z0-9_]+\b", CORE)) - {"MHS.SAFETY.NOT_CERTIFIED"}
        self.assertFalse(named - registered, named - registered)

    def test_the_stated_limits_equal_the_code_constants(self) -> None:
        import mhs.server as server_module
        self.assertEqual(server_module._MAX_DEADLINE_MS, 600_000)
        self.assertEqual(server_module._MAX_SSE_STREAMS_PER_PRINCIPAL, 4)
        self.assertEqual(server_module._LONG_RUNNING_DEFAULT_MAX_MS, 600_000)
        for text in ("600000 ms", "`max_command_deadline_ms` (600000)", "at most 4 streams", "`retry: 3000`",
                     "a batch over 64 requests", "(1048576)"):
            self.assertIn(text, CORE)


if __name__ == "__main__":
    unittest.main()
