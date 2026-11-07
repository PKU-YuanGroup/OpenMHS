"""ROS-free recording fake for the MuJoCo Go2 simulator endpoints.

The fake models the pinned upstream wire contract: a LowCmd publication on
/mujoco/lowcmd, a LowState publication on /mujoco/lowstate and a
Float32MultiArray qpos publication on /mujoco/pos.  It records outbound
publications, answers subscriptions with canned messages and never opens a
socket, starts ROS or runs MuJoCo.  Every number below is placeholder test
data, not a device fact.
"""

import threading
import time

from mhs.bridge.ros_transport import RecordingRosTransport

_GAP_S = 0.02  # placeholder default. The cited publish_sensor_data timer is 0.002 s (min_span_ms 4).


class FakeGo2MujocoSim(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.publish_state = True          # placeholder: silence the state topics
        self.last_command = None           # placeholder: last recorded motor_cmd array
        self.command_count = 0             # placeholder
        # Placeholder qpos: base position, base quaternion and twelve joint angles.
        self.qpos = [0.0, 0.0, 0.28, 1.0, 0.0, 0.0, 0.0,
                     0.1, 0.8, -1.5, -0.1, 0.8, -1.5,
                     0.1, 1.0, -1.5, -0.1, 1.0, -1.5]
        self._rest_qpos = list(self.qpos)  # counted confirmation samples; the echo below does not move them
        # Placeholder LowState motor slots; the simulator fills only 0-11.
        self.motor_state = [{"q": 0.1 * index, "dq": 0.0} for index in range(20)]
        self.quaternion = [1.0, 0.0, 0.0, 0.0]   # placeholder
        self.gyroscope = [0.0, 0.0, 0.0]          # placeholder
        self.republish = False             # placeholder: keep nonzero gains and a moving joint velocity
        self.stationary_hold = False       # placeholder: overwrite kp/kd but keep a stationary pose
        self.gap_s = _GAP_S                # placeholder spacing; tests set the 2 ms publication period
        self.null_dq = False               # placeholder: counted joint velocity is null
        self.base_moving = False           # placeholder: counted base x walks
        self._live_cv = threading.Condition()
        self._live = {}
        self._live_started = False

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
        """Pace ``builder()`` until this subscription id is unsubscribed.

        Two arrival topics each keep their own clock, so one topic's samples are
        not queued behind a finite batch of the other.
        """
        if not isinstance(ident, str):
            return
        with self._live_cv:
            self._live[ident] = {"builder": builder, "next_at": time.monotonic() + self.gap_s}
            if not self._live_started:
                self._live_started = True
                threading.Thread(target=self._pump_live, name="mhs-go2-samples", daemon=True).start()
            self._live_cv.notify_all()

    def _pump_live(self):
        while not self.closed:
            with self._live_cv:
                if self.closed:
                    return
                now = time.monotonic()
                due = [ident for ident, spec in self._live.items() if spec["next_at"] <= now]
                if not due:
                    soonest = min(spec["next_at"] for spec in self._live.values()) if self._live else now + 0.01
                    self._live_cv.wait(timeout=max(0.0, soonest - time.monotonic()))
                    continue
                ident = due[0]
                builder = self._live[ident]["builder"]
                self._live[ident]["next_at"] = now + self.gap_s
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

    def _passive(self):
        """True when counted samples should show a joint velocity of zero.

        ``republish`` keeps a moving joint. ``stationary_hold`` overwrites the stored gains and still reports
        a stationary pose. The exclusion subscription, not that pose, refuses the confirmation.
        """
        if self.stationary_hold:
            return True
        if self.republish:
            return False
        command = self.last_command or []
        if len(command) < 12:
            return False
        for entry in command[:12]:
            try:
                if float(entry.get("kp", 1.0)) != 0.0 or float(entry.get("kd", 1.0)) != 0.0:
                    return False
            except (TypeError, ValueError):
                return False
        return True

    def _lowstate_message(self, rate):
        motors = []
        for index, entry in enumerate(self.motor_state):
            item = dict(entry)
            if index < 12:
                item["dq"] = None if self.null_dq else rate  # placeholder
            motors.append(item)
        return {"motor_state": motors,
                "imu_state": {"quaternion": list(self.quaternion),
                              "gyroscope": list(self.gyroscope)}}

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if not self.publish_state:
                return None
            ident = message.get("id")
            topic = message.get("topic")
            if topic == "/mujoco/lowstate":
                # The first sample keeps the stored dq (the observation).  Counted samples are 0.4 rad/s until
                # kp and kd are zero, then 0.  The rate is read when the sample is fed.
                first = {"op": "publish", "topic": topic, "id": ident,
                         "msg": self._lowstate_message(self.motor_state[0]["dq"])}

                def later_state():
                    rate = 0.0 if self._passive() else 0.4  # placeholder rad/s
                    return {"op": "publish", "topic": topic, "id": ident,
                            "msg": self._lowstate_message(rate)}

                self._arm(ident, later_state)
                return first
            if topic == "/mujoco/lowcmd" and self.stationary_hold:
                # low_level_ctrl.cpp:160-167 republishes nonzero kp and kd. One sample is enough to refuse.
                command = [{"mode": 1, "q": 0.0, "dq": 0.0, "kp": 50.0, "kd": 1.0, "tau": 0.0} for _ in range(20)]
                return {"op": "publish", "topic": topic, "id": ident, "msg": {"motor_cmd": command}}
            if topic == "/mujoco/pos":
                first = {"op": "publish", "topic": topic, "id": ident, "msg": {"data": list(self.qpos)}}
                counter = {"n": 0}

                def later_pos():
                    counter["n"] += 1
                    data = list(self._rest_qpos)
                    if self.base_moving:
                        data[0] = 0.2 * counter["n"]  # placeholder metres, span above the fixture
                    return {"op": "publish", "topic": topic, "id": ident, "msg": {"data": data}}

                self._arm(ident, later_pos)
                return first
            return None
        if operation == "publish" and message.get("topic") == "/mujoco/lowcmd":
            body = message.get("msg")
            motor_cmd = body.get("motor_cmd") if isinstance(body, dict) else None
            if not isinstance(motor_cmd, list):
                return None
            self.last_command = [dict(entry) for entry in motor_cmd if isinstance(entry, dict)]
            self.command_count += 1
            if self.stationary_hold:
                for entry in self.last_command:
                    entry["kp"] = 50.0  # placeholder holding gain, not a device limit
                    entry["kd"] = 1.0   # placeholder holding gain, not a device limit
            # Placeholder observable for TCAP-003: the next /mujoco/pos echo carries the publication count.
            # Counted confirmation samples use _rest_qpos and do not follow this echo.
            self.qpos[2] = float(self.command_count)
        return None
