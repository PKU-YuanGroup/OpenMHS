"""ROS-free analytic fake for the pinned Unitree GO1 simulation topic contract.

The fake models the wire contract declared in ``driver.py``:

* subscriptions to ``/odom`` and ``/scan``;
* an advertise and a publish of ``geometry_msgs/msg/Twist`` on ``/cmd_vel``.

It is an analytic contract stand-in, not a recording of captured traffic: it
answers canned observations and keeps the last publication in plain
attributes.  It runs no ROS 2 graph, Gazebo, ray sensor, state machine or
physics.  Every number below is test data and is marked ``# placeholder``;
none is a device fact or a safety limit.

The pinned clone exposes no acknowledged ROS stop, pause or reset service or
action.  The fake also answers the companion gazebo_ros services
``/pause_physics`` and ``/get_model_list`` (the e-stop and its stall read-back):
a paused flag stands for the Gazebo world's, ``get_model_list`` stamps each
answer with a placeholder sim time that advances on every answer unless the
flag is set, and ``/odom`` and ``/scan`` are silent while it is set.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeUnitreeRos2Sim(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder echo state.  Real odometry comes from the Gazebo p3d
        # ground-truth plugin (the estimator's publish call is commented out
        # upstream); the fake echoes only the last published Twist so a
        # publication has an observable contract effect.
        self.last_linear_x = 0.0                 # placeholder
        self.last_linear_y = 0.0                 # placeholder
        self.last_angular_z = 0.0                # placeholder
        self.pose_x = 0.0                        # placeholder
        self.pose_y = 0.0                        # placeholder
        self.pose_z = 0.0                        # placeholder
        self.scan_ranges = [1.0, 2.0, 3.0]       # placeholder
        self.scan_intensities = []               # placeholder
        self.cmd_vel_messages = []               # recording helper, no device meaning
        self.malformed_odom = False              # placeholder negative-path switch
        self.malformed_scan = False              # placeholder negative-path switch
        self.reject_publish = False              # placeholder negative-path switch
        self.paused = False                      # placeholder: the fake starts running
        self.sim_ns = 2_000_000_000              # placeholder sim time, advances 1 ms per answer while running
        self.fail_pause = False                  # placeholder negative-path switch: the pause is not answered
        self.ignore_pause = False                # placeholder negative-path switch: the world keeps running
        self.fail_model_list = False             # placeholder negative-path switch: the read-back fails

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "advertise":
            return None
        if operation == "publish":
            self._record_publish(message)
            return None
        if operation == "call_service":
            return self._service(message)
        return None

    def _service(self, message):
        service = message.get("service")
        reply = {"op": "service_response", "service": service, "id": message.get("id"), "result": True}
        if service == "/pause_physics":
            if self.fail_pause:
                return None  # no answer: the e-stop's request times out
            self.paused = True
            return dict(reply, values={})
        if service == "/get_model_list":
            if self.fail_model_list:
                return dict(reply, result=False, values="get_model_list failed")  # placeholder
            if not self.paused or self.ignore_pause:
                self.sim_ns += 1_000_000  # placeholder: a running world's sim time advances
            stamp = {"sec": self.sim_ns // 1_000_000_000, "nanosec": self.sim_ns % 1_000_000_000}
            return dict(reply, values={"header": {"stamp": stamp, "frame_id": ""},
                                       "model_names": ["ground_plane", "go1"], "success": True})  # placeholder
        return dict(reply, result=False, values={})

    def _observation(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        if self.paused:
            return None  # a paused world runs no p3d plugin or ray sensor
        if topic == "/odom":
            if self.malformed_odom:
                return {"op": "publish", "topic": topic, "id": ident, "msg": "malformed"}  # placeholder
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": {"frame_id": "odom"},  # placeholder
                    "child_frame_id": "base_link",   # placeholder
                    "pose": {
                        "pose": {
                            "position": {"x": self.pose_x, "y": self.pose_y, "z": self.pose_z},  # placeholder
                            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                        }
                    },
                    "twist": {
                        "twist": {
                            "linear": {"x": self.last_linear_x, "y": self.last_linear_y, "z": 0.0},  # placeholder
                            "angular": {"x": 0.0, "y": 0.0, "z": self.last_angular_z},  # placeholder
                        }
                    },
                },
            }
        if topic == "/scan":
            if self.malformed_scan:
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": ident,
                    "msg": {"header": {"frame_id": "laser_link"}},  # placeholder; ranges deliberately absent
                }
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": {"frame_id": "laser_link"},  # placeholder
                    "angle_min": 0.0,                      # placeholder
                    "angle_max": 6.0,                      # placeholder
                    "angle_increment": 1.0,                # placeholder
                    "time_increment": 0.0,                 # placeholder
                    "scan_time": 0.1,                      # placeholder
                    "range_min": 0.1,                      # placeholder
                    "range_max": 10.0,                     # placeholder
                    "ranges": list(self.scan_ranges),      # placeholder
                    "intensities": list(self.scan_intensities),  # placeholder
                },
            }
        return None

    def _record_publish(self, message):
        if self.reject_publish:
            raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder
        topic = message.get("topic")
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        if topic == "/cmd_vel":
            linear = body.get("linear") if isinstance(body.get("linear"), dict) else {}
            angular = body.get("angular") if isinstance(body.get("angular"), dict) else {}
            self.last_linear_x = linear.get("x", 0.0)    # placeholder default
            self.last_linear_y = linear.get("y", 0.0)    # placeholder default
            self.last_angular_z = angular.get("z", 0.0)  # placeholder default
            self.cmd_vel_messages.append(message)
