"""Declared recovery after an e-stop: an explicit re-enable (CORE-086) and a terminal e-stop (CORE-087).

Two small drivers stand for the two blocked shapes of RE-ENABLE-AND-TERMINAL-STOP.md:

* ``Drive``: its stop switches the drive off and only an explicit switch-on enables it again (the Franka
  spine shape).  It declares that switch-on with ``reenable=True``.
* ``Session``: its stop closes the instrument session for good (the Thorlabs TLBC2 shape).  It declares
  ``estop_terminal``.

Positive cases show the declared contract served and passed by TSAFE-001; negative cases show every
malformed declaration refused (model, start-up, schema) and TSAFE-001 failing an endpoint that ignores a
declaration; counterfactual cases show the same drivers without the declarations failing exactly as the two
blocked packages did, and the runner failing SAFE-014 without its new-endpoint and ordering rules.
"""

from __future__ import annotations

import copy
import unittest
from unittest import mock

from mhs.client import MHSClient
from mhs.conformance import run_suite
from mhs.conformance.inprocess import client_for, run_suite_inprocess
from mhs.driver import (
    DEFAULT_ENDPOINT_ID,
    FAKE_FIDELITY,
    Action,
    Driver,
    DriverDefinitionError,
    DriverFailed,
    Field,
    Limit,
    RosDriver,
    action,
    build_device,
    build_reference,
    build_server,
    close_server,
    estop,
    interlock,
    read,
    reset,
    write,
)
from mhs.bridge.ros_transport import RecordingRosTransport
from mhs.errors import MHSError
from mhs.schema import default_store
from mhs.server import MHSServer

from tests.driver import support

MOVE = "x-cap.test.recovery-move.v1"
SWITCH_ON = "x-cap.test.recovery-switch-on.v1"
SWITCH_OFF = "x-cap.test.recovery-switch-off.v1"
MEASURE = "x-cap.test.recovery-measure.v1"
TERMINAL = "close() ends the instrument session; the vendor library requires a new initialisation (vendor.py:233)"
ESTOP_ENGAGED = "MHS.SAFETY.ESTOP_ENGAGED"
RESET_REFUSED = "MHS.SAFETY.RESET_REFUSED"


# ---------------------------------------------------------------------------
# drivers
# ---------------------------------------------------------------------------


class FakeDrive:
    """A drive that its stop switches off; only ``switch_on`` enables it again."""

    def __init__(self, **_options):
        self.state = "on"
        self.position = 0.0
        self.calls: list[object] = []
        self.fail_switch_on = False

    def switch_off(self):
        self.calls.append("switch_off")
        self.state = "off"

    def switch_on(self):
        self.calls.append("switch_on")
        if self.fail_switch_on:
            return False
        self.state = "on"
        return True

    def move(self, position):
        self.calls.append(("move", position))
        if self.state != "on":
            return False
        self.position = float(position)
        return True


class Drive(Driver):
    device_id, device_kind, mode, risk = "test/drive", "motion.axis", "hardware", "R1"
    backends = {"fake": FakeDrive}
    safe_state = "the drive is switched off"

    @read("state", type="string", description="drive state")
    def state(self):
        return self.native.state

    @read("position", unit="m", description="drive position")
    def position(self):
        return self.native.position

    @action(name=MOVE, input={"position": Field("number", unit="m", description="target position",
                                                limit=Limit(min=0.0, max=1.0, source="upstream_code",
                                                            ref="drive.py:10"))},
            output={"reached": Field("boolean", description="the target was reached")})
    def move(self, position):
        if not self.native.move(position):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "the drive is switched off")
        return {"reached": True}

    @action(name=SWITCH_OFF, safe_state=True, output={"state": Field("string", description="drive state")})
    def switch_off(self):
        self.native.switch_off()
        return {"state": self.native.state}

    @action(name=SWITCH_ON, reenable=True, output={"state": Field("string", description="drive state")})
    def switch_on(self):
        if not self.native.switch_on():
            raise DriverFailed("MHS.DEVICE.FAULTED", "the drive refused to switch on")
        return {"state": self.native.state}

    @estop
    def stop(self):
        self.native.switch_off()


class DriveWithoutDeclaration(Drive):
    """Counterfactual: the switch-on is bound but not declared as the re-enable (the old contract)."""

    @action(name=SWITCH_ON, output={"state": Field("string", description="drive state")})
    def switch_on(self):
        if not self.native.switch_on():
            raise DriverFailed("MHS.DEVICE.FAULTED", "the drive refused to switch on")
        return {"state": self.native.state}


class FakeSession:
    """An instrument session that ``close()`` ends for good."""

    def __init__(self, **_options):
        self.closed = False
        self.exposure = 10.0
        self.close_calls = 0
        self.reset_calls = 0
        self.on_reset = None

    def _check(self):
        if self.closed:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the session is closed; create a new endpoint")

    def get_exposure(self):
        self._check()
        return self.exposure

    def set_exposure(self, value):
        self._check()
        self.exposure = float(value)

    def close(self):
        self.close_calls += 1
        self.closed = True


class Session(Driver):
    device_id, device_kind, mode, risk = "test/session", "instrument", "hardware", "R1"
    backends = {"fake": FakeSession}
    safe_state = "the instrument session is closed"
    estop_terminal = TERMINAL

    @read("exposure", unit="ms", description="exposure time")
    def exposure(self):
        return self.native.get_exposure()

    @write("exposure", unit="ms", description="exposure time",
           limit=Limit(min=1.0, max=100.0, source="upstream_code", ref="vendor.py:120"))
    def set_exposure(self, value):
        self.native.set_exposure(value)

    @estop
    def stop(self):
        self.native.close()

    @reset
    def never_reopen(self):
        self.native.reset_calls += 1
        if self.native.on_reset is not None:
            self.native.on_reset()
        if self.native.closed:
            raise MHSError(RESET_REFUSED, "the session is closed; a reset cannot reopen it")


class SessionWithoutDeclaration(Session):
    """Counterfactual: the same terminal close without the declaration (the old contract)."""

    estop_terminal = None


def served(driver_class, **options):
    driver = driver_class(backend="fake")
    server = build_server(driver, **options)
    return driver, server, support.Client(server)


def details(receipt):
    return ((receipt or {}).get("error") or {}).get("details") or {}


def status(client):
    return client.rpc("mhs.safety.status", {"session_id": client.session_id, "device_id": client.device_id,
                                           "deadline_ms": 1000})


def entry(report, test_id):
    return next(item for item in report["tests"] if item["id"] == test_id)


# ---------------------------------------------------------------------------
# the declarations in the model, the manifest, the reference file and the schemas
# ---------------------------------------------------------------------------


class DeclarationTests(unittest.TestCase):
    def test_reenable_and_terminal_are_published_only_when_declared(self):
        self.assertEqual(Drive.driver_model().safety_manifest()["estop"]["reenable"], SWITCH_ON)
        self.assertNotIn("terminal", Drive.driver_model().safety_manifest()["estop"])
        self.assertEqual(Session.driver_model().safety_manifest()["estop"]["terminal"], TERMINAL)
        self.assertNotIn("reenable", Session.driver_model().safety_manifest()["estop"])
        for cls in (support.Arm, support.Bath, DriveWithoutDeclaration, SessionWithoutDeclaration):
            with self.subTest(driver=cls.__name__):
                estop_block = cls.driver_model().safety_manifest()["estop"]
                self.assertFalse({"reenable", "terminal"} & set(estop_block), estop_block)

    def test_manifests_and_reference_files_validate(self):
        store = default_store()
        for cls, key, value in ((Drive, "reenable", SWITCH_ON), (Session, "terminal", TERMINAL)):
            with self.subTest(driver=cls.__name__):
                device = build_device(cls(backend="fake"))
                manifest = device.manifest()
                self.assertEqual(manifest["safety"]["estop"][key], value)
                self.assertEqual(store.validate(manifest, "device.schema.json"), [])
                reference = build_reference(cls(backend="fake"))
                self.assertEqual(reference["safety"]["estop"][key], value)
                self.assertEqual(store.validate(reference, "reference.schema.json"), [])

    def test_schema_refuses_both_declarations_and_an_empty_terminal(self):
        store = default_store()
        manifest = build_device(Drive(backend="fake")).manifest()
        both = copy.deepcopy(manifest)
        both["safety"]["estop"]["terminal"] = TERMINAL
        self.assertTrue(store.validate(both, "device.schema.json"))
        empty = copy.deepcopy(build_device(Session(backend="fake")).manifest())
        empty["safety"]["estop"]["terminal"] = " "
        self.assertTrue(store.validate(empty, "device.schema.json"))
        bad_id = copy.deepcopy(manifest)
        bad_id["safety"]["estop"]["reenable"] = "switch on"
        self.assertTrue(store.validate(bad_id, "device.schema.json"))

    def test_reference_text_names_the_declarations(self):
        from mhs.reference_file import render_markdown

        self.assertIn(f"Re-enable after a reset: `{SWITCH_ON}`", render_markdown(build_reference(Drive(backend="fake"))))
        self.assertIn(f"- Terminal e-stop: {TERMINAL}. Every reset after an e-stop on the same endpoint is refused",
                      render_markdown(build_reference(Session(backend="fake"))))

    def assertDefinitionProblem(self, attributes, expected, base=Drive):
        cls = type("Broken" + base.__name__, (base,), dict(attributes))
        with self.assertRaises(DriverDefinitionError) as caught:
            cls.driver_model()
        self.assertIn(expected, str(caught.exception))

    def test_model_refuses_malformed_reenable_declarations(self):
        def second(self):
            return {}
        second_action = action(name="x-cap.test.recovery-second.v1", reenable=True)(second)
        self.assertDefinitionProblem({"second": second_action}, "only one action may be declared reenable=True")

        def safe(self):
            return {}
        self.assertDefinitionProblem({"switch_on": action(name=SWITCH_ON, reenable=True, safe_state=True)(safe)},
                                     "cannot be a safe_state action")

        def needs_input(self, speed):
            return {}
        self.assertDefinitionProblem(
            {"switch_on": action(name=SWITCH_ON, reenable=True,
                                 input={"speed": Field("number", unit="m/s", description="speed",
                                                       limit=Limit(min=0, max=1, source="upstream_code",
                                                                   ref="drive.py:3"))})(needs_input)},
            "called with an empty input")

        def observe(self):
            return {}
        self.assertDefinitionProblem(
            {"switch_on": action(name=SWITCH_ON, reenable=True, verb="read",
                                 output={"state": Field("string", description="state")})(observe)},
            "a read cannot re-enable the device")

    def test_model_refuses_malformed_terminal_declarations(self):
        self.assertDefinitionProblem({"estop_terminal": TERMINAL}, "has no re-enable", base=Drive)
        self.assertDefinitionProblem({"estop_terminal": ""}, "estop_terminal must be a non-empty string",
                                     base=Session)
        self.assertDefinitionProblem({"estop_terminal": "x" * 501}, "at most 500 characters", base=Session)

        class NoStop(Driver):
            device_id, device_kind, mode, risk = "test/no-stop", "instrument", "simulated", "R0"
            backends = {"fake": FakeSession}
            fidelity = copy.deepcopy(FAKE_FIDELITY)
            estop_terminal = TERMINAL

            @read("exposure", unit="ms", description="exposure time")
            def exposure(self):
                return self.native.get_exposure()

            @write("exposure", unit="ms", description="exposure time",
                   limit=Limit(min=1.0, max=100.0, source="upstream_code", ref="vendor.py:120"))
            def set_exposure(self, value):
                self.native.set_exposure(value)

        with self.assertRaises(DriverDefinitionError) as caught:
            NoStop.driver_model()
        self.assertIn("estop_terminal describes the native stop", str(caught.exception))


# ---------------------------------------------------------------------------
# start-up validation of a manifest, whatever produced it
# ---------------------------------------------------------------------------


class StartupValidationTests(unittest.TestCase):
    def assertRefused(self, driver_class, change, expected):
        device = build_device(driver_class(backend="fake"))
        change(device.safety.estop)
        with self.assertRaises(ValueError) as caught:
            MHSServer(DEFAULT_ENDPOINT_ID, [device], strict=True)
        self.assertIn(expected, str(caught.exception))

    def test_a_reenable_must_be_an_ordinary_bound_command(self):
        self.assertRefused(Drive, lambda estop: estop.update(reenable="x-cap.test.unbound.v1"),
                           "bound to exactly one resource")
        self.assertRefused(Drive, lambda estop: estop.update(reenable=SWITCH_OFF), "safe_state.achieved_by action")
        self.assertRefused(Drive, lambda estop: estop.update(reenable=MOVE), "called with an empty input")
        self.assertRefused(Drive, lambda estop: estop.update(reenable=7), "must name a bound capability id")

    def test_a_terminal_declaration_is_a_sentence_with_a_stop_path_and_no_reenable(self):
        self.assertRefused(Session, lambda estop: estop.update(terminal=" "), "must state in one sentence")
        self.assertRefused(Drive, lambda estop: estop.update(terminal=TERMINAL), "exclude each other")

    def test_a_terminal_declaration_needs_a_stop_path(self):
        class Plain(Driver):
            device_id, device_kind, mode, risk = "test/plain", "instrument", "simulated", "R0"
            backends = {"fake": FakeSession}
            fidelity = copy.deepcopy(FAKE_FIDELITY)

            @write("exposure", unit="ms", description="exposure time",
                   limit=Limit(min=1.0, max=100.0, source="upstream_code", ref="vendor.py:120"))
            def set_exposure(self, value):
                self.native.set_exposure(value)

        self.assertRefused(Plain, lambda estop: estop.update(terminal=TERMINAL), "has no native e-stop")

    def test_a_bridgeless_hardware_view_accepts_the_declared_native_stop(self):
        # Gate G3 serves the hardware view from the manifest alone (no bridge): the declared native stop counts.
        from mhs.driver import build_manifest
        from mhs.driver.build import device_from_manifest

        manifest = build_manifest(Session(backend="fake"), backend="hardware")
        self.assertEqual(manifest["safety"]["estop"]["native"], "stop")
        MHSServer(DEFAULT_ENDPOINT_ID, [device_from_manifest(manifest, None)], strict=True).close()
        stripped = copy.deepcopy(manifest)
        stripped["safety"]["estop"]["native"] = None
        with self.assertRaises(ValueError) as caught:
            MHSServer(DEFAULT_ENDPOINT_ID, [device_from_manifest(stripped, None)], strict=True)
        self.assertIn("has no native e-stop", str(caught.exception))

    def test_well_formed_and_absent_declarations_start(self):
        for cls in (Drive, Session, DriveWithoutDeclaration, SessionWithoutDeclaration, support.Arm):
            with self.subTest(driver=cls.__name__):
                server = build_server(cls(backend="fake"))
                close_server(server)


# ---------------------------------------------------------------------------
# runtime: the explicit re-enable
# ---------------------------------------------------------------------------


class ReenableRuntimeTests(unittest.TestCase):
    def test_reset_never_rearms_and_the_reenable_is_refused_while_latched(self):
        driver, server, client = served(Drive)
        self.addCleanup(close_server, server)
        self.assertEqual(client.command(MOVE, {"position": 0.4})["status"], "completed")
        self.assertEqual(client.estop()["status"], "completed")
        self.assertEqual(driver.native.state, "off")
        before = len(driver.native.calls)
        revision = client.read()["revision"]
        refused = client.command(SWITCH_ON)
        self.assertEqual((refused["status"], support.code(refused)), ("rejected", ESTOP_ENGAGED), refused)
        self.assertEqual(driver.native.calls[before:], [])
        self.assertEqual(client.read()["revision"], revision)
        receipt = client.reset()["result"]
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["reenable"], SWITCH_ON)
        self.assertIs(receipt["output"]["resumed"], False)
        # The reset re-armed nothing: the drive stays off and a move still fails at the device.
        self.assertEqual(driver.native.state, "off")
        self.assertNotIn("switch_on", driver.native.calls[before:])
        self.assertEqual(client.command(MOVE, {"position": 0.6})["status"], "failed")
        enabled = client.command(SWITCH_ON)
        self.assertEqual(enabled["status"], "completed", enabled)
        self.assertEqual(driver.native.state, "on")
        self.assertEqual(client.command(MOVE, {"position": 0.6})["status"], "completed")
        self.assertEqual(driver.native.position, 0.6)

    def test_a_device_without_a_reenable_reports_none(self):
        _driver, server, client = served(DriveWithoutDeclaration)
        self.addCleanup(close_server, server)
        client.estop()
        receipt = client.reset()["result"]
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertNotIn("reenable", receipt["output"])
        self.assertNotIn("terminated", status(client)["estop"])


# ---------------------------------------------------------------------------
# runtime: the terminal e-stop
# ---------------------------------------------------------------------------


class TerminalRuntimeTests(unittest.TestCase):
    def test_reset_after_a_terminal_estop_is_refused_without_a_bridge_call(self):
        driver, server, client = served(Session)
        self.addCleanup(close_server, server)
        self.assertEqual(client.write({"exposure": 20.0})["status"], "completed")
        self.assertEqual(client.estop()["status"], "completed")
        self.assertTrue(driver.native.closed)
        for _attempt in range(2):
            response = client.reset()
            receipt = response["result"]
            self.assertEqual((receipt["status"], support.code(receipt)), ("rejected", RESET_REFUSED), receipt)
            self.assertEqual(details(receipt)["reason"], "terminal_estop")
            self.assertEqual(details(receipt)["terminal"], TERMINAL)
            self.assertIs(details(receipt)["latched"], True)
            self.assertIn("new endpoint", receipt["error"]["remediation"])
        self.assertEqual(driver.native.reset_calls, 0)  # the bridge's reset was never called
        block = status(client)["estop"]
        self.assertIs(block["engaged"], True)
        self.assertIs(block["terminated"], True)
        self.assertEqual(block["terminal"], TERMINAL)
        refused = client.write({"exposure": 30.0})
        self.assertEqual((refused["status"], support.code(refused)), ("rejected", ESTOP_ENGAGED), refused)
        again = client.estop()
        self.assertEqual(again["status"], "completed", again)  # the e-stop is never refused
        self.assertEqual(driver.native.close_calls, 2)

    def test_counterfactual_without_the_declaration_the_reset_reaches_the_bridge(self):
        driver, server, client = served(SessionWithoutDeclaration)
        self.addCleanup(close_server, server)
        client.estop()
        receipt = client.reset()["result"]
        self.assertEqual(details(receipt)["reason"], "bridge_refused", receipt)
        self.assertEqual(driver.native.reset_calls, 1)
        self.assertNotIn("terminated", status(client)["estop"])

    def test_a_new_endpoint_restores_the_latch_and_resets_it(self):
        state_dir = support.temp_dir(self)
        _driver, server, client = served(Session, state_dir=state_dir)
        self.assertEqual(client.estop()["status"], "completed")
        self.assertEqual(details(client.reset()["result"])["reason"], "terminal_estop")
        close_server(server)
        fresh, server2, client2 = served(Session, state_dir=state_dir)
        self.addCleanup(close_server, server2)
        block = status(client2)["estop"]
        self.assertIs(block["engaged"], True)
        self.assertIs(block.get("restored"), True)
        self.assertNotIn("terminated", block)
        receipt = client2.reset()["result"]
        self.assertEqual(receipt["status"], "completed", receipt)  # a new native session: an ordinary reset
        self.assertEqual(fresh.native.reset_calls, 1)
        self.assertEqual(client2.write({"exposure": 25.0})["status"], "completed")
        self.assertEqual(client2.estop()["status"], "completed")
        self.assertEqual(details(client2.reset()["result"])["reason"], "terminal_estop")

    def test_a_terminal_stop_started_while_a_reset_is_checked_refuses_that_reset(self):
        driver, server, client = served(SessionWithoutDeclaration)
        self.addCleanup(close_server, server)
        device = server.devices[client.device_id]
        client.estop()
        driver.native.closed = False  # pretend the session survived, so only the declaration can refuse
        device.safety.estop["terminal"] = TERMINAL

        def stop_path_started_meanwhile():
            server._estop_state[client.device_id]["terminal"] = True

        original = device.bridge.interlocks
        device.bridge.interlocks = lambda: (stop_path_started_meanwhile(), original())[1]
        receipt = client.reset()["result"]
        self.assertEqual((receipt["status"], details(receipt)["reason"]), ("rejected", "terminal_estop"), receipt)
        self.assertEqual(driver.native.reset_calls, 0)
        self.assertIs(status(client)["estop"]["engaged"], True)

    def test_a_terminal_stop_started_inside_the_bridge_reset_keeps_the_latch(self):
        state_dir = support.temp_dir(self)
        _driver, server, client = served(Session, state_dir=state_dir)
        client.estop()
        close_server(server)
        fresh, server2, client2 = served(Session, state_dir=state_dir)
        self.addCleanup(close_server, server2)

        def stop_path_started_inside_reset():
            server2._estop_state[client2.device_id]["terminal"] = True

        fresh.native.on_reset = stop_path_started_inside_reset
        receipt = client2.reset()["result"]
        self.assertEqual((receipt["status"], support.code(receipt)), ("failed", RESET_REFUSED), receipt)
        self.assertEqual(details(receipt)["reason"], "terminal_estop")
        self.assertEqual(details(receipt)["bridge_reset"], "completed")
        self.assertIs(status(client2)["estop"]["engaged"], True)


# ---------------------------------------------------------------------------
# conformance: TSAFE-001 and the runner
# ---------------------------------------------------------------------------


def suite(driver_class, **options):
    calls = []

    def factory():
        calls.append(1)
        return build_server(driver_class(backend="fake"))

    report = run_suite_inprocess(factory, profile="MHS-Sim", level="CL3", **options)
    return report, len(calls)


class _ReenableIgnoresLatchClient(MHSClient):
    """A non-conformant endpoint view: the re-enable 'completes' while the device is latched."""

    latched = False

    def estop(self, *args, **kwargs):
        self.latched = True
        return super().estop(*args, **kwargs)

    def reset(self, *args, **kwargs):
        receipt = super().reset(*args, **kwargs)
        self.latched = False
        return receipt

    def invoke(self, capability_id, input=None, **kwargs):  # noqa: A002
        if capability_id == SWITCH_ON and self.latched:
            return {"status": "completed", "receipt_id": "forged", "output": {"state": "on"}}
        return super().invoke(capability_id, input, **kwargs)


class _ResetClient(MHSClient):
    """A non-conformant endpoint view: its reset answers ``answer`` instead of the server's receipt."""

    answer: dict = {}

    def reset(self, *args, **kwargs):
        super().reset(*args, **kwargs)
        return copy.deepcopy(self.answer)


def shared(driver_class, client_class=MHSClient, **attributes):
    server = build_server(driver_class(backend="fake"))
    client = type("Configured" + client_class.__name__, (client_class,), dict(attributes))(
        __import__("mhs.conformance.inprocess", fromlist=["Loopback"]).Loopback(server))
    client.hello()
    return server, client


class ConformanceTests(unittest.TestCase):
    def test_tsafe001_sends_the_declared_reenable_after_the_reset(self):
        report, _calls = suite(Drive)
        case = entry(report, "TSAFE-001")
        self.assertEqual(case["status"], "pass", case)
        self.assertIn(f"the declared re-enable {SWITCH_ON} was refused while latched and accepted after the reset",
                      case["detail"])
        self.assertIn("a new command recovered", case["detail"])
        self.assertEqual(case["spec_ref"], "SAFE-040, SAFE-042, SAFE-048")
        self.assertEqual(report["level_achieved"], "CL3", [(item["id"], item["status"], item.get("detail"))
                                                           for item in report["tests"]
                                                           if item["status"] != "pass" and item["required"]])

    def test_counterfactual_without_the_reenable_the_recovery_probe_fails(self):
        report, _calls = suite(DriveWithoutDeclaration)
        case = entry(report, "TSAFE-001")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("command after e-stop reset failed", case["detail"])

    def test_a_failing_reenable_fails_tsafe001(self):
        class StuckFake(FakeDrive):
            def __init__(self, **options):
                super().__init__(**options)
                self.fail_switch_on = True

        class StuckDrive(Drive):
            backends = {"fake": StuckFake}

        report, _calls = suite(StuckDrive)
        case = entry(report, "TSAFE-001")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn(f"the declared re-enable {SWITCH_ON} failed after the reset", case["detail"])

    def test_an_endpoint_that_lets_the_reenable_through_while_latched_fails_tsafe001(self):
        server, client = shared(Drive, _ReenableIgnoresLatchClient)
        self.addCleanup(close_server, server)
        report = run_suite(client, profile="MHS-Sim", level="CL3")
        case = entry(report, "TSAFE-001")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("not a rejected MHS.SAFETY.ESTOP_ENGAGED", case["detail"])

    def test_tsafe001_checks_the_terminal_declaration_and_the_retained_latch(self):
        report, calls = suite(Session)
        case = entry(report, "TSAFE-001")
        self.assertEqual(case["status"], "pass", case)
        self.assertIn("reset refused with MHS.SAFETY.RESET_REFUSED (terminal_estop) and the declared reason",
                      case["detail"])
        self.assertIn("latch retained, a new command was still refused", case["detail"])
        self.assertEqual(entry(report, "SAFE-014")["status"], "pass", entry(report, "SAFE-014"))
        self.assertEqual(entry(report, "SAFE-028")["status"], "pass", entry(report, "SAFE-028"))
        self.assertEqual(report["level_achieved"], "CL3")
        # base, OP, SAFE, then a new SAFE endpoint after TSAFE-001 and after SAFE-028 (CON-022)
        self.assertEqual(calls, 5)
        self.assertTrue(any("terminal e-stop (CORE-087) was engaged by TSAFE-001" in line
                            for line in report["limitations"]), report["limitations"])
        self.assertIn("and after each terminal e-stop", report["environment"]["notes"])

    def test_counterfactual_without_the_declaration_tsafe001_and_safe014_fail(self):
        report, calls = suite(SessionWithoutDeclaration)
        tsafe = entry(report, "TSAFE-001")
        self.assertEqual(tsafe["status"], "fail", tsafe)
        self.assertIn("RESET_REFUSED (bridge_refused)", tsafe["detail"])
        safe014 = entry(report, "SAFE-014")
        self.assertEqual(safe014["status"], "fail", safe014)
        self.assertIn("the session is closed", safe014["detail"])
        self.assertEqual(calls, 3)

    def test_counterfactual_without_a_new_endpoint_safe014_fails_after_the_terminal_stop(self):
        # The runner of suite 1.3.0 before this change kept one endpoint per group: with the suite's view of
        # the declaration switched off, TSAFE-001 still sees the server refuse the reset (terminal_estop), but
        # SAFE-014 then runs on the endpoint whose session the terminal stop closed.
        with mock.patch("mhs.conformance.tests_core._terminal_statement", return_value=None):
            report, calls = suite(Session)
        safe014 = entry(report, "SAFE-014")
        self.assertEqual(safe014["status"], "fail", safe014)
        self.assertIn("the session is closed", safe014["detail"])
        self.assertEqual(calls, 3)

    def test_a_shared_endpoint_runs_the_estop_tests_last(self):
        server, client = shared(Session)
        self.addCleanup(close_server, server)
        report = run_suite(client, profile="MHS-Sim", level="CL3")
        self.assertEqual(entry(report, "TSAFE-001")["status"], "pass", entry(report, "TSAFE-001"))
        self.assertEqual(entry(report, "SAFE-014")["status"], "pass", entry(report, "SAFE-014"))
        self.assertTrue(any("ran after every other test on this shared endpoint" in line
                            for line in report["limitations"]), report["limitations"])

    def test_counterfactual_a_shared_endpoint_in_registry_order_fails_safe014(self):
        server, client = shared(Session)
        self.addCleanup(close_server, server)
        with mock.patch("mhs.conformance.suite._declares_terminal", return_value=False):
            report = run_suite(client, profile="MHS-Sim", level="CL3")
        self.assertEqual(entry(report, "TSAFE-001")["status"], "pass")
        self.assertEqual(entry(report, "SAFE-014")["status"], "fail", entry(report, "SAFE-014"))

    def test_tsafe001_fails_an_endpoint_that_ignores_the_terminal_declaration(self):
        answers = {
            "released": ({"status": "completed", "output": {"reset": True, "latched": False}},
                         "never reset on the endpoint that engaged it"),
            "other reason": ({"status": "rejected", "error": {"mhs_code": RESET_REFUSED, "details": {
                "reason": "bridge_refused"}}}, "not a rejected MHS.SAFETY.RESET_REFUSED with details.reason "
                                               "terminal_estop"),
            "other statement": ({"status": "rejected", "error": {"mhs_code": RESET_REFUSED, "details": {
                "reason": "terminal_estop", "terminal": "something else", "latched": True}}},
                "does not carry the declared reason"),
        }
        for name, (answer, expected) in answers.items():
            with self.subTest(answer=name):
                server, client = shared(Session, _ResetClient, answer=answer)
                self.addCleanup(close_server, server)
                report = run_suite(client, profile="MHS-Sim", level="CL3")
                case = entry(report, "TSAFE-001")
                self.assertEqual(case["status"], "fail", case)
                self.assertIn(expected, case["detail"])

    def test_safe041_skips_a_terminal_device_without_stopping_it(self):
        class Gated(Session):
            @interlock("door", description="door closed", blocks=["cap.device.configure.v1"], source="simulated")
            def door(self):
                return True

        report, _calls = suite(Gated)
        case = entry(report, "SAFE-041")
        self.assertEqual(case["status"], "skip", case)
        self.assertIn("declares a terminal e-stop", case["detail"])
        stops = [item for item in report["limitations"] if "was engaged by" in item]
        self.assertTrue(stops and "SAFE-041" not in stops[0], stops)


# ---------------------------------------------------------------------------
# family drivers
# ---------------------------------------------------------------------------


SWITCH_ON_SPEC = {"service": "/spine/switch_on", "type": "spine_msgs/srv/SwitchOn",
                  "success": {"path": "success", "equals": True},
                  "result": {"map": {"switched_on": "success"}}}
SWITCH_OFF_SPEC = {"service": "/spine/switch_off", "type": "spine_msgs/srv/SwitchOff",
                   "success": {"path": "success", "equals": True},
                   "result": {"map": {"switched_off": "success"}}}


class SpinePeer:
    def __init__(self):
        self.state = "SwitchedOn"
        self.transport = RecordingRosTransport(self.handle)

    def handle(self, message):
        if message["op"] != "call_service":
            return None
        if message["service"] == "/spine/switch_on":
            self.state = "SwitchedOn"
        elif message["service"] == "/spine/switch_off":
            self.state = "SwitchedOff"
        return {"op": "service_response", "id": message["id"], "service": message["service"], "result": True,
                "values": {"success": True}}


def ros_spine(**extra):
    peer = SpinePeer()
    attributes = {
        "device_id": "ros/spine", "device_kind": "motion.axis", "mode": "hardware", "risk": "R1",
        "safe_state": "The spine is switched off",
        "commands": {SWITCH_ON: copy.deepcopy(SWITCH_ON_SPEC), SWITCH_OFF: copy.deepcopy(SWITCH_OFF_SPEC)},
        "actions": {SWITCH_ON: Action(name="switch_on", reenable=True,
                                      output={"switched_on": Field("boolean", description="acknowledged")}),
                    SWITCH_OFF: Action(name="switch_off", safe_state=True,
                                       output={"switched_off": Field("boolean", description="acknowledged")})},
        "safety_bindings": {"estop": copy.deepcopy(SWITCH_OFF_SPEC)},
        "backends": {"fake": lambda: peer.transport},
    }
    attributes.update(extra)
    return type("RosSpine", (RosDriver,), attributes), peer


class FamilyDriverTests(unittest.TestCase):
    def test_a_ros_reenable_is_declared_refused_while_latched_and_never_run_by_reset(self):
        cls, peer = ros_spine()
        self.assertEqual(cls.driver_model().safety_manifest()["estop"]["reenable"], SWITCH_ON)
        driver = cls(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        self.assertEqual(client.estop()["status"], "completed")
        self.assertEqual(peer.state, "SwitchedOff")
        refused = client.command(SWITCH_ON)
        self.assertEqual(support.code(refused), ESTOP_ENGAGED, refused)
        receipt = client.reset()["result"]
        self.assertEqual(receipt["output"]["reenable"], SWITCH_ON, receipt)
        self.assertEqual(peer.state, "SwitchedOff")
        self.assertEqual(client.command(SWITCH_ON)["status"], "completed")
        self.assertEqual(peer.state, "SwitchedOn")

    def test_a_reset_binding_on_the_reenable_target_is_a_definition_error(self):
        cls, _peer = ros_spine(safety_bindings={"estop": copy.deepcopy(SWITCH_OFF_SPEC),
                                                "reset": copy.deepcopy(SWITCH_ON_SPEC)})
        with self.assertRaises(DriverDefinitionError) as caught:
            cls.driver_model()
        self.assertIn("a reset never re-arms the device", str(caught.exception))

    def test_a_reset_binding_on_another_target_is_accepted(self):
        # The SDK compares the native target only; a reset binding that re-arms through another target stays
        # an author obligation checked by review (CORE-086).
        reset_spec = dict(SWITCH_ON_SPEC, service="/spine/fault_reset", type="spine_msgs/srv/FaultReset")
        cls, _peer = ros_spine(safety_bindings={"estop": copy.deepcopy(SWITCH_OFF_SPEC), "reset": reset_spec})
        self.assertEqual(cls.driver_model().reenable, SWITCH_ON)


# ---------------------------------------------------------------------------
# review s7: a decorated reset hook beside a re-enable (S7-01), late devices (S7-02), the empty input
# (S7-03), a re-enable in flight when the e-stop lands (S7-04), a replayed e-stop on a new endpoint (S7-05)
# and a permit-gated re-enable in TSAFE-001 (S7-07)
# ---------------------------------------------------------------------------


class Sneaky(Drive):
    """Probe A of review s7: a declared re-enable plus an @reset hook that switches the drive on itself."""

    @reset
    def rearm(self):
        self.native.switch_on()


class ClearsFaultsInReset(Drive):
    """A reset hook that only clears faults is refused as well: that recovery belongs in the re-enable."""

    @reset
    def clear(self):
        self.native.calls.append("clear_faults")


class ResetHookWithoutDeclaration(DriveWithoutDeclaration):
    """No re-enable declared, so an @reset hook is allowed (the start-up case tampers the manifest)."""

    @reset
    def clear(self):
        self.native.calls.append("clear_faults")


class ResetHookRuleTests(unittest.TestCase):
    def test_a_decorated_reenable_driver_with_a_reset_hook_is_refused_at_definition(self):
        for cls in (Sneaky, ClearsFaultsInReset):
            with self.subTest(driver=cls.__name__):
                with self.assertRaises(DriverDefinitionError) as caught:
                    cls.driver_model()
                self.assertIn("has no @reset hook", str(caught.exception))
                self.assertIn("belongs in the re-enable action", str(caught.exception))
                with self.assertRaises(DriverDefinitionError):
                    cls(backend="fake")  # probe A2: nothing can be served, so TSAFE-001 never sees it

    def test_counterfactual_the_hook_alone_or_the_reenable_alone_is_accepted(self):
        self.assertIsNone(ResetHookWithoutDeclaration.driver_model().reenable)
        self.assertEqual(ResetHookWithoutDeclaration.driver_model().reset_attr, "clear")
        self.assertEqual(Drive.driver_model().reenable, SWITCH_ON)
        self.assertIsNone(Drive.driver_model().reset_attr)
        self.assertEqual(ResetHookWithoutDeclaration(backend="fake").reset_hook, "clear")
        self.assertIsNone(Drive(backend="fake").reset_hook)

    def test_startup_refuses_a_declared_reenable_on_a_bridge_that_runs_a_reset_hook(self):
        device = build_device(ResetHookWithoutDeclaration(backend="fake"))
        device.safety.estop["reenable"] = SWITCH_ON
        for strict in (True, False):
            with self.subTest(strict=strict):
                with self.assertRaises(ValueError) as caught:
                    MHSServer(DEFAULT_ENDPOINT_ID, [device], strict=strict)
                self.assertIn("runs the @reset hook clear()", str(caught.exception))

    def test_the_probe_a_endpoint_never_rearms_in_its_reset(self):
        # What review s7 showed (state 'on' after the reset) cannot be built any more; the accepted shape
        # keeps the drive off until the re-enable.
        driver, server, client = served(Drive)
        self.addCleanup(close_server, server)
        client.estop()
        self.assertEqual(client.reset()["result"]["status"], "completed")
        self.assertEqual(driver.native.state, "off")


class LateDeviceTests(unittest.TestCase):
    def late(self, strict, change):
        server = MHSServer(DEFAULT_ENDPOINT_ID, [build_device(DriveWithoutDeclaration(backend="fake"))],
                           strict=strict)
        self.addCleanup(close_server, server)
        other = support.Client(server)                      # a session on the device given at construction
        driver = Drive(backend="fake")
        device = build_device(driver)
        change(device)
        server.devices[device.device_id] = device
        return driver, server, other, device.device_id

    def test_a_late_device_with_a_malformed_reenable_is_refused_but_still_stopped(self):
        for strict in (True, False):
            with self.subTest(strict=strict):
                driver, server, other, late_id = self.late(strict, lambda d: d.safety.estop.update(reenable=MOVE))
                opened = other.call("mhs.session.open", {"device_ids": [late_id], "mode": "simulated", "ttl_s": 60,
                                                         "principal": {"id": "late", "kind": "agent"}})
                self.assertEqual(opened["error"]["data"]["mhs_code"], "MHS.ADAPTER.MANIFEST_INVALID", opened)
                self.assertEqual(opened["error"]["data"]["details"]["reason"], "estop_recovery_invalid")
                hello = other.call("mhs.hello", {})
                self.assertNotIn(late_id, [item.get("device_id") for item in hello["result"]["devices"]])
                # The e-stop needs no session (CORE-076) and still reaches the late device.
                stopped = other.call("mhs.safety.estop", {"device_id": late_id, "reason": "test",
                                                          "deadline_ms": 5000})
                self.assertEqual(stopped["result"]["status"], "completed", stopped)
                self.assertEqual(driver.native.state, "off")
                self.assertEqual([item for item in driver.native.calls if isinstance(item, tuple)], [])
                reset = other.call("mhs.safety.reset", {"session_id": other.session_id, "device_id": late_id,
                                                        "deadline_ms": 5000})
                self.assertNotIn("result", reset)            # refused: never "reenable": MOVE
                self.assertTrue(server._latched.get(late_id))

    def test_a_late_well_formed_declaration_is_served(self):
        for strict in (True, False):
            with self.subTest(strict=strict):
                driver, server, _other, late_id = self.late(strict, lambda d: None)
                client = support.Client(server, late_id)
                client.estop()
                receipt = client.reset()["result"]
                self.assertEqual(receipt["output"]["reenable"], SWITCH_ON, receipt)
                self.assertEqual(driver.native.state, "off")

    def test_an_exempt_or_unbound_name_is_never_reported_as_the_reenable(self):
        from mhs.server import _estop_reenable

        device = build_device(Drive(backend="fake"))
        self.assertEqual(_estop_reenable(device), SWITCH_ON)
        for name in (SWITCH_OFF, "cap.motion.stop.v1", "x-cap.test.unbound.v1", ""):
            with self.subTest(name=name):
                device.safety.estop["reenable"] = name
                self.assertIsNone(_estop_reenable(device))


class EmptyInputTests(unittest.TestCase):
    SCHEMAS = {
        "oneOf": {"type": "object", "oneOf": [{"required": ["a"]}, {"required": ["b"]}]},
        "anyOf": {"type": "object", "anyOf": [{"required": ["a"]}]},
        "allOf": {"type": "object", "allOf": [{"required": ["a"]}]},
        "not an object": {"type": "string"},
        "minProperties": {"type": "object", "minProperties": 1},
        "top-level required": {"type": "object", "properties": {"a": {"type": "number"}}, "required": ["a"]},
    }

    def test_the_validator_decides_whether_the_empty_object_is_accepted(self):
        from mhs.driver.model import empty_input_problem

        for name, schema in self.SCHEMAS.items():
            with self.subTest(schema=name):
                self.assertIsNotNone(empty_input_problem(schema))
        for schema in (None, {}, {"type": "object", "properties": {}, "additionalProperties": False},
                       {"type": "object", "properties": {"a": {"type": "object", "required": ["x"]}}}):
            self.assertIsNone(empty_input_problem(schema), schema)

    def test_startup_refuses_a_reenable_whose_schema_requires_input_anywhere(self):
        for name, schema in self.SCHEMAS.items():
            with self.subTest(schema=name):
                device = build_device(Drive(backend="fake"))
                device.bindings_of(SWITCH_ON)[0].input_schema = copy.deepcopy(schema)
                with self.assertRaises(ValueError) as caught:
                    MHSServer(DEFAULT_ENDPOINT_ID, [device], strict=False)
                self.assertIn("does not accept an empty input", str(caught.exception))


class SlowFakeDrive(FakeDrive):
    """Commands already sent to the drive cannot be withdrawn: they ignore cancellation (review s7, S7-04).

    ``slow``: a switch-on waits for ``release`` and then switches the drive on.  ``slow_move``: a move waits for
    ``release`` and then, like an upstream cancel path that re-arms after its own quick-stop (the Franka spine,
    spine_controller.py:404-434), switches the drive back on and reports the move as not done.
    """

    def __init__(self, **options):
        super().__init__(**options)
        import threading

        self.entered = threading.Event()
        self.release = threading.Event()
        self.slow = False
        self.slow_move = False

    def switch_on(self):
        if self.slow:
            self.entered.set()
            self.release.wait(10)
        return super().switch_on()

    def move(self, position):
        if self.slow_move:
            self.calls.append(("move", position))
            self.entered.set()
            self.release.wait(10)
            self.calls.append("rearm_after_cancel")
            self.state = "on"
            return False
        return super().move(position)


class SlowDrive(Drive):
    backends = {"fake": SlowFakeDrive}
    estop_latency_ms = 300


class SlowDriveWithoutDeclaration(DriveWithoutDeclaration):
    backends = {"fake": SlowFakeDrive}
    estop_latency_ms = 300


class InFlightReenableTests(unittest.TestCase):
    def start(self, driver_class):
        import threading

        driver, server, client = served(driver_class)
        self.addCleanup(close_server, server)
        client.estop()
        self.assertEqual(client.reset()["result"]["status"], "completed")
        driver.native.slow = True
        sender = support.Client(server)
        thread = threading.Thread(target=lambda: sender.command(SWITCH_ON, deadline_ms=5000), daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(driver.native.release.set)
        self.assertTrue(driver.native.entered.wait(5))    # the switch-on is at the drive
        self.sender = thread
        return driver, server, client

    def wait_confirmed(self, client, seconds=5.0):
        import time

        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if status(client)["estop"].get("confirmed") is True:
                return True
            time.sleep(0.02)
        return False

    def test_a_reenable_that_lands_after_the_stop_is_stopped_again_before_the_stop_is_confirmed(self):
        driver, _server, client = self.start(SlowDrive)
        receipt = client.estop()
        # The switch-on is still at the drive: the stop is not reported achieved (SAFE-040, CORE-077).
        self.assertEqual((receipt["status"], support.code(receipt)), ("failed", "MHS.SAFETY.SAFE_STATE_UNREACHED"),
                         receipt)
        self.assertEqual(details(receipt)["reason"], "command_in_flight")
        self.assertTrue(details(receipt)["retrying"])
        self.assertIs(receipt["output"]["safe_state_achieved"], False)
        self.assertIs(status(client)["estop"].get("confirmed"), False)
        driver.native.release.set()                        # the switch-on lands after the first stop
        self.assertTrue(self.wait_confirmed(client))
        self.assertEqual(driver.native.state, "off")       # the stop was sent again after it
        # Each run of the stop path calls the native stop and the achieved_by switch-off: the first run, the
        # late switch-on, then the run after it.
        calls = [item for item in driver.native.calls if item in ("switch_on", "switch_off")]
        self.assertEqual(calls[-5:], ["switch_off", "switch_off", "switch_on", "switch_off", "switch_off"], calls)

    def test_a_reenable_that_settles_inside_the_budget_gives_a_completed_estop_with_the_device_off(self):
        import threading

        driver, _server, client = self.start(SlowDrive)
        threading.Timer(0.05, driver.native.release.set).start()
        receipt = client.estop()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIs(receipt["output"]["safe_state_achieved"], True)
        self.sender.join(10)                               # the switch-on has landed by now
        self.assertIn("switch_on", driver.native.calls)
        self.assertEqual(driver.native.state, "off")       # and the stop that confirmed came after it

    def test_counterfactual_an_undeclared_switch_on_in_flight_leaves_the_drive_on(self):
        # Without the declaration the endpoint does not know that the in-flight command is the opposite of
        # the stop: the e-stop is reported achieved and the late switch-on leaves the drive on.  This is why
        # the stop path waits for the declared re-enable.
        driver, _server, client = self.start(SlowDriveWithoutDeclaration)
        receipt = client.estop()
        self.assertEqual(receipt["status"], "completed", receipt)
        driver.native.release.set()
        import time

        end = time.monotonic() + 5
        while driver.native.state != "on" and time.monotonic() < end:
            time.sleep(0.02)
        self.assertEqual(driver.native.state, "on")
        self.assertIs(status(client)["estop"].get("confirmed"), True)


class InFlightCommandTests(unittest.TestCase):
    """CORE-086: on a device that declares a re-enable, every command in flight at the e-stop is waited for."""

    def start(self, driver_class):
        import threading

        driver, server, client = served(driver_class)
        self.addCleanup(close_server, server)
        driver.native.slow_move = True
        sender = support.Client(server)
        thread = threading.Thread(target=lambda: sender.command(MOVE, {"position": 0.5}, deadline_ms=5000),
                                  daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(driver.native.release.set)
        self.assertTrue(driver.native.entered.wait(5))    # the move is at the drive
        self.sender = thread
        return driver, server, client

    def finish(self, driver, client):
        driver.native.release.set()                        # the move's cancel path re-arms the drive
        self.sender.join(10)
        self.assertIn("rearm_after_cancel", driver.native.calls)
        return InFlightReenableTests.wait_confirmed(self, client)

    def test_a_move_whose_cancel_path_rearms_is_stopped_again_before_the_stop_is_confirmed(self):
        driver, _server, client = self.start(SlowDrive)
        receipt = client.estop()
        self.assertEqual((receipt["status"], details(receipt)["reason"]), ("failed", "command_in_flight"), receipt)
        self.assertEqual(len(details(receipt)["awaiting_operations"]), 1)
        self.assertIs(status(client)["estop"].get("confirmed"), False)
        self.assertTrue(self.finish(driver, client))
        self.assertEqual(driver.native.state, "off")       # the second stop came after the re-arm
        tail = driver.native.calls[driver.native.calls.index("rearm_after_cancel"):]
        self.assertIn("switch_off", tail)

    def test_counterfactual_without_a_declared_reenable_the_rearm_survives_a_confirmed_stop(self):
        # A device that declares no re-enable keeps the single run of the stop path: the e-stop is confirmed at
        # once, and the late re-arm of the cancel path leaves the drive on.
        driver, _server, client = self.start(SlowDriveWithoutDeclaration)
        receipt = client.estop()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(self.finish(driver, client))
        self.assertEqual(driver.native.state, "on")


ZERO = "x-cap.test.meter-zero.v1"
METER_ON = "x-cap.test.meter-power-on.v1"
INTENSITY = "cap.measure.intensity.v1"


class FakeMeter:
    """A detector whose stop switches its supply off; a reading or a zeroing can hang (they ignore cancellation)."""

    def __init__(self, **_options):
        import threading

        self.state = "on"
        self.calls: list[object] = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.slow_read = False
        self.slow_zero = False

    def switch_off(self):
        self.calls.append("switch_off")
        self.state = "off"

    def switch_on(self):
        self.calls.append("switch_on")
        self.state = "on"

    def read(self):
        if self.slow_read:
            self.entered.set()
            self.release.wait(10)
        return 42.0

    def zero(self):
        if self.slow_zero:
            self.entered.set()
            self.release.wait(10)
        self.calls.append("zero")


class Meter(Driver):
    device_id, device_kind, mode, risk = "test/meter", "instrument.spectrometer", "hardware", "R1"
    backends = {"fake": FakeMeter}
    safe_state = "the detector supply is switched off"
    estop_latency_ms = 300

    @action(cap=INTENSITY, description="one reading of the detector")
    def measure(self):
        return {"intensity": self.native.read()}

    @action(name=ZERO, output={"zeroed": Field("boolean", description="the detector was zeroed")})
    def zero(self):
        self.native.zero()
        return {"zeroed": True}

    @action(name=METER_ON, reenable=True, output={"state": Field("string", description="supply state")})
    def power_on(self):
        self.native.switch_on()
        return {"state": self.native.state}

    @estop
    def stop(self):
        self.native.switch_off()


class InFlightReadTests(unittest.TestCase):
    """Review s7 re-check, N-01: reads (as the latch counts them) are not waited for; effectful commands are."""

    def start(self, flag, capability_id):
        import threading

        driver, server, client = served(Meter)
        self.addCleanup(close_server, server)
        setattr(driver.native, flag, True)
        sender = support.Client(server)
        thread = threading.Thread(target=lambda: sender.command(capability_id, {}, deadline_ms=5000), daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(driver.native.release.set)
        self.assertTrue(driver.native.entered.wait(5))    # the command is at the device
        return driver, server, client

    def test_a_hung_read_does_not_delay_the_confirmation(self):
        driver, _server, client = self.start("slow_read", INTENSITY)
        receipt = client.estop()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIs(status(client)["estop"].get("confirmed"), True)
        self.assertEqual(driver.native.state, "off")

    def test_a_hung_effectful_command_still_delays_it(self):
        driver, _server, client = self.start("slow_zero", ZERO)
        receipt = client.estop()
        self.assertEqual((receipt["status"], details(receipt)["reason"]), ("failed", "command_in_flight"), receipt)
        self.assertIs(status(client)["estop"].get("confirmed"), False)
        driver.native.release.set()
        self.assertTrue(InFlightReenableTests.wait_confirmed(self, client))
        self.assertEqual(driver.native.state, "off")


class ReplayedEstopTests(unittest.TestCase):
    def test_a_replayed_estop_on_a_new_endpoint_makes_it_terminal_too(self):
        # S7-05 (probe3): a restored latch is reset as usual until a stop path starts on the new endpoint,
        # including the rerun that a replay of the latching e-stop's command_id causes (CORE-171).
        state_dir = support.temp_dir(self)
        _driver, server, client = served(Session, state_dir=state_dir)
        command_id = client.estop()["command_id"]
        close_server(server)
        fresh, server2, client2 = served(Session, state_dir=state_dir)
        self.addCleanup(close_server, server2)
        replay = client2.rpc("mhs.safety.estop", {"session_id": client2.session_id, "device_id": client2.device_id,
                                                  "reason": "replay", "command_id": command_id, "deadline_ms": 3000})
        self.assertIs(replay.get("replayed"), True, replay)
        self.assertTrue(fresh.native.closed)
        receipt = client2.reset()["result"]
        self.assertEqual((receipt["status"], details(receipt)["reason"]), ("rejected", "terminal_estop"), receipt)
        self.assertIs(status(client2)["estop"].get("terminated"), True)


class PermitGatedReenableTests(unittest.TestCase):
    def test_tsafe001_sends_nothing_when_the_reenable_permit_cannot_be_obtained(self):
        from types import SimpleNamespace

        from mhs.conformance import tests_core

        binding = SimpleNamespace(capability_id=SWITCH_ON, device_id="test/drive", resource="main",
                                  requires_permit=True, manifest={"mode": "hardware"})
        sent = []
        ctx = SimpleNamespace(
            primary_device={"device_id": "test/drive", "mode": "hardware",
                            "safety": {"estop": {"latching": True, "kind": "software", "reenable": SWITCH_ON}}},
            options=SimpleNamespace(approvals=[]), estop_kind=lambda: "software",
            bindings_of=lambda device_id, capability_id: [binding],
            estop=lambda *args, **kwargs: sent.append("estop"), reset=lambda *a, **k: sent.append("reset"))
        outcome = tests_core.safe_002(ctx)
        self.assertEqual(outcome.status, "skip", outcome)
        self.assertIn("needs a permit", outcome.detail)
        self.assertIn("Nothing was sent", outcome.detail)
        self.assertEqual(sent, [])
        self.assertIsNone(tests_core._reenable_permit_unavailable(
            SimpleNamespace(options=SimpleNamespace(approvals=[{"principal": "op"}])), binding))
        simulated = SimpleNamespace(**dict(vars(binding), manifest={"mode": "simulated"}))
        self.assertIsNone(tests_core._reenable_permit_unavailable(ctx, simulated))

    def test_a_permit_failure_after_the_estop_and_reset_is_a_verdict(self):
        from mhs.conformance import tests_core

        def no_permit(*_args, **_kwargs):
            raise tests_core._NoApprovals("no approvals")

        with mock.patch("mhs.conformance.tests_core._send_reenable", side_effect=no_permit):
            report, _calls = suite(Drive)
        case = entry(report, "TSAFE-001")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("could not obtain after the e-stop and the reset", case["detail"])


if __name__ == "__main__":
    unittest.main()
