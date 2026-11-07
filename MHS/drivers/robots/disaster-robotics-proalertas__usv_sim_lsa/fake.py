"""ROS-free recording fake for the USV_SIM_LSA differential-boat endpoints.

The fake models the pinned wire contract used by the driver: the heading
controller goal, state, result and thruster topics, and the Gazebo
``std_srvs/Empty`` pause, unpause and reset services.  It runs no physics and
does not replay captured traffic; every number below is test data, not a
device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeUsvSimLsa(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond, **_options)
        self.paused = False                    # placeholder state
        self.state_x = 240.0                   # placeholder
        self.state_y = 95.0                    # placeholder
        self.state_z = 1.0                     # placeholder
        self.goal_x = 240.0                    # placeholder
        self.goal_y = 95.0                     # placeholder
        self.result_flag = 0.0                 # placeholder
        self.thruster_left = 100.0             # placeholder
        self.thruster_right = 100.0            # placeholder
        self.fail_pause_service = False        # placeholder negative-path switch
        self.fail_pause_application = False    # placeholder negative-path switch
        self.fail_unpause_service = False      # placeholder negative-path switch
        self.fail_reset_service = False        # placeholder negative-path switch
        self.reject_reset_application = False  # placeholder negative-path switch

    def _state_message(self):
        return {
            "header": {"frame_id": "world", "stamp": {"secs": 0, "nsecs": 0}},  # placeholder
            "child_frame_id": "base_link",
            "pose": {
                "pose": {
                    "position": {"x": self.state_x, "y": self.state_y, "z": self.state_z},  # placeholder
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                },
                "covariance": [0.0] * 36,  # placeholder
            },
            "twist": {
                "twist": {
                    "linear": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                    "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                },
                "covariance": [0.0] * 36,  # placeholder
            },
        }

    def _joint_message(self):
        return {
            "header": {"frame_id": "", "stamp": {"secs": 0, "nsecs": 0}},  # placeholder
            "name": ["fwd_left", "fwd_right"],
            "position": [self.thruster_left, self.thruster_right],  # placeholder
            "velocity": [],
            "effort": [],
        }

    @staticmethod
    def _service_response(message, *, result, values):
        return {
            "op": "service_response",
            "service": message.get("service"),
            "id": message.get("id"),
            "result": result,
            "values": values,
        }

    def _respond(self, message):
        operation = message.get("op")
        topic = message.get("topic")
        if operation == "subscribe":
            if topic == "/diffboat/state":
                return {"op": "publish", "topic": topic, "id": message.get("id"),
                        "msg": self._state_message()}
            if topic == "/diffboat/move_usv/result":
                return {"op": "publish", "topic": topic, "id": message.get("id"),
                        "msg": {"data": self.result_flag}}  # placeholder
            if topic == "/diffboat/thruster_command":
                return {"op": "publish", "topic": topic, "id": message.get("id"),
                        "msg": self._joint_message()}
            return None
        if operation == "publish":
            if topic == "/diffboat/move_usv/goal":
                msg = message.get("msg") if isinstance(message.get("msg"), dict) else {}
                position = (((msg.get("pose") or {}).get("pose") or {}).get("position") or {})
                if isinstance(position.get("x"), (int, float)):
                    self.goal_x = float(position["x"])  # placeholder updated from the request
                if isinstance(position.get("y"), (int, float)):
                    self.goal_y = float(position["y"])  # placeholder updated from the request
                self.result_flag = 0.0  # placeholder: the fake does not simulate convergence
            return None
        if operation == "call_service":
            service = message.get("service")
            if service == "/gazebo/pause_physics":
                if self.fail_pause_service:
                    return self._service_response(message, result=False, values={})
                self.paused = True
                if self.fail_pause_application:
                    return self._service_response(message, result=True, values={"rejected": True})
                return self._service_response(message, result=True, values={})
            if service == "/gazebo/unpause_physics":
                if self.fail_unpause_service:
                    return self._service_response(message, result=False, values={})
                self.paused = False
                return self._service_response(message, result=True, values={})
            if service == "/gazebo/reset_simulation":
                if self.fail_reset_service:
                    return self._service_response(message, result=False, values={})
                if self.reject_reset_application:
                    return self._service_response(message, result=True, values={"rejected": True})
                self.state_x = 240.0  # placeholder reset value
                self.state_y = 95.0   # placeholder reset value
                self.state_z = 1.0    # placeholder reset value
                self.goal_x = 240.0   # placeholder reset value
                self.goal_y = 95.0    # placeholder reset value
                self.result_flag = 0.0  # placeholder reset value
                self.thruster_left = 100.0   # placeholder reset value
                self.thruster_right = 100.0  # placeholder reset value
                return self._service_response(message, result=True, values={})
            return self._service_response(message, result=False, values={})
        return None
