"""ROS-free analytic fake for the pinned panda_simulation wire contract.

The fake answers three upstream endpoints: the absolute ``/joint_states``
subscription (sensor_msgs/JointState), the absolute
``/joint_position_controller/command`` publication (std_msgs/Float64MultiArray)
and the absolute ``/robot_control_stop`` service (panda_msgs/RobotStopMsg, an
empty service), and the companion gazebo_ros services ``/gazebo/pause_physics``
and ``/gazebo/get_physics_properties`` (the e-stop and its read-back).  A paused
flag stands for the Gazebo world's: the pause sets it, the read-back reports it,
``/joint_states`` is silent while it is set, and a command stored while paused
moves no joint.  It runs no Gazebo, ros_control controller, MoveIt planning
group or Panda physics, and it is not a replay of captured ROS traffic.

Every number below is placeholder test data, not a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

#: The clone's collision detector says /joint_states publishes the two finger
#: joints first (panda_safety/src/CollisionDetector.cpp:40-41); these names and
#: positions are test data.
_JOINT_NAMES = [  # placeholder names and values
    "panda_finger_joint1",
    "panda_finger_joint2",
    "panda_joint1",
    "panda_joint2",
    "panda_joint3",
    "panda_joint4",
    "panda_joint5",
    "panda_joint6",
    "panda_joint7",
]


class FakePandaSimulation(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.joint_positions = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder
        self.stopped = False                       # placeholder state
        self.fail_stop_service = False             # placeholder negative-path switch
        self.fail_stop_application = False         # placeholder negative-path switch
        self.malformed_stop_response = False       # placeholder negative-path switch
        self.drop_joint_state = False              # placeholder negative-path switch
        self.ignore_joint_command = False          # placeholder negative-path switch
        self.seq = 0                               # placeholder ROS 1 header sequence
        self.stamp_secs = 0                        # placeholder
        self.stamp_nsecs = 0                       # placeholder
        self.received_commands = []                # placeholder recorded request data
        self.stored_command = None                 # placeholder: the custom controller's command_
        self.paused = False                        # placeholder: the fake starts running
        self.fail_pause = False                    # placeholder negative-path switch: the pause is not answered
        self.fail_readback = False                 # placeholder negative-path switch: a non-ODE engine
        self.ignore_pause = False                  # placeholder negative-path switch: another client unpaused

    def _joint_state_message(self):
        # The ROS 1 sensor_msgs/JointState shape: Header with seq and secs/nsecs, then
        # the name, position, velocity and effort arrays.
        self.seq += 1  # placeholder
        return {
            "header": {"seq": self.seq,  # placeholder
                       "stamp": {"secs": self.stamp_secs, "nsecs": self.stamp_nsecs},  # placeholder
                       "frame_id": ""},
            "name": list(_JOINT_NAMES),
            "position": list(self.joint_positions),
            "velocity": [0.0] * len(_JOINT_NAMES),  # placeholder
            "effort": [0.0] * len(_JOINT_NAMES),    # placeholder
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == "/joint_states" and not self.drop_joint_state and not self.paused:
                return {
                    "op": "publish",
                    "topic": "/joint_states",
                    "id": message.get("id"),
                    "msg": self._joint_state_message(),
                }
            return None
        if operation == "publish":
            if message.get("topic") == "/joint_position_controller/command":
                data = (message.get("msg") or {}).get("data")
                self.received_commands.append(list(data) if isinstance(data, list) else data)
                if (not self.ignore_joint_command and isinstance(data, list)
                        and len(data) == 7):  # placeholder length
                    self.stored_command = list(data)        # command_ = msg->data, paused or not
                    if not self.paused:                     # a paused world writes no joint command
                        self.joint_positions[2:] = list(data)  # placeholder finger prefix
                        self.stopped = False                   # placeholder state transition
            return None
        if operation == "call_service":
            service = message.get("service")
            if service == "/gazebo/pause_physics":
                if self.fail_pause:
                    return None  # no answer: the e-stop's request times out
                self.paused = True
                return {"op": "service_response", "service": service, "id": message.get("id"), "result": True,
                        "values": {}}
            if service == "/gazebo/get_physics_properties":
                if self.fail_readback:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": False, "values": "get_physics_properties not supported"}  # placeholder
                return {"op": "service_response", "service": service, "id": message.get("id"), "result": True,
                        "values": {"time_step": 0.001, "pause": self.paused and not self.ignore_pause,  # placeholder
                                   "max_update_rate": 1000.0, "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},
                                   "ode_config": {}, "success": True, "status_message": "placeholder"}}
            if service == "/robot_control_stop":
                if self.malformed_stop_response:
                    # A response that omits the transport result is not a successful stop.
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "values": {}}  # placeholder malformed reply
                if self.fail_stop_service:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": False, "values": "stop service unavailable"}  # placeholder
                self.stopped = True  # placeholder state transition
                if self.fail_stop_application:
                    # The transport answered, but the service's application predicate is not met.
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": True, "values": {"rejected": True}}  # placeholder
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": True, "values": {}}
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": False, "values": {}}  # placeholder rejection
        return None
