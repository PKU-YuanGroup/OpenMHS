"""ROS-free event-driven fake for the pinned Unitree Go2 simulation wire contract.

The fake models the RosDriver bindings declared in ``driver.py``:

* a ``unitree_go/msg/LowCmd`` publication on ``/lowcmd``;
* a ``std_msgs/msg/Empty`` publication on ``/reset`` and ``/unlock_base``;
* a ``unitree_go/msg/LowState`` subscription on ``/lowstate``;
* a ``nav_msgs/msg/Odometry`` subscription on ``/odometry/filtered``.

It is an analytic contract stand-in, not a recording of captured traffic: it
runs no ROS 2 graph, no pybullet physics, no timer and no base constraint.
Every number below is placeholder test data, not an upstream fact or a safety
limit.

The node has no stop service or action.  The fake does not invent one.  A
``/lowstate`` subscription keeps the command echo as its first sample, then a
live stream spaced on the wall clock (joint dq stays 0.4 rad/s until the last
LowCmd has kp, kd and tau zero on the twelve applied joints).  ``/odometry/filtered``
answers with one stamped burst: producer stamps step by 60 ms, so the stamp
source does not wait on that stream.  Every number is placeholder test data.
"""

import threading
import time

from mhs.bridge.ros_transport import RecordingRosTransport

# placeholder: Go2Configuration lists 12 joints in the pinned README scope
JOINT_COUNT = 12
# placeholder: Go2Configuration lists four foot sensor names
FOOT_COUNT = 4
# placeholder default. The cited Go2 timer is 1/500 s, and min_span_ms is 4.
_GAP_S = 0.05
# placeholder: one discarded stamp plus enough strictly later stamps for a window of three
_ODOM_BURST = 6


class FakeUnitreeSimulation(RecordingRosTransport):
    def __init__(self, **_options):
        # Placeholder state.  The values below are invented test data; they are
        # not copied from the upstream starting configuration or any limit.
        self.motor_count = JOINT_COUNT            # placeholder
        self.foot_count = FOOT_COUNT              # placeholder
        self.last_motor_cmd = None                # placeholder echo of the last command
        self.lowcmd_count = 0                     # recording helper
        self.reset_count = 0                      # recording helper
        self.unlock_count = 0                     # recording helper
        self.malformed_lowstate = False           # placeholder negative-path switch
        self.silent_lowstate = False              # placeholder negative-path switch
        self.malformed_odometry = False           # placeholder negative-path switch
        self.reject_publish = False               # placeholder negative-path switch
        # Reviewer addition: default entries appended after the 12 the node fills, to model a pre-sized
        # motor_state array (its size is set by the unitree_go definition, outside the clone).
        self.extra_motor_entries = 0              # placeholder switch
        self.keep_moving = False                  # placeholder: joint dq stays 0.4 after a zero-gain command
        self.null_dq = False                      # placeholder: counted samples carry a null dq
        self.frozen_stamps = False                # placeholder: every odometry stamp repeats one non-zero stamp
        self.base_moving = False                  # placeholder: counted twist stays nonzero
        self.gap_s = _GAP_S                       # placeholder spacing; tests set the 500 Hz period
        self._live_cv = threading.Condition()
        self._live: dict[str, dict] = {}
        self._live_started = False
        super().__init__(handler=self._respond)

    def send(self, message, *, timeout_s=None):
        """Queue the handler reply. An unsubscribe ends that subscription's live stream."""
        operation = message.get("op") if isinstance(message, dict) else None
        ident = message.get("id") if isinstance(message, dict) else None
        super().send(message, timeout_s=timeout_s)
        if operation == "unsubscribe" and isinstance(ident, str):
            with self._live_cv:
                self._live.pop(ident, None)
                self._live_cv.notify_all()

    def _arm(self, ident, builder):
        """Space ``builder()`` samples for this subscription until it is unsubscribed.

        A new subscription does not wait behind an older finite batch: only live
        subscription ids are served, and each id is paced on its own clock.
        """
        if not isinstance(ident, str):
            return
        with self._live_cv:
            self._live[ident] = {"builder": builder, "next_at": time.monotonic() + self.gap_s}
            if not self._live_started:
                self._live_started = True
                threading.Thread(target=self._pump_live, name="mhs-unitree-samples", daemon=True).start()
            self._live_cv.notify_all()

    def _pump_live(self):
        """Feed one due sample once the inbound queue is empty, then wait out that id's gap."""
        while not self.closed:
            with self._live_cv:
                if self.closed:
                    return
                now = time.monotonic()
                due = [ident for ident, spec in self._live.items() if spec["next_at"] <= now]
                if not due:
                    soonest = min(item["next_at"] for item in self._live.values()) if self._live else now + 0.01
                    self._live_cv.wait(timeout=max(0.0, soonest - time.monotonic()))
                    continue
                ident = due[0]
                spec = self._live[ident]
                builder = spec["builder"]
                spec["next_at"] = now + self.gap_s
            if not self._await_inbound_empty():
                with self._live_cv:
                    current = self._live.get(ident)
                    if current is not None:
                        current["next_at"] = time.monotonic()
                continue
            with self._live_cv:
                if ident not in self._live or self.closed:
                    continue
            try:
                self.feed(builder())
            except ConnectionError:
                return

    def _await_inbound_empty(self):
        deadline = time.monotonic() + 0.05
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

    def _gains_cut(self):
        """True when the last LowCmd has zero kp, kd and tau on the twelve joints the node applies."""
        if self.keep_moving:
            return False
        command = self.last_motor_cmd if isinstance(self.last_motor_cmd, list) else []
        if len(command) < JOINT_COUNT:
            return False
        for entry in command[:JOINT_COUNT]:
            if not isinstance(entry, dict):
                return False
            try:
                kp = float(entry.get("kp", 1.0))
                kd = float(entry.get("kd", 1.0))
                tau = float(entry.get("tau", 1.0))
            except (TypeError, ValueError):
                return False
            if kp != 0.0 or kd != 0.0 or tau != 0.0:
                return False
        return True

    # -- transport handler -----------------------------------------------------
    def _respond(self, message):
        operation = message.get("op")
        topic = message.get("topic")
        ident = message.get("id")
        if operation == "subscribe":
            if topic == "/lowstate":
                return self._lowstate(ident)
            if topic == "/odometry/filtered":
                return self._odometry(ident)
            return None
        if operation == "advertise":
            return None
        if operation == "publish":
            return self._publish(topic, message)
        if operation == "unsubscribe":
            return None
        return None

    # -- topic observations ----------------------------------------------------
    def _lowstate(self, ident):
        if self.silent_lowstate:
            return None
        if self.malformed_lowstate:
            return {"op": "publish", "topic": "/lowstate", "id": ident,
                    "msg": {"motor_state": "not-an-array"}}  # placeholder malformed reply
        # Placeholder contract effect: the last published command is echoed as
        # the observed q/dq so a publication changes the resource state.  This
        # is not pybullet-measured joint state and it is not physics.
        command = self.last_motor_cmd if isinstance(self.last_motor_cmd, list) else []
        motors = []
        for index in range(self.motor_count):
            entry = command[index] if index < len(command) and isinstance(command[index], dict) else {}
            motors.append({
                "mode": 1,                                      # placeholder
                "q": float(entry.get("q", 0.0)),                # placeholder echo
                "dq": float(entry.get("dq", 0.0)),              # placeholder echo
            })
        for _ in range(self.extra_motor_entries):
            motors.append({"mode": 0, "q": 0.0, "dq": 0.0})     # placeholder default entry the node never fills
        first = {
            "op": "publish",
            "topic": "/lowstate",
            "id": ident,
            "msg": {
                "motor_state": motors,
                "foot_force": [0] * self.foot_count,  # placeholder
                "imu_state": {
                    "quaternion": [1.0, 0.0, 0.0, 0.0],  # placeholder
                    "gyroscope": [0.0, 0.0, 0.0],        # placeholder
                    "accelerometer": [0.0, 0.0, 0.0],    # placeholder
                },
            },
        }
        # The first sample stays the command echo (observation and TCAP-003).  Counted samples are the
        # placeholder physics stream, built when they are fed: still moving until the zero-gain command.
        def later():
            rate = 0.0 if self._gains_cut() else 0.4  # placeholder rad/s
            streamed = []
            for index in range(self.motor_count):
                entry = motors[index]
                streamed.append({
                    "mode": entry["mode"],
                    "q": entry["q"],
                    "dq": None if self.null_dq else rate,  # placeholder
                })
            for extra in motors[self.motor_count:]:
                streamed.append(dict(extra))
            return {"op": "publish", "topic": "/lowstate", "id": ident,
                    "msg": {"motor_state": streamed, "foot_force": [0] * self.foot_count,
                            "imu_state": first["msg"]["imu_state"]}}

        self._arm(ident, later)
        return first

    def _odometry(self, ident):
        if self.malformed_odometry:
            return {"op": "publish", "topic": "/odometry/filtered", "id": ident,
                    "msg": {"pose": "not-an-object"}}  # placeholder malformed reply
        def sample(index):
            # Index 0 is discarded.  Its stamp is already non-zero, and each later stamp is 60 ms
            # greater, so three counted samples span 120 ms (the declared min_span_ms is 4).  A frozen stamp repeats
            # one non-zero time: a zero stamp would be invalid rather than stale.
            if self.frozen_stamps:
                sec, nanosec = 1, 0  # placeholder
            else:
                sec, nanosec = 0, (index + 1) * 60_000_000  # placeholder
            linear_x = 1.0 if index > 0 and self.base_moving else 0.0  # placeholder
            return {
                "op": "publish",
                "topic": "/odometry/filtered",
                "id": ident,
                "msg": {
                    "header": {"stamp": {"sec": sec, "nanosec": nanosec}, "frame_id": "odom"},  # placeholder
                    "child_frame_id": "base",  # placeholder
                    "pose": {"pose": {
                        "position": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                    }},
                    "twist": {"twist": {
                        "linear": {"x": linear_x, "y": 0.0, "z": 0.0},  # placeholder
                        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                    }},
                },
            }
        return [sample(index) for index in range(_ODOM_BURST)]

    # -- command publications --------------------------------------------------
    def _publish(self, topic, message):
        if self.reject_publish:
            raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        if topic == "/lowcmd":
            self.lowcmd_count += 1
            self.last_motor_cmd = body.get("motor_cmd")  # placeholder echo, no physics
        elif topic == "/reset":
            self.reset_count += 1
        elif topic == "/unlock_base":
            self.unlock_count += 1
        return None
