"""Native e-stop stays available when hardware actuation is refused.

CORE-076 and the wire form of ``mhs.safety.estop`` make a session optional.
HOST-090 and CORE-130 keep the e-stop available on a hardware device while
``allow_hardware`` is false: that flag refuses actuation, not the stop.
The device must still be one the host resolved on a configured endpoint.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from openai4s_mhs.config import EndpointSpec, MHSConfig
from openai4s_mhs.host import MHSHost, MHSHostError

from .fake_endpoint import FakeMHSServer, fake_connect


def _config(tmp: str, *, allow_hardware: bool = False) -> MHSConfig:
    return MHSConfig(
        endpoints=[
            EndpointSpec(id="fake", command=["python3", "-m", "fake.endpoint"])
        ],
        evidence_log=str(Path(tmp) / "evidence.jsonl"),
        allow_hardware=allow_hardware,
        command_timeout_ms=5000,
    )


class RecordingHardwareServer(FakeMHSServer):
    """Hardware device with a native stop, recording every transport method."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("mode", "hardware")
        super().__init__(**kwargs)
        self.calls: list[str] = []

    def dispatch(self, method: str, params: dict) -> Any:
        self.calls.append(method)
        return super().dispatch(method, params)

    def manifest(self) -> dict:
        manifest = super().manifest()
        manifest["capabilities"] = list(manifest["capabilities"]) + [
            {
                "capability_id": "cap.motion.estop.v1",
                "title": "Native emergency stop",
                "resource": self.resources[0],
            }
        ]
        safety = dict(manifest["safety"])
        safety["estop"] = {"kind": "both", "latching": True, "latency_ms": 50}
        manifest["safety"] = safety
        return manifest


class UngatedNativeEstopTests(unittest.TestCase):
    def make_host(self, server: FakeMHSServer, **config_kwargs: Any) -> MHSHost:
        self._tmp = tempfile.TemporaryDirectory(prefix="mhs-estop-ungated-")
        self.addCleanup(self._tmp.cleanup)
        host = MHSHost(
            _config(self._tmp.name, **config_kwargs), sdk_connect=fake_connect(server)
        )
        self.addCleanup(host.close)
        return host

    def test_hardware_estop_is_sent_without_actuation_permission(self) -> None:
        server = RecordingHardwareServer()
        host = self.make_host(server, allow_hardware=False)
        try:
            stop = host.estop("conveyor", "operator stop")
        except MHSHostError as exc:
            self.fail(
                f"e-stop was refused {exc.code} before the stop was sent; "
                f"transport calls={server.calls}"
            )
        self.assertEqual(stop["status"], "completed")
        self.assertEqual(stop["device_id"], server.device_id)
        self.assertEqual(server.estop_state, "engaged")
        self.assertEqual(server.estop_reason, "operator stop")
        # Discovery may run. The stop itself is session-independent: no
        # open_session, and the e-stop method is the only effectful call.
        self.assertEqual(server.calls, ["devices", "inspect", "estop"])
        self.assertEqual(server.sessions, {})
        ledger = host.ledger()
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["status"], "completed")
        self.assertEqual(ledger[0]["capability_id"], "cap.device.estop.v1")
        self.assertEqual(ledger[0]["device_id"], server.device_id)
        self.assertEqual(ledger[0]["endpoint_id"], "fake")

        # The stop must not leave a cached hardware session that a later
        # read or the native stop capability could reuse.
        with self.assertRaises(MHSHostError) as read_caught:
            host.read("conveyor")
        self.assertEqual(read_caught.exception.code, "MHS.HOST.HARDWARE_GATED")
        with self.assertRaises(MHSHostError) as command_caught:
            host.command("conveyor", "cap.motion.estop.v1", {})
        self.assertEqual(command_caught.exception.code, "MHS.HOST.HARDWARE_GATED")
        self.assertEqual(server.calls, ["devices", "inspect", "estop"])
        self.assertEqual(server.sessions, {})
        self.assertEqual(server.estop_state, "engaged")

    def test_unknown_device_is_still_refused_without_a_stop(self) -> None:
        server = RecordingHardwareServer()
        host = self.make_host(server, allow_hardware=False)
        with self.assertRaises(MHSHostError) as caught:
            host.estop("not-a-device", "operator stop")
        self.assertEqual(caught.exception.code, "MHS.HOST.DEVICE_NOT_FOUND")
        self.assertNotIn("estop", server.calls)
        self.assertNotIn("open_session", server.calls)
        self.assertEqual(server.estop_state, "released")
        self.assertEqual(host.ledger(), [])
