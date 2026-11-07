"""ROS-free canned fake for the pinned Webots demo endpoints.

The fake answers only the rosbridge operations this package declares:

* ``call_service`` on ``/robot/robot/time_step`` of type ``webots_ros/set_int``,
  for the step and the 0-value request bindings (no e-stop binding);
* ``subscribe`` on ``/robot/gps/values`` of type
  ``geometry_msgs/PointStamped``, returning one canned sample.

It is a canned contract stand-in, not the Webots simulator and not a recording
of captured traffic.  It runs no ROS node, no Webots controller, no physics and
no wall-clock loop.  Every number and string below that is not taken from the
request is placeholder test data, not a device fact or a safety limit.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_TIME_STEP_SERVICE = "/robot/robot/time_step"
_GPS_TOPIC = "/robot/gps/values"


class FakeWebotsDemo(RecordingRosTransport):
    """Package-local canned transport with the pinned service and topic shapes."""

    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.steps = 0                         # placeholder counter
        self.stopped = False                   # placeholder state
        self.gps_x = 1.0                       # placeholder
        self.gps_y = 2.0                       # placeholder
        self.gps_z = 0.0                       # placeholder
        self.gps_frame = "robot"               # placeholder frame name
        self.last_time_step = None             # placeholder request echo
        self.fail_service = False              # placeholder negative-path switch
        self.fail_application = False          # placeholder negative-path switch
        self.omit_gps = False                  # placeholder negative-path switch

    def _respond(self, message):
        operation = message.get("op")
        if operation == "call_service":
            return self._service(message)
        if operation == "subscribe":
            return self._observation(message)
        return None

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")
        if service != _TIME_STEP_SERVICE:
            return {"op": "service_response", "service": service, "id": ident,
                    "result": False, "values": "undeclared service"}  # placeholder
        if self.fail_service:
            return {"op": "service_response", "service": service, "id": ident,
                    "result": False, "values": "time_step service unavailable"}  # placeholder
        arguments = message.get("args")
        value = arguments.get("value") if isinstance(arguments, dict) else None
        if not isinstance(value, int) or isinstance(value, bool):
            return {"op": "service_response", "service": service, "id": ident,
                    "result": True, "values": {"success": False}}  # placeholder rejection
        if self.fail_application:
            return {"op": "service_response", "service": service, "id": ident,
                    "result": True, "values": {"success": False}}  # placeholder rejection
        self.last_time_step = value            # placeholder request echo
        if value == 0:
            self.stopped = True                # placeholder state
        elif value > 0:
            self.steps += 1                    # placeholder counter
        return {"op": "service_response", "service": service, "id": ident,
                "result": True, "values": {"success": True}}

    def _observation(self, message):
        if message.get("topic") != _GPS_TOPIC or self.omit_gps:
            return None
        return {
            "op": "publish",
            "topic": _GPS_TOPIC,
            "id": message.get("id"),
            "msg": {
                # ROS 1 std_msgs/Header: seq, stamp (secs, nsecs), frame_id.
                "header": {
                    "seq": 0,                    # placeholder
                    "frame_id": self.gps_frame,  # placeholder
                    "stamp": {"secs": 0, "nsecs": 0},  # placeholder
                },
                "point": {
                    "x": self.gps_x,             # placeholder
                    "y": self.gps_y,             # placeholder
                    "z": self.gps_z,             # placeholder
                },
            },
        }
