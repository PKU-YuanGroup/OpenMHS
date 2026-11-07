"""ROS-free contract fake for the multi-robot TurtleBot3 endpoints.

The fake models the wire contract declared in ``driver.py``:

* ``advertise``/``publish`` of ``geometry_msgs/Twist`` on ``/tb3_0/cmd_vel``
  and ``/tb3_1/cmd_vel``;
* ``subscribe`` to ``/tb3_0/scan``, ``/tb3_1/scan`` (``sensor_msgs/LaserScan``)
  and ``/tb3_0/odom``, ``/tb3_1/odom`` (``nav_msgs/Odometry``);
* the three services of the companion gazebo_ros API plugin the stop uses:
  ``/gazebo/pause_physics``, ``/gazebo/get_physics_properties`` and
  ``/gazebo/unpause_physics``.

It keeps a paused flag the way ``World::SetPaused`` does: while it is set no
world or sensor update runs, so odom and scan stay silent and a ``cmd_vel``
publication is only stored (the plugins' callback queues still run).  It is an
event-driven handler fake, not a replay of captured traffic.  It runs no ROS,
no Gazebo and no physics.  Every number below is test data and is marked
``# placeholder``; none is a device fact.
"""

import math

from mhs.bridge.ros_transport import RecordingRosTransport

_SCAN_TOPICS = {"/tb3_0/scan": "tb3_0", "/tb3_1/scan": "tb3_1"}
_ODOM_TOPICS = {"/tb3_0/odom": "tb3_0", "/tb3_1/odom": "tb3_1"}
_CMD_VEL_TOPICS = {"/tb3_0/cmd_vel": "tb3_0", "/tb3_1/cmd_vel": "tb3_1"}


class FakeMultiTurtlebot3(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.poses = {
            "tb3_0": {
                "position": {"x": -2.0, "y": 0.0, "z": 0.0},          # placeholder
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            },
            "tb3_1": {
                "position": {"x": 2.0, "y": 0.0, "z": 0.0},           # placeholder
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            },
        }
        self.ranges = {
            "tb3_0": [1.0] * 360,  # placeholder range samples
            "tb3_1": [1.0] * 360,  # placeholder range samples
        }
        self.last_cmd_vel = {
            "tb3_0": (0.0, 0.0),  # placeholder (linear m/s, angular rad/s)
            "tb3_1": (0.0, 0.0),  # placeholder (linear m/s, angular rad/s)
        }
        self.yaw = {"tb3_0": 0.0, "tb3_1": 0.0}  # placeholder heading state
        self.cmd_vel_messages = []       # recording helper, no device meaning
        self.malformed_scan = False      # placeholder negative-path switch
        self.drop_scan = False           # placeholder negative-path switch
        self.fail_publish = False        # placeholder negative-path switch
        # The world's paused flag (the closeworld2 launch starts it unpaused).
        self.paused = False              # placeholder state
        self.service_calls = []          # recording helper, no device meaning
        self.fail_pause = False          # placeholder negative-path switch
        self.fail_readback = False       # placeholder: a non-ODE engine answers false
        self.unpaused_by_other_client = False  # placeholder: the GUI or a client unpaused
        self.fail_resume = False         # placeholder negative-path switch

    def _respond(self, message):
        operation = message.get("op")
        if operation == "call_service":
            return self._service(message)
        if operation == "subscribe":
            return None if self.paused else self._observation(message)
        if operation == "publish":
            return self._command(message)
        return None

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
                "time_step": 0.001,                          # placeholder
                "pause": self.paused,
                "max_update_rate": 1000.0,                   # placeholder
                "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},  # placeholder
                "ode_config": {},                            # placeholder (fields not modelled)
                "success": True,
                "status_message": "GetPhysicsProperties: got properties",
            })
        if service == "/gazebo/unpause_physics":
            if self.fail_resume:
                return self._response(service, ident, False, {})
            self.paused = False
            for robot, (linear, angular) in self.last_cmd_vel.items():
                # The world runs again: each plugin applies its stored command at the next update.
                self._integrate(robot, linear, angular)
            return self._response(service, ident, True, {})
        return self._response(service, ident, False, {})

    @staticmethod
    def _response(service, ident, result, values):
        return {"op": "service_response", "service": service, "id": ident, "result": result, "values": values}

    def _observation(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        robot = _SCAN_TOPICS.get(topic)
        if robot is not None:
            if self.drop_scan:
                return None
            if self.malformed_scan:
                return {"op": "publish", "topic": topic, "id": ident, "msg": {}}  # placeholder malformed reply
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {"ranges": list(self.ranges[robot])},  # placeholder ranges
            }
        robot = _ODOM_TOPICS.get(topic)
        if robot is not None:
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {"pose": {"pose": dict(self.poses[robot])}},  # placeholder pose
            }
        return None

    def _command(self, message):
        if self.fail_publish:
            raise RuntimeError("placeholder injected publish failure")
        topic = message.get("topic")
        robot = _CMD_VEL_TOPICS.get(topic)
        if robot is None:
            return None
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        linear = body.get("linear") if isinstance(body.get("linear"), dict) else {}
        angular = body.get("angular") if isinstance(body.get("angular"), dict) else {}
        # The plugin's callback queue runs paused or not: the command is stored either way.
        self.last_cmd_vel[robot] = (linear.get("x", 0.0), angular.get("z", 0.0))  # placeholder defaults
        self.cmd_vel_messages.append(message)
        if not self.paused:
            self._integrate(robot, linear.get("x", 0.0), angular.get("z", 0.0))  # placeholder inputs
        return None

    def _integrate(self, robot: str, linear: float, angular: float) -> None:
        """Placeholder pose increment so a publication has a visible state effect.

        This is not physics and not a simulator timestep: it only makes the
        fake's odometry stand-in move in response to the declared command.
        """
        step = 0.1  # placeholder integration increment, not a simulated timestep
        yaw = self.yaw[robot] + angular * step
        pose = self.poses[robot]
        pose["position"]["x"] += linear * step * math.cos(yaw)
        pose["position"]["y"] += linear * step * math.sin(yaw)
        pose["orientation"]["z"] = math.sin(yaw / 2.0)
        pose["orientation"]["w"] = math.cos(yaw / 2.0)
        self.yaw[robot] = yaw
