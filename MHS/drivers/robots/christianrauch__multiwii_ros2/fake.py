"""ROS-free recording fake for the MultiWii ROS 2 topic surface.

The fake models only the pinned wire contract: the node's relative
``state``, ``rc/in``, ``motors``, ``local_position/pose``,
``global_position/rel_alt`` and ``imu/data_raw`` publishers, and the
``rc/override`` and ``rc/override/raw`` subscriptions.  It opens no socket,
starts no ROS node and runs no flight dynamics.  Every stored value and
canned reply below is test data, not a device fact or a safe envelope.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeMultiwiiRos2(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Canned observations.  The node leaves most message fields at their
        # defaults; the driver reads only the paths declared in driver.py.
        self.armed = False                                # placeholder
        self.rc_channels = [1500, 1500, 1500, 1000,       # placeholder
                            1000, 1000, 1000, 1000]       # placeholder
        self.motor_channels = [1000, 1000, 1000, 1000]    # placeholder
        self.altitude_m = 0.0                             # placeholder
        self.acceleration = {"x": 0.0, "y": 0.0, "z": 9.80665}  # placeholder
        self.angular_velocity = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder
        self.orientation = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}  # placeholder

        # Negative-path switches used by the repository tests.
        self.silent_topics = set()   # placeholder: a topic that emits no sample
        self.wrong_id_topics = set()  # placeholder: an unrelated event id
        self.fail_publish = False     # placeholder: simulate a broken link

        # Observations of the outbound override publications.
        self.override_publishes = 0   # placeholder counter
        self.raw_override_publishes = 0  # placeholder counter
        self.last_aert_channels = []  # placeholder
        self.last_raw_channels = []   # placeholder

    def _header(self):
        return {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": ""}  # placeholder

    def _state_message(self):
        return {
            "header": self._header(),
            "connected": False,       # placeholder
            "armed": bool(self.armed),
            "guided": False,          # placeholder
            "manual_input": False,    # placeholder
            "mode": "",               # placeholder
            "system_status": 0,       # placeholder
        }

    def _rc_message(self):
        return {"header": self._header(), "channels": list(self.rc_channels)}

    def _motor_message(self):
        return {"header": self._header(), "channels": list(self.motor_channels)}

    def _pose_message(self):
        return {
            "header": self._header(),
            "pose": {
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                "orientation": dict(self.orientation),
            },
        }

    def _altitude_message(self):
        return {"data": float(self.altitude_m)}

    def _imu_message(self):
        return {
            "header": self._header(),
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            "linear_acceleration": dict(self.acceleration),
            "angular_velocity": dict(self.angular_velocity),
        }

    def _subscribe(self, message):
        topic = message.get("topic")
        if topic in self.silent_topics:
            return None
        messages = {
            "/state": self._state_message,
            "/rc/in": self._rc_message,
            "/motors": self._motor_message,
            "/local_position/pose": self._pose_message,
            "/global_position/rel_alt": self._altitude_message,
            "/imu/data_raw": self._imu_message,
        }
        factory = messages.get(topic)
        if factory is None:
            return None
        event = {"op": "publish", "topic": topic, "id": message.get("id"), "msg": factory()}
        if topic in self.wrong_id_topics:
            event["id"] = "not-the-subscription-id"  # placeholder
        return event

    def _publish(self, message):
        topic = message.get("topic")
        body = message.get("msg")
        channels = body.get("channels") if isinstance(body, dict) else None
        if topic == "/rc/override":
            if self.fail_publish:
                raise ConnectionError("simulated rc/override link failure")  # placeholder
            self.override_publishes += 1
            if isinstance(channels, list):
                self.last_aert_channels = list(channels)
            return None
        if topic == "/rc/override/raw":
            if self.fail_publish:
                raise ConnectionError("simulated rc/override/raw link failure")  # placeholder
            self.raw_override_publishes += 1
            if isinstance(channels, list):
                self.last_raw_channels = list(channels)
            return None
        return None

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._subscribe(message)
        if operation == "publish":
            return self._publish(message)
        # advertise, unadvertise and unsubscribe need no fake reply.
        return None
