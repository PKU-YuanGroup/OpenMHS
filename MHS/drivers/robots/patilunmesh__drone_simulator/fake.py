"""ROS-free recording fake for the pinned CBF drone simulator endpoints.

The fake models the declared wire contract of the CBF demo node: a
nav_msgs/msg/Odometry publication on /drone1/true_pose and the
tutorial_interfaces/srv/ResetSim service on /ResetSim.  It runs no ROS graph,
CBF node, trajectory generator, LQR controller, obstacle detector or timer.
Every pose, timestamp, parameter and canned reply below is test data
(# placeholder), not a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeDroneCbfSim(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder running-simulation state; ResetSim returns it to the
        # declared start values.  These are not CBF or device facts.
        self.position = [1.25, -0.5, 2.0]       # placeholder
        self.orientation = [0.0, 0.0, 0.0, 1.0]  # placeholder
        self.linear = [0.0, 0.0, 0.0]           # placeholder
        self.angular = [0.0, 0.0, 0.0]          # placeholder
        self.cbf_param = 15.0                   # placeholder
        self.resets = 0                         # placeholder
        self.fail_reset_service = False         # placeholder negative-path switch
        self.fail_reset_application = False     # placeholder negative-path switch
        self.malformed_reset_reply = False      # placeholder negative-path switch

    def _odometry(self):
        return {
            "header": {"frame_id": "/drone", "stamp": {"sec": 0, "nanosec": 0}},  # placeholder
            "pose": {
                "pose": {
                    "position": {
                        "x": self.position[0],
                        "y": self.position[1],
                        "z": self.position[2],
                    },
                    "orientation": {
                        "x": self.orientation[0],
                        "y": self.orientation[1],
                        "z": self.orientation[2],
                        "w": self.orientation[3],
                    },
                },
                "covariance": [0.0] * 36,  # placeholder
            },
            "twist": {
                "twist": {
                    "linear": {
                        "x": self.linear[0],
                        "y": self.linear[1],
                        "z": self.linear[2],
                    },
                    "angular": {
                        "x": self.angular[0],
                        "y": self.angular[1],
                        "z": self.angular[2],
                    },
                },
                "covariance": [0.0] * 36,  # placeholder
            },
        }

    def _reset(self, request):
        self.resets += 1
        # The pinned callback resets i, zeros tru_pose and recreates the timer;
        # it does not stop the node.  The fake models the next running pose as
        # a placeholder depending on the selected CBF parameter, so a reset is
        # observable in the resource state.  This relationship is test data.
        if "cbf_param" in request:
            self.cbf_param = request["cbf_param"]
        self.position = [float(self.cbf_param), 0.0, 0.0]  # placeholder
        self.orientation = [0.0, 0.0, 0.0, 1.0]            # placeholder
        self.linear = [0.0, 0.0, 0.0]                      # placeholder
        self.angular = [0.0, 0.0, 0.0]                     # placeholder
        return self.cbf_param, request.get("reset", False)

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == "/drone1/true_pose":
                return {
                    "op": "publish",
                    "topic": "/drone1/true_pose",
                    "id": message.get("id"),
                    "msg": self._odometry(),
                }
            return None
        if operation == "call_service":
            service = message.get("service")
            if service != "/ResetSim":
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": False, "values": "placeholder unknown service"}
            if self.fail_reset_service:
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": False, "values": "placeholder reset service unavailable"}
            if self.malformed_reset_reply:
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": "yes", "values": {"done": True}}
            request = message.get("args") if isinstance(message.get("args"), dict) else {}
            self._reset(request)
            if self.fail_reset_application:
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": True, "values": {"done": False}}
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": True, "values": {"done": True}}
        return None
