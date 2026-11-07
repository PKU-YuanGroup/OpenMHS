"""ROS-free analytic contract fake for the pinned UR5LegoVision endpoints.

The fake models the declared wire contract from ``driver.py``: the three
absolute motion services, the two Gazebo ``std_srvs/Empty`` physics services,
and subscriptions to ``/ur5/joint_states`` and ``/ur5/ee_pose``.  It is an
analytic stand-in, not a recording of captured traffic; it runs no ROS,
Gazebo, MoveIt or controller code.  Every number and canned observation below
is test data and is marked ``# placeholder``.

While "paused", the upstream motion callbacks neither refuse nor answer: they
wait in a simulated-time ``rate.sleep()`` until Gazebo is unpaused.  The fake
has no clock, so it answers motion calls at once whether or not it is paused;
it records the paused state only for the pause/resume cases.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeUr5Legovision(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.paused = False  # placeholder state
        self.joint_names = [
            "shoulder_pan_joint",  # placeholder data
            "shoulder_lift_joint",  # placeholder data
            "elbow_joint",  # placeholder data
            "wrist_1_joint",  # placeholder data
            "wrist_2_joint",  # placeholder data
            "wrist_3_joint",  # placeholder data
        ]
        self.joint_positions = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder
        self.joint_velocities = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder
        self.joint_efforts = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder
        self.ee_position = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder
        self.ee_orientation = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}  # placeholder
        self.gripper_diameter_mm = 40.0  # placeholder
        self.move_joint_calls = []  # recording helper, no device meaning
        self.gripper_calls = []  # recording helper, no device meaning
        self.pause_calls = []  # recording helper, no device meaning
        self.resume_calls = []  # recording helper, no device meaning
        self.fail_move_service = False  # placeholder negative-path switch
        self.reject_move_application = False  # placeholder negative-path switch
        self.malformed_move_response = False  # placeholder negative-path switch
        self.fail_gripper_service = False  # placeholder negative-path switch
        self.reject_gripper_application = False  # placeholder negative-path switch
        self.malformed_gripper_response = False  # placeholder negative-path switch
        self.fail_pause_service = False  # placeholder negative-path switch
        self.reject_pause_application = False  # placeholder negative-path switch
        self.malformed_pause_response = False  # placeholder negative-path switch

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
        if topic == "/ur5/joint_states":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},  # placeholder
                    "name": list(self.joint_names),  # placeholder
                    "position": list(self.joint_positions),  # placeholder
                    "velocity": list(self.joint_velocities),  # placeholder
                    "effort": list(self.joint_efforts),  # placeholder
                },
            }
        if topic == "/ur5/ee_pose":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "position": dict(self.ee_position),  # placeholder
                    "orientation": dict(self.ee_orientation),  # placeholder
                },
            }
        return None

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")
        args = message.get("args") if isinstance(message.get("args"), dict) else {}
        if service == "/ur5/move_joints":
            self.move_joint_calls.append(dict(args))
            if self.fail_move_service:
                return self._response(service, ident, False)
            if self.malformed_move_response:
                return self._response(service, ident, True, "malformed")  # placeholder malformed reply
            target = args.get("q_des")
            if not isinstance(target, list) or len(target) != 6:
                return self._response(service, ident, True, {"success": False})  # placeholder refusal
            if self.reject_move_application:
                return self._response(service, ident, True, {"success": False})  # placeholder refusal
            self.joint_positions = [float(value) for value in target]  # placeholder echo, not physics
            return self._response(service, ident, True, {"success": True})
        if service == "/ur5/move_gripper":
            self.gripper_calls.append(dict(args))
            if self.fail_gripper_service:
                return self._response(service, ident, False)
            if self.malformed_gripper_response:
                return self._response(service, ident, True, "malformed")  # placeholder malformed reply
            diameter = args.get("data")
            if not isinstance(diameter, (int, float)) or isinstance(diameter, bool):
                return self._response(service, ident, True, {"ack": False})  # placeholder refusal
            if self.reject_gripper_application:
                return self._response(service, ident, True, {"ack": False})  # placeholder refusal
            self.gripper_diameter_mm = float(diameter)  # placeholder echo, not physics
            return self._response(service, ident, True, {"ack": True})
        if service == "/gazebo/pause_physics":
            self.pause_calls.append(True)  # placeholder recording
            if self.fail_pause_service:
                return self._response(service, ident, False)
            if self.malformed_pause_response:
                return self._response(service, ident, True, "malformed")  # placeholder malformed reply
            if self.reject_pause_application:
                return self._response(service, ident, True, {"rejected": True})  # placeholder refusal
            self.paused = True  # placeholder state
            return self._response(service, ident, True, {})
        if service == "/gazebo/unpause_physics":
            self.resume_calls.append(True)  # placeholder recording
            self.paused = False  # placeholder state
            return self._response(service, ident, True, {})
        return self._response(service, ident, False)

    @staticmethod
    def _response(service, ident, result, values=None):
        return {
            "op": "service_response",
            "service": service,
            "id": ident,
            "result": result,
            "values": {} if values is None else values,
        }
