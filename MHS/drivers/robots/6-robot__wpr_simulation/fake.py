"""ROS-free canned fake for the WPR Gazebo simulation endpoint contract.

The fake models the pinned upstream wire contract: a geometry_msgs/Twist
subscription on /cmd_vel, a nav_msgs/Odometry publication on /odom, and a
geometry_msgs/Pose2D publication on /wpb_home/pose_diff, plus the three
services of the companion gazebo_ros API plugin the stop uses:
/gazebo/pause_physics and /gazebo/unpause_physics (std_srvs/Empty) and
/gazebo/get_physics_properties (gazebo_msgs/GetPhysicsProperties).  It keeps a
paused flag the way World::SetPaused does: while it is set, the plugin's world
update does not run, so /odom stays silent and a cmd_vel publication is only
stored (the plugin's callback queue still runs).  It runs no Gazebo physics.
All numbers below are test data, not device facts.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeWprSimulation(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.odom_position = {"x": 0.0, "y": 0.0, "z": 0.0}          # placeholder
        self.odom_orientation = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}  # placeholder
        self.odom_linear = {"x": 0.0, "y": 0.0, "z": 0.0}            # placeholder
        self.odom_angular = {"x": 0.0, "y": 0.0, "z": 0.0}           # placeholder
        self.pose_diff = {"x": 0.0, "y": 0.0, "theta": 0.0}          # placeholder
        self.last_cmd_vel = None                                    # placeholder
        self.withhold_odom = False                                  # placeholder negative-path switch
        self.withhold_pose_diff = False                             # placeholder negative-path switch
        # The world's paused flag (wpb_simple.launch starts it unpaused).
        self.paused = False                                         # placeholder state
        self.service_calls = []                                     # recording helper, no device meaning
        self.fail_pause = False                                     # placeholder negative-path switch
        self.fail_readback = False                                  # placeholder: a non-ODE engine answers false
        self.unpaused_by_other_client = False                       # placeholder: the GUI or a client unpaused
        self.fail_resume = False                                    # placeholder negative-path switch

    def _respond(self, message):
        operation = message.get("op")
        if operation == "call_service":
            return self._service(message)
        if operation == "subscribe":
            topic = message.get("topic")
            if topic == "/odom" and not self.withhold_odom and not self.paused:
                return {
                    "op": "publish",
                    "topic": "/odom",
                    "id": message.get("id"),
                    "msg": {
                        "header": {"frame_id": "odom"},
                        "child_frame_id": "base_footprint",
                        "pose": {"pose": {"position": dict(self.odom_position),
                                          "orientation": dict(self.odom_orientation)}},
                        "twist": {"twist": {"linear": dict(self.odom_linear),
                                            "angular": dict(self.odom_angular)}},
                    },
                }
            if topic == "/wpb_home/pose_diff" and not self.withhold_pose_diff and not self.paused:
                return {
                    "op": "publish",
                    "topic": "/wpb_home/pose_diff",
                    "id": message.get("id"),
                    "msg": dict(self.pose_diff),
                }
            return None
        if operation == "publish" and message.get("topic") == "/cmd_vel":
            body = message.get("msg")
            if isinstance(body, dict):
                # The plugin's callback queue runs paused or not: the command is stored either way.
                self.last_cmd_vel = body
                if not self.paused:
                    self._advance(body)
            return None
        return None

    def _advance(self, body):
        linear = body.get("linear") if isinstance(body.get("linear"), dict) else {}
        angular = body.get("angular") if isinstance(body.get("angular"), dict) else {}
        self.odom_linear = {"x": linear.get("x", 0.0), "y": linear.get("y", 0.0), "z": 0.0}  # placeholder
        self.odom_angular = {"x": 0.0, "y": 0.0, "z": angular.get("z", 0.0)}  # placeholder
        # A canned, non-physical stand-in for the plugin's force loop:
        # one update moves the placeholder pose by a fixed step.
        self.odom_position = {"x": self.odom_position["x"] + 0.01 * linear.get("x", 0.0),  # placeholder
                              "y": self.odom_position["y"] + 0.01 * linear.get("y", 0.0),  # placeholder
                              "z": 0.0}  # placeholder

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")
        self.service_calls.append(service)
        if service == "/gazebo/pause_physics":
            if self.fail_pause:
                return None  # no answer: the binding times out
            self.paused = True
            return self._response(service, ident, True, {})
        if service == "/gazebo/get_physics_properties":
            if self.fail_readback:
                return self._response(service, ident, False, {})
            if self.unpaused_by_other_client:
                self.paused = False
            return self._response(service, ident, True, {
                "time_step": 0.001,                     # placeholder
                "pause": self.paused,
                "max_update_rate": 1000.0,              # placeholder
                "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},  # placeholder
                "ode_config": {},                       # placeholder (fields not modelled)
                "success": True,
                "status_message": "GetPhysicsProperties: got properties",
            })
        if service == "/gazebo/unpause_physics":
            if self.fail_resume:
                return self._response(service, ident, False, {})
            self.paused = False
            if isinstance(self.last_cmd_vel, dict):
                # The world runs again: the plugin applies the stored command at the next update.
                self._advance(self.last_cmd_vel)
            return self._response(service, ident, True, {})
        return self._response(service, ident, False, {})

    @staticmethod
    def _response(service, ident, result, values):
        return {"op": "service_response", "service": service, "id": ident, "result": result, "values": values}
