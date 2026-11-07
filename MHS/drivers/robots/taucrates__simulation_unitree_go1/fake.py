"""ROS-free analytic fake for the declared taucrates Go1 rosbridge surface.

The fake models only the wire contract declared in ``driver.py``:

* an advertise and a publish of ``geometry_msgs/Twist`` on ``/cmd_vel``;
* a subscription to ``sensor_msgs/LaserScan`` on ``/scan``.

It is an analytic contract stand-in, not a recording of captured traffic.  It
runs no ROS graph, Gazebo world, CHAMP controller, ray sensor, camera, state
estimator or physics step.  Every number below is test data and is marked
``# placeholder``; none is a device fact, a sourced limit or a safety claim.

The pinned source exposes no acknowledged ROS stop, pause or reset endpoint,
so the fake does not model one and the package does not claim a safe state.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeSimulationUnitreeGo1(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder echo state; the real robot state comes from Gazebo and
        # the external CHAMP controller, not from this fake.
        self.last_linear_x = 0.0              # placeholder
        self.last_linear_y = 0.0              # placeholder
        self.last_angular_z = 0.0             # placeholder
        self.cmd_vel_messages = []            # recording helper, no device meaning
        self.scan_ranges = [1.0, 2.0, 3.0]    # placeholder
        self.scan_intensities = []             # placeholder
        self.silent_scan = False               # placeholder negative-path switch
        self.malformed_scan = False            # placeholder negative-path switch
        self.reject_publish = False            # placeholder negative-path switch

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "advertise":
            return None
        if operation == "publish":
            self._record_publish(message)
            return None
        return None

    def _observation(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        if topic != "/scan" or self.silent_scan:
            return None
        if self.malformed_scan:
            # Missing header and range fields; the bridge must not report a
            # completed observation from this reply.
            return {"op": "publish", "topic": topic, "id": ident,
                    "msg": {"ranges": "not-an-array"}}  # placeholder malformed body
        return {
            "op": "publish",
            "topic": topic,
            "id": ident,
            "msg": {
                # ROS 1 std_msgs/Header: seq, stamp (secs, nsecs), frame_id.
                "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": "base_scan"},  # placeholder
                "angle_min": -1.0,                     # placeholder
                "angle_max": 1.0,                      # placeholder
                "angle_increment": 1.0,                # placeholder
                "time_increment": 0.0,                 # placeholder
                "scan_time": 0.1,                      # placeholder
                "range_min": 0.1,                      # placeholder
                "range_max": 10.0,                     # placeholder
                "ranges": list(self.scan_ranges),      # placeholder
                "intensities": list(self.scan_intensities),  # placeholder
            },
        }

    def _record_publish(self, message):
        if self.reject_publish:
            raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder
        topic = message.get("topic")
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        if topic == "/cmd_vel":
            linear = body.get("linear") if isinstance(body.get("linear"), dict) else {}
            angular = body.get("angular") if isinstance(body.get("angular"), dict) else {}
            self.last_linear_x = linear.get("x", 0.0)      # placeholder default
            self.last_linear_y = linear.get("y", 0.0)      # placeholder default
            self.last_angular_z = angular.get("z", 0.0)    # placeholder default
            self.cmd_vel_messages.append(message)
