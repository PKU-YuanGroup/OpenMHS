"""ROS-free recording fake for the pinned PX4 SITL / MAVROS contract.

The fake answers the rosbridge subscriptions and services that driver.py
declares and records the setpoint publications. It contacts no ROS graph,
rosbridge peer, PX4 SITL, Gazebo or MAVROS process. Every state value below is
synthesized placeholder data, not a device fact and not a replay of captured
ROS traffic.

The sensed-confirmation stop (SAFE-049) needs stamped samples: the state and
altitude subscriptions are answered with a short burst whose ROS 1 stamps
(secs, nsecs) increase on a placeholder clock, each sample advancing a
placeholder landing by one tick; the first sample of a burst is the state
before that tick and is returned at once.  The rest are fed one at a time.
A ROS 1 sample counts only when its producer stamp is strictly after the
bridge clock at subscribe (BL-17).  The fake starts armed
in OFFBOARD at the offb hover altitude, so nothing satisfies the predicate
before the land request arrived.
"""

import threading
import time

from mhs.bridge.ros_transport import RecordingRosTransport

#: Placeholder landed-state values for test data only; neither is a driver
#: bound or a touchdown/landing claim.
_ON_GROUND = 1  # placeholder
_LANDING = 4  # placeholder
_IN_AIR = 2  # placeholder
_BURST = 16  # placeholder: samples per sensed subscription
_TICK_NS = 100_000_000  # placeholder: 0.1 s of simulated time per sample
_GROUND_AMSL = 0.0  # placeholder home altitude


class FakePx4Sitl(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder MAVROS state. None of these values is a device fact.
        self.connected = True  # placeholder
        self.armed = True  # placeholder: armed and flying, as offb_node leaves the vehicle
        self.mode = "OFFBOARD"  # placeholder
        self.altitude_amsl = 2.0  # placeholder: the offb hover height above the placeholder ground
        self.landed_state = _IN_AIR  # placeholder
        self.descending = False  # placeholder AUTO.LAND descent in progress
        self._stamp_base = 0  # placeholder: wall time captured at the start of one subscribe
        self._stamp_step = 0  # placeholder: samples already stamped in that subscribe
        self.disarm_requests = 0  # placeholder counter
        self.vtol_state = 0  # placeholder
        self.position = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder
        self.velocity = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder
        self.yaw = 0.0  # placeholder
        self.yaw_rate = 0.0  # placeholder
        self.landing_requested = False  # placeholder
        self.sent_setpoints = []  # placeholder recording of outbound publications
        # Negative-path switches used by the package tests.
        self.fail_state_topic = False  # placeholder
        self.fail_altitude_topic = False  # placeholder
        self.fail_arming_service = False  # placeholder
        self.reject_arming_application = False  # placeholder
        self.fail_mode_service = False  # placeholder
        self.reject_mode_application = False  # placeholder
        self.fail_land_service = False  # placeholder
        self.reject_land_application = False  # placeholder
        self.malformed_land_response = False  # placeholder
        self.ignore_land = False  # placeholder: the land request is acknowledged, nothing descends
        self.no_auto_disarm = False  # placeholder: PX4 does not disarm at touchdown
        self.frozen_stamps = False  # placeholder: every sample repeats one stamp
        self.null_altitude = False  # placeholder: amsl is null in every sample
        self.silent_sensed = False  # placeholder: the state and altitude topics answer nothing

    def _stamp(self):
        """Placeholder ROS 1 clock. A producer stamp is not a freshness proof.

        Each ``_subscribe`` starts its own clock at that call's wall time. The bridge discards every ROS 1 stamp.
        """
        if self.frozen_stamps:
            total = self._frozen_ns
        else:
            self._stamp_step += 1
            total = self._stamp_base + self._stamp_step * _TICK_NS
        return {"secs": total // 1_000_000_000, "nsecs": total % 1_000_000_000}

    def _tick(self):
        if not self.descending:
            return
        height = self.altitude_amsl - _GROUND_AMSL
        step = max(0.5, height / 4.0)  # placeholder descent per sample
        self.altitude_amsl = _GROUND_AMSL if height <= step else round(self.altitude_amsl - step, 6)
        if self.altitude_amsl == _GROUND_AMSL:
            self.descending = False
            self.landed_state = _ON_GROUND
            if not self.no_auto_disarm:
                self.armed = False  # placeholder of PX4 auto-disarm after touchdown

    def offb_rearm(self):
        """offb_node requests OFFBOARD and arming again and climbs to its hover pose; placeholder."""
        self.armed, self.mode, self.descending, self.landed_state = True, "OFFBOARD", False, _IN_AIR
        self.altitude_amsl = _GROUND_AMSL + 2.0  # placeholder

    def _header(self, frame_id):
        return {
            "seq": 0,  # placeholder
            "stamp": self._stamp(),
            "frame_id": frame_id,
        }

    def _state_message(self, connected, armed, mode):
        return {
            "header": self._header("base_link"),
            "connected": connected,
            "armed": armed,
            "guided": True,  # placeholder
            "manual_input": False,  # placeholder
            "mode": mode,
            "system_status": 3,  # placeholder
        }

    def _altitude_message(self, amsl):
        return {
            "header": self._header("base_link"),
            "monotonic": float(amsl),  # placeholder
            "amsl": None if self.null_altitude else float(amsl),
            "local": 0.0,  # placeholder
            "relative": 0.0,  # placeholder
            "terrain": 0.0,  # placeholder
            "bottom_clearance": 0.0,  # placeholder
        }

    def _subscribe(self, topic, ident):
        if topic not in ("/mavros/state", "/mavros/altitude") or self.silent_sensed:
            return None
        if (topic == "/mavros/state" and self.fail_state_topic) or (
                topic == "/mavros/altitude" and self.fail_altitude_topic):
            return None
        if self.frozen_stamps:
            # Captured during this subscribe. A ROS 1 stamp is not a freshness proof.
            self._frozen_ns = time.time_ns() + 1
        else:
            self._stamp_base = time.time_ns()
            self._stamp_step = 0
        samples = []
        for _ in range(_BURST):
            body = (self._state_message(self.connected, self.armed, self.mode) if topic == "/mavros/state"
                    else self._altitude_message(self.altitude_amsl))
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

    def _publish(self, message):
        topic = message.get("topic")
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        self.sent_setpoints.append({"topic": topic, "msg": body})  # placeholder recording
        if self.mode == "AUTO.LAND":
            return None  # placeholder: PX4 in AUTO.LAND does not follow offboard setpoints
        if topic == "/mavros/setpoint_position/local":
            pose = body.get("pose") if isinstance(body.get("pose"), dict) else {}
            position = pose.get("position") if isinstance(pose.get("position"), dict) else {}
            # Placeholder effect only: the fake snaps its local pose to the
            # published setpoint. It integrates no motion and this is not an
            # arrival or flight-dynamics claim.
            self.position = {
                "x": float(position.get("x", self.position["x"])),
                "y": float(position.get("y", self.position["y"])),
                "z": float(position.get("z", self.position["z"])),
            }
            # Placeholder effect only: the fake follows the z of the setpoint
            # with its AMSL altitude so the resource changes. It integrates no
            # motion and this is not an arrival or flight-dynamics claim.
            self.altitude_amsl = self.position["z"]
        elif topic == "/mavros/setpoint_raw/local":
            velocity = body.get("velocity") if isinstance(body.get("velocity"), dict) else {}
            self.velocity = {
                "x": float(velocity.get("x", self.velocity["x"])),
                "y": float(velocity.get("y", self.velocity["y"])),
                "z": float(velocity.get("z", self.velocity["z"])),
            }
            self.yaw = float(body.get("yaw", self.yaw))
            self.yaw_rate = float(body.get("yaw_rate", self.yaw_rate))
        return None

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")
        values = message.get("args") if isinstance(message.get("args"), dict) else {}

        def reply(ok, response):
            return {"op": "service_response", "service": service, "id": ident,
                    "result": ok, "values": response}

        if service == "/mavros/cmd/arming":
            if self.fail_arming_service:
                return reply(False, {})
            if self.reject_arming_application:
                return reply(True, {"success": False, "result": 1})  # placeholder rejection
            if values.get("value") is True:
                self.armed = True  # placeholder acknowledgement effect
            elif values.get("value") is False:
                self.disarm_requests += 1  # placeholder counter
                if self.landed_state != _ON_GROUND or self.descending:
                    return reply(True, {"success": False, "result": 1})  # placeholder: PX4 refuses in the air
                self.armed = False  # placeholder
            return reply(True, {"success": True, "result": 0})  # placeholder
        if service == "/mavros/set_mode":
            if self.fail_mode_service:
                return reply(False, {})
            if self.reject_mode_application:
                return reply(True, {"mode_sent": False})  # placeholder rejection
            if values.get("custom_mode") == "OFFBOARD":
                self.mode = "OFFBOARD"  # placeholder acknowledgement effect
            return reply(True, {"mode_sent": True})  # placeholder
        if service == "/mavros/cmd/land":
            if self.fail_land_service:
                return reply(False, {})
            if self.malformed_land_response:
                return reply(True, "not-a-service-values-object")  # placeholder malformed reply
            if self.reject_land_application:
                return reply(True, {"success": False, "result": 1})  # placeholder rejection
            self.landing_requested = True  # placeholder
            if self.landed_state == _ON_GROUND and not self.descending:
                return reply(True, {"success": False, "result": 1})  # placeholder: already on the ground
            if not self.ignore_land:
                self.landed_state = _LANDING  # placeholder: request acknowledged, no touchdown claim yet
                self.mode = "AUTO.LAND"  # placeholder
                self.descending = True
            return reply(True, {"success": True, "result": 0})  # placeholder
        return reply(False, {})

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._subscribe(message.get("topic"), message.get("id"))
        if operation == "publish":
            return self._publish(message)
        if operation == "call_service":
            return self._service(message)
        return None
