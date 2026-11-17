"""ROS-free analytic fake for the pinned dobot_bringup_v4 ROS 2 endpoints.

The fake models the wire contract declared in ``driver.py``:

* subscriptions to ``/joint_states`` (sensor_msgs/msg/JointState), the tool-vector topic
  (dobot_msgs_v4/msg/ToolVectorActual) and the status topic (dobot_msgs_v4/msg/RobotStatus);
* ``call_service`` on the declared MovJ, MovL, Stop and EnableRobot services.

It is an in-memory analytic stand-in, not a recording of captured traffic and not the upstream
node.  It runs no ROS graph, no TCP connection and no controller.  Every number below is test data
and is marked ``# placeholder``; none is a device fact, a Limit or a reference.  In particular the
fake moves instantly and has no kinematics, no dynamics and no queue: a MovJ updates the published
joint positions at once, and a MovL updates the published tool pose at once.  That is a fidelity gap
of the fake, not a claim about the arm.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_JOINTS = "/joint_states"
_TOOL = "/dobot_msgs_v4/msg/ToolVectorActual"
_STATUS = "/dobot_msgs_v4/msg/RobotStatus"

_MOVJ = "/dobot_bringup_ros2/srv/MovJ"
_MOVL = "/dobot_bringup_ros2/srv/MovL"
_STOP = "/dobot_bringup_ros2/srv/Stop"
_ENABLE = "/dobot_bringup_ros2/srv/EnableRobot"


class FakeDobot6AxisRos2(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder state only: no value here is a device fact.
        self.joint_positions = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder
        self.tcp_pose = {"x": 300.0, "y": 0.0, "z": 250.0,       # placeholder
                         "rx": 0.0, "ry": 90.0, "rz": 0.0}       # placeholder
        self.enabled = True          # placeholder
        self.connected = True        # placeholder
        self.stopped = False         # placeholder observation flag
        self.service_calls = []      # recording helper, no device meaning
        self._next_result_id = 1     # placeholder queue-id counter
        # Placeholder negative-path switches.
        self.fail_service = False
        self.fail_application = False
        self.malformed_reply = False
        self.dashboard_failure = False  # placeholder: upstream swallowed TCP error leaves res at zero

    # -- inbound rosbridge messages ---------------------------------------------------------
    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "call_service":
            return self._service(message)
        return None

    def _observation(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        if topic == _JOINTS:
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": "dummy_link"},  # placeholder
                    "name": ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"],
                    "position": list(self.joint_positions),  # placeholder
                    "velocity": [], "effort": [],
                },
            }
        if topic == _TOOL:
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": dict(self.tcp_pose),  # placeholder
            }
        if topic == _STATUS:
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {"is_enable": self.enabled, "is_connected": self.connected},  # placeholder
            }
        return None

    def _reply(self, message, service, values):
        result = not self.fail_service
        if self.fail_application:
            values = dict(values, res=-1)  # placeholder nonzero controller error, still a ROS service response
        return {
            "op": "service_response",
            "service": service,
            "id": message.get("id"),
            "result": result,
            "values": values,
        }

    def _service(self, message):
        service = message.get("service")
        if service not in (_MOVJ, _MOVL, _STOP, _ENABLE):
            return {
                "op": "service_response",
                "service": service,
                "id": message.get("id"),
                "result": False,
                "values": {},
            }
        self.service_calls.append({"service": service, "args": message.get("args")})
        if self.malformed_reply:
            # A reply that does not carry the declared response fields: the bridge must not
            # interpret a missing res as an acknowledgement.
            return {"op": "service_response", "service": service,
                    "id": message.get("id"), "result": True, "values": {}}
        if self.fail_service or self.fail_application:
            values = {"res": -1}  # placeholder rejection, no state change
            if service in (_MOVJ, _MOVL):
                values["robot_return"] = ""
            return self._reply(message, service, values)
        if service == _MOVJ:
            return self._move_joint(message)
        if service == _MOVL:
            return self._move_pose(message)
        if service == _STOP:
            if self.dashboard_failure:
                # command.cpp:157-160 catches a TCP error without setting err_id, then
                # callRosService returns true (:221-228). Stop.srv still carries default res=0.
                return self._reply(message, service, {"res": 0})
            self.stopped = True                     # placeholder
            return self._reply(message, service, {"res": 0})  # placeholder reply; Stop.srv has no robot_return
        self.enabled = True                         # placeholder
        return self._reply(message, service, {"res": 0})  # placeholder reply; EnableRobot.srv has no robot_return

    def _move_joint(self, message):
        args = message.get("args") if isinstance(message.get("args"), dict) else {}
        if args.get("mode") is not True:
            return self._reply(message, _MOVJ, {"res": -1, "robot_return": ""})  # placeholder reply
        angles = []
        for name in ("a", "b", "c", "d", "e", "f"):
            value = args.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return self._reply(message, _MOVJ, {"res": -1, "robot_return": ""})  # placeholder reply
            angles.append(float(value))
        # Placeholder instant completion: the fake has no queue and no motion over time.
        self.joint_positions = [value * 3.141592653589793 / 180.0 for value in angles]  # unit conversion
        result_id = self._next_result_id
        self._next_result_id += 1
        return self._reply(message, _MOVJ, {"res": 0, "robot_return": "{" + str(result_id) + "}"})  # placeholder reply

    def _move_pose(self, message):
        args = message.get("args") if isinstance(message.get("args"), dict) else {}
        if args.get("mode") is not False:
            return self._reply(message, _MOVL, {"res": -1, "robot_return": ""})  # placeholder reply
        values = []
        for name in ("a", "b", "c", "d", "e", "f"):
            value = args.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return self._reply(message, _MOVL, {"res": -1, "robot_return": ""})  # placeholder reply
            values.append(float(value))
        # Placeholder instant completion; the pose is echoed, no inverse kinematics are modelled.
        self.tcp_pose = {"x": values[0], "y": values[1], "z": values[2],
                         "rx": values[3], "ry": values[4], "rz": values[5]}
        result_id = self._next_result_id
        self._next_result_id += 1
        return self._reply(message, _MOVL, {"res": 0, "robot_return": "{" + str(result_id) + "}"})  # placeholder reply
