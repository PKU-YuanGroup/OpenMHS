"""ROS-free contract fake for the pinned TurtleBot3 rosbridge endpoints.

The fake models the upstream wire contract declared in ``driver.py``:

* a ``publish`` of ``geometry_msgs/msg/TwistStamped`` on ``/cmd_vel``;
* a ``call_service`` of ``std_srvs/srv/SetBool`` on ``/motor_power``;
* subscriptions to ``/battery_state``, ``/odom``, ``/joint_states`` and
  ``/sensor_state`` with the message fields the resource reads select.

It is an analytic contract stand-in, not a recording of captured traffic: it
answers canned observations and keeps the torque-enable flag in a plain
attribute.  It runs no ROS, no physics and no TurtleBot3 code.  Every number
below is test data and is marked ``# placeholder``; none is a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeTurtlebot3(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.torque_enabled = True          # placeholder state
        self.last_linear_x = 0.0            # placeholder
        self.last_angular_z = 0.0           # placeholder
        self.motor_power_calls = []         # recording helper, no device meaning
        self.cmd_vel_messages = []          # recording helper, no device meaning
        self.fail_motor_service = False     # placeholder negative-path switch
        self.reject_motor_application = False  # placeholder negative-path switch
        self.malformed_motor_response = False  # placeholder negative-path switch

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "publish":
            self._record_cmd_vel(message)
            return None
        if operation == "call_service":
            return self._service(message)
        return None

    def _observation(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        if topic == "/battery_state":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "voltage": 11.1,        # placeholder
                    "percentage": 0.75,     # placeholder
                    "present": True,        # placeholder
                },
            }
        if topic == "/odom":
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
                    # Placeholder echo of the last published setpoint, not a
                    # measured velocity and not a physics integration.
                    "twist": {
                        "twist": {
                            "linear": {"x": self.last_linear_x, "y": 0.0, "z": 0.0},   # placeholder
                            "angular": {"x": 0.0, "y": 0.0, "z": self.last_angular_z},  # placeholder
                        }
                    },
                },
            }
        if topic == "/joint_states":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "name": ["wheel_left_joint", "wheel_right_joint"],
                    "velocity": [0.0, 0.0],  # placeholder
                },
            }
        if topic == "/sensor_state":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {"torque": self.torque_enabled},
            }
        return None

    def _record_cmd_vel(self, message):
        if message.get("topic") != "/cmd_vel":
            return
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        twist = body.get("twist") if isinstance(body.get("twist"), dict) else {}
        linear = twist.get("linear") if isinstance(twist.get("linear"), dict) else {}
        angular = twist.get("angular") if isinstance(twist.get("angular"), dict) else {}
        self.last_linear_x = linear.get("x", 0.0)    # placeholder default
        self.last_angular_z = angular.get("z", 0.0)  # placeholder default
        self.cmd_vel_messages.append(message)

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")
        if service != "/motor_power":
            return {
                "op": "service_response",
                "service": service,
                "id": ident,
                "result": False,
                "values": {"success": False, "message": "unsupported service"},  # placeholder
            }
        if self.malformed_motor_response:
            return {
                "op": "service_response",
                "service": service,
                "id": ident,
                "result": True,
                "values": "malformed",  # placeholder malformed reply
            }
        if self.fail_motor_service:
            return {
                "op": "service_response",
                "service": service,
                "id": ident,
                "result": False,
                "values": {"success": False, "message": "write failed"},  # placeholder
            }
        args = message.get("args") if isinstance(message.get("args"), dict) else {}
        enabled = bool(args.get("data", False))  # placeholder default
        self.motor_power_calls.append(enabled)
        if self.reject_motor_application:
            return {
                "op": "service_response",
                "service": service,
                "id": ident,
                "result": True,
                "values": {"success": False, "message": "rejected by fake"},  # placeholder
            }
        self.torque_enabled = enabled
        return {
            "op": "service_response",
            "service": service,
            "id": ident,
            "result": True,
            "values": {"success": True, "message": "ok"},  # placeholder
        }
