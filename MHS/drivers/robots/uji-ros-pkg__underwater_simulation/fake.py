"""ROS-free recording fake for the UWSim topic contract.

The fake models the wire contract declared in ``driver.py``:

* a subscription to ``/uwsim/joint_state`` (sensor_msgs/JointState);
* a subscription to ``/uwsim/g500/range`` (sensor_msgs/Range);
* an advertise and a publish of ``geometry_msgs/TwistStamped`` on
  ``/g500/twist``.

It is an analytic contract stand-in, not a recording of captured traffic: it
answers canned observations and keeps the last publication in plain
attributes.  It runs no ROS graph, UWSim, OSG, Bullet physics or wall-clock
loop.  Every number below is test data and is marked ``# placeholder``; none is
a device fact or a safety limit.

The clone exposes no ROS service or action that could stop the simulator, so
the fake does not model one and the package does not claim an acknowledged
stop.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeUnderwaterSimulation(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder observation state.  The real values come from the
        # operator's UWSim scene; nothing here is a device fact.
        self.joint_names = ["joint1", "joint2"]          # placeholder
        self.joint_positions = [0.0, 0.0]                # placeholder
        self.range_value = 0.0                           # placeholder
        self.last_twist = None                           # recording helper
        self.twist_messages = []                         # recording helper
        self.malformed_joint_state = False               # placeholder negative-path switch
        self.silent_range = False                        # placeholder negative-path switch
        self.reject_publish = False                      # placeholder negative-path switch

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
        if topic == "/uwsim/joint_state":
            if self.malformed_joint_state:
                return {"op": "publish", "topic": topic, "id": ident, "msg": "malformed"}  # placeholder
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": {"frame_id": "world"},                 # placeholder
                    "name": list(self.joint_names),                  # placeholder
                    "position": list(self.joint_positions),          # placeholder
                    "effort": [0.0 for _ in self.joint_names],       # placeholder
                },
            }
        if topic == "/uwsim/g500/range":
            if self.silent_range:
                return None
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": {"frame_id": "world"},                 # placeholder
                    "radiation_type": 0,                              # placeholder (ULTRASOUND)
                    "field_of_view": 0.0,                             # placeholder
                    "min_range": 0.0,                                 # placeholder
                    "max_range": 5.0,                                 # placeholder
                    "range": self.range_value,                        # placeholder
                },
            }
        return None

    def _record_publish(self, message):
        if self.reject_publish:
            raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder
        topic = message.get("topic")
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        if topic == "/g500/twist":
            self.last_twist = body
            self.twist_messages.append(message)
