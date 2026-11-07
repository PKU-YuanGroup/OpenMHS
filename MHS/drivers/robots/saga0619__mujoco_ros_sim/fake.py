"""ROS-free analytic contract fake for the mujoco_ros_sim rosbridge endpoints.

The fake models only the wire contract declared in ``driver.py``: fresh
``sensor_msgs/JointState``, ``mujoco_ros_msgs/SensorState`` and
``std_msgs/Float32`` samples on the three observation topics, and recorded
``mujoco_ros_msgs/JointSet`` publications.  It is not a replay of captured
traffic.  It runs no MuJoCo, ROS graph, physics or controller.  Every number
below is test data, not a device fact, and each is marked ``# placeholder``.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_JOINT_SET = "/mujoco_ros_interface/joint_set"
_JOINT_STATES = "/mujoco_ros_interface/joint_states"
_SENSOR_STATES = "/mujoco_ros_interface/sensor_states"
_SIM_TIME = "/mujoco_ros_interface/sim_time"


class FakeMujocoRosSim(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Fixed placeholder observations; the upstream sizes these from the
        # loaded MJCF model (m->nu, m->njnt, m->nsensor, m->sensor_dim).
        self.joint_names = ["joint_0", "joint_1"]          # placeholder
        self.joint_positions = [0.0, 0.0]                  # placeholder
        self.joint_velocities = [0.0, 0.0]                 # placeholder
        self.joint_accelerations = [0.0, 0.0]              # placeholder
        self.sensor_names = ["sensor_0", "user information"]  # placeholder
        self.sensor_values = [[0.0], [0.0, 0.0]]           # placeholder
        self.sim_time = 0.5                                # placeholder
        self.joint_set_messages = []                       # outbound log helper, no device meaning
        # Negative-path switches used by test_driver.py only.
        self.fail_next_send = False                        # placeholder
        self.drop_joint_states = False                     # placeholder
        self.malformed_joint_states = False                # placeholder

    def _respond(self, message):
        if self.fail_next_send:
            self.fail_next_send = False
            raise ConnectionError("placeholder transport failure")
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "publish" and message.get("topic") == _JOINT_SET:
            self.joint_set_messages.append(message)
        return None

    def _observation(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        if topic == _JOINT_STATES:
            if self.drop_joint_states:
                return None
            if self.malformed_joint_states:
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": ident,
                    "msg": {"position": "not-an-array"},  # placeholder malformed reply
                }
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},  # placeholder ROS 1 Header
                    "name": list(self.joint_names),
                    "position": list(self.joint_positions),
                    "velocity": list(self.joint_velocities),
                    "effort": list(self.joint_accelerations),
                },
            }
        if topic == _SENSOR_STATES:
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},  # placeholder ROS 1 Header
                    "sensor": [
                        {"name": name, "data": list(values)}
                        for name, values in zip(self.sensor_names, self.sensor_values)
                    ],
                },
            }
        if topic == _SIM_TIME:
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {"data": self.sim_time},
            }
        return None
