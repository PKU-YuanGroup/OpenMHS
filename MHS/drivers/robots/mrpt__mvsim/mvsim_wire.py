"""The MVSim service messages this package exchanges, encoded and decoded with the standard library only.

The field numbers, types and required fields are those of the pinned message definitions
(``modules/msgs/proto/*.proto`` at cfaf9f28f57fe5798a6b1defa65a435402bd38d0); the bytes follow the public Protocol
Buffers wire format (a varint key ``field << 3 | wire type``; varints for bools, 64-bit little-endian doubles,
length-delimited strings, bytes and embedded messages). Every field of a request is written, in field order, as a
proto2 message with all its fields set serialises. A decoded answer that misses a required field, repeats a scalar
or does not parse is refused (``ValueError``); unknown fields are skipped, as protobuf does.

``frame``/``unframe`` are MVSim's ZMQ message envelope (``mvsim::sendMessage`` and ``parseMessageToParts``,
modules/comms/src/Comms/common.cpp:20-46): the message's type name, then its serialised bytes, each written by an
MRPT archive as a little-endian uint32 length followed by the bytes (MRPT's string serialisation, outside the clone).
Only the live client (``MvsimServiceClient`` below, built by ``sim.py``) frames messages; the upstream Python client
and this package's fake exchange the unframed bytes of ``callService``. The client takes the pyzmq module as an
argument, so this module imports nothing outside the standard library.
"""

from __future__ import annotations

import math
import struct
import threading
import time

_VARINT, _FIXED64, _LENGTH, _FIXED32 = 0, 1, 2, 5


class ServiceNotOffered(LookupError):
    """The MVSim server named no usable endpoint for a service: a request for it was never sent to the service."""


#: The answer type of each service this package calls (World_services.cpp:251-273). The serving client answers a
#: request for a service it does not offer with a ``GenericAnswer`` whose success is false (Client.cpp:565-580).
ANSWER_TYPES = {"set_controller_twist": "mvsim_msgs.SrvSetControllerTwistAnswer",
                "get_pose": "mvsim_msgs.SrvGetPoseAnswer"}
GENERIC_ANSWER = "mvsim_msgs.GenericAnswer"

_MAX_MESSAGE = 1 << 20  # bound on any message this package parses (this client's own bound, not an MVSim limit)


# -- encoding --------------------------------------------------------------------------------------------------


def _varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("negative varint")
    out = bytearray()
    while True:
        bits = value & 0x7F
        value >>= 7
        if value:
            out.append(bits | 0x80)
        else:
            out.append(bits)
            return bytes(out)


def _key(field: int, wire_type: int) -> bytes:
    return _varint(field << 3 | wire_type)


def _double(field: int, value: float) -> bytes:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("a twist component must be a finite number")
    return _key(field, _FIXED64) + struct.pack("<d", value)


def _bytes(field: int, data: bytes) -> bytes:
    return _key(field, _LENGTH) + _varint(len(data)) + data


def _string(field: int, text: str) -> bytes:
    return _bytes(field, text.encode("utf-8"))


def twist(vx: float, vy: float, wz: float) -> bytes:
    """``mvsim_msgs.Twist`` (Twist.proto:5-12): vx=1, vy=2, vz=3, wx=4, wy=5, wz=6, all required doubles."""
    return b"".join(_double(field, value) for field, value in enumerate((vx, vy, 0.0, 0.0, 0.0, wz), 1))


def set_controller_twist(object_id: str, vx: float, vy: float, wz: float) -> bytes:
    """``SrvSetControllerTwist`` (SrvSetControllerTwist.proto:7-11): objectId=1, twistSetPoint=2."""
    return _string(1, object_id) + _bytes(2, twist(vx, vy, wz))


def get_pose(object_id: str) -> bytes:
    """``SrvGetPose`` (SrvGetPose.proto:5-7): objectId=1."""
    return _string(1, object_id)


def get_service_info_request(service_name: str) -> bytes:
    """``GetServiceInfoRequest`` (GetServiceInfoRequest.proto:5-7): serviceName=1."""
    return _string(1, service_name)


def call_service(service_name: str, serialized_input: bytes) -> bytes:
    """``CallService`` (CallService.proto:5-13): serviceName=1, serializedInput=2."""
    return _string(1, service_name) + _bytes(2, bytes(serialized_input))


# -- decoding --------------------------------------------------------------------------------------------------


def _read_varint(data: bytes, index: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        if index >= len(data) or shift > 63:
            raise ValueError("truncated or oversized varint")
        byte = data[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, index
        shift += 7


def fields(data: bytes) -> dict[int, list[tuple[int, object]]]:
    """Every field of one serialised message: ``{number: [(wire type, value), ...]}`` (``ValueError`` if malformed)."""
    if not isinstance(data, (bytes, bytearray)) or len(data) > _MAX_MESSAGE:
        raise ValueError("a message must be at most 1 MiB of bytes")
    data = bytes(data)
    out: dict[int, list[tuple[int, object]]] = {}
    index = 0
    while index < len(data):
        key, index = _read_varint(data, index)
        number, wire_type = key >> 3, key & 7
        if number < 1:
            raise ValueError("invalid field number")
        if wire_type == _VARINT:
            value, index = _read_varint(data, index)
        elif wire_type == _FIXED64:
            if index + 8 > len(data):
                raise ValueError("truncated 64-bit field")
            value, index = data[index:index + 8], index + 8
        elif wire_type == _LENGTH:
            size, index = _read_varint(data, index)
            if index + size > len(data):
                raise ValueError("truncated length-delimited field")
            value, index = data[index:index + size], index + size
        elif wire_type == _FIXED32:
            if index + 4 > len(data):
                raise ValueError("truncated 32-bit field")
            value, index = data[index:index + 4], index + 4
        else:
            raise ValueError(f"unsupported wire type {wire_type}")
        out.setdefault(number, []).append((wire_type, value))
    return out


def _one(found: dict[int, list[tuple[int, object]]], number: int, wire_type: int, *, required: bool) -> object:
    items = found.get(number, [])
    if any(kind != wire_type for kind, _ in items):
        raise ValueError(f"field {number} has the wrong wire type")
    if not items:
        if required:
            raise ValueError(f"required field {number} is missing")
        return None
    return items[-1][1]  # protobuf keeps the last value of a repeated scalar field


def _as_bool(value: object) -> bool:
    return bool(value)


def _as_double(value: object) -> float:
    number = struct.unpack("<d", value)[0]  # type: ignore[arg-type]
    if not math.isfinite(number):
        raise ValueError("a double field is not finite")
    return number


def _as_text(value: object) -> str:
    return bytes(value).decode("utf-8")  # type: ignore[arg-type]


def answer(data: bytes) -> tuple[bool, str]:
    """``(success, errorMessage)`` of a ``SrvSetControllerTwistAnswer`` (SrvSetControllerTwistAnswer.proto:5-10).

    ``GenericAnswer`` (GenericAnswer.proto:5-10, the answer to an unknown service) has the same two fields.
    """
    found = fields(data)
    success = _as_bool(_one(found, 1, _VARINT, required=True))
    message = _one(found, 2, _LENGTH, required=False)
    return success, _as_text(message) if message is not None else ""


def _vector(data: object, names: tuple[str, ...]) -> dict[str, float]:
    found = fields(data)  # type: ignore[arg-type]
    return {name: _as_double(_one(found, number, _FIXED64, required=True)) for number, name in enumerate(names, 1)}


def pose_answer(data: bytes) -> dict[str, object]:
    """A ``SrvGetPoseAnswer`` (SrvGetPoseAnswer.proto:8-18): success=1, errorMessage=2, pose=3 (Pose.proto:5-12),
    objectIsInCollision=4, twist=5 (Twist.proto:5-12). ``pose`` and ``twist`` are ``None`` when absent."""
    found = fields(data)
    success = _as_bool(_one(found, 1, _VARINT, required=True))
    message = _one(found, 2, _LENGTH, required=False)
    collision = _as_bool(_one(found, 4, _VARINT, required=True))
    pose = _one(found, 3, _LENGTH, required=False)
    twist_value = _one(found, 5, _LENGTH, required=False)
    return {
        "success": success,
        "error": _as_text(message) if message is not None else "",
        "pose": _vector(pose, ("x", "y", "z", "yaw", "pitch", "roll")) if pose is not None else None,
        "twist": _vector(twist_value, ("vx", "vy", "vz", "wx", "wy", "wz")) if twist_value is not None else None,
        "collision": collision,
    }


def service_info_answer(data: bytes) -> tuple[bool, str, str]:
    """``(success, errorMessage, serviceEndpoint)`` of a ``GetServiceInfoAnswer`` (GetServiceInfoAnswer.proto:5-13)."""
    found = fields(data)
    success = _as_bool(_one(found, 1, _VARINT, required=True))
    message = _one(found, 2, _LENGTH, required=False)
    endpoint = _one(found, 3, _LENGTH, required=False)
    return success, _as_text(message) if message is not None else "", _as_text(endpoint) if endpoint is not None else ""


# -- the ZMQ envelope (sim.py) ---------------------------------------------------------------------------------


def service_port(endpoint: str) -> int:
    """The TCP port of a service endpoint the server reported, ``tcp://<host>:<port>`` (``ValueError`` otherwise).

    The serving client binds its service socket to ``tcp://0.0.0.0:*`` and reports ZMQ's last endpoint
    (Client.cpp:166-167, 462; common.cpp:75-86), a wildcard host; only the port is used.
    """
    text = str(endpoint)
    host, separator, port = text[len("tcp://"):].rpartition(":") if text.startswith("tcp://") else ("", "", "")
    if not separator or not host or not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError(f"not a tcp://<host>:<port> endpoint: {text[:80]!r}")
    return int(port)


def frame(type_name: str, payload: bytes) -> bytes:
    """MVSim's envelope: the type name, then the serialised message, each a little-endian uint32 length plus bytes."""
    name = type_name.encode("utf-8")
    return struct.pack("<I", len(name)) + name + struct.pack("<I", len(payload)) + bytes(payload)


def unframe(message: bytes) -> tuple[str, bytes]:
    """``(type name, serialised message)`` of one envelope (``ValueError`` when it is not exactly one envelope)."""
    data = bytes(message)
    parts = []
    index = 0
    for _ in range(2):
        if index + 4 > len(data):
            raise ValueError("truncated MVSim envelope")
        (size,) = struct.unpack_from("<I", data, index)
        index += 4
        if size > _MAX_MESSAGE or index + size > len(data):
            raise ValueError("MVSim envelope length out of bounds")
        parts.append(data[index:index + size])
        index += size
    if index != len(data):
        raise ValueError("trailing bytes after the MVSim envelope")
    return parts[0].decode("utf-8"), parts[1]


# -- the bounded service client (sim.py passes pyzmq in) ---------------------------------------------------------


class MvsimServiceClient:
    """A bounded client of MVSim's services with the upstream client's ``callService``/``shutdown`` members.

    ``zmq`` is the pyzmq module, passed in by the ``sim`` backend (``sim.py``); this module never imports it. One
    deadline bounds every socket operation of a call. Step 1 asks the server's main REP socket for the service's
    endpoint (``GetServiceInfoRequest``; Client.cpp:745-778, Server.cpp:416-438), cached per service as the upstream
    client caches it and dropped after any failed call; step 2 sends ``CallService`` to the configured host at the port
    of that endpoint and returns the answer's serialised message unframed, as the upstream ``callService`` returns it
    (Client.cpp:781-805). Unlike the upstream client, which connects to the reported endpoint verbatim (Client.cpp:775,
    783), it never follows a host the server names: the simulator reports its wildcard bind (``service_port``). Only
    the services of ``ANSWER_TYPES`` are called, and an answer must be that service's answer type or a ``GenericAnswer``
    whose success is false, so no other message can read as an accepted setpoint. A fresh REQ socket with linger 0
    serves each request, so a timed-out request never blocks the next one and concurrent calls do not share a socket.
    A call that does not finish in time raises ``TimeoutError``; a service the server does not offer, or names no usable
    endpoint for, raises ``ServiceNotOffered`` (nothing was sent to the service); an answer of another type raises
    ``ValueError``.
    """

    def __init__(self, zmq, host, port, timeout_s):
        self._zmq = zmq
        self._host = host
        self._server = f"tcp://{host}:{port}"
        self._timeout_s = timeout_s
        self._context = zmq.Context()
        self._endpoints = {}
        self._lock = threading.Lock()  # guards the endpoint cache and the closed flag only
        self._closed = False

    def callService(self, serviceName, inputSerializedMsg):
        expected = ANSWER_TYPES.get(serviceName)
        if expected is None:
            raise ServiceNotOffered(f"this client calls only {sorted(ANSWER_TYPES)}, not {serviceName!r}")
        deadline = time.monotonic() + self._timeout_s
        try:
            endpoint = self._endpoint(serviceName, deadline)
            reply = self._request(endpoint, frame(
                "mvsim_msgs.CallService", call_service(serviceName, bytes(inputSerializedMsg))), deadline)
            type_name, data = unframe(reply)
            if type_name == GENERIC_ANSWER:
                if answer(data)[0]:
                    raise ValueError(f"a GenericAnswer claiming success is not an answer of {serviceName}")
            elif type_name != expected:
                raise ValueError(f"unexpected answer type {type_name!r} from {serviceName} (expected {expected})")
            return data
        except BaseException:
            with self._lock:
                self._endpoints.pop(serviceName, None)
            raise

    def shutdown(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        # Every socket is closed with linger 0 after its request: terminating the context waits at most for the calls
        # still in flight, each bounded by its own deadline. Later calls are refused.
        self._context.term()

    def _endpoint(self, service, deadline):
        with self._lock:
            cached = self._endpoints.get(service)
        if cached is not None:
            return cached
        reply = self._request(self._server, frame(
            "mvsim_msgs.GetServiceInfoRequest", get_service_info_request(service)), deadline)
        type_name, data = unframe(reply)
        if type_name != "mvsim_msgs.GetServiceInfoAnswer":
            raise ValueError(f"unexpected answer type {type_name!r} to GetServiceInfoRequest")
        success, message, endpoint = service_info_answer(data)
        if not success or not endpoint:
            raise ServiceNotOffered(f"MVSim does not offer service {service!r}: {message}")
        try:
            endpoint = f"tcp://{self._host}:{service_port(endpoint)}"
        except ValueError as exc:
            raise ServiceNotOffered(f"MVSim named no usable endpoint for service {service!r}: {exc}") from exc
        with self._lock:
            self._endpoints[service] = endpoint
        return endpoint

    def _request(self, endpoint, payload, deadline):
        zmq = self._zmq
        with self._lock:
            if self._closed:
                raise ConnectionError("the MVSim client was shut down")
        socket = self._context.socket(zmq.REQ)
        try:
            socket.setsockopt(zmq.LINGER, 0)
            remaining = int((deadline - time.monotonic()) * 1000)
            if remaining <= 0:
                raise TimeoutError("the MVSim call's deadline expired before sending")
            socket.setsockopt(zmq.SNDTIMEO, remaining)
            socket.connect(endpoint)
            socket.send(payload)
            remaining = int((deadline - time.monotonic()) * 1000)
            if remaining <= 0:
                raise TimeoutError("the MVSim call's deadline expired after sending")
            socket.setsockopt(zmq.RCVTIMEO, remaining)
            return socket.recv()
        except zmq.Again as exc:
            raise TimeoutError("MVSim did not answer within the client's bound") from exc
        finally:
            socket.close(linger=0)
