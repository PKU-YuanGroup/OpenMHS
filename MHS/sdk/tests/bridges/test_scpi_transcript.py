"""ScpiBridge over stdlib sockets, pyvisa (optional) and recorded transcripts.

FIT-04 / FIT-09: there was no SCPI bridge at all (``python3 -m
mhs.bridge.scpi_visa`` -> "No module named"), and ``bindings.schema`` rejects
``OUTP:STAT {value}`` as a native symbol; SCPI command templates now live in a
command map, never in ``native``.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import socketserver
import tempfile
import threading
import unittest

from tests.bridges import support

from mhs import signals
from mhs.bridge.scpi import ScpiBridge, SocketTransport
from mhs.bridge.serial import SerialBridge
from mhs.bridge.transcript import Transcript, TranscriptDivergence
from mhs.server import Resource


def lockin_config(**extra: object) -> dict:
    config = {
        "idn": {"expect": "^Stanford_Research_Systems,SR860"},
        "commands": {
            "x-cap.test.frequency.v1": {"resource": "lockin", "query": "FREQ?",
                                        "parse": {"kind": "float"},
                                        "result": {"map": {"frequency": "output.$"}}},
            "x-cap.test.set_frequency.v1": {"resource": "lockin", "write": "FREQ {value:g}",
                                            "args": {"value": {"from": "input.frequency", "type": "number"}},
                                            "result": {"map": {}}},
            "x-cap.test.output.v1": {"resource": "lockin", "query": "OUTP? {channel:d}",
                                     "args": {"channel": {"from": "input.channel", "type": "integer",
                                                          "default": 0}},
                                     "parse": {"kind": "float"},
                                     "result": {"map": {"x": "output.$"}}},
        },
        "safety_bindings": {"estop": {"write": "OUTP OFF"}},
    }
    config.update(extra)
    return config


class TranscriptTests(unittest.TestCase):
    def test_replay_passes_in_order(self) -> None:
        transcript = Transcript.from_json(support.LOCKIN_TRANSCRIPT)
        bridge = ScpiBridge(lockin_config(), transport=transcript.line_transport())
        try:
            self.assertEqual(bridge.call("x-cap.test.frequency.v1", {}), {"frequency": 1000.0})
            bridge.call("x-cap.test.set_frequency.v1", {"frequency": 2000})
            self.assertEqual(bridge.call("x-cap.test.frequency.v1", {}), {"frequency": 2000.0})
            self.assertEqual(bridge.call("x-cap.test.output.v1", {}), {"x": 1.25e-06})
            self.assertEqual(bridge.idn, support.IDN)
            transcript.assert_complete()
        finally:
            bridge.close()

    def test_replay_end_to_end_through_the_server(self) -> None:
        transcript = Transcript.from_json(support.LOCKIN_TRANSCRIPT)
        config = lockin_config()
        bridge = ScpiBridge(config, device_id="mhs://localhost:7799/lab/lockin",
                            transport=transcript.line_transport())
        device = support.simulated_device(
            "mhs://localhost:7799/lab/lockin",
            resources=[Resource("lockin", "instrument.lockin")],
            capabilities=[support.open_capability(cap, "lockin") for cap in config["commands"]],
            bridge=bridge,
        )
        harness = support.Harness(device)
        try:
            self.assertEqual(harness.command("x-cap.test.frequency.v1")["output"], {"frequency": 1000.0})
            self.assertEqual(harness.command("x-cap.test.set_frequency.v1", {"frequency": 2000})["status"],
                             "completed")
            self.assertEqual(harness.command("x-cap.test.frequency.v1")["output"], {"frequency": 2000.0})
            self.assertEqual(harness.command("x-cap.test.output.v1", {"channel": 0})["output"], {"x": 1.25e-06})
            transcript.assert_complete()
            diverged = harness.command("x-cap.test.frequency.v1")   # the recording has ended
            self.assertEqual(diverged["status"], "failed", diverged)
        finally:
            bridge.close()

    def test_divergence_raises(self) -> None:
        transcript = Transcript.from_json(support.LOCKIN_TRANSCRIPT)
        bridge = ScpiBridge(lockin_config(), transport=transcript.line_transport())
        try:
            bridge.call("x-cap.test.frequency.v1", {})
            with self.assertRaises(TranscriptDivergence) as caught:
                bridge.call("x-cap.test.set_frequency.v1", {"frequency": 3000})
            self.assertIn("FREQ 2000", str(caught.exception))
            self.assertIn("FREQ 3000", str(caught.exception))
        finally:
            bridge.close()

    def test_unconsumed_exchanges_fail_assert_complete(self) -> None:
        transcript = Transcript.from_json(support.LOCKIN_TRANSCRIPT)
        bridge = ScpiBridge(lockin_config(), transport=transcript.line_transport())
        try:
            bridge.call("x-cap.test.frequency.v1", {})
            with self.assertRaises(TranscriptDivergence):
                transcript.assert_complete()
        finally:
            bridge.close()

    def test_round_trip_and_recording(self) -> None:
        transcript = Transcript.from_json(support.LOCKIN_TRANSCRIPT)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lockin.transcript.json")
            transcript.dump(path)
            loaded = Transcript.load(path)
        self.assertEqual(loaded.to_json(), transcript.to_json())
        recorded = Transcript(name="recorded")
        live = Transcript.from_json(support.LOCKIN_TRANSCRIPT).line_transport()
        recorder = recorded.recorder(live)
        recorder.query("*IDN?", timeout_s=1)
        recorder.query("FREQ?", timeout_s=1)
        recorder.write("FREQ 2000", timeout_s=1)
        self.assertEqual(recorded.to_json()["exchanges"], support.LOCKIN_TRANSCRIPT["exchanges"][:3])

    def test_identity_mismatch_is_not_ready(self) -> None:
        data = copy.deepcopy(support.LOCKIN_TRANSCRIPT)
        data["exchanges"][0]["recv"] = "Keysight,34465A,1,1"
        bridge = ScpiBridge(lockin_config(), transport=Transcript.from_json(data).line_transport())
        try:
            with self.assertRaises(Exception) as caught:
                bridge.call("x-cap.test.frequency.v1", {})
            self.assertEqual(getattr(caught.exception, "code", None), "MHS.DEVICE.NOT_READY")
        finally:
            bridge.close()

    def test_serial_bridge_replays_a_transcript(self) -> None:
        transcript = Transcript.from_json({"exchanges": [{"send": "TEMP?", "recv": "21.5"},
                                                         {"send": "TEMP?", "recv": "21.7"}]})
        bridge = SerialBridge(
            {"port": "/dev/fake", "timeout_s": 0.2, "capabilities": {
                "cap.measure.temperature.v1": {"resource": "instrument", "command": "TEMP?",
                                               "parse": {"kind": "float", "field": "temperature"}}}},
            serial_factory=lambda **kwargs: transcript.serial(),
        )
        try:
            self.assertEqual(bridge.call("cap.measure.temperature.v1", {}), {"temperature": 21.5})
            self.assertEqual(bridge.call("cap.measure.temperature.v1", {}), {"temperature": 21.7})
            transcript.assert_complete()
        finally:
            bridge.close()

    def test_http_like_exchanges(self) -> None:
        transcript = Transcript.from_json({"exchanges": [
            {"send": {"method": "GET", "path": "/health"}, "recv": {"status": 200, "body": {"ok": True}}},
            {"send": {"method": "POST", "path": "/run", "body": {"protocol": "p1"}}, "recv": {"status": 202}},
        ]})
        http = transcript.http()
        self.assertEqual(http.request("GET", "/health"), {"status": 200, "body": {"ok": True}})
        with self.assertRaises(TranscriptDivergence):
            http.request("POST", "/run", body={"protocol": "p2"})


class ScpiCommandSafetyTests(unittest.TestCase):
    def test_string_arguments_cannot_inject_commands(self) -> None:
        config = lockin_config()
        config["commands"]["x-cap.test.mode.v1"] = {
            "resource": "lockin", "write": "ISRC {mode}",
            "args": {"mode": {"from": "input.mode", "type": "string"}}, "result": {"map": {}}}
        transcript = Transcript()   # nothing may reach the wire
        bridge = ScpiBridge(config, transport=transcript.line_transport())
        try:
            for bad in ("A;*RST", "A\n*RST", "A\r"):
                with self.subTest(mode=bad):
                    with self.assertRaises(Exception) as caught:
                        bridge.call("x-cap.test.mode.v1", {"mode": bad})
                    self.assertEqual(getattr(caught.exception, "code", None), "MHS.CAPABILITY.INPUT_INVALID")
            self.assertEqual(transcript.position, 0)
        finally:
            bridge.close()

    def test_command_map_is_validated(self) -> None:
        for bad in ({"query": "A?", "write": "B"}, {"resource": "x"}, {"query": "A?", "parse": {"kind": "complex"}},
                    {"query": "A?", "colour": 1}):
            with self.subTest(entry=bad):
                with self.assertRaises(Exception) as caught:
                    ScpiBridge({"idn": False, "commands": {"x-cap.test.bad.v1": bad}},
                               transport=Transcript().line_transport())
                self.assertEqual(getattr(caught.exception, "code", None), "MHS.ADAPTER.MANIFEST_INVALID")

    def test_estop_is_written_without_an_identity_probe(self) -> None:
        # an open transport is used directly: no identity probe delays the stop
        transcript = Transcript.from_json({"exchanges": [{"send": "OUTP OFF"}]})
        bridge = ScpiBridge(lockin_config(), transport=transcript.line_transport())
        try:
            result = bridge.estop("stop")
            self.assertEqual(result["native"], "OUTP OFF")
            transcript.assert_complete()
            self.assertEqual(bridge.estop_native, "OUTP OFF")
        finally:
            bridge.close()


class _Instrument(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        frequency = "1000.0"
        for raw in self.rfile:
            line = raw.decode("ascii").strip()
            if line == "*IDN?":
                self.wfile.write((support.IDN + "\n").encode("ascii"))
            elif line == "FREQ?":
                self.wfile.write((frequency + "\n").encode("ascii"))
            elif line.startswith("FREQ "):
                frequency = line.split(" ", 1)[1]
            elif line == "SILENT?":
                continue


class SocketTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Instrument)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def test_stdlib_socket_transport_end_to_end(self) -> None:
        config = lockin_config(host="127.0.0.1", port=self.port, timeout_s=0.5)
        config["commands"]["x-cap.test.silent.v1"] = {"resource": "lockin", "query": "SILENT?",
                                                     "parse": {"kind": "str"}, "result": {"map": {"v": "output.$"}}}
        bridge = ScpiBridge(config, device_id="mhs://localhost:7799/lab/lockin")
        device = support.simulated_device(
            "mhs://localhost:7799/lab/lockin",
            resources=[Resource("lockin", "instrument.lockin")],
            capabilities=[support.open_capability(cap, "lockin") for cap in config["commands"]],
            bridge=bridge,
        )
        harness = support.Harness(device)
        try:
            self.assertEqual(harness.command("x-cap.test.frequency.v1")["output"], {"frequency": 1000.0})
            self.assertEqual(harness.command("x-cap.test.set_frequency.v1", {"frequency": 1234.5})["status"],
                             "completed")
            self.assertEqual(harness.command("x-cap.test.frequency.v1")["output"], {"frequency": 1234.5})
            silent = harness.command("x-cap.test.silent.v1")
            self.assertEqual(silent["status"], "unknown", silent)
            self.assertFalse(silent["error"]["retryable"])
        finally:
            bridge.close()

    def test_socket_transport_timeout_raises_timeout_error(self) -> None:
        transport = SocketTransport("127.0.0.1", self.port, terminator="\n", timeout_s=0.2)
        try:
            self.assertEqual(transport.query("*IDN?", timeout_s=0.5), support.IDN)
            with self.assertRaises(TimeoutError):
                transport.query("SILENT?", timeout_s=0.1)
        finally:
            transport.close()


@unittest.skipUnless(importlib.util.find_spec("pyvisa") and importlib.util.find_spec("pyvisa_sim"),
                     "pyvisa and pyvisa-sim are not installed")
class PyvisaSimTests(unittest.TestCase):  # pragma: no cover - optional dependency
    def test_pyvisa_sim_resource(self) -> None:
        bridge = ScpiBridge({
            "visa_resource": "ASRL1::INSTR",
            "visa_backend": "@sim",
            "terminator": "\n",
            "idn": {"command": "?IDN", "expect": "LSG Serial Instrument"},
            "commands": {"x-cap.test.idn.v1": {"resource": "inst", "query": "?IDN", "parse": {"kind": "str"},
                                               "result": {"map": {"idn": "output.$"}}}},
        })
        try:
            self.assertIn("LSG", bridge.call("x-cap.test.idn.v1", {})["idn"])
        finally:
            bridge.close()


if __name__ == "__main__":
    unittest.main()
