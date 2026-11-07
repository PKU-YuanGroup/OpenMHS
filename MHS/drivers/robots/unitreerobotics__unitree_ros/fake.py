"""ROS-free recording fake for the pinned Unitree A1 Gazebo joint topics.

The fake models the wire contract declared in ``driver.py``:

* ``publish`` of ``unitree_legged_msgs/MotorCmd`` on the twelve
  ``/a1_gazebo/<joint>_controller/command`` topics;
* ``subscribe`` to ``/a1_gazebo/lowState/state`` selecting ``motorState``.

It is an analytic contract stand-in, not a recording of captured traffic and
not a physics engine.  It runs no ROS, no Gazebo, no controller loop and no
Unitree code.  Every number below is test data and is marked ``# placeholder``;
none is a device fact and none is copied into a Fact or a Limit.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

#: The servo order of the twelve A1 joints.
_JOINTS = (
    "FR_hip", "FR_thigh", "FR_calf",
    "FL_hip", "FL_thigh", "FL_calf",
    "RR_hip", "RR_thigh", "RR_calf",
    "RL_hip", "RL_thigh", "RL_calf",
)


class FakeUnitreeRos(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.command_topics = {
            f"/a1_gazebo/{joint}_controller/command": index
            for index, joint in enumerate(_JOINTS)
        }
        self.low_state_topic = "/a1_gazebo/lowState/state"
        self.motor_state = [self._motor(index) for index in range(20)]
        self.published = []              # recording helper, no device meaning
        self.drop_low_state = False      # placeholder negative-path switch
        self.close_after_publish = False # placeholder negative-path switch

    @staticmethod
    def _motor(index):
        # Placeholder MotorState values in the pinned servo order.
        return {
            "mode": 10,                  # placeholder
            "q": 0.0,                   # placeholder
            "dq": 0.0,                  # placeholder
            "ddq": 0.0,                 # placeholder
            "tauEst": 0.0,              # placeholder
            "q_raw": 0.0,               # placeholder
            "dq_raw": 0.0,              # placeholder
            "ddq_raw": 0.0,             # placeholder
            "temperature": 25,          # placeholder
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "publish":
            return self._publish(message)
        return None

    def _observation(self, message):
        if message.get("topic") != self.low_state_topic or self.drop_low_state:
            return None
        return {
            "op": "publish",
            "topic": self.low_state_topic,
            "id": message.get("id"),
            "msg": {"motorState": [dict(item) for item in self.motor_state]},
        }

    def _publish(self, message):
        topic = message.get("topic")
        index = self.command_topics.get(topic)
        if index is None:
            return None
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        self.published.append({"topic": topic, "msg": dict(body)})
        # Placeholder echo only: the fake has no controller or physics.  It
        # copies the commanded values into the next LowState observation so a
        # test can see that the publication reached the fake.
        state = self.motor_state[index]
        state["mode"] = int(body.get("mode", 0))          # placeholder
        state["q"] = float(body.get("q", 0.0))            # placeholder
        state["dq"] = float(body.get("dq", 0.0))          # placeholder
        state["tauEst"] = float(body.get("tau", 0.0))     # placeholder
        if self.close_after_publish:
            self.close()
        return None
