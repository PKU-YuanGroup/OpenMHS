"""ROS-free recording fake for the cpezzato Panda simulation endpoints.

The fake models only the pinned wire contract used by ``driver.py``: a
``sensor_msgs/JointState`` publication on ``/robot1/joint_states``, a
``std_msgs/Float64`` free-energy publication on ``/panda_free_energy``, the
seven absolute effort command topics the AIC node advertises, and the companion
gazebo_ros services ``/gazebo/pause_physics`` and
``/gazebo/get_physics_properties`` (the e-stop and its read-back).  A paused
flag stands for the Gazebo world's: the pause sets it, the read-back reports
it, ``/robot1/joint_states`` is silent while it is set, and an effort stored
while paused reaches no joint.  It runs no Gazebo, controller manager, AIC
loop, physics engine or MoveIt.

Every number and message below is test data, not a device fact, and is marked
``# placeholder``.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

#: Placeholder joint names in the order the fake publishes them (test data).
_JOINT_NAMES = [
    "panda_joint1",
    "panda_joint2",
    "panda_joint3",
    "panda_joint4",
    "panda_joint5",
    "panda_joint6",
    "panda_joint7",
]

#: The seven absolute effort topics the pinned AIC constructor advertises.
_EFFORT_TOPICS = {f"/robot1/panda_joint{joint}_controller/command"
                  for joint in range(1, 8)}  # placeholder joint count


class FakePandaSimulation(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.positions = [0.0] * 7                 # placeholder
        self.velocities = [0.0] * 7                # placeholder
        self.efforts = [0.0] * 7                   # placeholder
        self.free_energy = 0.0                     # placeholder
        self.seq = 0                               # placeholder ROS 1 header sequence
        self.commanded_efforts = {}                # placeholder recorded publications (the controllers' commands)
        self.applied_efforts = {}                  # placeholder: efforts a running world would write to the joints
        self.silent_joint_states = False           # placeholder negative-path switch
        self.omit_joint_state_position = False     # placeholder negative-path switch
        self.paused = False                        # placeholder: the fake world starts running
        self.fail_pause = False                    # placeholder negative-path switch: the pause is not answered
        self.fail_readback = False                 # placeholder negative-path switch: a non-ODE engine
        self.ignore_pause = False                  # placeholder negative-path switch: another client unpaused

    def _joint_state(self, ident):
        # A ROS 1 sensor_msgs/JointState always carries a std_msgs/Header (seq, secs/nsecs).
        self.seq += 1  # placeholder
        message = {
            "header": {"seq": self.seq, "stamp": {"secs": 0, "nsecs": 0},  # placeholder
                       "frame_id": ""},                                     # placeholder
            "name": list(_JOINT_NAMES),
            "velocity": list(self.velocities),     # placeholder
            "effort": list(self.efforts),          # placeholder
        }
        if not self.omit_joint_state_position:
            message["position"] = list(self.positions)  # placeholder
        return {
            "op": "publish",
            "topic": "/robot1/joint_states",
            "id": ident,
            "msg": message,
        }

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")
        if service == "/gazebo/pause_physics":
            if self.fail_pause:
                return None  # no answer: the e-stop's request times out
            self.paused = True
            return {"op": "service_response", "service": service, "id": ident, "result": True, "values": {}}
        if service == "/gazebo/get_physics_properties":
            if self.fail_readback:
                return {"op": "service_response", "service": service, "id": ident, "result": False,
                        "values": "get_physics_properties not supported"}  # placeholder
            return {"op": "service_response", "service": service, "id": ident, "result": True,
                    "values": {"time_step": 0.001, "pause": self.paused and not self.ignore_pause,  # placeholder
                               "max_update_rate": 1000.0, "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},
                               "ode_config": {}, "success": True, "status_message": "placeholder"}}
        return {"op": "service_response", "service": service, "id": ident, "result": False,
                "values": {}}  # placeholder rejection

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            ident = message.get("id")
            if topic == "/robot1/joint_states":
                if self.silent_joint_states or self.paused:  # a paused world runs no joint_state_controller
                    return None
                return self._joint_state(ident)
            if topic == "/panda_free_energy":
                return {
                    "op": "publish",
                    "topic": "/panda_free_energy",
                    "id": ident,
                    "msg": {"data": self.free_energy},  # placeholder
                }
            return None
        if operation == "publish":
            topic = message.get("topic")
            if topic in _EFFORT_TOPICS:
                value = (message.get("msg") or {}).get("data")
                self.commanded_efforts[topic] = value  # placeholder recorded command, paused or not
                if not self.paused:                    # a paused world writes no effort to a joint
                    self.applied_efforts[topic] = value
            return None
        if operation == "call_service":
            return self._service(message)
        return None
