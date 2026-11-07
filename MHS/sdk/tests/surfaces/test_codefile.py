"""Code files (WP-08 08b, SURF-03 / AF-04): ``mhs.run.lab``, ``mhs run`` and the ledger.

Port of the reviewer's ``codefile.py``: one client session was overwritten by
the next device, a rejected command did not raise, and nothing tied a run's
receipts together.  Here every device gets its own handle and session,
``check=True`` raises :class:`MHSRejected`, and every run leaves
``.mhs-run/<id>.json`` whose receipt ids verify against the endpoint's
evidence.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
import warnings
from pathlib import Path
from unittest import mock

from mhs.client import MHSClient, MHSRejected, add_observer, connect
from mhs.errors import MHSError
from mhs.run import LEDGER_VERSION, Ledger, lab, run_script, verify_ledger

from . import _support as s

LAB = "mhs://localhost:7400/lab/"
TRANSFER = ("cap.fluid.transfer.v1", {"source_well": "A1", "destination_well": "B1", "volume_ul": 50})
MOVE = ("cap.sample.move.v1", {"plate_id": "plate-001", "to": "reader"})
MEASURE = ("cap.measure.spectrum.v1", {"plate_id": "plate-001", "wavelengths_nm": [562]})

THREE_DEVICE_SCRIPT = textwrap.dedent("""\
    import sys
    from mhs.run import lab

    with lab(sys.argv[1]) as bench:
        bench["liquid-handler"].invoke("cap.fluid.transfer.v1",
                                       {"source_well": "A1", "destination_well": "B1", "volume_ul": 50})
        bench["sample-mover"].invoke("cap.sample.move.v1", {"plate_id": "plate-001", "to": "reader"})
        spectrum = bench["plate-reader"].invoke("cap.measure.spectrum.v1",
                                                {"plate_id": "plate-001", "wavelengths_nm": [562]})
        print("measured", spectrum.status)
""")

REJECTED_SCRIPT = textwrap.dedent("""\
    import sys
    from mhs.run import lab

    with lab(sys.argv[1]) as cell:
        cell["conveyor-workcell"].invoke("cap.world.step.v1", {"ticks": 1})
        cell["conveyor-workcell"].invoke("cap.world.step.v1", {"ticks": 1000000000})
        print("not reached")
""")


def _quiet_reference(name: str):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return s.reference(name)


class LabTest(unittest.TestCase):
    def setUp(self):
        self.spec, self.server = _quiet_reference("lab")
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-run-")
        self.ledgers = Path(self.tmp.name)
        warnings.simplefilter("ignore")

    def tearDown(self):
        warnings.resetwarnings()
        self.spec.close()
        self.tmp.cleanup()

    def test_per_device_handles_and_sessions(self):
        with lab(self.server, ledger=self.ledgers) as bench:
            self.assertEqual(len(bench), 3)
            self.assertEqual(list(bench.devices), [LAB + "liquid-handler", LAB + "plate-reader", LAB + "sample-mover"])
            self.assertIs(bench["sample-mover"], bench[LAB + "sample-mover"])
            self.assertIn("plate-reader", bench)
            for handle, (capability, payload) in zip((bench["liquid-handler"], bench["sample-mover"],
                                                      bench["plate-reader"]), (TRANSFER, MOVE, MEASURE)):
                self.assertEqual(handle.invoke(capability, payload).status, "completed")
            sessions = {handle.session_id for handle in bench}
            self.assertEqual(len(sessions), 3, "each device has its own session")
            self.assertTrue(all(client.session_id is None for client in bench.clients))
            with self.assertRaises(MHSError) as ctx:
                bench["lab"]
            self.assertEqual(ctx.exception.code, "MHS.HOST.DEVICE_AMBIGUOUS")
            with self.assertRaises(MHSError) as ctx:
                bench["no-such-device"]
            self.assertEqual(ctx.exception.code, "MHS.DEVICE.UNKNOWN")
            self.assertEqual(len(bench.receipts), 3)

    def test_check_raises_on_a_refusal(self):
        with lab(self.server, ledger=False) as bench:
            with self.assertRaises(MHSRejected) as ctx:
                bench["plate-reader"].invoke("cap.measure.spectrum.v1", {"plate_id": "plate-001",
                                                                         "wavelengths_nm": "not-a-list"})
            self.assertEqual(ctx.exception.status, "rejected")
            self.assertEqual(ctx.exception.receipt["status"], "rejected")
        with lab(self.server, check=False, ledger=False) as bench:
            receipt = bench["plate-reader"].invoke("cap.measure.spectrum.v1", {"plate_id": "plate-001",
                                                                               "wavelengths_nm": "not-a-list"})
            self.assertEqual(receipt.status, "rejected")
        self.assertEqual(list(self.ledgers.iterdir()), [])

    def test_ledger_verifies_against_the_endpoint_evidence(self):
        with lab(self.server, ledger=self.ledgers) as bench:
            for name, (capability, payload) in zip(("liquid-handler", "sample-mover", "plate-reader"),
                                                   (TRANSFER, MOVE, MEASURE)):
                bench[name].invoke(capability, payload)
        path = bench.ledger_path
        self.assertEqual(path.parent, self.ledgers)
        ledger = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(ledger["ledger_version"], LEDGER_VERSION)
        self.assertEqual(ledger["outcome"], "completed")
        self.assertEqual(len(ledger["receipt_ids"]), 3)
        self.assertEqual({item["device_id"] for item in ledger["receipts"]},
                         {LAB + "liquid-handler", LAB + "sample-mover", LAB + "plate-reader"})
        self.assertEqual(ledger["endpoints"][0]["endpoint_id"], s.ENDPOINT_ID)
        for key in ("script_sha256", "started_at", "ended_at", "run_id"):
            self.assertIn(key, ledger)
        with connect(self.server) as client:
            bundle = client.export_evidence()
        result = verify_ledger(ledger, bundle)
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["checked"], 3)
        # A receipt id the endpoint never issued is caught.
        forged = dict(ledger, receipts=ledger["receipts"] + [dict(ledger["receipts"][0], receipt_id="0" * 26)])
        self.assertEqual(verify_ledger(forged, bundle)["missing"], ["0" * 26])
        tampered = dict(ledger, receipts=[dict(ledger["receipts"][0], status="failed")])
        self.assertFalse(verify_ledger(tampered, bundle)["valid"])

    def test_refusal_inside_the_block_is_recorded(self):
        with self.assertRaises(MHSRejected):
            with lab(self.server, ledger=self.ledgers) as bench:
                bench["plate-reader"].invoke("cap.measure.spectrum.v1", {"plate_id": "plate-001",
                                                                         "wavelengths_nm": "not-a-list"})
        ledger = json.loads(bench.ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(ledger["outcome"], "rejected")
        self.assertEqual(ledger["error"]["status"], "rejected")
        self.assertEqual(ledger["receipts"][0]["status"], "rejected")
        self.assertEqual(ledger["error"]["receipt_id"], ledger["receipt_ids"][0])

    def test_estop_every_device(self):
        with lab(self.server, ledger=False) as bench:
            receipts = bench.estop("code file stop")
            self.assertEqual([item.status for item in receipts], ["completed"] * 3)
            with self.assertRaises(MHSRejected) as ctx:
                bench["sample-mover"].invoke(*MOVE)
            self.assertEqual(ctx.exception.code, "MHS.SAFETY.ESTOP_ENGAGED")

    def test_estop_tries_every_device_before_raising(self):
        # Verifier finding: the loop stopped at the first exception, leaving later devices running.
        with lab(self.server, ledger=False) as bench:
            first = bench["liquid-handler"]
            self.assertIs(next(iter(bench)), first)
            with mock.patch.object(first, "estop", side_effect=MHSError("MHS.TRANSPORT.CLOSED", "connection reset")):
                with self.assertRaises(MHSError) as ctx:
                    bench.estop("partial stop")
            error = ctx.exception
            self.assertEqual(error.code, "MHS.TRANSPORT.CLOSED")
            self.assertEqual([(item["device_id"], item["mhs_code"]) for item in error.data["errors"]],
                             [(LAB + "liquid-handler", "MHS.TRANSPORT.CLOSED")])
            self.assertEqual([item["status"] for item in error.data["receipts"]], ["completed"] * 2)
            for name in ("sample-mover", "plate-reader"):
                status = bench[name].safety()
                self.assertTrue(status.get("estop_engaged", (status.get("estop") or {}).get("engaged")), name)

    def test_device_ids_resolve_through_discovery(self):
        with s.Http(self.server) as http, tempfile.TemporaryDirectory() as tmp:
            env = {"MHS_ENDPOINTS": http.url, "MHS_ENDPOINTS_FILE": str(Path(tmp) / "none.json")}
            with mock.patch.dict(os.environ, env):
                with lab("sample-mover", LAB + "plate-reader", ledger=False) as bench:
                    self.assertEqual(list(bench.devices), [LAB + "sample-mover", LAB + "plate-reader"])
                    self.assertEqual(len(bench.clients), 1, "one connection per endpoint")
                    self.assertEqual(bench["sample-mover"].invoke(*MOVE).status, "completed")
                with self.assertRaises(MHSError) as ctx:
                    lab("no-such-device", ledger=False)
                self.assertEqual(ctx.exception.code, "MHS.DEVICE.UNKNOWN")

    def test_a_device_claimed_by_two_discovered_endpoints_is_ambiguous(self):
        spec, other = _quiet_reference("lab")
        try:
            with s.Http(self.server) as one, s.Http(other) as two, tempfile.TemporaryDirectory() as tmp:
                env = {"MHS_ENDPOINTS": f"{one.url},{two.url}", "MHS_ENDPOINTS_FILE": str(Path(tmp) / "none.json")}
                with mock.patch.dict(os.environ, env):
                    with self.assertRaises(MHSError) as ctx:
                        lab("sample-mover", ledger=False)
                    self.assertEqual(ctx.exception.code, "MHS.HOST.DEVICE_AMBIGUOUS")
                    self.assertEqual(sorted(ctx.exception.data["endpoints"]), sorted([one.url, two.url]))
                    # Naming the endpoint settles it: a device the lab already has is not looked up again.
                    with lab(one.url, "sample-mover", ledger=False) as bench:
                        self.assertEqual((len(bench.clients), len(bench)), (1, 3))
        finally:
            spec.close()

    def test_a_discovered_endpoint_never_gets_the_lab_token(self):
        # Verifier finding: token= went to whichever discovered endpoint claimed the device.
        from mhs.adapter import close_server, load

        token = "lab-token-0123456789"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            thermostat = load(s.THERMOSTAT, log_ready=False,
                              auth_tokens={token: {"id": "agent:test", "kind": "agent"}})
        try:
            with s.Http(thermostat) as http, tempfile.TemporaryDirectory() as tmp:
                env = {"MHS_ENDPOINTS": http.url, "MHS_ENDPOINTS_FILE": str(Path(tmp) / "none.json")}
                with mock.patch.dict(os.environ, env):
                    with self.assertRaises(MHSError) as ctx:
                        lab("tutorial-thermostat", token=token, ledger=False)
                    self.assertEqual(ctx.exception.code, "MHS.AUTH.UNAUTHENTICATED")
                    with lab(http.url, token=token, ledger=False) as bench:  # named in the call: token sent
                        self.assertEqual(len(bench), 1)
                (Path(tmp) / "thermostat.token").write_text(token + "\n", encoding="utf-8")
                endpoints = Path(tmp) / "endpoints.json"
                endpoints.write_text(json.dumps({"endpoints": [
                    {"transport": "http", "url": http.url, "token_file": "thermostat.token"}]}), encoding="utf-8")
                with mock.patch.dict(os.environ, {"MHS_ENDPOINTS": "", "MHS_ENDPOINTS_FILE": str(endpoints)}):
                    with lab("tutorial-thermostat", ledger=False) as bench:  # the entry's own token_file
                        self.assertIn("setpoint", bench["tutorial-thermostat"].read()["state"])
        finally:
            close_server(thermostat)

    def test_a_discovered_stdio_endpoint_starts_in_its_cwd(self):
        # Verifier finding: lab() ignored the endpoints-file cwd, so a relative launch command failed
        # (MHS.TRANSPORT.CLOSED) unless the caller happened to run from that directory.
        sdk = s.THERMOSTAT.parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            endpoints = Path(tmp) / "endpoints.json"
            endpoints.write_text(json.dumps({"endpoints": [{
                "transport": "stdio", "cwd": str(sdk),
                "command": [sys.executable, "-m", "mhs", "serve", "examples/thermostat", "--stdio"],
                "devices": ["mhs://localhost/tutorial-thermostat/fake"]}]}), encoding="utf-8")
            env = {"MHS_ENDPOINTS": "", "MHS_ENDPOINTS_FILE": str(endpoints), "PYTHONDONTWRITEBYTECODE": "1",
                   "PYTHONPATH": str(s.SDK_SRC) + os.pathsep + os.environ.get("PYTHONPATH", "")}
            saved = os.getcwd()
            os.chdir(tmp)  # anywhere but the entry's cwd
            try:
                with mock.patch.dict(os.environ, env):
                    with lab("tutorial-thermostat", ledger=False) as bench:
                        self.assertIn("setpoint", bench["tutorial-thermostat"].read()["state"])
            finally:
                os.chdir(saved)

    def test_an_unreadable_token_file_is_an_auth_error_not_a_traceback(self):
        with s.Http(self.server) as http, tempfile.TemporaryDirectory() as tmp:
            endpoints = Path(tmp) / "endpoints.json"
            endpoints.write_text(json.dumps({"endpoints": [
                {"transport": "http", "url": http.url, "token_file": "missing.token"}]}), encoding="utf-8")
            with mock.patch.dict(os.environ, {"MHS_ENDPOINTS": "", "MHS_ENDPOINTS_FILE": str(endpoints)}):
                with self.assertRaises(MHSError) as ctx:
                    lab("sample-mover", ledger=False)
        self.assertEqual(ctx.exception.code, "MHS.AUTH.UNAUTHENTICATED")
        self.assertTrue(str(ctx.exception.data["token_file"]).endswith("missing.token"))

    def test_a_ledger_checked_against_another_endpoint_is_not_valid(self):
        from mhs.reference import build_endpoint, build_server

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            spec = build_endpoint("lab", endpoint_id="mhs://localhost:7499")
            other = build_server(spec, log_ready=False)
        try:
            with lab(self.server, ledger=self.ledgers) as bench:
                bench["sample-mover"].invoke(*MOVE)
            ledger = json.loads(bench.ledger_path.read_text(encoding="utf-8"))
            with connect(other) as client:
                result = verify_ledger(ledger, client.export_evidence())
            self.assertFalse(result["valid"], result)
            self.assertEqual(result["checked"], 0)
            self.assertEqual(result["reasons"], ["endpoint_not_in_ledger", "no_receipts_for_endpoint"])
            with connect(self.server) as client:
                own = verify_ledger(ledger, client.export_evidence())
            self.assertTrue(own["valid"], own)
            self.assertEqual((own["checked"], own["reasons"]), (1, []))
        finally:
            spec.close()

    def test_lab_needs_a_target(self):
        with self.assertRaises(MHSError):
            lab()

    def test_an_open_client_is_used_not_closed(self):
        client = connect(self.server)
        try:
            with lab(client, ledger=False) as bench:
                self.assertEqual(len(bench), 3)
            self.assertEqual(client.devices()[0]["device_id"], LAB + "liquid-handler")  # still open
        finally:
            client.close()


class ObserverTest(unittest.TestCase):
    def setUp(self):
        self.spec, self.server = _quiet_reference("conveyor")
        warnings.simplefilter("ignore")

    def tearDown(self):
        warnings.resetwarnings()
        self.spec.close()

    def test_observer_sees_hello_receipts_and_batches(self):
        seen: list[tuple[str, str | None]] = []

        def observe(event, _client, payload):
            seen.append((event, payload.get("receipt_id") or payload.get("endpoint_id")))

        remove = add_observer(observe)
        try:
            with connect(self.server) as client:
                client.open_session([s.CONVEYOR])
                receipt = client.invoke("cap.world.step.v1", {"ticks": 1}, device_id=s.CONVEYOR)
                batch = client.batch([{"method": "mhs.command", "params": {
                    "session_id": client.session_id, "capability_id": "cap.world.step.v1", "input": {"ticks": 1},
                    "device_id": s.CONVEYOR, "command_id": "01J8ZQ3V6Y7M2N4P6R8S0T2V4W", "deadline_ms": 5000}}])
        finally:
            remove()
        self.assertIn(("hello", s.ENDPOINT_ID), seen)
        self.assertIn(("receipt", receipt["receipt_id"]), seen)
        self.assertIn(("receipt", batch[0]["result"]["receipt_id"]), seen)
        count = len(seen)
        with connect(self.server) as client:
            client.hello()
        self.assertEqual(len(seen), count, "a removed observer sees nothing")

    def test_a_failing_observer_never_breaks_the_client(self):
        def broken(*_args):
            raise RuntimeError("observer bug")

        remove = add_observer(broken)
        try:
            with connect(self.server) as client:
                client.open_session([s.CONVEYOR])
                self.assertEqual(client.invoke("cap.world.step.v1", {"ticks": 1}).status, "completed")
        finally:
            remove()

    def test_lost_responses_are_recorded(self):
        class Lost:
            kind = "test"
            timeout = 1.0

            def request(self, message, *, timeout=None):
                raise MHSError("MHS.OUTCOME.TIMEOUT", "no response", retryable=False)

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(directory=tmp)
            client = MHSClient(Lost())
            with self.assertRaises(MHSError):
                client.invoke("cap.world.step.v1", {"ticks": 1}, session_id="s", command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V4W")
            document = json.loads(ledger.close(outcome="error").read_text(encoding="utf-8"))
        self.assertEqual(document["lost"], [{"method": "mhs.command", "code": "MHS.OUTCOME.TIMEOUT",
                                             "command_id": "01J8ZQ3V6Y7M2N4P6R8S0T2V4W", "may_have_effect": True}])

    def test_in_process_connect(self):
        with connect(self.server) as client:
            self.assertEqual(client.transport.kind, "inprocess")
            self.assertEqual(client.endpoint_id, s.ENDPOINT_ID)
        with MHSClient(self.server) as client:
            self.assertEqual(client.hello()["endpoint_id"], s.ENDPOINT_ID)


class MhsRunTest(unittest.TestCase):
    """``mhs run script.py``: the script runs as __main__ under one ledger."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-run-")
        self.dir = Path(self.tmp.name)
        warnings.simplefilter("ignore")

    def tearDown(self):
        warnings.resetwarnings()
        self.tmp.cleanup()

    def _script(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_three_device_run_ledger_verifies_against_evidence(self):
        script = self._script("three.py", THREE_DEVICE_SCRIPT)
        spec, server = _quiet_reference("lab")
        try:
            with s.Http(server) as http:
                result = subprocess.run([sys.executable, "-m", "mhs", "run", str(script), http.url],
                                        cwd=self.dir, capture_output=True, text=True, timeout=120,
                                        env=s.child_env())
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("measured completed", result.stdout)
                ledgers = sorted((self.dir / ".mhs-run").glob("*.json"))
                self.assertEqual(len(ledgers), 1, "one ledger per run (lab() inside mhs run writes no other)")
                ledger = json.loads(ledgers[0].read_text(encoding="utf-8"))
                self.assertIn(f"mhs run: ledger .mhs-run/{ledgers[0].name} (3 receipt(s), outcome completed)",
                              result.stderr)
                self.assertEqual(ledger["script"], str(script))
                self.assertEqual(ledger["argv"], [str(script), http.url])
                import hashlib

                self.assertEqual(ledger["script_sha256"], hashlib.sha256(script.read_bytes()).hexdigest())
                self.assertEqual(ledger["exit_code"], 0)
                self.assertEqual(len(ledger["receipt_ids"]), 3)
                with connect(http.url) as client:
                    bundle = client.export_evidence()
                verified = verify_ledger(ledger, bundle)
                self.assertTrue(verified["valid"], verified)
                self.assertEqual(verified["checked"], 3)
                code, out, _err = s.run_cli("evidence", "-e", http.url, "--ledger", str(ledgers[0]))
                self.assertEqual(code, 0, out)
                report = json.loads(out)
                self.assertTrue(report["valid"])
                self.assertEqual(report["ledger"]["checked"], 3)
        finally:
            spec.close()

    def test_rejected_run_exits_1_and_keeps_the_ledger(self):
        script = self._script("reject.py", REJECTED_SCRIPT)
        spec, server = _quiet_reference("conveyor")
        try:
            with s.Http(server) as http:
                code, path = run_script(script, [http.url], ledger_dir=self.dir / "ledgers")
        finally:
            spec.close()
        self.assertEqual(code, 1)
        ledger = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(ledger["outcome"], "rejected")
        self.assertEqual([item["status"] for item in ledger["receipts"]], ["completed", "rejected"])
        self.assertEqual(ledger["error"]["status"], "rejected")
        self.assertEqual(ledger["exit_code"], 1)
        self.assertEqual(sys.argv[0] != str(script), True, "sys.argv is restored")

    def test_exit_codes_of_the_script(self):
        for text, expected, outcome in (("import sys\nsys.exit(3)\n", 3, "exited"),
                                        ("raise ValueError('bug')\n", 1, "error"),
                                        ("print('nothing to do')\n", 0, "completed")):
            with self.subTest(text=text):
                script = self._script("exit.py", text)
                with mock.patch("sys.stderr"), mock.patch("sys.stdout"):
                    code, path = run_script(script, ledger_dir=self.dir / "exit")
                self.assertEqual(code, expected)
                ledger = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual((ledger["outcome"], ledger["receipt_ids"]), (outcome, []))

    def test_unclosed_lab_writes_its_ledger_at_exit(self):
        script = self._script("plain.py", textwrap.dedent("""\
            import sys
            from mhs.run import lab

            bench = lab("stdio:" + sys.executable + " -m mhs.reference conveyor --stdio --quiet")
            bench["conveyor-workcell"].invoke("cap.world.step.v1", {"ticks": 1})
        """))
        result = subprocess.run([sys.executable, str(script)], cwd=self.dir, capture_output=True, text=True,
                                timeout=120, env=s.child_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        ledgers = sorted((self.dir / ".mhs-run").glob("*.json"))
        self.assertEqual(len(ledgers), 1)
        ledger = json.loads(ledgers[0].read_text(encoding="utf-8"))
        self.assertEqual((ledger["outcome"], len(ledger["receipt_ids"])), ("unclosed", 1))
        self.assertEqual(ledger["script"], str(script))

    def test_transport_error_exits_3(self):
        script = self._script("down.py", "import sys\nfrom mhs.run import lab\nlab(sys.argv[1])\n")
        with mock.patch("sys.stderr"):
            code, path = run_script(script, [s.closed_port_url()], ledger_dir=self.dir / "down")
        self.assertEqual(code, 3)
        ledger = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(ledger["error"]["code"], "MHS.TRANSPORT.UNAVAILABLE")

    def test_a_script_that_changes_directory_keeps_the_ledger_where_it_started(self):
        # Verifier finding: the ledger followed os.chdir() and the printed relative path did not exist.
        (self.dir / "sub").mkdir()
        script = self._script("chdir.py", "import os\nos.chdir('sub')\nprint('moved')\n")
        saved = os.getcwd()
        os.chdir(self.dir)
        try:
            here = os.getcwd()
            with mock.patch("sys.stdout"), mock.patch("sys.stderr"):
                code, path = run_script(script)
            self.assertEqual(os.getcwd(), here, "the working directory is restored")
            self.assertEqual(code, 0)
            self.assertTrue(path.is_absolute())
            self.assertEqual(path.parent, Path(here) / ".mhs-run")
            self.assertFalse((self.dir / "sub" / ".mhs-run").exists())
            code, _out, err = s.run_cli("run", str(script))
            self.assertEqual(code, 0)
            shown = err.split("mhs run: ledger ", 1)[1].split(" (", 1)[0]
            self.assertTrue(shown.startswith(".mhs-run/"), err)
            self.assertTrue(Path(shown).is_file(), "the printed path exists from the caller's directory")
        finally:
            os.chdir(saved)


if __name__ == "__main__":
    unittest.main()
