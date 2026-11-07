"""ROS-free protocol fake for the opendrone base-node contract.

The fake answers the rosbridge subscriptions and the ``/land`` and
``/mavros/cmd/arming`` services that the driver declares, and it records the
``/planner/output`` publication.  It contacts no ROS graph, PX4 SITL, Gazebo
or MAVROS process.  Every state value below is synthesized placeholder data,
not a device fact and not a replay of captured ROS traffic.

The sensed-confirmation stop (SAFE-049) needs stamped samples: every
sensed subscription is answered with a short burst of samples whose ROS 1
stamps (secs, nsecs) increase on a placeholder clock, and each sample advances
a placeholder landing by one tick.  The first sample of a burst is the state
before that tick and is returned at once.  The rest are fed one at a time.
A ROS 1 sample counts only when its producer stamp is strictly after the
bridge clock at subscribe (BL-17).  Nothing satisfies the predicate before
``/land`` arrived: the fake starts airborne and armed.
"""

import threading
import time

from mhs.bridge.ros_transport import RecordingRosTransport

#: PlannerOutputPoint VALID_POSITION bit; test data copied from the pinned
#: message definition (the sourced Fact is opendrone/msg/PlannerOutputPoint.msg:4).
_VALID_POSITION = 1  # placeholder
_BURST = 16                 # placeholder: samples per subscription
_TICK_NS = 100_000_000      # placeholder: 0.1 s of simulated time per sample
_STATE_TOPIC = "/mavros/state"
_POSE_TOPIC = "/mavros/local_position/pose"


class FakeOpendrone(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder state: a latched target, a local pose, and a fake
        # MAVROS/base status.  None of these are device facts.
        self.target = {"x": 0.0, "y": 0.0, "z": 2.0}          # placeholder
        self.position = {"x": 0.0, "y": 0.0, "z": 2.0}        # placeholder: airborne at the takeoff height
        self.flight_state = 3                                  # placeholder MISSION_EXECUTION
        self.connected = True                                  # placeholder
        self.armed = True                                      # placeholder
        self.mode = "OFFBOARD"                                 # placeholder
        self.landing_requested = False                         # placeholder
        self.landing_locked = False                            # placeholder of the node's landing_locked_
        self.descending = False                                # placeholder AUTO.LAND descent in progress
        self._stamp_base = 0                                   # placeholder: wall time of one subscribe
        self._stamp_step = 0                                   # placeholder: samples already stamped in it
        self.land_requests = 0                                 # placeholder counter
        self.disarm_requests = 0                               # placeholder counter
        # Negative-path switches used by the package tests.
        self.fail_land_service = False                         # placeholder
        self.fail_land_application = False                     # placeholder
        self.malformed_land_response = False                   # placeholder
        self.silent_topics = False                             # placeholder
        self.silent_setpoint = False                           # placeholder
        self.ignore_land = False                               # placeholder: /land acknowledged, no descent
        self.no_auto_disarm = False                            # placeholder: PX4 does not disarm at touchdown
        self.flight_state_lies = False                         # placeholder: /flight_state says LANDED at once
        self.frozen_stamps = False                             # placeholder: every sample repeats one stamp
        self.null_altitude = False                             # placeholder: pose z is null in every sample
        self.published_points = []                             # placeholder

    # -- placeholder dynamics ------------------------------------------------------------------------------
    def _stamp(self):
        """Placeholder ROS 1 clock. A producer stamp is not a freshness proof.

        Each subscribe starts its own clock at that call's wall time. The bridge discards every ROS 1 stamp.
        """
        if self.frozen_stamps:
            total = self._frozen_ns
        else:
            self._stamp_step += 1
            total = self._stamp_base + self._stamp_step * _TICK_NS
        return {"secs": total // 1_000_000_000, "nsecs": total % 1_000_000_000}

    def _tick(self):
        if self.flight_state == 4 and self.landing_locked:
            self.flight_state = 5                              # placeholder: LANDED on mode_sent
        if not self.descending:
            return
        z = self.position["z"]
        if z > 0.0:
            step = max(0.5, z / 4.0)                            # placeholder descent per sample
            self.position["z"] = 0.0 if z <= step else round(z - step, 6)
            self.mode = "AUTO.LAND"
        if self.position["z"] == 0.0:
            self.descending = False
            if not self.no_auto_disarm:
                self.armed = False                             # placeholder of PX4 auto-disarm at touchdown

    def takeoff(self, height=1.0):
        """Another actor re-arms and climbs (a ground station or another MAVROS client); placeholder."""
        self.armed, self.mode, self.descending = True, "OFFBOARD", False
        self.position["z"] = float(height)

    def _header(self, frame_id):
        return {
            "seq": 0,                                          # placeholder
            "stamp": self._stamp(),
            "frame_id": frame_id,
        }

    def _pose(self, position):
        pose = {
            "header": self._header("map"),
            "pose": {
                "position": dict(position),
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            },
        }
        return pose

    def _state(self):
        return {
            "header": self._header("base_link"),
            "connected": self.connected,
            "armed": self.armed,
            "guided": True,                    # placeholder
            "manual_input": False,             # placeholder
            "mode": self.mode,
            "system_status": 3,                # placeholder
        }

    def _burst(self, topic, ident):
        if self.frozen_stamps:
            # Captured during this subscribe. A ROS 1 stamp is not a freshness proof.
            self._frozen_ns = time.time_ns() + 1
        else:
            self._stamp_base = time.time_ns()
            self._stamp_step = 0
        samples = []
        for _ in range(_BURST):
            if topic == _STATE_TOPIC:
                body = self._state()
            else:
                body = self._pose(self.position)
                if self.null_altitude:
                    body["pose"]["position"]["z"] = None
            samples.append({"op": "publish", "topic": topic, "id": ident, "msg": body})
            self._tick()
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
            if self.silent_topics:
                return None
            topic = message.get("topic")
            if topic in (_STATE_TOPIC, _POSE_TOPIC):
                return self._burst(topic, message.get("id"))
            if topic == "/mavros/setpoint_position/local":
                if self.silent_setpoint:
                    return None
                if not self.frozen_stamps:
                    self._stamp_base = time.time_ns()
                    self._stamp_step = 0
                return {"op": "publish", "topic": topic, "id": message.get("id"),
                        "msg": self._pose(self.target)}
            if topic == "/flight_state":
                state = 5 if (self.flight_state_lies and self.landing_requested) else self.flight_state
                return {"op": "publish", "topic": topic, "id": message.get("id"), "msg": {"data": state}}
            return None
        if operation == "publish":
            if message.get("topic") == "/planner/output":
                body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
                points = body.get("points")
                if isinstance(points, list):
                    self.published_points = [dict(item) for item in points if isinstance(item, dict)]
                    selected = next(
                        (item for item in self.published_points
                         if isinstance(item.get("valid_mask"), int)
                         and not isinstance(item.get("valid_mask"), bool)
                         and item["valid_mask"] & _VALID_POSITION),
                        None,
                    )
                    if selected is not None:
                        position = selected.get("position")
                        if isinstance(position, dict):
                            self.target = {
                                "x": float(position.get("x", self.target["x"])),  # placeholder
                                "y": float(position.get("y", self.target["y"])),  # placeholder
                                "z": float(position.get("z", self.target["z"])),  # placeholder
                            }
                            # Placeholder effect only: the fake snaps its local pose to the target instead of
                            # integrating motion.  Once the landing lock is set the node no longer publishes
                            # its target (LANDING/LANDED), so the pose stays.
                            if not self.landing_locked:
                                self.position = dict(self.target)
            return None
        if operation == "call_service":
            service = message.get("service")
            ident = message.get("id")
            if service == "/mavros/cmd/arming":
                value = (message.get("args") or {}).get("value")
                self.disarm_requests += 1 if value is False else 0
                landed = self.position["z"] == 0.0 and not self.descending
                ok = value is False and landed                  # placeholder: PX4 refuses disarm in the air
                if ok:
                    self.armed = False
                return {"op": "service_response", "service": service, "id": ident, "result": True,
                        "values": {"success": ok, "result": 0 if ok else 1}}  # placeholder
            if service != "/land":
                return {"op": "service_response", "service": service, "id": ident, "result": False, "values": {}}
            if self.fail_land_service:
                return {"op": "service_response", "service": "/land", "id": ident, "result": False, "values": {}}
            if self.malformed_land_response:
                return {"op": "service_response", "service": "/land", "id": ident,
                        "result": True, "values": "not-a-service-values-object"}
            if self.fail_land_application:
                return {"op": "service_response", "service": "/land", "id": ident,
                        "result": True,
                        "values": {"success": False,
                                   "message": "base position baseline ignores land=false"}}  # placeholder
            self.land_requests += 1
            self.landing_requested = True
            self.landing_locked = True
            self.flight_state = 4                               # placeholder LANDING
            if not self.ignore_land and self.position["z"] > 0.0:
                self.descending = True
            return {"op": "service_response", "service": "/land", "id": ident,
                    "result": True,
                    "values": {"success": True,
                               "message": "base position baseline landing requested"}}  # placeholder
        return None
