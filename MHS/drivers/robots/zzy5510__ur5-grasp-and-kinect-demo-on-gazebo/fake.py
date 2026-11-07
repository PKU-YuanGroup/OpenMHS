"""ROS-free contract fake for the pinned UR5 grasp Gazebo simulation.

The fake models the declared rosbridge wire contract from ``driver.py``: the
private ``pause_physics`` and ``unpause_physics`` services and the ``/clock``
and ``/joint_states`` subscriptions.  It is an analytic stand-in, not a
recording of captured traffic; it runs no ROS, Gazebo, ODE, move_group or
controller code.  Every number and canned observation below is test data and
is marked ``# placeholder``.

While paused the upstream world-update clock hook and the controller update
loop stop, so the fake answers neither subscription.  A subscription that
receives no event waits at the client deadline, as the live topic would.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeUr5GraspKinectGazebo(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.paused = False  # placeholder state
        self.clock_secs = 12  # placeholder
        self.clock_nsecs = 340000000  # placeholder
        self.joint_names = [
            "shoulder_pan_joint",    # placeholder data
            "shoulder_lift_joint",   # placeholder data
            "elbow_joint",           # placeholder data
            "wrist_1_joint",         # placeholder data
            "wrist_2_joint",         # placeholder data
            "wrist_3_joint",         # placeholder data
            "arm_to_finger1",        # placeholder data
            "arm_to_finger2",        # placeholder data
        ]
        self.joint_positions = [0.0] * 8  # placeholder
        self.joint_velocities = [0.0] * 8  # placeholder
        self.joint_efforts = [0.0] * 8  # placeholder
        self.pause_calls = []  # placeholder recording helper, no device meaning
        self.resume_calls = []  # placeholder recording helper, no device meaning
        self.fail_pause_service = False  # placeholder negative-path switch
        self.reject_pause_application = False  # placeholder negative-path switch
        self.malformed_pause_response = False  # placeholder negative-path switch
        self.fail_resume_service = False  # placeholder negative-path switch
        self.reject_resume_application = False  # placeholder negative-path switch

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "call_service":
            return self._service(message)
        return None

    def _observation(self, message):
        if self.paused:
            return None
        topic = message.get("topic")
        ident = message.get("id")
        if topic == "/clock":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {"clock": {"secs": self.clock_secs, "nsecs": self.clock_nsecs}},  # placeholder
            }
        if topic == "/joint_states":
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
        return None

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")
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
            if self.fail_resume_service:
                return self._response(service, ident, False)
            if self.reject_resume_application:
                return self._response(service, ident, True, {"rejected": True})  # placeholder refusal
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
