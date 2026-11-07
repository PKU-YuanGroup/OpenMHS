"""ROS-free contract fake for the pinned quadruped_ctrl endpoints.

The fake models the upstream wire contract declared in ``driver.py``:

* a ``publish`` of ``geometry_msgs/Twist`` on ``/cmd_vel``;
* ``call_service`` requests to ``/gait_type`` and ``/robot_mode`` with the
  ``quadruped_ctrl/QuadrupedCmd`` type;
* subscriptions to ``/robot_odom`` and ``/imu0`` with the fields the
  observation capabilities select.

It is an analytic contract stand-in with canned replies, not a recording of
captured traffic: it runs no ROS, rosbridge, pybullet, physics or controller.
Canned state and telemetry numbers are test data and are marked
``# placeholder``; none is a device fact. The 0 and -1 service result codes
follow the pinned QuadrupedCmd.srv comment (0 success, -1 false).

The sensed-confirmation stop (SAFE-049) needs stamped samples: an odometry or
IMU subscription is answered with a short burst whose ROS 1 stamps (secs,
nsecs) increase on a placeholder clock.  The fake starts walking (robot mode
1); while a speed is commanded a burst is a projection of the walk that is
not stored (two reads agree); after a zero Twist the placeholder filtered
speed decays to the standing branch, and in robot mode 0 only gait 4 stands,
which is stored.  The first sample of a burst is the stored state and is
returned at once.  The rest are fed one at a time.  A ROS 1 producer stamp is not a freshness
proof (BL-17); the placeholder clock still steps by ``_DT`` and the bridge discards every stamp.
"""

import threading
import time

from mhs.bridge.ros_transport import RecordingRosTransport

_BURST = 16          # placeholder: samples per subscription
_DT = 0.1            # placeholder: simulated seconds per sample
_DECAY = 0.5         # placeholder decay of the filtered speed per sample (not the 0.01 per-step filter)
_STAND_Z = 0.25      # placeholder standing height
_COLLAPSED_Z = 0.05  # placeholder height after a torque cut


class FakeQuadrupedCtrl(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.gait_type = 9                    # placeholder state (trotting)
        self.robot_mode = 1                   # placeholder state: the node's mode after start-up
        self.odom_x = 0.0                     # placeholder echo of the last linear.x
        self.odom_y = 0.0                     # placeholder echo of the last linear.y
        self.odom_z = _STAND_Z                # placeholder base height
        self.last_cmd_vel = [0.3, 0.0, 0.0]   # placeholder [linear.x, linear.y, angular.x]: walking
        self.speed = 0.3                      # placeholder filtered speed
        self._stamp_base = 0                  # placeholder: wall time captured at the start of one burst
        self._stamp_step = 0                  # placeholder: samples already stamped in that burst
        self.cmd_vel_messages = []            # recording helper, no device meaning
        self.service_calls = []               # recording helper, no device meaning
        self.fail_gait_service = False        # placeholder negative-path switch
        self.reject_gait_application = False  # placeholder negative-path switch
        self.malformed_gait_response = False  # placeholder negative-path switch
        self.fail_robot_mode_service = False  # placeholder negative-path switch
        self.reject_robot_mode_application = False  # placeholder negative-path switch
        self.competing_cmd_vel = False        # placeholder: another publisher keeps commanding a speed
        self.collapsed = False                # placeholder: a torque cut drops the base below the band
        self.frozen_stamps = False            # placeholder: every sample repeats one stamp
        self.null_rate = False                # placeholder: the IMU angular_velocity.x is null
        self.silent = False                   # placeholder: odometry and IMU answer nothing

    def _standing(self, speed):
        if self.robot_mode == 1:
            return speed == 0.0               # the adaptive gait stands once the filtered speed is ~0
        return self.gait_type == 4 and speed == 0.0

    def _stamp(self):
        """Placeholder ROS 1 clock. A producer stamp is not a freshness proof. The step stays ``_DT``.

        Each ``_burst`` starts its own clock at that call's wall time. The bridge discards every ROS 1 stamp.
        """
        if self.frozen_stamps:
            total = self._frozen_ns
        else:
            self._stamp_step += 1
            total = self._stamp_base + self._stamp_step * int(_DT * 1_000_000_000)
        return {"secs": total // 1_000_000_000, "nsecs": total % 1_000_000_000}

    def _sample(self, topic, ident, x, y, z, rate):
        stamp = self._stamp()
        if topic == "/robot_odom":
            body = {"header": {"seq": 0, "stamp": stamp, "frame_id": "world"},  # placeholder
                    "child_frame_id": "body",
                    "pose": {"pose": {"position": {"x": x, "y": y, "z": z},
                                      "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}}}  # placeholder
        else:
            body = {"header": {"seq": 0, "stamp": stamp, "frame_id": "body"},  # placeholder
                    "linear_acceleration": {"x": 0.0, "y": 0.0, "z": 9.81},  # placeholder
                    "angular_velocity": {"x": None if self.null_rate else 0.0, "y": 0.0, "z": rate},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}  # placeholder
        return {"op": "publish", "topic": topic, "id": ident, "msg": body}

    def _burst(self, topic, ident):
        if self.competing_cmd_vel:
            self.last_cmd_vel = [0.3, 0.0, 0.0]  # placeholder: another /cmd_vel publisher
        commanded = abs(self.last_cmd_vel[0]) + abs(self.last_cmd_vel[1]) + abs(self.last_cmd_vel[2])
        x, y, speed = self.odom_x, self.odom_y, self.speed
        if commanded > 0.0:
            speed = max(speed, commanded)  # placeholder: a commanded speed makes the robot walk
        z = _COLLAPSED_Z if self.collapsed else self.odom_z
        if self.frozen_stamps:
            # Captured during this subscribe. A ROS 1 stamp is not a freshness proof.
            self._frozen_ns = time.time_ns() + 1
        else:
            self._stamp_base = time.time_ns()
            self._stamp_step = 0
        samples = []
        for _ in range(_BURST):
            standing = self._standing(speed)
            samples.append(self._sample(topic, ident, x, y, z, 0.0 if standing else 0.2))  # placeholder rate
            if not standing:
                x = round(x + max(speed, 0.05) * _DT, 9)  # placeholder: a walking gait moves the base
            speed = 0.0 if commanded == 0.0 and speed < 0.01 else (
                round(speed * _DECAY, 9) if commanded == 0.0 else speed)
        if commanded == 0.0 and (self.robot_mode == 1 or self.gait_type == 4):
            self.odom_x, self.odom_y, self.speed = x, y, speed  # the decay to standing is stored (placeholder)
        return self._after_latch(samples)

    def send(self, message, *, timeout_s=None):
        """Queue the handler reply, then let the live-sample pump run (BL-17)."""
        before = getattr(self, "_live_serial", 0)
        super().send(message, timeout_s=timeout_s)
        if getattr(self, "_live_serial", 0) != before:
            with self._live_cv:
                self._latch_ready += 1
                self._live_cv.notify_all()

    def _after_latch(self, samples):
        """The first sample is the latch. Later samples wait until the reader has taken it (BL-17)."""
        if not samples:
            return None
        rest = list(samples[1:])
        if rest:
            if getattr(self, "_live_cv", None) is None:
                self._live_cv = threading.Condition()
                self._live_batches = []
                self._live_serial = 0
                self._latch_ready = 0
                self._live_started = False
            with self._live_cv:
                self._live_serial += 1
                self._live_batches.append((self._live_serial, rest))
                if not self._live_started:
                    self._live_started = True
                    threading.Thread(target=self._pump_live, name="mhs-ros1-latch", daemon=True).start()
                self._live_cv.notify_all()
        return samples[0]

    def _pump_live(self):
        """Feed each live sample only when the inbound queue is empty.

        One shared queue serves every topic. A producer stamp is not a freshness
        proof. The pump still spaces the burst so a subscribe handler does not
        deliver every later sample in the latch reply.
        """
        while not self.closed:
            with self._live_cv:
                while not self._live_batches and not self.closed:
                    self._live_cv.wait(timeout=0.05)
                if self.closed or not self._live_batches:
                    continue
                token, batch = self._live_batches.pop(0)
                deadline = time.monotonic() + 2.0
                while self._latch_ready < token and not self.closed and time.monotonic() < deadline:
                    self._live_cv.wait(timeout=0.05)
                ready = self._latch_ready >= token and not self.closed
            if not ready:
                continue
            for item in batch:
                if not self._await_inbound_empty():
                    break
                try:
                    self.feed(item)
                except ConnectionError:
                    return

    def _await_inbound_empty(self):
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if self.closed:
                return False
            try:
                queued = self.buffered()
            except Exception:
                return False
            if not queued:
                return True
            time.sleep(0.001)
        return False

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "publish":
            self._record_cmd_vel(message)
            return None
        if operation == "call_service":
            return self._service(message)
        return None

    def _observation(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        if topic in ("/robot_odom", "/imu0"):
            return None if self.silent else self._burst(topic, ident)
        return None

    def _record_cmd_vel(self, message):
        if message.get("topic") != "/cmd_vel":
            return
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        linear = body.get("linear") if isinstance(body.get("linear"), dict) else {}
        angular = body.get("angular") if isinstance(body.get("angular"), dict) else {}
        self.last_cmd_vel = [
            linear.get("x", 0.0),    # placeholder default
            linear.get("y", 0.0),    # placeholder default
            angular.get("x", 0.0),   # placeholder default
        ]
        # Placeholder analytic echo for the resource state; the fake runs no
        # physics and does not integrate the command into a pose.  A zero Twist
        # (the stop request) leaves the pose where the walk stopped.
        if any(self.last_cmd_vel):
            self.odom_x = self.last_cmd_vel[0]
            self.odom_y = self.last_cmd_vel[1]
            self.speed = abs(self.last_cmd_vel[0]) + abs(self.last_cmd_vel[1])
        self.cmd_vel_messages.append(message)

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")
        args = message.get("args") if isinstance(message.get("args"), dict) else {}
        if service == "/gait_type":
            return self._quadruped_cmd_service(
                service, ident, args, self.fail_gait_service, self.reject_gait_application,
                self.malformed_gait_response, "gait",
            )
        if service == "/robot_mode":
            return self._quadruped_cmd_service(
                service, ident, args, self.fail_robot_mode_service, self.reject_robot_mode_application,
                False, "mode",
            )
        return {
            "op": "service_response",
            "service": service,
            "id": ident,
            "result": False,
            "values": {"result": -1, "description": "unsupported service"},  # placeholder
        }

    def _quadruped_cmd_service(self, service, ident, args, fail_service, reject, malformed, label):
        if fail_service:
            return {
                "op": "service_response",
                "service": service,
                "id": ident,
                "result": False,
                "values": {"result": -1, "description": "service unavailable"},  # placeholder
            }
        if malformed:
            return {
                "op": "service_response",
                "service": service,
                "id": ident,
                "result": True,
                "values": "malformed",  # placeholder malformed reply
            }
        requested = args.get("cmd") if isinstance(args.get("cmd"), int) else 0  # placeholder default
        if reject:
            return {
                "op": "service_response",
                "service": service,
                "id": ident,
                "result": True,
                "values": {"result": -1, "description": "application rejected"},  # placeholder
            }
        self.service_calls.append((service, requested))
        if service == "/gait_type":
            self.gait_type = requested
        else:
            self.robot_mode = requested
        return {
            "op": "service_response",
            "service": service,
            "id": ident,
            "result": True,
            "values": {"result": 0, "description": "get the " + label},  # placeholder
        }
