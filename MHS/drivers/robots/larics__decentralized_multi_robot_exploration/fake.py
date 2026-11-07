"""ROS-free contract fake for the pinned Stage multi-robot exploration endpoints.

The fake answers the rosbridge JSON operations that the configuration-only
``RosDriver`` declares: one Clock publish, two LaserScan publishes, two
Odometry publishes, the exploration stack's PointArray publish and the two
``cmd_vel`` Twist publications.  It also answers the clone's ``reset_positions``
service, which the driver does not bind.  It runs no Stage, no ROS graph and
no physics; every value below is test data and is marked ``# placeholder``.

The sensed-confirmation stop (SAFE-049) needs stamped samples.  An odometry
subscription is answered with a short burst whose ROS 1 stamps (secs, nsecs)
increase on a placeholder clock.  The fake starts with both robots moving.
A zero Twist stores a stop for that robot; any other Twist stores the commanded
axes.  The first sample of a burst is the stored state.  A burst is not stored
back, so two ordinary reads agree.  Switches below model the fail-closed paths
and the watchdog: the confirmation can see a robot at rest even when the zero
Twist was not applied.
"""

import copy

from mhs.bridge.ros_transport import RecordingRosTransport

#: One shipped sicklaser declares 1081 samples (frontier_exploration/stage-worlds/
#: pioneer3dx-sick.world:242); the fake keeps that length but every value is a
#: # placeholder.
SAMPLE_COUNT = 1081
_BURST = 16                       # placeholder: samples per odometry subscription
_STAMP_STEP_NS = 150_000_000     # placeholder: producer time between samples (150 ms)


class FakeDecentralizedMultiRobotExploration(RecordingRosTransport):
    """Deterministic rosbridge contract stand-in for the Stage exploration world."""

    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Every value in this constructor is placeholder test data.
        self.clock_secs = 12                     # placeholder
        self.clock_nsecs = 340000000             # placeholder
        self.clock_ns = 100_000_000_000          # placeholder producer clock for odometry stamps
        self.poses = {                           # placeholder x, y, yaw
            "robot_0": [8.093, 0.561, 0.840],    # placeholder
            "robot_1": [4.864, -3.911, 0.662],   # placeholder
        }
        self.velocities = {                      # placeholder linear.x, linear.y, angular.z; both robots moving
            "robot_0": [0.4, 0.0, 0.0],          # placeholder
            "robot_1": [0.25, 0.0, 0.15],        # placeholder
        }
        self.initial_poses = copy.deepcopy(self.poses)
        self.frontiers = [                       # placeholder centroid list
            {"x": 1.0, "y": 2.0, "z": 0.0},      # placeholder
            {"x": -2.0, "y": 0.5, "z": 0.0},     # placeholder
        ]
        self.fail_reset_service = False          # placeholder negative switch
        self.fail_reset_application = False      # placeholder negative switch
        self.silent_topics = set()               # placeholder negative switch
        self.silent_odom = False                 # placeholder: both odometry topics answer nothing
        self.frozen_stamps = False               # placeholder: every odometry sample repeats one stamp
        self.null_linear_x = False               # placeholder: twist.linear.x is null
        self.apply_zero = True                   # placeholder: a zero Twist stores a stop
        self.watchdog_rest = False               # placeholder: samples report rest even if the zero was not stored
        self.competing = False                   # placeholder: another cmd_vel publisher keeps both robots moving
        self.drift_at_rest = False               # placeholder: pose changes even when the stored speed is zero
        self.hold_pose = False                   # placeholder: report a nonzero twist without moving the pose
        self.reject_publish = False              # placeholder: cmd_vel publications raise
        self.ignore_zero = set()                 # placeholder: robots whose zero Twist is not stored
        self.cmd_vel_messages = []               # recording helper, no device meaning

    @staticmethod
    def _stamp(secs, nsecs):
        return {"secs": secs, "nsecs": nsecs}

    def _header(self, frame_id, stamp=None):
        return {"seq": 0,                                       # placeholder
                "stamp": stamp if stamp is not None else self._stamp(self.clock_secs, self.clock_nsecs),
                "frame_id": frame_id}

    def _scan(self, robot):
        return {
            "header": self._header(f"{robot}/base_laser_link"),
            "angle_min": -3.141592653589793,                    # placeholder
            "angle_max": 3.141592653589793,                     # placeholder
            "angle_increment": 0.005817,                        # placeholder
            "time_increment": 0.0,                              # placeholder
            "scan_time": 0.0,                                   # placeholder
            "range_min": 0.0,                                   # placeholder
            "range_max": 20.0,                                  # placeholder
            "ranges": [5.0 for _ in range(SAMPLE_COUNT)],       # placeholder
            "intensities": [300.0 for _ in range(SAMPLE_COUNT)],  # placeholder
        }

    def _at_rest_sample(self, robot):
        """The velocity a confirmation sample reports for one robot."""
        if self.competing:
            return [0.4, 0.1, 0.2]              # placeholder: move_base keeps commanding
        if self.watchdog_rest:
            return [0.0, 0.0, 0.0]              # placeholder: the watchdog clamp, not SetSpeed
        return list(self.velocities[robot])

    def _odom_message(self, robot, x, y, yaw, velocity, stamp):
        linear_x, linear_y, angular_z = velocity
        return {
            "header": self._header(f"{robot}/base_pose_ground_truth", stamp),
            "child_frame_id": f"{robot}/base_link",
            "pose": {"pose": {
                "position": {"x": x, "y": y, "z": 0.0},         # placeholder
                "orientation": {"x": 0.0, "y": 0.0,             # placeholder
                                "z": 0.0, "w": 1.0},            # placeholder
            }},
            "twist": {"twist": {
                "linear": {"x": None if self.null_linear_x else linear_x, "y": linear_y, "z": 0.0},  # placeholder
                "angular": {"x": 0.0, "y": 0.0, "z": angular_z},  # placeholder
            }},
        }

    def _odom_burst(self, robot, ident):
        """One placeholder burst.  The stored pose is the first sample and is not updated here."""
        x, y, yaw = self.poses[robot]
        velocity = self._at_rest_sample(robot)
        moving = any(abs(item) > 0.0 for item in velocity) or self.drift_at_rest
        samples = []
        for _ in range(_BURST):
            stamp = self._stamp(self.clock_ns // 1_000_000_000, self.clock_ns % 1_000_000_000)
            samples.append({
                "op": "publish",
                "topic": f"/{robot}/odom",
                "id": ident,
                "msg": self._odom_message(robot, x, y, yaw, velocity, stamp),
            })
            if moving and not self.hold_pose:
                x = round(x + 0.05, 9)           # placeholder drift, larger than the fixture span
            if not self.frozen_stamps:
                self.clock_ns += _STAMP_STEP_NS
        return samples

    def _publish(self, topic, ident, message):
        return {"op": "publish", "topic": topic, "id": ident, "msg": message}

    def _subscribe(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        if topic in self.silent_topics or (self.silent_odom and topic in ("/robot_0/odom", "/robot_1/odom")):
            return None
        if topic == "/clock":
            return self._publish(topic, ident, {
                "clock": self._stamp(self.clock_secs, self.clock_nsecs),
            })
        if topic in ("/robot_0/base_scan", "/robot_1/base_scan"):
            return self._publish(topic, ident, self._scan(topic.split("/")[1]))
        if topic in ("/robot_0/odom", "/robot_1/odom"):
            return self._odom_burst(topic.split("/")[1], ident)
        if topic == "/filtered_frontiers":
            return self._publish(topic, ident, {"points": copy.deepcopy(self.frontiers)})
        return None

    def _cmd_vel(self, message):
        if self.reject_publish:
            raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder
        topic = message.get("topic", "")
        parts = topic.strip("/").split("/")
        if len(parts) != 2 or parts[1] != "cmd_vel" or parts[0] not in self.poses:
            return None
        body = message.get("msg") or {}
        linear = body.get("linear") or {}
        angular = body.get("angular") or {}
        forward = float(linear.get("x", 0.0))                  # placeholder
        lateral = float(linear.get("y", 0.0))                  # placeholder
        turn = float(angular.get("z", 0.0))                    # placeholder
        robot = parts[0]
        self.cmd_vel_messages.append(message)
        zero = forward == 0.0 and lateral == 0.0 and turn == 0.0
        if zero and (not self.apply_zero or robot in self.ignore_zero):
            return None
        # Echo the commanded twist into the stored odometry.  No pose integration
        # and no Stage step are claimed.  A zero Twist stores a stop.
        self.velocities[robot] = [forward, lateral, turn]
        return None

    def _reset(self, message):
        """The clone's reset_positions: restore the initial poses and leave the commanded speed."""
        if self.fail_reset_service:
            return {"op": "service_response", "service": message.get("service"),
                    "id": message.get("id"), "result": False,
                    "values": "reset service unavailable"}      # placeholder
        if self.fail_reset_application:
            return {"op": "service_response", "service": message.get("service"),
                    "id": message.get("id"), "result": True,
                    "values": {"rejected": True}}              # placeholder
        self.poses = copy.deepcopy(self.initial_poses)
        return {"op": "service_response", "service": message.get("service"),
                "id": message.get("id"), "result": True, "values": {}}

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._subscribe(message)
        if operation == "publish":
            return self._cmd_vel(message)
        if operation == "call_service":
            if message.get("service") == "/reset_positions":
                return self._reset(message)
            return {"op": "service_response", "service": message.get("service"),
                    "id": message.get("id"), "result": False, "values": {}}
        return None
