"""ROS-free canned transport fake for the map_simulator ROS 2 endpoints.

The fake models only the pinned wire surface used by ``driver.py``: the
absolute ``/simulator/spawn`` service, the per-robot ``cmd_vel`` subscription
and the ``odom`` and ``scan`` publications for one configured robot namespace.
It runs no map_simulator, OpenCV, occupancy-grid, collision or laser code.

Every number below is test data, not a device fact, and is marked
``# placeholder``.  The fake is not a recording of captured ROS traffic.

The sensed-confirmation stop (SAFE-049) needs stamped samples.  An
``/robot1/odom`` subscription is answered with a short burst.  The first
sample is the stored published twist (the sample the confirmation discards).
Later samples snap to the last ``cmd_vel``, which is what the callback does
when it copies the command into ``odom.twist.twist`` (src/robot.cpp:223-225).
A non-zero command steps the stored pose by a placeholder ``dt`` so the
resource changes, and does not replace the stored twist; two reads with no
new command agree.  A zero command, with none of the fail-closed switches
set, stores a still pose and a zero twist.  The fake starts with a non-zero
stored twist, so nothing satisfies the predicate before that zero command.
"""

import copy
import math

from mhs.bridge.ros_transport import RecordingRosTransport

#: One configured robot namespace.  This is a deployment choice, not an
#: upstream default; the driver and the fake use the same resolved endpoints.
_MAIN_NAMESPACE = "/robot1/"
_MAIN_TOPIC = "/robot1"

#: Placeholder scan sample count; the real count is parsed from the URDF or
#: defaults to 100 (src/robot.cpp:131-132).
_SCAN_SAMPLES = 100  # placeholder

#: Samples per /odom subscription.  The confirmation ring holds at least 16;
#: eight leaves the first sample to be discarded and three counted samples
#: whose stamps span the driver's min_span_ms.
_BURST = 8  # placeholder
#: Nanoseconds between counted samples.  Three counted samples then span
#: 100 ms, the driver's min_span_ms.  1/20 s is the same duration as the
#: simulator's default rate parameter (src/simulator.cpp:17); this step is
#: still a placeholder, not that parameter.
_STAMP_STEP_NS = 50_000_000  # placeholder
#: Stored twist before any zero command, so the discarded first sample does
#: not itself satisfy the at-rest predicate.
_INITIAL_LINEAR_X = 0.2  # placeholder


def _zero_twist():
    return {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},      # placeholder
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},     # placeholder
    }


def _twist(linear_x, linear_y, angular_z):
    twist = _zero_twist()
    twist["linear"]["x"] = float(linear_x)    # placeholder
    twist["linear"]["y"] = float(linear_y)    # placeholder
    twist["angular"]["z"] = float(angular_z)  # placeholder
    return twist


def _all_zero(twist):
    return all(twist["linear"][key] == 0.0 for key in ("x", "y", "z")) and all(
        twist["angular"][key] == 0.0 for key in ("x", "y", "z"))


def _pose(x, y, theta):
    return {
        "position": {"x": float(x), "y": float(y), "z": 0.0},          # placeholder
        "orientation": {"x": 0.0, "y": 0.0,                          # placeholder
                        "z": math.sin(float(theta) / 2.0),           # placeholder
                        "w": math.cos(float(theta) / 2.0)},          # placeholder
    }


def _scan_message():
    return {
        "angle_min": -1.5,          # placeholder
        "angle_max": 1.5,           # placeholder
        "angle_increment": 0.03,    # placeholder
        "range_min": 0.1,           # placeholder
        "range_max": 5.0,           # placeholder
        "ranges": [1.0] * _SCAN_SAMPLES,  # placeholder
    }


class FakeMapSimulator(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.main_namespace = _MAIN_NAMESPACE  # placeholder deployment namespace
        self.pose = _pose(0.0, 0.0, 0.0)      # placeholder stored pose
        # The twist the next odom burst's first sample publishes.  A resource
        # read keeps that first sample.  It changes only when a zero command
        # is stored, or when a spawn of /robot1 clears it (resetTo).
        self.published = _twist(_INITIAL_LINEAR_X, 0.0, 0.0)  # placeholder
        # The last cmd_vel the callback would have copied.  Later burst
        # samples snap to this.  It is not the stored odom twist.
        self.command = _twist(_INITIAL_LINEAR_X, 0.0, 0.0)    # placeholder
        self.clock_ns = 1_000_000_000         # placeholder; a zero stamp is refused
        self.scan = _scan_message()           # placeholder
        self.robots = {
            _MAIN_NAMESPACE: {
                "pose": copy.deepcopy(self.pose),
                "twist": copy.deepcopy(self.published),
                "scan": self.scan,
            }
        }
        self.spawn_calls = []                 # placeholder test observation
        self.last_cmd_vel = None              # placeholder test observation
        self.last_odom_linear_x = []          # placeholder: linear.x of the last odom burst
        self.last_odom_stamps_ns = []         # placeholder: producer stamps of that burst
        self.odom_bursts = []                 # placeholder: linear.x of every odom burst, in order
        self.fail_spawn_service = False       # placeholder negative-path switch
        self.reject_spawn_application = False  # placeholder negative-path switch
        self.silent_odom = False              # placeholder: /odom answers nothing
        self.silent_scan = False              # placeholder negative-path switch
        self.omit_odom_twist = False          # placeholder negative-path switch
        self.fail_twist = False               # placeholder negative-path switch
        self.competing_publisher = False      # placeholder: another cmd_vel publisher keeps a non-zero twist
        self.frozen_stamps = False            # placeholder: every /odom sample repeats one stamp
        self.null_pose = False                # placeholder: pose.position.x is null in every /odom sample

    # -- inbound events -----------------------------------------------------
    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._subscribe(message)
        if operation == "publish":
            topic = message.get("topic")
            if topic == _MAIN_TOPIC + "/cmd_vel":
                if self.fail_twist:
                    raise RuntimeError("placeholder fake cmd_vel transport failure")
                self._apply_twist(message.get("msg") or {})
            return None
        if operation == "call_service":
            if message.get("service") == "/simulator/spawn":
                return self._spawn(message)
            return {
                "op": "service_response",
                "service": message.get("service"),
                "id": message.get("id"),
                "result": False,
                "values": {},  # placeholder unknown-service response
            }
        return None

    def _subscribe(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        if topic == _MAIN_TOPIC + "/odom":
            if self.silent_odom:
                return None
            if self.omit_odom_twist:
                # One sample, not a burst: the odometry capability maps
                # twist.twist and must fail closed when it is absent.
                body = {"pose": {"pose": copy.deepcopy(self.pose)}}  # placeholder
                return {"op": "publish", "topic": topic, "id": ident, "msg": body}
            return self._odom_burst(topic, ident)
        if topic == _MAIN_TOPIC + "/scan":
            if self.silent_scan:
                return None
            return {"op": "publish", "topic": topic, "id": ident,
                    "msg": copy.deepcopy(self.scan)}
        return None

    def _odom_burst(self, topic, ident):
        # A competing publisher is local to this burst.  It does not replace
        # the stored command, and the burst is not stored.
        command = _twist(_INITIAL_LINEAR_X, 0.0, 0.0) if self.competing_publisher else copy.deepcopy(self.command)
        stamp_ns = self.clock_ns
        samples = []
        linears = []
        stamps = []
        for index in range(_BURST):
            # Sample 0 is the stored publication (discarded by the
            # confirmation).  Later samples are the command the callback
            # would have copied.
            twist = self.published if index == 0 else command
            body = {
                "header": {
                    "stamp": {"sec": stamp_ns // 1_000_000_000,
                              "nanosec": stamp_ns % 1_000_000_000},
                    "frame_id": "odom",  # placeholder
                },
                "pose": {"pose": copy.deepcopy(self.pose)},
                "twist": {"twist": copy.deepcopy(twist)},
            }
            if self.null_pose:
                body["pose"]["pose"]["position"]["x"] = None
            samples.append({"op": "publish", "topic": topic, "id": ident, "msg": body})
            linears.append(twist["linear"]["x"])
            stamps.append(stamp_ns)
            if not self.frozen_stamps:
                stamp_ns += _STAMP_STEP_NS
        self.last_odom_linear_x = linears
        self.last_odom_stamps_ns = stamps
        self.odom_bursts.append(list(linears))
        # Store only a clean zero.  A non-zero projection, a competing
        # publisher, a repeated stamp or a null pose leaves the stored odom
        # where it was, so the next read still shows the pre-request twist.
        if (_all_zero(command) and not self.competing_publisher
                and not self.frozen_stamps and not self.null_pose):
            self.published = _zero_twist()
            self.clock_ns = stamp_ns
            robot = self.robots.get(self.main_namespace)
            if robot is not None:
                robot["pose"] = copy.deepcopy(self.pose)
                robot["twist"] = copy.deepcopy(self.published)
        return samples

    def _spawn(self, message):
        if self.fail_spawn_service:
            return {
                "op": "service_response",
                "service": message.get("service"),
                "id": message.get("id"),
                "result": False,
                "values": {},  # placeholder service failure
            }
        if self.reject_spawn_application:
            return {
                "op": "service_response",
                "service": message.get("service"),
                "id": message.get("id"),
                "result": True,
                "values": {"rejected": True},  # placeholder application rejection
            }
        args = dict(message.get("args") or {})
        self.spawn_calls.append(copy.deepcopy(args))
        namespace = str(args.get("robot_namespace") or "/")
        if not namespace.endswith("/"):
            namespace += "/"
        pose = _pose(args.get("x", 0.0), args.get("y", 0.0), args.get("theta", 0.0))
        if namespace in self.robots:
            # The upstream addRobot twin branch resets the pose and clears the
            # odometry twist; it does not stop an earlier cmd_vel publisher.
            robot = self.robots[namespace]
            robot["pose"] = pose
            robot["twist"] = _zero_twist()
        else:
            self.robots[namespace] = {
                "pose": pose,
                "twist": _zero_twist(),
                "scan": _scan_message(),
            }
        if namespace == self.main_namespace:
            # resetTo clears odom.twist.twist (include/map_simulator/robot.h:135-143).
            # That is a teleport of this fake's stored sample, not a stop.
            self.pose = copy.deepcopy(pose)
            self.command = _zero_twist()
            self.published = _zero_twist()
        return {
            "op": "service_response",
            "service": message.get("service"),
            "id": message.get("id"),
            "result": True,
            "values": {},
        }

    def _apply_twist(self, message):
        linear = message.get("linear") or {}
        angular = message.get("angular") or {}
        self.last_cmd_vel = {
            "linear": {key: float(linear.get(key, 0.0)) for key in ("x", "y", "z")},     # placeholder
            "angular": {key: float(angular.get(key, 0.0)) for key in ("x", "y", "z")},   # placeholder
        }
        # The callback copies the command.  The stored odom twist stays until a
        # later burst keeps a zero command.  A non-zero command steps the
        # stored pose so the resource changes (the gate's effect check).  The
        # step is a placeholder, not Robot::move.
        self.command = copy.deepcopy(self.last_cmd_vel)
        if not _all_zero(self.command):
            dt = 0.1  # placeholder
            self.pose["position"]["x"] += self.command["linear"]["x"] * dt
            self.pose["position"]["y"] += self.command["linear"]["y"] * dt
            theta = (2.0 * math.atan2(self.pose["orientation"]["z"], self.pose["orientation"]["w"])
                     + self.command["angular"]["z"] * dt)
            self.pose["orientation"]["z"] = math.sin(theta / 2.0)
            self.pose["orientation"]["w"] = math.cos(theta / 2.0)
