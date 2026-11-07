"""ROS-free recording fake for the Webots ROS 2 Spot plug-in endpoints.

The fake models the pinned wire contract: the /cmd_vel Twist publication, the
/joint_states and /Spot/odometry observations, the SpotMotion /Spot/stand_up,
/Spot/sit_down and /Spot/lie_down services, the SpotHeight /Spot/set_height
service, and the std_srvs SetBool /Spot/float_mode service.

The sensed-confirmation stop needs stamped /Spot/odometry. While fixed_motion
is set the plug-in publishes that topic from defined_motions and again from
step (spot_driver.py:702 and :950). The clone does not say getTime() stays
fixed between those calls. A sensed subscribe carries queue_length 1 and
throttle_rate. This fake models rosbridge QueueMessageHandler on a simulated
clock: a second copy still queued replaces the first, and a copy that arrives
after the first was forwarded is delivered once the throttle elapses. That
delivered copy keeps the same stamp, and the sensed window then fails closed.
It does not run rosbridge. With honor_throttle false it emits both samples of
each pair immediately. An ordinary resource subscribe has no throttle_rate and
gets one canned sample, not the confirmation burst.

All numbers below are placeholder test data, not device facts. The fake runs
no Webots engine, gait, contact, sensor or wall-clock loop.
"""

import copy
import math
from collections import deque

from mhs.bridge.ros_transport import RecordingRosTransport


def forward_rosbridge_queue(arrivals, throttle_s, queue_length):
    """Deterministic stand-in for rosbridge QueueMessageHandler.

    rosbridge_library/internal/subscription_modifiers.py queues with maxlen
    queue_length and publishes one message when throttle_s has elapsed since
    the previous publish. Messages that share an arrival time are queued
    before that publish, so maxlen 1 keeps the last of them. A message already
    published is not dropped: a later copy waits out the throttle and is then
    forwarded. throttle_s is seconds, as MessageHandler.set_throttle_rate stores
    milliseconds / 1000. This function does not sleep and does not start a thread.
    """
    if queue_length < 1:
        raise ValueError("queue_length must be at least 1")
    pending = deque()
    forwarded = []
    last_publish = None
    index = 0
    count = len(arrivals)

    def due(now):
        if last_publish is None:
            return 0.0
        return max(0.0, last_publish + throttle_s - now)

    while index < count or pending:
        nxt = arrivals[index][0] if index < count else None
        if pending and last_publish is not None:
            publish_at = last_publish + throttle_s
            if nxt is None or publish_at <= nxt:
                forwarded.append(pending.popleft())
                last_publish = publish_at
                continue
        if index >= count:
            break
        arrival = arrivals[index][0]
        while index < count and arrivals[index][0] == arrival:
            pending.append(arrivals[index][1])
            if len(pending) > queue_length:
                pending.popleft()
            index += 1
        if pending and due(arrival) == 0.0:
            forwarded.append(pending.popleft())
            last_publish = arrival
    return forwarded

#: Placeholder joint order observed from the upstream publisher shape.
_JOINT_NAMES = [
    "front left shoulder abduction motor",   # placeholder name
    "front left shoulder rotation motor",    # placeholder name
    "front left elbow motor",                # placeholder name
    "front right shoulder abduction motor",  # placeholder name
    "front right shoulder rotation motor",   # placeholder name
    "front right elbow motor",               # placeholder name
    "rear left shoulder abduction motor",    # placeholder name
    "rear left shoulder rotation motor",     # placeholder name
    "rear left elbow motor",                 # placeholder name
    "rear right shoulder abduction motor",   # placeholder name
    "rear right shoulder rotation motor",    # placeholder name
    "rear right elbow motor",                # placeholder name
    "front left piston motor",               # placeholder name
    "front right piston motor",              # placeholder name
    "rear left piston motor",                # placeholder name
    "rear right piston motor",               # placeholder name
]

#: 16 placeholder joint positions (12 legs plus 4 piston entries).
_JOINT_POSITIONS = [0.0] * 16  # placeholder

#: Placeholder confirmation burst. Eight pairs, 100 ms of stamp time apart.
#: The first unique sample is discarded by the bridge; the next is still above
#: the fixture lying band; the rest sit inside it when the lie holds.
_PAIRS = 8
_TICK_NS = 100_000_000          # placeholder producer tick, 100 ms; min_span_ms 200 matches three of these
_STAMP0 = 10_000_000_000        # placeholder non-zero ROS time, nanoseconds
_STRADDLE_S = 0.001             # placeholder: the second copy arrives after the first was forwarded
_STRADDLE_GAP_S = 0.05          # placeholder: the next step starts only after that copy's throttle has elapsed
_STAND_Z = 0.50                 # placeholder, outside the fixture lying band
_MID_Z = 0.30                   # placeholder, still outside that band
_LIE_Z = 0.12                   # placeholder, inside the fixture band 0.05..0.25
_DRIFT_X = 0.20                 # placeholder metres of x motion per sample while not lying


class FakeWebotsRos2Spot(RecordingRosTransport):
    def forward_queue(self, arrivals, throttle_s, queue_length):
        """Expose the rosbridge queue stand-in to the package tests without reaching into sys."""
        return forward_rosbridge_queue(arrivals, throttle_s, queue_length)

    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.fixed_motion = False             # placeholder state
        self.previous_cmd = False             # placeholder state
        self.float_mode = False               # placeholder state; the plug-in starts false
        self.zd = 0.0                         # placeholder state
        self.last_cmd_vel = None              # placeholder state
        self.previous_cmd_vel = {             # placeholder; the plug-in stores an empty Twist and the stop does not clear it
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
        }
        self.odom_twist = {                    # placeholder state
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},    # placeholder
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},   # placeholder
        }
        self.fail_lie_service = False         # placeholder negative-path switch
        self.reject_lie_application = False   # placeholder negative-path switch
        self.fail_stand_service = False       # placeholder negative-path switch
        self.honor_throttle = True            # placeholder: apply the queue-and-throttle model when throttle_rate is set
        self.straddle_publish = False         # placeholder: the second copy arrives after the first was forwarded
        self.rotating = False                 # placeholder: yaw advances at 1 rad/s of producer time; position stays
        self.competing_float = False          # placeholder: another client sets float mode true after the request
        self.competing_cmd_vel = False        # placeholder: another /cmd_vel keeps the base moving
        self.silent = False                   # placeholder: /Spot/odometry answers nothing
        self.frozen_stamps = False            # placeholder: every confirmation sample repeats one stamp
        self.null_position = False            # placeholder: pose.pose.position.x is null
        self.service_calls = []               # placeholder test record
        self.last_odom_stamps = []           # placeholder: (sec, nanosec) of the last odometry burst, in emit order

    def _lying(self):
        # Placeholder stand-in for "float mode is off, the lie was accepted, and nothing else is walking the base".
        return (self.fixed_motion and not self.float_mode
                and not self.competing_cmd_vel and not self.competing_float)

    def _stamp(self, total_ns):
        return {"sec": total_ns // 1_000_000_000, "nanosec": total_ns % 1_000_000_000}

    def _pose(self, index):
        if not self._lying():
            return (round(index * _DRIFT_X, 9), 0.0, _STAND_Z)  # placeholder walk
        if index <= 0:
            return (0.0, 0.0, _STAND_Z)  # placeholder: leading sample, still high
        if index == 1:
            return (0.0, 0.0, _MID_Z)    # placeholder: settling, still outside the band
        return (0.0, 0.0, _LIE_Z)        # placeholder lying height

    def _orientation(self, total_ns):
        # Placeholder. A still base is the identity quaternion. Rotation is 1 rad/s of
        # producer time. The predicate reads this quaternion: the second publish in one
        # step can zero the finite-difference twist after previous_rotation is stored.
        if not self.rotating:
            return {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
        yaw = (total_ns - _STAMP0) / 1_000_000_000
        return {"x": 0.0, "y": 0.0, "z": math.sin(yaw / 2.0), "w": math.cos(yaw / 2.0)}

    def _odom_msg(self, total_ns, x, y, z):
        return {
            "header": {"frame_id": "odom", "stamp": self._stamp(total_ns)},  # placeholder frame
            "child_frame_id": "base_link",   # placeholder frame
            "pose": {
                "pose": {
                    "position": {
                        "x": None if self.null_position else x,  # placeholder
                        "y": y,                                  # placeholder
                        "z": z,                                  # placeholder
                    },
                    "orientation": self._orientation(total_ns),  # placeholder
                }
            },
            "twist": {
                "twist": {
                    "linear": dict(self.odom_twist["linear"]),    # placeholder
                    "angular": dict(self.odom_twist["angular"]),  # placeholder
                }
            },
        }

    def _publish(self, topic, ident, body):
        return {"op": "publish", "topic": topic, "id": ident, "msg": body}

    def _one_odom(self, message):
        # Resource reads are one canned sample. They are not the confirmation burst.
        body = {
            "header": {"frame_id": "odom"},  # placeholder frame
            "child_frame_id": "base_link",   # placeholder frame
            "pose": {
                "pose": {
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                }
            },
            "twist": {
                "twist": {
                    "linear": dict(self.odom_twist["linear"]),    # placeholder
                    "angular": dict(self.odom_twist["angular"]),  # placeholder
                }
            },
        }
        return self._publish(message.get("topic"), message.get("id"), body)

    def _burst(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        throttle = message.get("throttle_rate")
        produced = []
        for index in range(_PAIRS):
            total_ns = _STAMP0 if self.frozen_stamps else _STAMP0 + index * _TICK_NS
            x, y, z = self._pose(index)
            body = self._odom_msg(total_ns, x, y, z)
            # Two publishes per controller step. The second can carry a zero twist; both
            # placeholders share the pose and the stamp of this step.
            produced.append(body)
            produced.append(copy.deepcopy(body))
        if self.honor_throttle and throttle is not None:
            queue_length = message.get("queue_length")
            if not isinstance(queue_length, int) or isinstance(queue_length, bool) or queue_length < 1:
                queue_length = 1
            arrivals = self._arrivals(produced, float(throttle) / 1000.0)
            forwarded = forward_rosbridge_queue(arrivals, float(throttle) / 1000.0, queue_length)
        else:
            forwarded = produced
        samples = []
        stamps = []
        for body in forwarded:
            samples.append(self._publish(topic, ident, body))
            stamp = body["header"]["stamp"]
            stamps.append((stamp["sec"], stamp["nanosec"]))
        self.last_odom_stamps = stamps
        return samples

    def _arrivals(self, produced, throttle_s):
        # Placeholder clock. Copies of one step share an arrival time, so a length-1 queue
        # keeps one. straddle_publish delivers the second copy after the first was forwarded
        # and holds the next step until that copy has gone out.
        arrivals = []
        step_s = _TICK_NS / 1_000_000_000
        if self.straddle_publish:
            # The next step must arrive after the delayed copy is forwarded and that
            # publish's throttle has elapsed, or the new pair is queued together and
            # collapsed instead of straddling the publish.
            step_s = 2 * throttle_s + _STRADDLE_GAP_S
        for index in range(0, len(produced), 2):
            start = index // 2 * step_s
            arrivals.append((start, produced[index]))
            second = start + _STRADDLE_S if self.straddle_publish else start
            arrivals.append((second, produced[index + 1]))
        return arrivals

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            if topic == "/joint_states":
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": message.get("id"),
                    "msg": {
                        "name": list(_JOINT_NAMES),
                        "position": list(_JOINT_POSITIONS),  # placeholder
                        "velocity": [0.0] * 16,              # placeholder
                        "effort": [0.0] * 16,                # placeholder
                    },
                }
            if topic == "/Spot/odometry":
                if self.silent:
                    return None
                if message.get("throttle_rate") is None:
                    return self._one_odom(message)
                return self._burst(message)
            return None
        if operation == "publish":
            if message.get("topic") == "/cmd_vel":
                msg = message.get("msg") if isinstance(message.get("msg"), dict) else {}
                linear = msg.get("linear") if isinstance(msg.get("linear"), dict) else {}
                angular = msg.get("angular") if isinstance(msg.get("angular"), dict) else {}
                self.last_cmd_vel = msg  # placeholder record
                self.previous_cmd_vel = copy.deepcopy(msg)  # placeholder record; the stop does not clear it
                self.fixed_motion = False  # the callback clears the lie
                # Placeholder echo: the fake changes its canned odometry twist so the
                # resource state reflects the last publication; this is not measured motion.
                self.odom_twist = {
                    "linear": {"x": linear.get("x", 0.0), "y": linear.get("y", 0.0),
                               "z": linear.get("z", 0.0)},  # placeholder
                    "angular": {"x": angular.get("x", 0.0), "y": angular.get("y", 0.0),
                                "z": angular.get("z", 0.0)},  # placeholder
                }
            return None
        if operation == "call_service":
            return self._service(message)
        return None

    def _service(self, message):
        service = message.get("service")
        values = message.get("args") if isinstance(message.get("args"), dict) else {}
        self.service_calls.append(service)  # placeholder test record
        if service == "/Spot/float_mode":
            self.float_mode = bool(values.get("data", False))
            if self.competing_float:
                self.float_mode = True  # placeholder: another client sets float mode true
            text = "Float mode set to True" if self.float_mode else "Float mode set to False"  # placeholder
            return self._response(service, message, result=True, values={"success": True, "message": text})
        if service == "/Spot/stand_up":
            if self.fail_stand_service:
                return self._response(service, message, result=False, values={})
            override = bool(values.get("override", False))
            if self.previous_cmd and not override:
                return self._response(service, message, result=True,
                                      values={"answer": "performing previous command, override with bool argument"})
            self.fixed_motion = True
            self.previous_cmd = True
            return self._response(service, message, result=True, values={"answer": "standing up"})
        if service == "/Spot/sit_down":
            override = bool(values.get("override", False))
            if self.previous_cmd and not override:
                return self._response(service, message, result=True,
                                      values={"answer": "performing previous command, override with bool argument"})
            self.fixed_motion = True
            self.previous_cmd = True
            return self._response(service, message, result=True, values={"answer": "sitting down"})
        if service == "/Spot/lie_down":
            if self.fail_lie_service:
                return self._response(service, message, result=False, values={})
            if self.reject_lie_application:
                # The plug-in sets fixed_motion before this refusal. This switch does not: the
                # base keeps walking, so a refused lie stays unconfirmed.
                return self._response(service, message, result=True,
                                      values={"answer": "performing previous command, override with bool argument"})
            self.fixed_motion = True
            self.previous_cmd = True
            return self._response(service, message, result=True, values={"answer": "lying down"})
        if service == "/Spot/set_height":
            height = values.get("height")
            if not isinstance(height, (int, float)) or not -0.2 <= height <= 0.2:  # placeholder copy of the source bound
                return self._response(service, message, result=True,
                                      values={"answer": "set height within -0.2 and 0.2"})
            self.zd = -float(height)
            return self._response(service, message, result=True, values={"answer": ""})
        return self._response(service, message, result=False, values={})

    @staticmethod
    def _response(service, request, *, result, values):
        return {
            "op": "service_response",
            "service": service,
            "id": request.get("id"),
            "result": result,
            "values": values,
        }
