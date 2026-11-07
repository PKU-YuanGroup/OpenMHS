"""ROS-free recording fake for the swarm_stage_ros target endpoint.

The fake models the pinned wire contract that this package binds: a
``turtlesim/Pose`` publication on ``/robot_0`` consumed by the posctrl
follower.  It records advertise and publish messages only.  Every number and
message below is test data (# placeholder), not a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeSwarmStageRos(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.advertised = []                 # placeholder recording
        self.last_target = None              # placeholder state
        self.publish_count = 0               # placeholder counter
        self.fail_publish = False            # placeholder negative-path switch

    def _respond(self, message):
        operation = message.get("op")
        if operation == "advertise":
            self.advertised.append(
                {"topic": message.get("topic"), "type": message.get("type")}  # placeholder record
            )
            return None
        if operation == "publish":
            if message.get("topic") != "/robot_0":
                return None
            if self.fail_publish:
                raise RuntimeError("placeholder target publication failed")
            pose = message.get("msg")
            if not isinstance(pose, dict):
                raise RuntimeError("placeholder target message is not an object")
            self.last_target = dict(pose)    # placeholder state
            self.publish_count += 1          # placeholder counter
            return None
        return None
