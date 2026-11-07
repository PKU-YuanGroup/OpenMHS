"""Fake MVSim client: the upstream client's ``callService``/``shutdown`` surface, answered like MVSim's World services.

The upstream Python client (``pymvsim_comms.mvsim.Client``) passes a serialised protobuf request to a named service
and returns the serialised answer (modules/comms/python/generated-sources-pybind/mvsim/Comms/Client.cpp:74-87). This
fake answers the two services the package uses as World answers them at the pin:

* ``set_controller_twist`` (World_services.cpp:124-170): ``success`` false with ``objectId not found`` for an unknown
  vehicle and with the controller-refusal message when the controller does not accept twist commands; otherwise the
  setpoint is stored and ``success`` is true.
* ``get_pose`` (World_services.cpp:78-122): ``success`` with the pose, the twist (vz, wx, wy written as 0) and the
  collision flag, or ``success`` false for an unknown object.

Any other service gets the ``GenericAnswer`` the client's service thread sends for an unknown service
(Client.cpp:565-580). The answers are encoded here, independently of the package's request encoder, so a wrong field
number in either is caught by the tests. The vehicle name, pose and the ideal twist response (the twist equals the
setpoint, as the ``twist_ideal`` controller of VehicleDifferential.h:178-203 does) are placeholder test data; the
fake runs no simulation, physics, clock or ZMQ socket.
"""

from __future__ import annotations

import struct

from .mvsim_wire import fields

_VEHICLE = "r1"  # placeholder vehicle name (the clone's teleop example drives 'r1', examples_python/mvsim-teleop.py:40)
_POSE = {"x": 1.0, "y": 2.0, "z": 0.0, "yaw": 0.5, "pitch": 0.0, "roll": 0.0}  # placeholder pose


def _varint(value):
    out = bytearray()
    while True:
        bits, value = value & 0x7F, value >> 7
        out.append(bits | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _field(number, wire_type, payload):
    return _varint(number << 3 | wire_type) + payload


def _boolean(number, value):
    return _field(number, 0, _varint(1 if value else 0))


def _text(number, value):
    data = value.encode("utf-8")
    return _field(number, 2, _varint(len(data)) + data)


def _message(number, data):
    return _field(number, 2, _varint(len(data)) + data)


def _doubles(values):
    return b"".join(_field(number, 1, struct.pack("<d", value)) for number, value in enumerate(values, 1))


def _decode_twist(data):
    found = fields(data)
    return [struct.unpack("<d", found[number][-1][1])[0] for number in range(1, 7)]


class FakeMvsimClient:
    def __init__(self, vehicle=_VEHICLE, **_options):
        self.vehicles = {str(vehicle)}            # placeholder world: one vehicle
        self.setpoint = [0.0, 0.0, 0.0]          # placeholder state: vx, vy, wz of the controller setpoint
        self.pose = dict(_POSE)                   # placeholder state
        self.collision = False                    # placeholder state
        self.calls = []                           # placeholder test record: (service, decoded request fields)
        self.accepts_twist = True                 # placeholder negative-path switch (a raw-force or trajectory controller)
        self.unanswered = False                   # placeholder negative-path switch (the client's bounded wait expired)
        self.garbled = False                      # placeholder negative-path switch (an answer that does not parse)
        self.shut_down = False                    # placeholder test record

    def callService(self, serviceName, inputSerializedMsg):
        request = fields(inputSerializedMsg)
        self.calls.append((serviceName, request))
        if self.unanswered:
            raise TimeoutError("placeholder: no answer within the client's bound")
        if self.garbled:
            return b"\x0a\x05ab"  # placeholder: a truncated message
        if serviceName == "set_controller_twist":
            return self._set_controller_twist(request)
        if serviceName == "get_pose":
            return self._get_pose(request)
        message = f"Requested unknown service `{serviceName}`"
        return _boolean(1, False) + _text(2, message)

    def _set_controller_twist(self, request):
        object_id = request[1][-1][1].decode("utf-8")
        if object_id not in self.vehicles:
            return _boolean(1, False) + _text(2, "objectId not found")
        if not self.accepts_twist:
            return _boolean(1, False) + _text(2, "objectId vehicle controller did not accept the twist command")
        vx, vy, _vz, _wx, _wy, wz = _decode_twist(request[2][-1][1])
        self.setpoint = [vx, vy, wz]
        return _boolean(1, True)

    def _get_pose(self, request):
        object_id = request[1][-1][1].decode("utf-8")
        if object_id not in self.vehicles:
            return _boolean(1, False) + _boolean(4, False)
        vx, vy, wz = self.setpoint  # placeholder ideal response: the twist is the setpoint
        pose = [self.pose[name] for name in ("x", "y", "z", "yaw", "pitch", "roll")]
        return (_boolean(1, True) + _message(3, _doubles(pose)) + _boolean(4, self.collision)
                + _message(5, _doubles([vx, vy, 0.0, 0.0, 0.0, wz])))

    def shutdown(self):
        self.shut_down = True
