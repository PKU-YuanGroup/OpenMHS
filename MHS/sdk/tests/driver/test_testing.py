"""mhs.testing: Recorder (never invents attributes), its phases, failure injection, re-exports, check_driver."""

from __future__ import annotations

import asyncio
import inspect
import os
import subprocess
import sys
import threading
import unittest
from unittest import mock

import mhs.testing as testing
from mhs.bridge.base import Bridge
from mhs.bridge.transcript import Transcript
from mhs.conformance.inprocess import Loopback
from mhs.driver import Driver, Limit, estop, read, write
from mhs.driver.check import INNER_ENV
from mhs.testing import Recorder, check_driver, log_of

from tests.driver import gate_support as gs


class Native:
    def __init__(self) -> None:
        self.value = 1.0
        self.stopped = False

    def get(self) -> float:
        return self.value

    def set(self, value: float) -> None:
        self.value = value

    async def aget(self) -> float:
        await asyncio.sleep(0)
        return self.value

    def stop(self) -> None:
        self.stopped = True


class Probe(Driver):
    device_id, device_kind = "probe", "thermal.zone"
    mode, risk = "simulated", "R0"
    fidelity = {"engine": "test", "fidelity_level": "F0", "determinism": {"kind": "exact"}, "timestep_ms": 0,
                "realtime_factor": 0, "reset": "full", "snapshot_restore": False, "gaps": ["test"]}
    backends = {"fake": Native}

    @read("value", unit="Cel")
    async def value(self):
        return await self.native.aget()

    @write("value", unit="Cel", limit=Limit(min=0, max=10, source="vendor_doc", ref="m.md:1"))
    def set_value(self, value):
        self.native.set(value)

    @estop
    def stop(self):
        self.native.stop()


class SyncProbe(Driver):
    device_id, device_kind = "sync-probe", "thermal.zone"
    mode, risk = "simulated", "R0"
    fidelity = Probe.fidelity
    backends = {"fake": Native}

    @read("value", unit="Cel")
    def value(self):
        return self.native.get()

    @write("value", unit="Cel", limit=Limit(min=0, max=10, source="vendor_doc", ref="m.md:1"))
    def set_value(self, value):
        self.make_bridge(value)

    def make_bridge(self, value):
        self.native.set(value)


class RecorderTests(unittest.TestCase):
    def test_forwards_and_records(self) -> None:
        native = Native()
        recorder = Recorder(native)
        self.assertEqual(recorder.get(), 1.0)
        recorder.set(2.5)
        self.assertEqual(native.value, 2.5)
        self.assertEqual(recorder.value, 2.5)
        recorder.value = 3.0
        self.assertEqual(native.value, 3.0)
        log = log_of(recorder)
        self.assertEqual([(call.name, call.kind) for call in log.calls],
                         [("get", "call"), ("set", "call"), ("value", "get"), ("value", "set")])
        self.assertEqual(log.calls[1].args, (2.5,))
        self.assertEqual(log.found, {"get", "set", "value"})
        self.assertEqual([call.name for call in log.actuations()], ["get", "set", "value"])

    def test_unknown_attributes_raise(self) -> None:
        recorder = Recorder(Native())
        with self.assertRaises(AttributeError):
            recorder.turbo()
        self.assertFalse(hasattr(recorder, "nothing_here"))
        log = log_of(recorder)
        self.assertEqual(log.missing, {"turbo", "nothing_here"})
        self.assertNotIn("turbo", log.found)

    def test_standalone_methods_and_attributes(self) -> None:
        recorder = Recorder(methods={"read": 21.5, "double": lambda x: 2 * x}, attributes={"port": "/dev/x"})
        self.assertEqual(recorder.read(), 21.5)
        self.assertEqual(recorder.double(4), 8)
        self.assertEqual(recorder.port, "/dev/x")
        with self.assertRaises(AttributeError):
            recorder.write("x")
        with self.assertRaises(TypeError):
            Recorder()

    def test_the_interface_never_shadows_a_backend_attribute(self) -> None:
        class Upstream:
            def calls(self) -> str:
                return "the upstream's own calls()"

            def reset(self) -> str:
                return "the upstream's own reset()"

        recorder = Recorder(Upstream())
        self.assertEqual(recorder.calls(), "the upstream's own calls()")
        self.assertEqual(recorder.reset(), "the upstream's own reset()")
        self.assertEqual(len(log_of(recorder).calls), 2)
        with self.assertRaises(TypeError):
            log_of(Upstream())

    def test_signature_is_kept(self) -> None:
        self.assertEqual(list(inspect.signature(Recorder(Native()).set).parameters), ["value"])

    def test_failure_injection(self) -> None:
        recorder = Recorder(Native())
        log = log_of(recorder)
        with log.fail() as failure:
            with self.assertRaises(RuntimeError):
                recorder.set(1.0)
        self.assertEqual(failure.raised, 1)
        recorder.set(1.0)  # the failure is gone
        with log.fail(ValueError("boom"), names=["stop"]):
            recorder.set(2.0)
            with self.assertRaises(ValueError):
                recorder.stop()

    def test_phases_follow_the_bridge_contract(self) -> None:
        holder: dict = {}

        def wrap(native):
            holder["recorder"] = Recorder(native)
            return holder["recorder"]

        driver = Probe(backend="fake", native_wrapper=wrap)
        try:
            driver.open()
            log = log_of(holder["recorder"])
            # As the gate does: an async getter runs on the driver's event loop, where the stack shows the
            # getter itself (not Bridge.read), so its code object is registered as a read.
            log.phase_codes[inspect.unwrap(Probe.value).__code__] = "read"
            mark = log.mark()
            driver.read("main")                       # async getter on the driver's loop thread
            self.assertEqual({call.phase for call in log.since(mark)}, {"read"})
            mark = log.mark()
            driver.write("main", {"value": 4.0})
            self.assertEqual([(call.name, call.phase) for call in log.since(mark)], [("set", "act")])
            mark = log.mark()
            driver.estop("test")
            self.assertEqual([(call.name, call.phase) for call in log.in_phase("estop", mark)], [("stop", "estop")])
            self.assertEqual(log.actuations(mark)[0].name, "stop")
        finally:
            driver.close()

    def test_windows_give_helper_threads_their_phase(self) -> None:
        recorder = Recorder(Native())
        log = log_of(recorder)
        seen: list[str] = []

        def helper() -> None:
            recorder.get()
            seen.append(log.calls[-1].phase)

        with log.window("read"):
            thread = threading.Thread(target=helper)
            thread.start()
            thread.join()
        with log.window("estop"), log.window("read"):
            thread = threading.Thread(target=helper)
            thread.start()
            thread.join()
        thread = threading.Thread(target=helper)
        thread.start()
        thread.join()
        self.assertEqual(seen, ["read", "estop", "act"])
        with self.assertRaises(ValueError):
            with log.window("nope"):
                pass

    def test_sdk_bridge_frames_mark_reads(self) -> None:
        holder: dict = {}

        def wrap(native):
            holder["recorder"] = Recorder(native)
            return holder["recorder"]

        driver = SyncProbe(backend="fake", native_wrapper=wrap)
        try:
            driver.open()
            log = log_of(holder["recorder"])
            mark = log.mark()
            driver.read("main")                       # Driver.read / _read_param: the SDK's own contract methods
            self.assertEqual([(call.name, call.phase) for call in log.since(mark)], [("get", "read")])
            mark = log.mark()
            driver.write("main", {"value": 3.0})      # set_value -> a helper named like a contract method
            self.assertEqual([(call.name, call.phase) for call in log.since(mark)], [("set", "act")])
        finally:
            driver.close()

    def test_contract_names_outside_the_sdk_open_no_phase(self) -> None:
        # Only the SDK's code opens a phase by method name: a driver or helper called read/make_bridge does not,
        # so a native failure in it is still injected and counted as an actuation.
        recorder = Recorder(Native())

        class Helper(Bridge):
            def read(self, resource_id, fields=None, ctx=None):
                return {"value": recorder.get()}

            def make_bridge(self):
                recorder.set(2.0)

        Helper().read("main")
        Helper().make_bridge()
        self.assertEqual([call.phase for call in log_of(recorder).calls], ["act", "act"])
        with log_of(recorder).fail():
            with self.assertRaises(RuntimeError):
                Helper().make_bridge()


class ReexportTests(unittest.TestCase):
    def test_reexports(self) -> None:
        self.assertIs(testing.Transcript, Transcript)
        self.assertIs(testing.Loopback, Loopback)
        self.assertTrue(callable(testing.client_for))
        self.assertEqual(sorted(testing.__all__), sorted(set(testing.__all__)))


class CheckDriverTests(unittest.TestCase):
    def test_check_driver_returns_the_report_without_writing(self) -> None:
        directory = gs.copy_tutorial(self)
        report = check_driver(directory, gates=["G1", "G2", "G3", "G5"])
        self.assertEqual(report["failed"], [])
        self.assertFalse((directory / "check-report.json").exists())

    def test_inside_the_gate_g9_is_skipped(self) -> None:
        directory = gs.copy_tutorial(self)
        with mock.patch.dict(os.environ, {INNER_ENV: "1"}):
            report = check_driver(directory, gates=["G1", "G9"])
        gate = next(item for item in report["gates"] if item["id"] == "G9")
        self.assertEqual(gate["status"], "skip")
        self.assertFalse(gate["required"])
        self.assertEqual(report["evidence_state"], "none")

    def test_the_package_test_runs_with_the_network_disabled(self) -> None:
        directory = gs.copy_tutorial(self)
        (directory / "test_net.py").write_text(
            "import errno, socket, unittest\n\n"
            "class Net(unittest.TestCase):\n"
            "    def test_no_network(self):\n"
            "        with self.assertRaises(OSError) as caught:\n"
            "            socket.create_connection(('192.0.2.1', 9), timeout=5)\n"
            "        self.assertIn('disabled', str(caught.exception))\n"
            "        with self.assertRaises(OSError) as caught:\n"
            "            socket.socket().connect(('192.0.2.1', 9))\n"
            "        self.assertEqual(caught.exception.errno, errno.ENETUNREACH)\n"
            "        with self.assertRaises(socket.gaierror):\n"
            "            socket.getaddrinfo('example.com', 80)\n"
            "    def test_loopback_works(self):\n"
            "        server = socket.socket()\n"
            "        server.bind(('127.0.0.1', 0))\n"
            "        server.listen(1)\n"
            "        client = socket.create_connection(server.getsockname(), timeout=5)\n"
            "        client.close()\n"
            "        server.close()\n", encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(gs.SRC)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        done = subprocess.run([sys.executable, "-m", "mhs.driver._repotests", str(directory / "test_net.py")],
                              capture_output=True, text=True, timeout=120, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)

    @unittest.skipIf(os.name == "nt", "device files are a POSIX notion")
    def test_the_package_test_cannot_open_device_files(self) -> None:
        directory = gs.temp_root(self)
        (directory / "test_dev.py").write_text(
            "import io, os, pathlib, unittest\n\n"
            "class Dev(unittest.TestCase):\n"
            "    def test_serial_ports_are_refused(self):\n"
            "        for opener in (lambda p: open(p, 'r+b'), lambda p: io.open(p, 'rb'),\n"
            "                       lambda p: os.open(p, os.O_RDWR), lambda p: pathlib.Path(p).open('rb')):\n"
            "            with self.assertRaises(PermissionError) as caught:\n"
            "                opener('/dev/ttyACM0')\n"
            "            self.assertIn('acceptance gate', str(caught.exception))\n"
            "    def test_ordinary_files_and_dev_null_work(self):\n"
            "        with open(os.devnull, 'wb') as handle:\n"
            "            handle.write(b'x')\n"
            "        with open(__file__, encoding='utf-8') as handle:\n"
            "            self.assertIn('Dev', handle.read())\n", encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(gs.SRC)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        done = subprocess.run([sys.executable, "-m", "mhs.driver._repotests", str(directory / "test_dev.py")],
                              capture_output=True, text=True, timeout=120, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
