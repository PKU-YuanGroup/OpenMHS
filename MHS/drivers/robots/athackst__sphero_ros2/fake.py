"""ROS-free recording fake for the pinned Sphero ROS 2 topic contract.

The fake models the upstream wire contract declared in ``driver.py``:

* subscriptions to ``/odom``, ``/imu``, ``/collision`` and ``/diagnostics``;
* publications on ``/cmd_vel``, ``/set_color``, ``/set_back_led``,
  ``/disable_stabilization``, ``/set_heading`` and ``/set_angular_velocity``.

It is an analytic contract stand-in, not a recording of captured traffic: it
answers canned observations and keeps the last publication in plain
attributes.  It runs no ROS, no Bluetooth, no Sphero firmware and no physics.
Every number below is test data and is marked ``# placeholder``; none is a
device fact or a safety limit.

The node's own 0.6 s no-command roll-zero timer and its shutdown-only
``stop()`` are not ROS endpoints, so the fake does not model them and the
package does not claim them as an acknowledged stop.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeSpheroRos2(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder echo state.  A live odometry message is produced by the
        # Sphero firmware and decoded by the BLE driver; this fake only echoes
        # the last publication so a command has an observable contract effect.
        self.last_linear_x = 0.0          # placeholder
        self.last_linear_y = 0.0          # placeholder
        self.last_color = (0.0, 0.0, 0.0)  # placeholder
        self.last_back_led = 0.0          # placeholder
        self.stabilization_disabled = False  # placeholder
        self.last_heading_rad = 0.0       # placeholder
        self.last_angular_velocity_rad = 0.0  # placeholder
        self.cmd_vel_messages = []        # recording helper, no device meaning
        self.published_topics = []        # recording helper, no device meaning
        self.reject_publish = False       # placeholder negative-path switch
        self.malformed_odom = False       # placeholder negative-path switch

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
        if topic == "/odom":
            if self.malformed_odom:
                return {"op": "publish", "topic": topic, "id": ident, "msg": "malformed"}  # placeholder
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "pose": {
                        "pose": {
                            "position": {"x": 0.0, "y": 0.0, "z": 0.0},          # placeholder
                            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                        }
                    },
                    # Placeholder echo of the last publication, not measured motion.
                    "twist": {
                        "twist": {
                            "linear": {"x": self.last_linear_x, "y": self.last_linear_y, "z": 0.0},  # placeholder
                            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                        }
                    },
                },
            }
        if topic == "/imu":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                    "linear_acceleration": {"x": 0.0, "y": 0.0, "z": 9.8},    # placeholder
                    "angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},       # placeholder
                },
            }
        if topic == "/collision":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "x": 0, "y": 0, "z": 0, "axis": 0,                       # placeholder
                    "x_magnitude": 0, "y_magnitude": 0,                     # placeholder
                    "speed": 0, "timestamp": 0,                             # placeholder
                },
            }
        if topic == "/diagnostics":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "status": [
                        {"name": "Battery Status", "level": 0, "message": "Battery OK"},  # placeholder
                    ]
                },
            }
        return None

    def _record_publish(self, message):
        if self.reject_publish:
            raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder
        topic = message.get("topic")
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        self.published_topics.append(topic)
        if topic == "/cmd_vel":
            linear = body.get("linear") if isinstance(body.get("linear"), dict) else {}
            self.last_linear_x = linear.get("x", 0.0)    # placeholder default
            self.last_linear_y = linear.get("y", 0.0)    # placeholder default
            self.cmd_vel_messages.append(message)
        elif topic == "/set_color":
            self.last_color = (
                body.get("r", 0.0),   # placeholder default
                body.get("g", 0.0),   # placeholder default
                body.get("b", 0.0),   # placeholder default
            )
        elif topic == "/set_back_led":
            self.last_back_led = body.get("data", 0.0)     # placeholder default
        elif topic == "/disable_stabilization":
            self.stabilization_disabled = bool(body.get("data", False))  # placeholder default
        elif topic == "/set_heading":
            self.last_heading_rad = body.get("data", 0.0)  # placeholder default
        elif topic == "/set_angular_velocity":
            self.last_angular_velocity_rad = body.get("data", 0.0)  # placeholder default
