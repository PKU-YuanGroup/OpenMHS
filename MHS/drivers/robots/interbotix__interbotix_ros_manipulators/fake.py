"""ROS-free recording fake for the Interbotix X-Series wire interface.

The fake answers only the two endpoints declared in driver.py: a
``commands/joint_group`` publication and a ``joint_states`` subscription.
There is no motor server, no arm physics and no stop acknowledgement.  Every
number below is test data, not a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeWx250s(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # placeholder joint sample: seven names and seven raw positions, not a device fact
        self.joint_names = ["waist", "shoulder", "elbow", "forearm_roll", "wrist_angle",
                            "wrist_rotate", "gripper"]  # placeholder
        self.joint_positions = [0.0, -0.2, 0.3, 0.0, 0.0, 0.0, 0.0]  # placeholder
        self.silent_joint_states = False   # placeholder negative-path switch
        self.malformed_joint_states = False  # placeholder negative-path switch
        self.last_group_command = None     # placeholder

    def _respond(self, message):
        operation = message.get("op")
        topic = message.get("topic")
        if operation == "subscribe" and topic == "/wx250s/joint_states":
            if self.silent_joint_states:
                return None
            sample = {
                "name": list(self.joint_names),  # placeholder
                "position": list(self.joint_positions),  # placeholder
            }
            if self.malformed_joint_states:
                sample.pop("position", None)
            return {
                "op": "publish",
                "topic": topic,
                "id": message.get("id"),
                "msg": sample,
            }
        if operation == "publish" and topic == "/wx250s/commands/joint_group":
            self.last_group_command = dict(message.get("msg") or {})  # placeholder
            return None
        if operation == "call_service":
            service = message.get("service")
            return {
                "op": "service_response",
                "service": service,
                "id": message.get("id"),
                "result": False,
                "values": "no service endpoint is declared",  # placeholder
            }
        return None
