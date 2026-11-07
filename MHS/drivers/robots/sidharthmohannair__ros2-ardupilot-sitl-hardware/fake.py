"""ROS-free recording fake for the MAVROS endpoints used by this repository.

The fake models only the wire contract the pinned mission script binds:
``/mavros/state`` (mavros_msgs/State), ``/mavros/local_position/pose``
(geometry_msgs/PoseStamped), ``/mavros/setpoint_position/local``
(PoseStamped), and the CommandBool, SetMode and CommandTOL services.  It opens
no socket, starts no ROS node and runs no flight dynamics.  Every stored value
and canned reply below is test data, not a device fact or a safe envelope.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeRos2ArdupilotSitlHardware(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # All values below are placeholders for the wire contract; they are
        # not measured vehicle state and never become Facts or Limits.
        self.connected = True                    # placeholder
        self.armed = False                      # placeholder
        self.mode = "GUIDED"                    # placeholder
        self.position = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder, metres
        self.ack_land_without_transition = False  # placeholder safety counterexample
        self.mode_calls = 0                     # placeholder call counter
        self.arm_calls = 0                      # placeholder call counter
        self.takeoff_calls = 0                 # placeholder call counter
        self.publish_calls = 0                 # placeholder call counter

        # Negative-path switches used by the repository tests.
        self.fail_mode_transport = False        # placeholder
        self.fail_mode_application = False      # placeholder
        self.mode_missing_sent = False          # placeholder
        self.fail_arm_transport = False         # placeholder
        self.fail_arm_application = False       # placeholder
        self.arm_missing_success = False        # placeholder
        self.fail_takeoff_transport = False     # placeholder
        self.fail_takeoff_application = False   # placeholder
        self.takeoff_missing_success = False    # placeholder
        self.fail_land_transport = False        # placeholder
        self.fail_land_application = False      # placeholder

    def _state_message(self):
        return {
            "connected": bool(self.connected),  # placeholder
            "armed": bool(self.armed),          # placeholder
            "guided": self.mode == "GUIDED",    # placeholder
            "manual_input": False,              # placeholder
            "mode": str(self.mode),             # placeholder
            "system_status": 3,                 # placeholder
        }

    def _pose_message(self):
        return {
            "header": {
                "frame_id": "map",              # placeholder
                "stamp": {"secs": 0, "nsecs": 0},  # placeholder
            },
            "pose": {
                "position": dict(self.position),  # placeholder
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            },
        }

    def _subscribe(self, message):
        topic = message.get("topic")
        if topic == "/mavros/state":
            return {"op": "publish", "topic": topic, "id": message.get("id"),
                    "msg": self._state_message()}
        if topic == "/mavros/local_position/pose":
            return {"op": "publish", "topic": topic, "id": message.get("id"),
                    "msg": self._pose_message()}
        return None

    def _publish(self, message):
        if message.get("topic") != "/mavros/setpoint_position/local":
            return None
        self.publish_calls += 1
        body = message.get("msg")
        pose = body.get("pose") if isinstance(body, dict) else None
        position = pose.get("position") if isinstance(pose, dict) else None
        if isinstance(position, dict):
            for axis in ("x", "y", "z"):
                value = position.get(axis)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    self.position[axis] = float(value)
        return None

    @staticmethod
    def _response(message, *, result, values):
        return {"op": "service_response", "service": message.get("service"),
                "id": message.get("id"), "result": result, "values": values}

    def _set_mode(self, message):
        self.mode_calls += 1
        args = message.get("args")
        custom_mode = args.get("custom_mode") if isinstance(args, dict) else None
        if self.fail_mode_transport or (custom_mode == "LAND" and self.fail_land_transport):
            return self._response(message, result=False,
                                  values="set_mode service unavailable")  # placeholder
        if custom_mode == "LAND" and self.fail_land_application:
            return self._response(message, result=True,
                                  values={"mode_sent": False})  # placeholder
        if self.fail_mode_application:
            return self._response(message, result=True,
                                  values={"mode_sent": False})  # placeholder
        if self.mode_missing_sent:
            return self._response(message, result=True, values={})  # placeholder
        if isinstance(custom_mode, str) and custom_mode:
            if not (custom_mode == "LAND" and self.ack_land_without_transition):
                self.mode = custom_mode
        return self._response(message, result=True,
                              values={"mode_sent": True})  # placeholder

    def _arm(self, message):
        self.arm_calls += 1
        if self.fail_arm_transport:
            return self._response(message, result=False,
                                  values="arming service unavailable")  # placeholder
        if self.fail_arm_application:
            return self._response(message, result=True,
                                  values={"success": False})  # placeholder
        if self.arm_missing_success:
            return self._response(message, result=True, values={})  # placeholder
        args = message.get("args")
        requested = args.get("value") if isinstance(args, dict) else None
        if isinstance(requested, bool):
            self.armed = requested
        return self._response(message, result=True,
                              values={"success": True})  # placeholder

    def _takeoff(self, message):
        self.takeoff_calls += 1
        if self.fail_takeoff_transport:
            return self._response(message, result=False,
                                  values="takeoff service unavailable")  # placeholder
        if self.fail_takeoff_application:
            return self._response(message, result=True,
                                  values={"success": False})  # placeholder
        if self.takeoff_missing_success:
            return self._response(message, result=True, values={})  # placeholder
        args = message.get("args")
        altitude = args.get("altitude") if isinstance(args, dict) else None
        if isinstance(altitude, (int, float)) and not isinstance(altitude, bool):
            self.position["z"] = float(altitude)
        return self._response(message, result=True,
                              values={"success": True})  # placeholder

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._subscribe(message)
        if operation == "publish":
            return self._publish(message)
        if operation == "unsubscribe" or operation == "advertise":
            return None
        if operation == "call_service":
            service = message.get("service")
            if service == "/mavros/set_mode":
                return self._set_mode(message)
            if service == "/mavros/cmd/arming":
                return self._arm(message)
            if service == "/mavros/cmd/takeoff":
                return self._takeoff(message)
            return self._response(message, result=False,
                                  values="undeclared fake service")  # placeholder
        return None
