"""ROS-free analytic stand-in for the UUV Simulator current-environment endpoints.

The fake models the rosbridge traffic the :class:`RosDriver` actually sends:
the three relative current services and the stamped flow topic.  It is an
analytic stand-in, not a recording of captured traffic and not the upstream
Gazebo world plugin.  Every canned reply and state value below is test data,
marked ``# placeholder``; none is a device fact, a Limit or a reference.
"""

import math

from mhs.bridge.ros_transport import RecordingRosTransport

_SET_VELOCITY = "/hydrodynamics/set_current_velocity"
_SET_HORZ = "/hydrodynamics/set_current_horz_angle"
_SET_VERT = "/hydrodynamics/set_current_vert_angle"
_FLOW = "/hydrodynamics/current_velocity"


class FakeUuvCurrent(RecordingRosTransport):
    """Canned current-environment service and flow-topic replies for tests."""

    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # The configured model ranges are placeholders copied from no device;
        # a real deployment supplies them in the world's constant_current SDF.
        self.velocity_min = 0.0          # placeholder
        self.velocity_max = 5.0          # placeholder
        self.angle_min = -math.pi        # placeholder
        self.angle_max = math.pi         # placeholder
        self.velocity = 0.0              # placeholder
        self.horizontal_angle = 0.0      # placeholder
        self.vertical_angle = 0.0        # placeholder
        self.flow = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder
        self.frame_id = "/world"         # upstream OnUpdateCurrentVel frames the flow
        self.fail_service = False        # placeholder negative-path switch
        self.fail_application = False    # placeholder negative-path switch
        self.sets = []                   # placeholder accepted service requests

    def _update_flow(self):
        # Placeholder analytic mapping from the model means to a flow vector.
        horizontal = self.horizontal_angle
        vertical = self.vertical_angle
        self.flow = {
            "x": self.velocity * math.cos(horizontal) * math.cos(vertical),
            "y": self.velocity * math.sin(horizontal) * math.cos(vertical),
            "z": self.velocity * math.sin(vertical),
        }

    def _set_velocity(self, request):
        velocity = request.get("velocity")
        horizontal = request.get("horizontal_angle")
        vertical = request.get("vertical_angle")
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                   for value in (velocity, horizontal, vertical)):
            return False
        if not self.velocity_min <= velocity <= self.velocity_max:
            return False
        if not self.angle_min <= horizontal <= self.angle_max:
            return False
        if not self.angle_min <= vertical <= self.angle_max:
            return False
        self.velocity, self.horizontal_angle, self.vertical_angle = velocity, horizontal, vertical
        self._update_flow()
        self.sets.append(dict(request))
        return True

    def _set_angle(self, request, vertical=False):
        angle = request.get("angle")
        if not isinstance(angle, (int, float)) or isinstance(angle, bool):
            return False
        if not self.angle_min <= angle <= self.angle_max:
            return False
        if vertical:
            self.vertical_angle = angle
        else:
            self.horizontal_angle = angle
        self._update_flow()
        self.sets.append(dict(request))
        return True

    def _response(self, service, ident, accepted):
        if self.fail_service:
            return {"op": "service_response", "service": service, "id": ident,
                    "result": False, "values": {}}
        if self.fail_application:
            # A transport success with a rejected application result: the
            # success predicate must fail rather than report completion.
            return {"op": "service_response", "service": service, "id": ident,
                    "result": True, "values": {"success": False}}
        return {"op": "service_response", "service": service, "id": ident,
                "result": True, "values": {"success": accepted}}

    def _flow_message(self, ident):
        return {
            "op": "publish",
            "topic": _FLOW,
            "id": ident,
            "msg": {
                "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": self.frame_id},
                "twist": {
                    "linear": {"x": self.flow["x"], "y": self.flow["y"], "z": self.flow["z"]},
                    "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
                },
            },
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == _FLOW:
                return self._flow_message(message.get("id"))
            return None
        if operation in ("unsubscribe", "advertise", "unadvertise"):
            return None
        if operation != "call_service":
            return None
        service = message.get("service")
        ident = message.get("id")
        request = message.get("args") if isinstance(message.get("args"), dict) else {}
        if service == _SET_VELOCITY:
            return self._response(service, ident, self._set_velocity(request))
        if service == _SET_HORZ:
            return self._response(service, ident, self._set_angle(request, vertical=False))
        if service == _SET_VERT:
            return self._response(service, ident, self._set_angle(request, vertical=True))
        return {"op": "service_response", "service": service, "id": ident,
                "result": False, "values": {}}
