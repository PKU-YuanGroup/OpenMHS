"""ROS-free recording fake for the XTDrone typhoon_h480_0 wire contracts.

The fake models the declared MAVROS topics and the two vendored gazebo_ros
services ``/gazebo/pause_physics`` and ``/gazebo/get_physics_properties``.
A paused flag stands for the world's paused bit: the pause sets it, the
read-back reports it, and pose and target observations are silent while it
is set. Silence while paused is an assumption tied to the model's
``enable_lockstep`` flag, not a measured PX4 trace. The fake opens no socket
and runs no ROS node, communication node, PX4 SITL, Gazebo or MAVROS.

Every stored value and switch below is test data. Each invented value is
marked ``# placeholder`` and is not a Fact or a Limit.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_SETPOINT_TOPIC = "/typhoon_h480_0/mavros/setpoint_position/local"
_TARGET_TOPIC = "/typhoon_h480_0/mavros/setpoint_raw/target_local"
_POSE_TOPIC = "/typhoon_h480_0/mavros/local_position/pose"
_PAUSE = "/gazebo/pause_physics"
_READBACK = "/gazebo/get_physics_properties"


class FakeXtdrone(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder state. last_target tracks a publication only while the
        # world is running. The pose sample never moves. retained_setpoint is
        # the last transmitted request, including one sent while paused.
        self.last_target = {"x": 0.0, "y": 0.0, "z": 0.0}       # placeholder
        self.current_position = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder
        self.retained_setpoint = None                           # placeholder
        self.paused = False           # placeholder: multi_vehicle paused default is false
        self.target_calls = 0         # placeholder call counter
        self.pose_calls = 0           # placeholder call counter
        self.publish_calls = 0        # placeholder call counter
        self.silent_target = False    # placeholder
        self.silent_pose = False      # placeholder
        self.malformed_target = False  # placeholder
        self.malformed_pose = False   # placeholder
        self.fail_publish = False     # placeholder
        self.fail_pause = False       # placeholder: the pause service is not answered
        self.fail_readback = False    # placeholder: a non-ODE engine (service result false)
        self.ignore_pause = False     # placeholder: another client unpaused before the read-back

    def send(self, message, *, timeout_s=None):
        """Raise before a position publication is recorded when the negative switch is set."""
        if (self.fail_publish and isinstance(message, dict)
                and message.get("op") == "publish"
                and message.get("topic") == _SETPOINT_TOPIC):
            raise ConnectionError("fake position-setpoint transport failure")  # placeholder
        return super().send(message, timeout_s=timeout_s)

    def _target_message(self):
        position = dict(self.last_target)  # placeholder
        if self.malformed_target:
            position = "not-an-object"      # placeholder malformed reply
        return {
            "header": {"frame_id": "map", "stamp": {"secs": 0, "nsecs": 0}},  # placeholder
            "coordinate_frame": 1,          # placeholder
            "type_mask": 0,                 # placeholder
            "position": position,
            "velocity": {"x": 0.0, "y": 0.0, "z": 0.0},              # placeholder
            "acceleration_or_force": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
            "yaw": 0.0,                     # placeholder
            "yaw_rate": 0.0,                # placeholder
        }

    def _pose_message(self):
        pose = {
            "position": dict(self.current_position),  # placeholder
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
        }
        if self.malformed_pose:
            pose = "not-an-object"          # placeholder malformed reply
        return {
            "header": {"frame_id": "map", "stamp": {"secs": 0, "nsecs": 0}},  # placeholder
            "pose": pose,
        }

    def _subscribe(self, message):
        topic = message.get("topic")
        if topic == _TARGET_TOPIC:
            self.target_calls += 1
            if self.silent_target or self.paused:
                return None
            return {"op": "publish", "topic": topic, "id": message.get("id"),
                    "msg": self._target_message()}
        if topic == _POSE_TOPIC:
            self.pose_calls += 1
            if self.silent_pose or self.paused:
                return None
            return {"op": "publish", "topic": topic, "id": message.get("id"),
                    "msg": self._pose_message()}
        return None

    def _publish(self, message):
        if message.get("topic") != _SETPOINT_TOPIC:
            return None
        self.publish_calls += 1
        body = message.get("msg")
        pose = body.get("pose") if isinstance(body, dict) else None
        position = pose.get("position") if isinstance(pose, dict) else None
        if isinstance(position, dict):
            sent = {}
            for axis in ("x", "y", "z"):
                value = position.get(axis)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    sent[axis] = float(value)
            if sent:
                self.retained_setpoint = sent
                if not self.paused:
                    self.last_target.update(sent)
        return None

    def _service(self, message):
        service = message.get("service")
        reply = {"op": "service_response", "service": service, "id": message.get("id")}
        if service == _PAUSE:
            if self.fail_pause:
                return None
            self.paused = True
            reply["result"] = True
            reply["values"] = {}
            return reply
        if service == _READBACK:
            if self.fail_readback:
                reply["result"] = False
                reply["values"] = "get_physics_properties not supported"  # placeholder
                return reply
            if self.ignore_pause:
                # Another client cleared the flag before this read-back.
                self.paused = False
            reply["result"] = True
            reply["values"] = {
                "time_step": 0.001,          # placeholder
                "pause": self.paused,
                "max_update_rate": 1000.0,   # placeholder
                "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},  # placeholder
                "ode_config": {},            # placeholder
                "success": True,             # placeholder; the binding checks pause, not this field
                "status_message": "placeholder",
            }
            return reply
        reply["result"] = False
        reply["values"] = "no other service is declared for this surface"  # placeholder
        return reply

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._subscribe(message)
        if operation == "publish":
            return self._publish(message)
        if operation == "call_service":
            return self._service(message)
        if operation in ("unsubscribe", "advertise", "unadvertise"):
            return None
        return None
