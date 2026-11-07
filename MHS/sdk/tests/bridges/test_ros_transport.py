"""No ROS or third-party dependency is needed for transport adapter tests."""

from __future__ import annotations

import json
import socket
import unittest
from unittest import mock

from mhs.bridge.ros_transport import RecordingRosTransport, WebSocketTransport
from mhs.bridge.transcript import TranscriptDivergence


class Peer:
    def __init__(self, incoming=()):
        self.incoming = list(incoming)
        self.sent = []
        self.timeouts = []
        self.closed = False

    def settimeout(self, value):
        self.timeouts.append(value)

    def send(self, value):
        self.sent.append(value)

    def recv(self):
        if not self.incoming:
            raise socket.timeout()
        return self.incoming.pop(0)

    def close(self, timeout=0):
        self.closed = True


class RosTransportTests(unittest.TestCase):
    def test_lazy_connect_text_json_and_close(self):
        peer = Peer(['{"op":"publish","topic":"/x","msg":{"data":4}}'])
        connector = mock.Mock(return_value=peer)
        transport = WebSocketTransport("ws://localhost:9090", connector=connector)
        self.assertFalse(connector.called)
        transport.send({"op": "subscribe", "topic": "/x"})
        self.assertEqual(transport.recv()["msg"], {"data": 4})
        self.assertEqual(json.loads(peer.sent[0]), {"op": "subscribe", "topic": "/x"})
        self.assertEqual(peer.timeouts, [0.02], "concurrent read/send must not mutate the shared socket timeout")
        self.assertEqual(connector.call_args.kwargs["redirect_limit"], 0)
        transport.close()
        self.assertTrue(peer.closed)

    def test_url_rejects_credentials_query_fragment_and_other_schemes(self):
        for url in ("http://host", "ws:///", "ws://a:b@host", "ws://host?token=x", "ws://host/#fragment"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                WebSocketTransport(url)

    def test_invalid_frames_and_nonfinite_values_are_rejected(self):
        for value in (b"bytes", "", "[]", "{bad}", '{"value":NaN}'):
            with self.subTest(value=value):
                transport = WebSocketTransport("ws://localhost", connector=lambda *a, **kw: Peer([value]))
                with self.assertRaises((ValueError, ConnectionError)):
                    transport.recv(timeout_s=0.02)
                transport.close()

    def test_message_size_limit_in_both_directions(self):
        transport = WebSocketTransport("ws://localhost", max_message_bytes=256,
                                       connector=lambda *a, **kw: Peer([json.dumps({"x": "x" * 500})]))
        with self.assertRaises(ValueError):
            transport.send({"x": "x" * 500})
        with self.assertRaises(ValueError):
            transport.recv(timeout_s=0.02)
        transport.close()

    def test_closed_transport_never_connects(self):
        connector = mock.Mock()
        transport = WebSocketTransport("ws://localhost", connector=connector)
        transport.close()
        with self.assertRaises(ConnectionError):
            transport.send({"op": "subscribe"})
        self.assertFalse(connector.called)

    def test_missing_dependency_is_only_required_on_io(self):
        with mock.patch("mhs.bridge.ros_transport.importlib.import_module", side_effect=ImportError()):
            transport = WebSocketTransport("ws://localhost")
            with self.assertRaisesRegex(RuntimeError, "websocket-client"):
                transport.send({"op": "subscribe"})
            transport.close()

    def test_fake_checks_unread_and_unconsumed_exchanges(self):
        fake = RecordingRosTransport(exchanges=[{"send": {"op": "subscribe", "topic": "/x"},
                                                "recv": {"op": "publish", "topic": "/x", "msg": {"data": 1}}}])
        with self.assertRaises(TranscriptDivergence):
            fake.assert_complete()
        fake.send({"op": "subscribe", "topic": "/x", "id": "dynamic"})
        with self.assertRaises(TranscriptDivergence):
            fake.assert_complete()
        self.assertEqual(fake.recv()["msg"], {"data": 1})
        fake.assert_complete()
        with self.assertRaises(TranscriptDivergence):
            fake.send({"op": "subscribe", "topic": "/x"})

    def test_fake_does_not_alias_input_or_observation(self):
        fake = RecordingRosTransport()
        payload = {"op": "publish", "msg": {"x": 1}}
        fake.send(payload)
        fake.feed(payload)
        payload["msg"]["x"] = 9
        self.assertEqual(fake.sent[0]["msg"], {"x": 1})
        self.assertEqual(fake.recv()["msg"], {"x": 1})


if __name__ == "__main__":
    unittest.main()
