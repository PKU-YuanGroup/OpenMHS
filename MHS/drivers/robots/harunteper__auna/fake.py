"""ROS-free analytic fake for the pinned AuNa cmd_vel multiplexer contract.

The fake models the upstream wire contract declared in ``driver.py``:

* ``auna_msgs/srv/SetString`` on ``/robot1/toggle_cmd_vel_source``;
* ``std_srvs/srv/Trigger`` on ``/robot1/get_source_status``;
* one ``geometry_msgs/msg/TwistStamped`` publication on
  ``/robot1/cmd_vel/teleop``.

It is an analytic contract stand-in, not a replay of captured traffic.  It
runs no ROS, no rosbridge, no multiplexer node, no Gazebo plugin and no
vehicle.  Every number and canned reply below is test data and is marked
``# placeholder``; none is a device fact or a safety limit.

The fake keeps the source name and the last teleop command only, so a test can
see that a request reached the modelled upstream contract.  It does not model
the 20 Hz timer that repeats the cached command, and it never claims that the
vehicle moved or stopped.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

#: Source names the shipped control configuration declares.  This is modelled
#: from auna_common/config/control/topics.yaml, not invented device state.
_SOURCES = ("wallfollowing", "teleop", "cacc", "nav2")


class FakeAuna(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.current_source = "OFF"          # placeholder state
        self.last_command = {                # placeholder state
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},   # placeholder
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
        }
        self.fail_source_service = False     # placeholder negative-path switch
        self.reject_source_application = False  # placeholder negative-path switch
        self.malformed_source_values = False  # placeholder negative-path switch
        self.fail_publish = False            # placeholder negative-path switch
        self.malformed_status_values = False  # placeholder negative-path switch

    def _respond(self, message):
        operation = message.get("op")
        if operation == "advertise":
            return None
        if operation == "publish":
            if message.get("topic") == "/robot1/cmd_vel/teleop":
                if self.fail_publish:
                    raise ConnectionError("injected teleop publication failure")
                twist = message.get("msg", {}).get("twist", {})  # placeholder structure
                if isinstance(twist, dict):
                    self.last_command = {
                        "linear": dict(twist.get("linear", {})),
                        "angular": dict(twist.get("angular", {})),
                    }
            return None
        if operation == "subscribe":
            return None
        if operation == "call_service":
            service = message.get("service")
            if service == "/robot1/toggle_cmd_vel_source":
                return self._source_service(message)
            if service == "/robot1/get_source_status":
                return self._status_service(message)
            return {
                "op": "service_response",
                "service": service,
                "id": message.get("id"),
                "result": False,
                "values": {},
            }  # placeholder negative reply
        return None

    def _source_service(self, message):
        service = message.get("service")
        args = message.get("args")
        data = args.get("data") if isinstance(args, dict) else None
        if self.fail_source_service:
            return {
                "op": "service_response",
                "service": service,
                "id": message.get("id"),
                "result": False,
                "values": {},
            }  # placeholder transport failure
        if not isinstance(data, str):
            return {
                "op": "service_response",
                "service": service,
                "id": message.get("id"),
                "result": True,
                "values": {"success": False, "message": "malformed SetString request"},  # placeholder reply
            }
        if self.reject_source_application:
            return {
                "op": "service_response",
                "service": service,
                "id": message.get("id"),
                "result": True,
                "values": {"success": False, "message": "source rejected by injected fault"},  # placeholder reply
            }
        if self.malformed_source_values:
            return {
                "op": "service_response",
                "service": service,
                "id": message.get("id"),
                "result": True,
                "values": {"success": "not-a-bool", "message": "malformed success field"},  # placeholder reply
            }
        if data == "OFF":
            self.current_source = "OFF"       # placeholder state
            success, reply = True, "Velocity source turned OFF"  # placeholder reply
        elif data in _SOURCES:
            self.current_source = data        # placeholder state
            success, reply = True, "Velocity source set to: " + data  # placeholder reply
        else:
            success, reply = False, "Requested source '" + data + "' not in input_sources"  # placeholder reply
        return {
            "op": "service_response",
            "service": service,
            "id": message.get("id"),
            "result": True,
            "values": {"success": success, "message": reply},
        }

    def _status_service(self, message):
        service = message.get("service")
        if self.malformed_status_values:
            values = {"success": True}  # placeholder malformed reply
        else:
            values = {"success": True, "message": "Current source: " + self.current_source}  # placeholder reply
        return {
            "op": "service_response",
            "service": service,
            "id": message.get("id"),
            "result": True,
            "values": values,
        }
