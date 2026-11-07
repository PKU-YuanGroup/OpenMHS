"""Acceptance run of the MVSim service package: the gate, plus cases for its stop, its wire encoding and its fake.

Add cases, never remove the check_driver call.
"""

import importlib.util
import json
import struct
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown, build_server, close_server as close_built
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent


def _wire_module():
    # The gate loads this file on its own, so the package's standard-library codec is loaded from its file.
    spec = importlib.util.spec_from_file_location("mvsim_wire_under_test", HERE / "mvsim_wire.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mvsim_wire = _wire_module()
TWIST = "x-cap.mrpt.mvsim_controller_twist.v1"
POSE = "x-cap.mrpt.mvsim_pose.v1"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


def example_overlay():
    return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


def double(field, value):
    return bytes([field << 3 | 1]) + struct.pack("<d", value)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WireEncoding(unittest.TestCase):
    """Byte vectors written out from the pinned .proto field numbers, independent of the encoder's code."""

    def test_set_controller_twist_request(self) -> None:
        twist = b"".join(double(field, value) for field, value in
                         ((1, 0.5), (2, 0.0), (3, 0.0), (4, 0.0), (5, 0.0), (6, -1.25)))
        expected = b"\x0a\x02r1" + b"\x12" + bytes([len(twist)]) + twist
        self.assertEqual(len(twist), 54)
        self.assertEqual(mvsim_wire.set_controller_twist("r1", 0.5, 0.0, -1.25), expected)

    def test_get_pose_and_service_requests(self) -> None:
        self.assertEqual(mvsim_wire.get_pose("veh7"), b"\x0a\x04veh7")
        self.assertEqual(mvsim_wire.get_service_info_request("get_pose"), b"\x0a\x08get_pose")
        self.assertEqual(mvsim_wire.call_service("get_pose", b"\x0a\x02r1"), b"\x0a\x08get_pose\x12\x04\x0a\x02r1")

    def test_answers(self) -> None:
        self.assertEqual(mvsim_wire.answer(b"\x08\x01"), (True, ""))
        self.assertEqual(mvsim_wire.answer(b"\x08\x00\x12\x03bad"), (False, "bad"))
        for broken in (b"", b"\x12\x03bad", b"\x08", b"\x0a\x05ab", b"\x09\x01"):
            with self.subTest(broken=broken):
                with self.assertRaises(ValueError):
                    mvsim_wire.answer(broken)

    def test_the_envelope(self) -> None:
        framed = mvsim_wire.frame("mvsim_msgs.SrvGetPose", b"\x0a\x02r1")
        self.assertEqual(framed, b"\x15\x00\x00\x00mvsim_msgs.SrvGetPose\x04\x00\x00\x00\x0a\x02r1")
        self.assertEqual(mvsim_wire.unframe(framed), ("mvsim_msgs.SrvGetPose", b"\x0a\x02r1"))
        for broken in (framed[:-1], framed + b"\x00", b"\x01\x00"):
            with self.subTest(broken=broken):
                with self.assertRaises(ValueError):
                    mvsim_wire.unframe(broken)

    def test_non_finite_setpoints_are_never_encoded(self) -> None:
        with self.assertRaises(ValueError):
            mvsim_wire.set_controller_twist("r1", float("nan"), 0.0, 0.0)


class MvsimCases(unittest.TestCase):
    def serve(self, *, overlay=True):
        server = load(HERE, backend="fake", site_limits=example_overlay() if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def direct(self, **options):
        driver = load_driver(HERE, "fake", options=options or None)
        self.addCleanup(driver.close)
        return driver, driver.native

    def test_a_setpoint_reaches_set_controller_twist_and_reports_what_was_accepted(self) -> None:
        driver, fake = self.direct()
        self.assertEqual(driver.call(TWIST, {"vx": 0.25, "wz": -0.5}), {"accepted": True, "vx": 0.25, "wz": -0.5})
        service, request = fake.calls[-1]
        self.assertEqual(service, "set_controller_twist")
        self.assertEqual(request[1][-1][1], b"r1")
        self.assertEqual(fake.setpoint, [0.25, 0.0, -0.5])

    def test_the_configured_vehicle_is_addressed(self) -> None:
        driver, fake = self.direct(vehicle="veh2")
        driver.call(TWIST, {"vx": 0.1, "wz": 0.0})
        self.assertEqual(fake.calls[-1][1][1][-1][1], b"veh2")

    def test_a_refused_setpoint_fails(self) -> None:
        driver, fake = self.direct()
        fake.accepts_twist = False
        with self.assertRaises(DriverFailed) as caught:
            driver.call(TWIST, {"vx": 0.1, "wz": 0.0})
        self.assertEqual(caught.exception.code, "MHS.DEVICE.PRECONDITION_UNMET")

    def test_an_unknown_vehicle_fails(self) -> None:
        driver, fake = self.direct()
        fake.vehicles = {"other"}
        with self.assertRaises(DriverFailed):
            driver.call(TWIST, {"vx": 0.1, "wz": 0.0})

    def test_no_answer_or_a_garbled_answer_is_unknown(self) -> None:
        for switch in ("unanswered", "garbled"):
            with self.subTest(switch=switch):
                driver, fake = self.direct()
                setattr(fake, switch, True)
                with self.assertRaises(OutcomeUnknown):
                    driver.call(TWIST, {"vx": 0.1, "wz": 0.0})

    def test_the_pose_read(self) -> None:
        client = self.serve()
        client.invoke(TWIST, {"vx": 0.3, "wz": 0.2}, **self.ids)
        receipt = client.invoke(POSE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]["pose"]), {"x", "y", "z", "yaw", "pitch", "roll"})
        self.assertEqual(receipt["output"]["twist"], {"vx": 0.3, "vy": 0.0, "wz": 0.2})
        self.assertFalse(receipt["output"]["in_collision"])

    def test_a_pose_read_of_an_unknown_vehicle_fails(self) -> None:
        driver, fake = self.direct()
        fake.vehicles = {"other"}
        with self.assertRaises(DriverFailed):
            driver.call(POSE, {})

    def test_a_setpoint_without_the_operator_overlay_is_refused(self) -> None:
        client = self.serve(overlay=False)
        receipt = client.invoke(TWIST, {"vx": 0.0, "wz": 0.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_a_setpoint_outside_the_overlay_is_refused(self) -> None:
        client = self.serve()
        receipt = client.invoke(TWIST, {"vx": 0.9, "wz": 0.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_the_estop_sets_a_zero_twist_and_latches(self) -> None:
        client = self.serve()
        client.invoke(TWIST, {"vx": 0.4, "wz": 0.6}, **self.ids)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        refused = client.invoke(TWIST, {"vx": 0.1, "wz": 0.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_stop_itself_sends_a_zero_twist(self) -> None:
        driver, fake = self.direct()
        driver.call(TWIST, {"vx": 0.4, "wz": 0.6})
        driver.stop()
        self.assertEqual(fake.setpoint, [0.0, 0.0, 0.0])
        self.assertEqual(fake.calls[-1][0], "set_controller_twist")

    def test_a_refused_or_unanswered_stop_raises(self) -> None:
        for switch, error in (("accepts_twist", DriverFailed), ("unanswered", OutcomeUnknown)):
            with self.subTest(switch=switch):
                driver, fake = self.direct()
                setattr(fake, switch, switch != "accepts_twist")
                with self.assertRaises(error):
                    driver.stop()

    def test_an_unanswered_stop_is_reported_unreached_with_the_latch_held(self) -> None:
        driver = load_driver(HERE, "fake")
        server = build_server(driver, site_limits=example_overlay())
        self.addCleanup(close_built, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        driver.native.unanswered = True
        receipt = client.estop("test", device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        refused = client.invoke(TWIST, {"vx": 0.1, "wz": 0.0}, device_id=device_id, session_id=session)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_close_shuts_the_client_down(self) -> None:
        driver = load_driver(HERE, "fake")
        fake = driver.native
        driver.close()
        self.assertTrue(fake.shut_down)


class FakeSocket:
    def __init__(self, zmq):
        self.zmq, self.options, self.endpoint, self.sent, self.closed = zmq, {}, None, None, False

    def setsockopt(self, option, value):
        self.options[option] = value

    def connect(self, endpoint):
        self.endpoint = endpoint

    def send(self, payload):
        self.sent = payload

    def recv(self):
        handler = self.zmq.replies.get(self.endpoint)
        answer = handler(self.sent) if handler is not None else None
        if answer is None:
            raise self.zmq.Again()
        return answer

    def close(self, linger=None):
        self.closed, self.linger = True, linger


class FakeZmq:
    """The few pyzmq names MvsimServiceClient uses; replies maps an endpoint to a handler of the framed request."""

    REQ, LINGER, SNDTIMEO, RCVTIMEO = 3, 17, 28, 27

    class Again(Exception):
        pass

    def __init__(self, replies):
        self.replies, self.sockets, self.terminated = replies, [], False

    def Context(self):
        return self

    def socket(self, kind):
        self.assert_kind = kind
        socket = FakeSocket(self)
        self.sockets.append(socket)
        return socket

    def term(self):
        self.terminated = True


SERVER = "tcp://localhost:23700"
REPORTED = "tcp://0.0.0.0:40001"  # the simulator's wildcard bind, as it reports it (Client.cpp:166-167, 462)
SERVICE = "tcp://localhost:40001"  # where the client connects: the configured host at the reported port


def info_answer(endpoint):
    data = endpoint.encode()
    return mvsim_wire.frame("mvsim_msgs.GetServiceInfoAnswer", b"\x08\x01\x1a" + bytes([len(data)]) + data)


class BoundedClient(unittest.TestCase):
    def client(self, replies, timeout_s=0.2):
        zmq = FakeZmq(replies)
        return mvsim_wire.MvsimServiceClient(zmq, "localhost", 23700, timeout_s), zmq

    def test_a_call_asks_the_server_for_the_endpoint_then_calls_the_service(self) -> None:
        requests = []

        def service(payload):
            requests.append(mvsim_wire.unframe(payload))
            return mvsim_wire.frame("mvsim_msgs.SrvSetControllerTwistAnswer", b"\x08\x01")

        client, zmq = self.client({SERVER: lambda payload: info_answer(REPORTED), SERVICE: service})
        self.assertEqual(client.callService("set_controller_twist", b"\x0a\x02r1"), b"\x08\x01")
        self.assertEqual(mvsim_wire.unframe(zmq.sockets[0].sent),
                         ("mvsim_msgs.GetServiceInfoRequest", b"\x0a\x14set_controller_twist"))
        self.assertEqual(requests, [("mvsim_msgs.CallService",
                                     b"\x0a\x14set_controller_twist\x12\x04\x0a\x02r1")])
        client.callService("set_controller_twist", b"\x0a\x02r1")
        self.assertEqual([socket.endpoint for socket in zmq.sockets], [SERVER, SERVICE, SERVICE], "endpoint cached")
        for socket in zmq.sockets:
            self.assertTrue(socket.closed)
            self.assertEqual((socket.linger, socket.options[zmq.LINGER]), (0, 0))
            self.assertLessEqual(socket.options[zmq.RCVTIMEO], 200)

    def test_no_answer_is_a_timeout_and_forgets_the_endpoint(self) -> None:
        client, zmq = self.client({SERVER: lambda payload: info_answer(REPORTED)})
        with self.assertRaises(TimeoutError):
            client.callService("set_controller_twist", b"")
        with self.assertRaises(TimeoutError):
            client.callService("set_controller_twist", b"")
        self.assertEqual([socket.endpoint for socket in zmq.sockets], [SERVER, SERVICE, SERVER, SERVICE])

    def test_a_service_the_server_does_not_offer(self) -> None:
        refusal = mvsim_wire.frame("mvsim_msgs.GetServiceInfoAnswer", b"\x08\x00\x12\x02no")
        client, zmq = self.client({SERVER: lambda payload: refusal})
        with self.assertRaises(mvsim_wire.ServiceNotOffered):
            client.callService("get_pose", b"")
        self.assertEqual(len(zmq.sockets), 1, "nothing was sent to a service")

    def test_an_unexpected_answer_type_is_refused(self) -> None:
        wrong = mvsim_wire.frame("mvsim_msgs.GenericAnswer", b"\x08\x01")
        client, _zmq = self.client({SERVER: lambda payload: wrong})
        with self.assertRaises(ValueError):
            client.callService("get_pose", b"")

    def test_an_answer_of_another_type_never_reads_as_accepted(self) -> None:
        # Only the service's own answer type, or a GenericAnswer refusing an unknown service, is passed on.
        for type_name, data in (("mvsim_msgs.SrvGetPoseAnswer", b"\x08\x01\x20\x00"),
                                ("mvsim_msgs.GenericAnswer", b"\x08\x01"),
                                ("mvsim_msgs.SrvShutdownAnswer", b"\x08\x01")):
            with self.subTest(type_name=type_name):
                client, zmq = self.client({SERVER: lambda payload: info_answer(REPORTED),
                                           SERVICE: lambda payload: mvsim_wire.frame(type_name, data)})
                with self.assertRaises(ValueError):
                    client.callService("set_controller_twist", mvsim_wire.set_controller_twist("r1", 0.0, 0.0, 0.0))
                self.assertEqual([socket.endpoint for socket in zmq.sockets], [SERVER, SERVICE])
        refusal = b"\x08\x00\x12\x02no"
        client, _zmq = self.client({SERVER: lambda payload: info_answer(REPORTED),
                                    SERVICE: lambda payload: mvsim_wire.frame("mvsim_msgs.GenericAnswer", refusal)})
        self.assertEqual(client.callService("set_controller_twist", b""), refusal)
        self.assertEqual(mvsim_wire.answer(refusal), (False, "no"))

    def test_the_client_never_follows_a_host_the_server_names(self) -> None:
        client, zmq = self.client({SERVER: lambda payload: info_answer("tcp://elsewhere.example:40001"),
                                   SERVICE: lambda payload: mvsim_wire.frame(
                                       "mvsim_msgs.SrvSetControllerTwistAnswer", b"\x08\x01")})
        self.assertEqual(client.callService("set_controller_twist", b""), b"\x08\x01")
        self.assertEqual([socket.endpoint for socket in zmq.sockets], [SERVER, SERVICE])
        for reported in ("ipc:///tmp/mvsim", "tcp://host", "tcp://:40001", "tcp://host:0", "tcp://host:99999",
                         "tcp://host:4x"):
            with self.subTest(reported=reported):
                client, zmq = self.client({SERVER: lambda payload: info_answer(reported)})
                with self.assertRaises(mvsim_wire.ServiceNotOffered):
                    client.callService("get_pose", b"")
                self.assertEqual(len(zmq.sockets), 1, "nothing was sent to a service")

    def test_only_the_package_services_are_called(self) -> None:
        client, zmq = self.client({})
        with self.assertRaises(mvsim_wire.ServiceNotOffered):
            client.callService("shutdown", b"")
        self.assertEqual(zmq.sockets, [])
        self.assertEqual(mvsim_wire.service_port("tcp://0.0.0.0:40001"), 40001)

    def test_shutdown_terminates_and_refuses_later_calls(self) -> None:
        client, zmq = self.client({})
        client.shutdown()
        self.assertTrue(zmq.terminated)
        with self.assertRaises(ConnectionError):
            client.callService("get_pose", b"")
        self.assertEqual(zmq.sockets, [])


if __name__ == "__main__":
    unittest.main()
