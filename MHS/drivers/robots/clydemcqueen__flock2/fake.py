"""ROS-free recording fake for the flock2 drone_base topic contract.

The fake models the declared rosbridge endpoints:

* publication on ``/start_mission``, ``/stop_mission`` and ``/solo/cmd_vel``;
* a subscription to the relative ``base_odom`` topic, resolved as
  ``/solo/base_odom`` for the shipped single-drone namespace.

It keeps the last commanded Twist and the mission flag in plain attributes so
the package tests can observe the publication effect.  It runs no ROS, no
Tello firmware, no flight dynamics and no landing sequence.  Every numeric
value below is test data, marked ``# placeholder``; none is a device fact or a
safety limit.

The upstream ``/stop_mission`` callback clears the mission flag, publishes a
zero Twist and may forward an asynchronous land request to an external
service.  This fake models only the local flag and zero Twist; it does not
claim that a drone stopped, hovered or landed.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeFlock2(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.mission = False                  # placeholder state
        self.last_cmd_vel = (0.0, 0.0, 0.0, 0.0)  # placeholder
        self.odom_position = {"x": 0.0, "y": 0.0, "z": 1.0}  # placeholder
        self.odom_orientation = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}  # placeholder
        self.odom_twist = {
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},   # placeholder
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
        }
        self.published_topics = []            # recording helper, no device meaning
        self.stop_requests = 0                # placeholder counter
        self.malformed_odom = False           # placeholder negative-path switch
        self.reject_publish = False           # placeholder negative-path switch

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == "/solo/base_odom":
                if self.malformed_odom:
                    return {"op": "publish", "topic": "/solo/base_odom", "id": message.get("id"),
                            "msg": "malformed"}  # placeholder negative path
                return {"op": "publish", "topic": "/solo/base_odom", "id": message.get("id"),
                        "msg": self._odometry()}
            return None
        if operation == "advertise":
            return None
        if operation == "unadvertise":
            return None
        if operation == "publish":
            if self.reject_publish:
                raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder
            self._record(message)
            return None
        return None

    def _odometry(self):
        return {
            "pose": {"pose": {"position": dict(self.odom_position),
                              "orientation": dict(self.odom_orientation)}},
            "twist": {"twist": {
                "linear": dict(self.odom_twist["linear"]),
                "angular": dict(self.odom_twist["angular"]),
            }},
        }

    def _record(self, message):
        topic = message.get("topic")
        body = message.get("msg")
        self.published_topics.append(topic)
        if topic == "/start_mission":
            self.mission = True
            return
        if topic == "/stop_mission":
            # The real callback clears the mission, publishes a zero Twist
            # through all_stop(), and may forward a land request.  The fake
            # records only the local effects.
            self.stop_requests += 1
            self.mission = False
            self.last_cmd_vel = (0.0, 0.0, 0.0, 0.0)  # placeholder zero command
            return
        if topic == "/solo/cmd_vel" and isinstance(body, dict):
            linear = body.get("linear") if isinstance(body.get("linear"), dict) else {}
            angular = body.get("angular") if isinstance(body.get("angular"), dict) else {}
            self.last_cmd_vel = (
                linear.get("x", 0.0),  # placeholder fallback
                linear.get("y", 0.0),  # placeholder fallback
                linear.get("z", 0.0),  # placeholder fallback
                angular.get("z", 0.0),  # placeholder fallback
            )
