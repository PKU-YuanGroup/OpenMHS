"""ROS-free canned fake for the Hakoniwa infra-sensor publication.

The fake models the one pinned wire contract this package binds: the
``geometry_msgs/msg/Twist`` publication on the absolute
``/TB3RoboAvatar_cmd_pos`` topic created by ``infra_sensor_urg``.  It starts no
ROS node and runs no LiDAR filter, estimator or physics.  Every value and
negative-path switch below is test data, not a device fact or a bound.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeHakoniwaInfraSensor(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder publication values; geometry_msgs/Twist has no header.
        self.linear = {"x": 0.27, "y": 0.02, "z": 0.0}       # placeholder
        self.angular = {"x": 0.0, "y": 0.0, "z": 0.0}       # placeholder

        # Placeholder negative-path switches used by the repository tests.
        self.silent = False          # placeholder: emit no publication
        self.wrong_id = False        # placeholder: emit an unrelated subscription id
        self.fail_subscribe = False  # placeholder: simulate a broken transport link
        self.malformed = None        # placeholder: omit or corrupt one message field

        self.subscriptions = 0       # placeholder counter
        self.last_subscribe = None   # placeholder echo of the received request

    def _message(self):
        message = {
            "linear": dict(self.linear),
            "angular": dict(self.angular),
        }
        if self.malformed == "missing_linear":
            message.pop("linear")
        elif self.malformed == "missing_angular":
            message.pop("angular")
        elif self.malformed == "string_component":
            message["linear"]["x"] = "not-a-number"  # placeholder
        elif self.malformed == "missing_axis":
            message["linear"].pop("y")
        elif self.malformed == "nonfinite_pitch":
            # placeholder: np.arcsin in the node's euler_from_quaternion gives NaN outside -1..1
            message["angular"]["y"] = float("nan")
        elif self.malformed == "not_an_object":
            return []                                # placeholder wire shape
        return message

    def _respond(self, message):
        operation = message.get("op")
        if operation != "subscribe":
            return None
        self.subscriptions += 1
        self.last_subscribe = dict(message)
        if message.get("topic") != "/TB3RoboAvatar_cmd_pos":
            return None
        if self.fail_subscribe:
            raise ConnectionError("simulated /TB3RoboAvatar_cmd_pos subscription failure")  # placeholder
        if self.silent:
            return None
        event = {
            "op": "publish",
            "topic": "/TB3RoboAvatar_cmd_pos",
            "id": message.get("id"),
            "msg": self._message(),
        }
        if self.wrong_id:
            event["id"] = "not-the-subscription-id"  # placeholder
        return event
