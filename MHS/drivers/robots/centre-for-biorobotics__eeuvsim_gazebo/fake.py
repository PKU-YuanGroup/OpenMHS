"""ROS-free analytic fake for the eeUVsim UCAT rosbridge contract.

The fake answers the declared subscriptions and records the declared
publications:

* ``/ucat/state`` with ``gazebo_msgs/msg/EntityState``;
* ``/hw/flippers_feedback`` with ``eeuv_sim_interfaces/msg/FlippersFeedbacks``;
* an advertise and a publish of ``eeuv_sim_interfaces/msg/Flippers`` on
  ``/hw/flippers_cmd``;
* an advertise and a publish of ``std_msgs/msg/Bool`` on ``/ucat/reset``.

It is an analytic contract stand-in, not a recording of captured traffic.  It
runs no Fossen dynamics, fin CPG, Gazebo scene or ROS graph.  Every number
below is test data and is marked ``# placeholder``; none is a device fact, a
limit or a trajectory.  The first /ucat/state sample stays the stored state.
Later samples are a placeholder stream: linear velocity 0.4 m/s until every
commanded flipper amplitude is 0, then the twist is zero.  They are wall-clock
spaced so arrival freshness can count them.
"""

import copy
import threading
import time

from mhs.bridge.ros_transport import RecordingRosTransport

_GAP_S = 0.02  # placeholder default. The shipped /ucat/state period is 0.01 s (min_span_ms 19).


class FakeEeuvSimUcat(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.silent_state = False        # placeholder negative-path switch
        self.malformed_state = False     # placeholder negative-path switch
        self.fail_publish = False        # placeholder negative-path switch
        self.fin_commands = []           # recording helper, no device meaning
        self.reset_requests = []         # recording helper, no device meaning
        self.state = {
            "name": "base_link",         # placeholder entity name
            "pose": {
                "position": {"x": 0.0, "y": 0.0, "z": -5.0},  # placeholder position
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder orientation
            },
            "twist": {
                "linear": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder linear velocity
                "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder angular velocity
            },
            "reference_frame": "world",  # placeholder frame name
        }
        self.keep_swimming = False       # placeholder: twist stays nonzero after zero amplitudes
        self.null_twist = False           # placeholder: counted samples carry a null linear.x
        self.gap_s = _GAP_S               # placeholder spacing; tests set the 10 ms publication period
        self._live_cv = threading.Condition()
        self._live = {}
        self._live_started = False
        self.feedback = {
            "flipper_fr": {"angular_pos": 0.0, "angular_vel": 0.0, "angular_acc": 0.0},  # placeholder
            "flipper_br": {"angular_pos": 0.0, "angular_vel": 0.0, "angular_acc": 0.0},  # placeholder
            "flipper_bl": {"angular_pos": 0.0, "angular_vel": 0.0, "angular_acc": 0.0},  # placeholder
            "flipper_fl": {"angular_pos": 0.0, "angular_vel": 0.0, "angular_acc": 0.0},  # placeholder
        }

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
        """Pace ``builder()`` until this subscription id is unsubscribed."""
        if not isinstance(ident, str):
            return
        with self._live_cv:
            self._live[ident] = {"builder": builder, "next_at": time.monotonic() + self.gap_s}
            if not self._live_started:
                self._live_started = True
                threading.Thread(target=self._pump_live, name="mhs-eeuv-samples", daemon=True).start()
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

    def _fins_idle(self):
        if self.keep_swimming or not self.fin_commands:
            return False
        body = self.fin_commands[-1]
        flippers = body.get("flippers") if isinstance(body, dict) else None
        if not isinstance(flippers, list) or len(flippers) < 4:
            return False
        for item in flippers[:4]:
            if not isinstance(item, dict):
                return False
            try:
                if float(item.get("amplitude", 1.0)) != 0.0:
                    return False
            except (TypeError, ValueError):
                return False
        return True

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "advertise":
            return None
        if operation == "publish":
            self._record_publication(message)
            return None
        return None

    def _observation(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        if topic == "/ucat/state":
            if self.silent_state:
                return None
            if self.malformed_state:
                # A transport-valid publish that omits most of the declared state.
                return {"op": "publish", "topic": topic, "id": ident,
                        "msg": {"name": "base_link"}}  # placeholder negative reply
            first = {"op": "publish", "topic": topic, "id": ident, "msg": copy.deepcopy(self.state)}

            def later():
                streamed = copy.deepcopy(self.state)
                if self.null_twist:
                    streamed["twist"]["linear"]["x"] = None  # placeholder invalid field
                elif not self._fins_idle():
                    streamed["twist"]["linear"]["x"] = 0.4  # placeholder m/s while fins are commanded
                return {"op": "publish", "topic": topic, "id": ident, "msg": streamed}

            self._arm(ident, later)
            return first
        if topic == "/hw/flippers_feedback":
            return {"op": "publish", "topic": topic, "id": ident, "msg": dict(self.feedback)}
        return None

    def _record_publication(self, message):
        if self.fail_publish:
            raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder negative path
        topic = message.get("topic")
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        if topic == "/hw/flippers_cmd":
            self.fin_commands.append(body)
            # Placeholder contract effect only: echo each commanded amplitude as
            # a fin angular position so a resource read observes that the
            # publication reached the fake.  This is not fin dynamics.
            flippers = body.get("flippers") if isinstance(body.get("flippers"), list) else []
            for name, item in zip(("flipper_fr", "flipper_br", "flipper_bl", "flipper_fl"), flippers):
                if isinstance(item, dict):
                    self.feedback[name]["angular_pos"] = item.get("amplitude", 0.0)  # placeholder echo
        elif topic == "/ucat/reset":
            self.reset_requests.append(body)
