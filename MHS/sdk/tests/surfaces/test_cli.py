"""The ``mhs`` CLI (WP-08 08b): the exit-code table, serve, e-stop without a mode, operator reset, validate.

Ports of the reviewer's SURF-08 / TESTS-12 repros (``mhs-review-scratch/integration-surfaces``):
``mhs safety --estop`` failed on a hardware device without ``--mode``; a
refused connection was ``MHS.OUTCOME.TIMEOUT`` with exit 3 for every error;
a rejection exited 2; malformed ``--input`` exited 1; ``mhs devices`` printed
549 lines for one device; ``mhs conform`` hid why a level was capped.
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import tempfile
import time
import unittest
import warnings
from pathlib import Path
from unittest import mock

from mhs import _ids
from mhs.adapter import close_server, load
from mhs.cli import build_parser, exit_code_for
from mhs.errors import MHSError

from . import _support as s

AGENT_TOKEN = "agent-token-0123456789"
OPERATOR_TOKEN = "operator-token-9876543210"


def _load_thermostat(**options):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load(s.THERMOSTAT, log_ready=False, **options)


class _Servers(unittest.TestCase):
    """Loopback HTTP endpoints shared by a test class."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="mhs-cli-")
        cls.dir = Path(cls.tmp.name)
        for name, token in (("agent", AGENT_TOKEN), ("operator", OPERATOR_TOKEN), ("wrong", "not-a-token")):
            (cls.dir / f"{name}.token").write_text(token + "\n", encoding="utf-8")
        cls.spec, cls.server = s.reference("conveyor")
        cls.http = s.Http(cls.server).__enter__()
        cls.hw_spec, cls.hw_server = s.reference("conveyor", hardware=True)
        cls.hw_http = s.Http(cls.hw_server).__enter__()
        cls.thermo = _load_thermostat(auth_tokens={AGENT_TOKEN: {"id": "agent:test", "kind": "agent"},
                                                   OPERATOR_TOKEN: {"id": "operator:test", "kind": "operator"}})
        cls.thermo_http = s.Http(cls.thermo).__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.thermo_http.__exit__(None, None, None)
        close_server(cls.thermo)
        cls.hw_http.__exit__(None, None, None)
        cls.hw_spec.close()
        cls.http.__exit__(None, None, None)
        cls.spec.close()
        cls.tmp.cleanup()

    def token(self, name: str) -> str:
        return str(self.dir / f"{name}.token")


class ExitCodeTableTest(_Servers):
    """One table, every command: 0 ok, 1 refused, 2 usage, 3 transport, 4 auth, 5 conformance."""

    def test_exit_code_table(self):
        url, hw, auth = self.http.url, self.hw_http.url, self.thermo_http.url
        step = ["call", "-e", url, "-c", "cap.world.step.v1"]
        table = [
            ("version", ["version"], 0),
            ("devices --json", ["devices", "-e", url, "--json"], 0),
            ("call completed", [*step, "-i", '{"ticks": 1}', "--json"], 0),
            ("estop on hardware without --mode", ["estop", "-e", hw, "--json"], 0),
            ("token accepted", ["devices", "-e", auth, "--token-file", self.token("agent"), "--json"], 0),
            ("conform reaches the level", ["conform", str(s.THERMOSTAT), "--level", "CL3"], 0),
            ("rejected receipt", [*step, "-i", '{"ticks": 1000000000}', "--json"], 1),
            ("endpoint error: unknown capability", ["call", "-e", url, "-c", "cap.no.such.v1", "--json"], 1),
            ("invalid document", ["validate", str(self.dir / "agent.token"), "--schema", "device"], 1),
            ("no command", [], 2),
            ("unknown flag", ["devices", "--bogus"], 2),
            ("--input is not JSON", [*step, "-i", "{not json"], 2),
            ("--input is not an object", [*step, "-i", "[1]"], 2),
            ("unsupported endpoint", ["devices", "-e", "ftp://example.invalid"], 2),
            ("missing code file", ["run", str(self.dir / "missing.py")], 2),
            ("serve nothing", ["serve", str(self.dir / "no-such-driver")], 2),
            ("transport: connection refused", ["devices", "-e", s.closed_port_url(), "--json"], 3),
            ("auth: no token", ["devices", "-e", auth, "--json"], 4),
            ("auth: wrong token", ["devices", "-e", auth, "--token-file", self.token("wrong"), "--json"], 4),
            ("auth: reset without a terminal",
             ["reset", "-e", auth, "--operator-token-file", self.token("operator")], 4),
            ("auth: hardware backend not allowed", ["serve", str(s.THERMOSTAT), "--backend", "hardware"], 4),
            ("conformance below target", ["conform", str(s.THERMOSTAT), "--level", "CL4"], 5),
        ]
        with mock.patch("mhs.cli._interactive", return_value=False):
            for name, argv, expected in table:
                with self.subTest(name):
                    code, out, err = s.run_cli(*argv)
                    self.assertEqual(code, expected, f"{argv}\nstdout: {out[-800:]}\nstderr: {err[-800:]}")

    def test_conform_an_authenticated_endpoint_with_a_token_file(self):
        auth = self.thermo_http.url
        code, out, err = s.run_cli("conform", "-e", auth, "--token-file", self.token("agent"), "--level", "CL0",
                                   "--json")
        self.assertEqual(code, 0, f"stdout: {out[-800:]}\nstderr: {err[-800:]}")
        self.assertIsNotNone(json.loads(out)["level_achieved"])
        self.assertEqual(s.run_cli("conform", "-e", auth, "--level", "CL0")[0], 4)  # no token: auth exit
        self.assertEqual(s.run_cli("conform", "--command", "python3 -m mhs serve x --stdio",
                                   "--token-file", self.token("agent"))[0], 2)  # a token needs HTTP

    def test_exit_code_for_maps_error_codes(self):
        for code, expected in (("MHS.TRANSPORT.UNAVAILABLE", 3), ("MHS.TRANSPORT.CLOSED", 3),
                               ("MHS.OUTCOME.TIMEOUT", 3), ("MHS.OUTCOME.UNKNOWN", 3),
                               ("MHS.AUTH.UNAUTHENTICATED", 4), ("MHS.AUTH.FORBIDDEN", 4),
                               ("MHS.DEVICE.UNKNOWN", 1), ("MHS.CAPABILITY.UNKNOWN", 1),
                               ("MHS.SESSION.EXPIRED", 1)):
            with self.subTest(code):
                self.assertEqual(exit_code_for(MHSError(code, "x")), expected)

    def test_a_receipt_maps_to_0_or_1_except_auth_refusals(self):
        from mhs.cli import _receipt_exit
        from mhs.client import MHSRejected

        for receipt, expected in (({"status": "completed"}, 0), ({"status": "running"}, 0),
                                  ({"status": "rejected", "error": {"mhs_code": "MHS.SAFETY.ENVELOPE_VIOLATION"}}, 1),
                                  ({"status": "unknown"}, 1),
                                  ({"status": "failed", "error": {"mhs_code": "MHS.TRANSPORT.CLOSED"}}, 1),
                                  ({"status": "rejected", "error": {"mhs_code": "MHS.AUTH.FORBIDDEN"}}, 4),
                                  ({"status": "rejected", "error": {"mhs_code": "MHS.AUTH.HARDWARE_DISABLED"}}, 4)):
            with self.subTest(receipt=receipt):
                self.assertEqual(_receipt_exit(receipt), expected)
                if expected:
                    self.assertEqual(exit_code_for(MHSRejected(receipt)), expected)

    def test_rejection_is_a_receipt_on_stdout(self):
        code, out, _err = s.run_cli("call", "-e", self.http.url, "-c", "cap.world.step.v1",
                                    "-i", '{"ticks": 1000000000}', "--json")
        self.assertEqual(code, 1)
        receipt = json.loads(out)
        self.assertEqual(receipt["status"], "rejected")
        self.assertTrue(receipt["error"]["mhs_code"].startswith(("MHS.SAFETY.", "MHS.CAPABILITY.")))

    def test_closed_port_reports_transport_unavailable(self):
        code, out, _err = s.run_cli("devices", "-e", s.closed_port_url(), "--json")
        self.assertEqual(code, 3)
        error = json.loads(out)["error"]
        self.assertEqual(error["mhs_code"], "MHS.TRANSPORT.UNAVAILABLE")
        self.assertTrue(error["retryable"])
        self.assertFalse(error["data"]["may_have_effect"])

    def test_closed_port_through_python_dash_m(self):
        # The acceptance command, as a person would type it.
        result = subprocess.run([sys.executable, "-m", "mhs", "devices", "-e", s.closed_port_url(), "--json"],
                                capture_output=True, text=True, timeout=60, env=s.child_env())
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(json.loads(result.stdout)["error"]["mhs_code"], "MHS.TRANSPORT.UNAVAILABLE")


class EstopTest(_Servers):
    """``mhs estop`` needs no session and no mode (SURF-08: MODE_MISMATCH on hardware)."""

    def test_estop_on_fake_hardware_without_mode(self):
        manifest = json.loads(s.run_cli("devices", "-e", self.hw_http.url, "--json")[1])["devices"][0]
        self.assertEqual(manifest["mode"], "hardware")
        code, out, err = s.run_cli("estop", "-e", self.hw_http.url, "operator panic stop", "--json")
        self.assertEqual(code, 0, err)
        receipts = json.loads(out)["receipts"]
        self.assertEqual([item["status"] for item in receipts], ["completed"])
        status = json.loads(s.run_cli("status", "-e", self.hw_http.url, "--json")[1])["devices"][0]
        self.assertTrue(status.get("estop_engaged", status["estop"].get("engaged")))
        # Latched: an effectful command is refused with a receipt (exit 1), never sent to the bridge.
        code, out, _err = s.run_cli("call", "-e", self.hw_http.url, "-c", "cap.world.step.v1",
                                    "-i", '{"ticks": 1}', "--json")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_legacy_safety_estop_needs_no_mode(self):
        spec, server = s.reference("conveyor", hardware=True)
        try:
            with s.Http(server) as http:
                code, out, err = s.run_cli("safety", "-e", http.url, "--estop", "panic stop", "--json")
                self.assertEqual(code, 0, err)
                self.assertEqual(json.loads(out)["receipts"][0]["status"], "completed")
        finally:
            spec.close()

    def test_estop_without_device_stops_every_device(self):
        spec, server = s.reference("lab", hardware=True)
        try:
            with s.Http(server) as http:
                code, out, _err = s.run_cli("estop", "-e", http.url, "--json")
                self.assertEqual(code, 0)
                receipts = json.loads(out)["receipts"]
                self.assertEqual(len(receipts), 3)
                self.assertEqual({item["status"] for item in receipts}, {"completed"})
                code, out, _err = s.run_cli("estop", "-e", http.url, "--device", "sample-mover")
                self.assertEqual(code, 0)
                self.assertEqual(len(out.strip().splitlines()), 1)
                self.assertIn("lab/sample-mover", out)
        finally:
            spec.close()

    def _engaged_devices(self, url: str) -> set[str]:
        statuses = json.loads(s.run_cli("status", "-e", url, "--json")[1])["devices"]
        return {item["device_id"].rsplit("/", 1)[-1] for item in statuses
                if item.get("estop_engaged", (item.get("estop") or {}).get("engaged"))}

    def test_an_unknown_device_never_keeps_the_others_running(self):
        # Verifier repro: a mistyped --device aborted the loop, so the devices after it were never stopped.
        for order in (["liquid_handler", "sample-mover", "plate-reader"],    # the typo first
                      ["sample-mover", "liquid_handler", "plate-reader"]):   # the typo in the middle
            with self.subTest(order=order):
                spec, server = s.reference("lab", hardware=True)
                try:
                    with s.Http(server) as http:
                        argv = ["estop", "-e", http.url, "mistyped device test"]
                        for name in order:
                            argv += ["--device", name]
                        code, out, err = s.run_cli(*argv, "--json")
                        self.assertEqual(code, 1, err)
                        payload = json.loads(out)
                        self.assertEqual([item["status"] for item in payload["receipts"]], ["completed"] * 2)
                        self.assertEqual([(item["device"], item["error"]["mhs_code"]) for item in payload["errors"]],
                                         [("liquid_handler", "MHS.DEVICE.UNKNOWN")])
                        self.assertEqual(self._engaged_devices(http.url), {"sample-mover", "plate-reader"})
                finally:
                    spec.close()

    def test_human_output_names_every_device_not_stopped(self):
        spec, server = s.reference("lab", hardware=True)
        try:
            with s.Http(server) as http:
                code, out, err = s.run_cli("estop", "-e", http.url, "--device", "sample-mover",
                                           "--device", "liquid_handler", "--device", "plate-reader")
                self.assertEqual(code, 1)
                lines = out.strip().splitlines()
                self.assertEqual(len(lines), 2)
                self.assertTrue(all(line.startswith("completed") for line in lines))
                self.assertIn("liquid_handler: MHS.DEVICE.UNKNOWN", err)
                self.assertIn("NOT stopped: liquid_handler", err)
                # An ambiguous name is reported, never guessed; nothing else was named, so nothing is sent.
                code, out, err = s.run_cli("estop", "-e", http.url, "--device", "lab", "--json")
                self.assertEqual(code, 1)
                payload = json.loads(out)
                self.assertEqual(payload["receipts"], [])
                self.assertEqual(payload["errors"][0]["error"]["mhs_code"], "MHS.HOST.DEVICE_AMBIGUOUS")
                self.assertNotIn("liquid-handler", self._engaged_devices(http.url))
        finally:
            spec.close()

    def test_a_lost_stop_is_exit_3_and_the_others_are_still_sent(self):
        from mhs.client import MHSClient

        real = MHSClient.estop

        def flaky(client, reason, device_id=None, **kwargs):
            if device_id and device_id.endswith("/liquid-handler"):
                raise MHSError("MHS.TRANSPORT.CLOSED", "connection reset")
            return real(client, reason, device_id=device_id, **kwargs)

        spec, server = s.reference("lab", hardware=True)
        try:
            with s.Http(server) as http:
                with mock.patch.object(MHSClient, "estop", flaky):
                    code, out, _err = s.run_cli("estop", "-e", http.url, "--json")
                self.assertEqual(code, 3)
                payload = json.loads(out)
                self.assertEqual(len(payload["receipts"]), 2)
                self.assertEqual(payload["errors"][0]["error"]["mhs_code"], "MHS.TRANSPORT.CLOSED")
                self.assertEqual(self._engaged_devices(http.url), {"plate-reader", "sample-mover"})
        finally:
            spec.close()


class ResetTest(_Servers):
    """``mhs reset``: an operator token and a person at an interactive terminal."""

    def _latch(self):
        code, _out, err = s.run_cli("estop", "-e", self.thermo_http.url, "--token-file", self.token("agent"))
        self.assertEqual(code, 0, err)

    def _engaged(self) -> bool:
        status = json.loads(s.run_cli("status", "-e", self.thermo_http.url, "--token-file", self.token("agent"),
                                      "--json")[1])["devices"][0]
        return bool(status.get("estop_engaged", status["estop"].get("engaged")))

    def test_operator_reset_at_a_terminal(self):
        self._latch()
        self.assertTrue(self._engaged())
        with mock.patch("mhs.cli._interactive", return_value=True), \
                mock.patch("mhs.cli._confirm", return_value=True) as confirm:
            code, out, err = s.run_cli("reset", "-e", self.thermo_http.url,
                                       "--operator-token-file", self.token("operator"), "--json")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(json.loads(out)["status"], "completed")
        self.assertIn("tutorial-thermostat", confirm.call_args[0][0])
        self.assertFalse(self._engaged())
        from mhs.client import connect

        with connect(self.thermo_http.url, token=AGENT_TOKEN) as client:
            receipts = client.export_evidence()["receipts"]
        reset = [item for item in receipts if item.get("capability_id") == "cap.internal.safety_reset.v1"]
        self.assertTrue(reset)
        # The endpoint binds the principal to the operator's token, not to the claim the CLI sends.
        self.assertEqual(reset[-1]["principal"]["id"], "operator:test")

    def test_not_confirmed_sends_nothing(self):
        self._latch()
        with mock.patch("mhs.cli._interactive", return_value=True), \
                mock.patch("mhs.cli._confirm", return_value=False):
            code, _out, err = s.run_cli("reset", "-e", self.thermo_http.url,
                                        "--operator-token-file", self.token("operator"))
        self.assertEqual(code, 1)
        self.assertIn("not confirmed", err)
        self.assertTrue(self._engaged())

    def test_reset_needs_the_operator_token_file(self):
        code, _out, err = s.run_cli("reset", "-e", self.thermo_http.url)
        self.assertEqual(code, 2)
        self.assertIn("--operator-token-file", err)

    def test_reset_needs_http(self):
        code, _out, err = s.run_cli("reset", "-e", "stdio:python3 -m mhs serve x --stdio",
                                    "--operator-token-file", self.token("operator"))
        self.assertEqual(code, 2)
        self.assertIn("HTTP", err)

    @unittest.skipUnless(hasattr(os, "fork") and sys.platform != "win32", "needs a POSIX pseudo-terminal")
    def test_reset_through_a_pseudo_terminal(self):
        import pty

        self._latch()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)  # fork() beside the HTTP threads; the child execs
            pid, fd = pty.fork()
        if pid == 0:  # pragma: no cover - the child process
            os.environ.update(s.child_env())
            os.execv(sys.executable, [sys.executable, "-m", "mhs", "reset", "-e", self.thermo_http.url,
                                      "--operator-token-file", self.token("operator")])
        output, answered, deadline = b"", False, time.monotonic() + 60
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([fd], [], [], 0.5)
                if not ready:
                    continue
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                output += chunk
                if b"Type 'reset'" in output and not answered:
                    os.write(fd, b"reset\n")
                    answered = True
        finally:
            _pid, status = os.waitpid(pid, 0)
            os.close(fd)
        self.assertTrue(answered, output.decode(errors="replace"))
        self.assertEqual(os.waitstatus_to_exitcode(status), 0, output.decode(errors="replace"))
        self.assertIn(b"completed", output)
        self.assertFalse(self._engaged())

    def test_hardware_reset_with_the_client_token_is_an_auth_exit(self):
        # A receipt refused with MHS.AUTH.* exits 4, like the same error raised without a receipt (it was 1).
        from ..safety._strict_support import arm_device, arm_server

        tokens = {AGENT_TOKEN: {"id": "agent:test", "kind": "agent"},
                  OPERATOR_TOKEN: {"id": "operator:test", "kind": "operator"}}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = arm_server(arm_device(mode="hardware", risk="R2"), strict=True, auth_tokens=tokens)[0]
        with s.Http(server) as http:
            agent = ("-e", http.url, "--token-file", self.token("agent"))
            self.assertEqual(s.run_cli("estop", *agent)[0], 0)
            with mock.patch("mhs.cli._interactive", return_value=True), \
                    mock.patch("mhs.cli._confirm", return_value=True):
                code, out, err = s.run_cli("reset", "-e", http.url, "--operator-token-file", self.token("agent"),
                                           "--json")
                self.assertEqual(code, 4, out + err)
                receipt = json.loads(out)
                self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]),
                                 ("rejected", "MHS.AUTH.FORBIDDEN"))
                status = json.loads(s.run_cli("status", *agent, "--json")[1])["devices"][0]
                self.assertTrue(status.get("estop_engaged", (status.get("estop") or {}).get("engaged")))
                code, out, err = s.run_cli("reset", "-e", http.url, "--operator-token-file",
                                           self.token("operator"), "--json")
                self.assertEqual(code, 0, out + err)

    def test_reset_refused_without_a_terminal(self):
        self._latch()
        result = subprocess.run(
            [sys.executable, "-m", "mhs", "reset", "-e", self.thermo_http.url,
             "--operator-token-file", self.token("operator")],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60, env=s.child_env())
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertIn("interactive terminal", result.stderr)
        self.assertTrue(self._engaged())


class OutputTest(_Servers):
    def test_devices_human_output_is_one_line_per_device(self):
        spec, server = s.reference("lab")
        try:
            with s.Http(server) as http:
                code, out, _err = s.run_cli("devices", "-e", http.url)
        finally:
            spec.close()
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(line.startswith("mhs://localhost:7400/lab/") for line in lines))
        self.assertTrue(all("capabilities" in line for line in lines))

    def test_devices_json_keeps_full_manifests(self):
        code, out, _err = s.run_cli("devices", "-e", self.http.url, "--json")
        self.assertEqual(code, 0)
        device = json.loads(out)["devices"][0]
        self.assertTrue(device["capabilities"][0]["input_schema"])

    def test_describe_and_inspect_alias(self):
        args = ("-e", self.thermo_http.url, "--token-file", self.token("agent"))
        code, out, _err = s.run_cli("describe", *args)
        self.assertEqual(code, 0)
        self.assertIn("risk: R2", out)
        self.assertIn("not certified", out)
        self.assertIn("setpoint 5..80 Cel", out)
        self.assertIn("fan_speed operator_required", out)
        self.assertIn("interlock: lid_closed", out)
        self.assertIn("gaps: transport replaced by fake backend", out)
        self.assertEqual(s.run_cli("inspect", *args)[1], out)
        device = json.loads(s.run_cli("describe", *args, "--device", "tutorial-thermostat", "--json")[1])
        self.assertIn("reference", device)

    def test_write_named_parameter(self):
        args = ("-e", self.thermo_http.url, "--token-file", self.token("agent"))
        code, out, _err = s.run_cli("write", "main", "--patch", '{"setpoint": 40}', *args, "--json")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["status"], "completed")
        code, out, _err = s.run_cli("write", "main", "--patch", '{"setpoint": 400}', *args, "--json")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        state = json.loads(s.run_cli("read", "main", *args, "--json")[1])
        self.assertEqual(state["state"]["setpoint"], 40)

    def test_conform_prints_failing_and_capping_ids(self):
        code, out, _err = s.run_cli("conform", str(s.THERMOSTAT), "--level", "CL4")
        self.assertEqual(code, 5)
        self.assertIn("capped at CL3", out)
        self.assertIn("FAIL FID-016", out)
        self.assertIn("below target: achieved CL3, required CL4; capped by FID-016 (fail)", out)

    def test_conform_json_stdout_is_one_json_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = Path(tmp) / "report.json"
            code, out, err = s.run_cli("conform", str(s.THERMOSTAT), "--level", "CL4", "--json", "-o", str(saved))
            self.assertEqual(code, 5)
            report = json.loads(out)  # nothing but the report on stdout, also below target
            self.assertEqual(report["level_achieved"], "CL3")
            self.assertIn("below target: achieved CL3, required CL4", err)
            self.assertIn(f"report saved: {saved}", err)
            self.assertTrue(saved.is_file())

    def test_conform_needs_one_subject(self):
        self.assertEqual(s.run_cli("conform")[0], 2)
        self.assertEqual(s.run_cli("conform", str(s.THERMOSTAT), "--reference", "lab")[0], 2)

    def test_parser_names_the_project(self):
        description = build_parser().description
        self.assertTrue(description.startswith(_ids.PROJECT_NAME))
        self.assertIn("not affiliated", description)
        self.assertNotIn("Model Hardware Standard", description)

    def test_version(self):
        code, out, _err = s.run_cli("version")
        self.assertEqual(code, 0)
        self.assertIn(_ids.SDK_VERSION, out)
        self.assertIn("protocol 1.0", out)


class DriverAndValidateTest(unittest.TestCase):
    def test_driver_subcommand_delegates(self):
        code, out, _err = s.run_cli("driver", "reference", str(s.THERMOSTAT), "--check")
        self.assertEqual(code, 0, out)
        code, out, _err = s.run_cli("driver", "catalog", "search", "thermal", "setpoint")
        self.assertEqual(code, 0)
        self.assertIn("cap.thermal.setpoint.v1", out)
        self.assertEqual(s.run_cli("driver", "check")[0], 2)

    def test_validate_driver_directory(self):
        code, out, _err = s.run_cli("validate", str(s.THERMOSTAT), "--json")
        self.assertEqual(code, 0, out)
        report = json.loads(out)
        self.assertEqual((report["kind"], report["valid"], report["problems"]), ("driver", True, []))

    def test_validate_documents(self):
        for name in ("reference.json", "site-limits.example.json", "driver.lock.json", "RESULT.json"):
            with self.subTest(name):
                code, out, _err = s.run_cli("validate", str(s.THERMOSTAT / name))
                self.assertEqual(code, 0, out)
                self.assertTrue(out.startswith("OK "))
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "mhs-adapter.json"
            broken.write_text(json.dumps({"adapter_id": "x", "bridges": []}), encoding="utf-8")
            code, out, _err = s.run_cli("validate", str(broken))
            self.assertEqual(code, 1)
            self.assertTrue(out.startswith("INVALID "))
            endpoints = Path(tmp) / "endpoints.json"
            endpoints.write_text(json.dumps({"endpoints": [{"transport": "http"}]}), encoding="utf-8")
            self.assertEqual(s.run_cli("validate", str(endpoints))[0], 1)
            unknown = Path(tmp) / "thing.json"
            unknown.write_text("{}", encoding="utf-8")
            self.assertEqual(s.run_cli("validate", str(unknown))[0], 2)


class ServeTest(unittest.TestCase):
    """``mhs serve <driver-dir>``: stdio, HTTP, MCP and the usage rules."""

    def test_serve_thermostat_stdio_answers_hello(self):
        hello = {"jsonrpc": "2.0", "id": 1, "method": "mhs.hello",
                 "params": {"client": {"name": "test", "version": "0"}, "protocol_versions": ["1.0"]}}
        result = subprocess.run([sys.executable, "-m", "mhs", "serve", str(s.THERMOSTAT), "--stdio"],
                                input=json.dumps(hello) + "\n", capture_output=True, text=True, timeout=60,
                                env=s.child_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout.splitlines()[0])
        self.assertEqual(response["id"], 1)
        self.assertEqual(response["result"]["mhs_version"], "1.0")
        self.assertEqual([item["device_id"] for item in response["result"]["devices"]],
                         ["mhs://localhost/tutorial-thermostat/fake"])
        self.assertIn('"mhs_ready": true', result.stderr)

    def test_serve_http_then_terminate(self):
        process = subprocess.Popen([sys.executable, "-m", "mhs", "serve", str(s.THERMOSTAT), "--port", "0"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=s.child_env())
        try:
            ready, _, _ = select.select([process.stdout], [], [], 30)
            self.assertTrue(ready, "mhs serve printed no ready line")
            url = json.loads(process.stdout.readline())["url"]
            code, out, err = s.run_cli("estop", "-e", url, "--json")
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)["receipts"][0]["status"], "completed")
            self.assertEqual(s.run_cli("devices", "-e", url)[0], 0)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()
        self.assertEqual(process.returncode, 0)

    def test_serve_mcp_projection(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
        result = subprocess.run([sys.executable, "-m", "mhs", "serve", str(s.THERMOSTAT), "--mcp"],
                                input="".join(json.dumps(item) + "\n" for item in messages), capture_output=True,
                                text=True, timeout=60, env=s.child_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = {item["id"]: item for item in map(json.loads, result.stdout.splitlines()) if "id" in item}
        tools = responses[2]["result"]["tools"]
        names = {tool["name"] for tool in tools}
        self.assertIn("mhs__estop", names)
        self.assertIn("mhs__tutorial_thermostat_fake__thermal_setpoint", names)
        self.assertNotIn("mhs__reset", names)  # operator tools stay hidden by default
        setpoint = next(tool for tool in tools if tool["name"].endswith("thermal_setpoint"))
        # describe_inputs=True, as python3 -m mhs.mcp serves.
        self.assertIn("Unit: Cel", setpoint["inputSchema"]["properties"]["target_temperature"]["description"])

    def test_serve_usage_rules(self):
        thermostat = str(s.THERMOSTAT)
        for argv in (["serve", thermostat, "--stdio", "--port", "0"],
                     ["serve", thermostat, "--operator-tools"],
                     ["serve", thermostat, "--stdio", "--token-file", "x"],
                     ["serve", thermostat, "--arm"],
                     ["serve", "conveyor", "--backend", "fake"],
                     ["serve", "lab", "--state-dir", "x"],
                     ["serve", "replay", "--stdio"],
                     ["serve", "replay", "--stdio", "--bundle", str(s.THERMOSTAT / "no-such-bundle.json")]):
            with self.subTest(argv=argv):
                code, _out, err = s.run_cli(*argv)
                self.assertEqual(code, 2, err)
                self.assertIn("usage error", err)

    def test_serve_refuses_a_non_loopback_bind_without_a_token(self):
        code, _out, err = s.run_cli("serve", str(s.THERMOSTAT), "--port", "0", "--host", "0.0.0.0")
        self.assertEqual(code, 4, err)
        self.assertIn("MHS.AUTH.TRANSPORT_INSECURE", err)


if __name__ == "__main__":
    unittest.main()
