"""ROS-free recording fake for the RoboMaster simulator endpoints.

The fake models the pinned upstream wire contract: the std_srvs/Empty
pause/unpause services, the rm_simulator/GameState start_game service, a
rm_simulator/ReferSystemInfo publication and the two base/turret command
topics.  It runs no Gazebo physics and no ROS node.  Every number below is
test data, not a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeRobomasterSimulator(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.paused = False                 # placeholder state
        self.game_started = True            # placeholder state
        self.turret_position = 0.0          # placeholder
        self.base_twist = {"linear": {"x": 0.0, "y": 0.0, "z": 0.0},   # placeholder
                           "angular": {"x": 0.0, "y": 0.0, "z": 0.0}}  # placeholder
        self.fail_pause_service = False         # placeholder negative-path switch
        self.fail_pause_application = False     # placeholder negative-path switch
        self.fail_unpause_service = False       # placeholder negative-path switch
        self.fail_unpause_application = False   # placeholder negative-path switch
        self.fail_start_service = False         # placeholder negative-path switch
        self.fail_start_application = False     # placeholder negative-path switch
        self.silent_referee = False             # placeholder negative-path switch
        self.malformed_referee = False          # placeholder negative-path switch

    def _referee(self):
        message = {
            "gameTime": 12.5,                                          # placeholder
            "robotHealth": [2000, 2000, 2000, 2000],                   # placeholder
            "remain_bullet": [50, 0, 50, 0],                           # placeholder
            "robotShoot": [1, 1, 1, 1],                                # placeholder
            "robotMove": [1, 1, 1, 1],                                 # placeholder
            "cellStateNumber": [66, 8, 16, 1, 4, 32],                  # placeholder
            "cellX": [0.5, 1.9, 4.1, 7.6, 6.2, 4.0],                   # placeholder
            "cellY": [3.36, 1.935, 4.59, 1.74, 3.165, 0.51],           # placeholder
            "robotPose": [
                {"x": 0.6476, "y": 3.3831, "yaw": 0.0403},             # placeholder
                {"x": 0.5326, "y": 4.6993, "yaw": 0.0332},             # placeholder
                {"x": 7.7354, "y": 4.5524, "yaw": 3.1402},             # placeholder
                {"x": 7.7263, "y": 0.5635, "yaw": 3.1311},             # placeholder
            ],
        }
        if self.malformed_referee:
            message.pop("robotPose", None)
        return message

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == "/refer_system_info" and not self.silent_referee:
                return {
                    "op": "publish",
                    "topic": "/refer_system_info",
                    "id": message.get("id"),
                    "msg": self._referee(),
                }
            return None
        if operation == "publish":
            topic = message.get("topic")
            if topic == "/jackal0/turret_position":
                self.turret_position = (message.get("msg") or {}).get("data")  # placeholder record
            elif topic == "/jackal0/cmd_vel":
                self.base_twist = dict(message.get("msg") or {})              # placeholder record
            return None
        if operation == "call_service":
            service = message.get("service")
            if service == "/gazebo/pause_physics":
                if self.fail_pause_service:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": False, "values": "pause service unavailable"}  # placeholder
                self.paused = True
                if self.fail_pause_application:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": True, "values": {"rejected": True}}  # placeholder
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": True, "values": {}}
            if service == "/gazebo/unpause_physics":
                if self.fail_unpause_service:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": False, "values": "unpause service unavailable"}  # placeholder
                self.paused = False
                if self.fail_unpause_application:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": True, "values": {"rejected": True}}  # placeholder
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": True, "values": {}}
            if service == "/start_game":
                if self.fail_start_service:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": False, "values": "start_game service unavailable"}  # placeholder
                start = bool((message.get("args") or {}).get("start"))  # placeholder request
                self.game_started = start
                if self.fail_start_application:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": True, "values": {"received": False}}  # placeholder
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": True, "values": {"received": True}}
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": False, "values": "no service endpoint is declared"}  # placeholder
        return None
