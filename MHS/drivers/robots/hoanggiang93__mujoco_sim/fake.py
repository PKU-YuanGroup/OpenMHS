"""ROS-free recording fake for the pinned mujoco_sim ROS 1 endpoints.

The fake answers only the three rosbridge operations this package declares:
the ``/mujoco/reset`` service of type ``std_srvs/Trigger`` and subscriptions
to ``/mujoco/object_states`` (``mujoco_msgs/ObjectStateArray``) and
``/mujoco/robot_joint_states`` (``sensor_msgs/JointState``).  It runs no
MuJoCo engine, ros_control loop, ROS node or simulator process.

Every value below that is not derived from the request is placeholder test
data, not a device fact; each such assignment carries a ``# placeholder``
marker.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_RESET = "/mujoco/reset"
_OBJECT_STATES = "/mujoco/object_states"
_ROBOT_JOINT_STATES = "/mujoco/robot_joint_states"


class FakeMujocoSim(RecordingRosTransport):
    """Package-local recording transport with the pinned service/topic shapes."""

    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # placeholder negative-path switches and counters, not device facts
        self.fail_reset_service = False
        self.fail_reset_application = False
        self.omit_object_states = False
        self.silent_object_states = False
        self.silent_joint_states = False
        self.reset_count = 0
        self.object_states_reads = 0
        self.joint_states_reads = 0

    def _object_states_message(self):
        # placeholder sample: one body at the origin with identity orientation
        return {
            "object_states": [
                {
                    "name": "box",  # placeholder
                    "pose": {
                        "position": {"x": 0.0, "y": 0.0, "z": 0.5},  # placeholder
                        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                    },
                    "velocity": {
                        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                    },
                }
            ]
        }

    def _joint_states_message(self):
        # placeholder sample: one named hinge joint at rest
        return {
            "name": ["joint1"],  # placeholder
            "position": [0.0],  # placeholder
            "velocity": [0.0],  # placeholder
            "effort": [0.0],  # placeholder
        }

    def _respond(self, message):
        operation = message.get("op")
        ident = message.get("id")
        if operation == "subscribe":
            topic = message.get("topic")
            if topic == _OBJECT_STATES:
                self.object_states_reads += 1
                if self.silent_object_states:
                    return None
                body = self._object_states_message()
                if self.omit_object_states:
                    body = {}
                return {"op": "publish", "topic": topic, "id": ident, "msg": body}
            if topic == _ROBOT_JOINT_STATES:
                self.joint_states_reads += 1
                if self.silent_joint_states:
                    return None
                return {"op": "publish", "topic": topic, "id": ident,
                        "msg": self._joint_states_message()}
            return None
        if operation == "call_service":
            service = message.get("service")
            if service == _RESET:
                if self.fail_reset_service:
                    return {"op": "service_response", "service": service, "id": ident,
                            "result": False, "values": "reset service unavailable"}  # placeholder
                self.reset_count += 1
                if self.fail_reset_application:
                    # The Trigger transport answered but the callback reported failure.
                    return {"op": "service_response", "service": service, "id": ident,
                            "result": True,
                            "values": {"success": False,
                                       "message": "Failed to reset"}}  # placeholder
                return {"op": "service_response", "service": service, "id": ident,
                        "result": True,
                        "values": {"success": True,
                                   "message": "Reset successfully!"}}  # placeholder
            return {"op": "service_response", "service": service, "id": ident,
                    "result": False, "values": "undeclared service"}  # placeholder
        return None
