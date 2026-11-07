"""ROS-free canned fake for the ur_gripper_gz world-pause contract.

The fake models the wire shape the driver declares: one
``sensor_msgs/msg/JointState`` publication on ``/joint_states``, the companion
gz-sim world control service ``/world/empty/control``
(``ros_gz_interfaces/srv/ControlWorld``) and the statistics topic
``/world/empty/stats`` (``WorldStatistics``).  It runs no Gazebo physics, no
ros_gz bridge and no controller.  Every number below is test data, not a
device fact.

The world starts unpaused.  A world-control request is answered when it is
queued and applied after the next statistics sample, which is the order
SimulationRunner.Step uses: PublishStats, then ProcessMessages.  Statistics
are published every ``stats_period_s`` while subscribed.  ``/joint_states``
answers on subscribe whether or not the world is paused.
"""

import time

from mhs.bridge.ros_transport import RecordingRosTransport

_WORLD = "/world/empty"
_JOINTS = "/joint_states"
#: Placeholder names.  constants.py names these six strings as JOINT_ORDER; the
#: fake does not claim that a live /joint_states sample carries them.
_JOINT_NAMES = (
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
)


class FakeUrGripperGz(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.joint_names = list(_JOINT_NAMES)          # placeholder
        self.joint_position = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder
        self.joint_velocity = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder
        self.withhold_joint_states = False             # placeholder negative-path switch
        # The companion world (gz-sim through the operator's ros_gz bridges).
        self.paused = False                            # placeholder: the launch passes -r
        self.pending_pause = None                      # queued world control, applied after the next sample
        self.stats_period_s = 0.1                      # placeholder for the companion's 10 messages per second
        self.stats_subscriptions = set()               # recording helper
        self.last_stats_at = 0.0                       # recording helper: the first sample is immediate
        self.iterations = 5000                         # placeholder
        self.controls = []                             # recording helper: world control requests received
        self.fail_control = False                      # placeholder: the call is not answered
        self.reject_control = False                   # placeholder: the bridge answers success false
        self.ignore_pause = False                      # placeholder: the request is queued as success but not applied
        self.silent_stats = False                      # placeholder: no statistics samples

    def _joint_message(self):
        return {
            "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": ""},  # placeholder
            "name": list(self.joint_names),
            "position": list(self.joint_position),
            "velocity": list(self.joint_velocity),
            "effort": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # placeholder, not mapped
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            if topic == _WORLD + "/stats":
                self.stats_subscriptions.add(message.get("id"))
                return None
            if topic == _JOINTS and not self.withhold_joint_states:
                return {"op": "publish", "topic": topic, "id": message.get("id"),
                        "msg": self._joint_message()}
            return None
        if operation == "unsubscribe":
            self.stats_subscriptions.discard(message.get("id"))
            return None
        if operation == "call_service":
            return self._service(message)
        return None

    def _service(self, message):
        service = message.get("service")
        reply = {"op": "service_response", "service": service, "id": message.get("id"), "result": True}
        if service != _WORLD + "/control":
            return dict(reply, result=False, values={})
        request = (message.get("args") or {}).get("world_control") or {}
        self.controls.append(dict(request))
        if self.fail_control:
            return None
        if self.reject_control:
            return dict(reply, values={"success": False})
        pause = bool(request.get("pause"))
        if not (pause and self.ignore_pause):
            self.pending_pause = pause
        return dict(reply, values={"success": True})

    def recv(self, *, timeout_s=None):
        now = time.monotonic()
        if self.stats_subscriptions and not self.silent_stats and now - self.last_stats_at >= self.stats_period_s:
            self.last_stats_at = now
            sample = {
                "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": ""},  # placeholder gz header
                "sim_time": {"sec": 0, "nanosec": 0},                            # placeholder
                "pause_time": {"sec": 0, "nanosec": 0},                          # placeholder
                "real_time": {"sec": 0, "nanosec": 0},                           # placeholder
                "paused": self.paused,
                "iterations": self.iterations,                                   # placeholder
                "model_count": 1,                                                # placeholder
                "real_time_factor": 0.0,                                         # placeholder
            }
            # PublishStats runs before ProcessMessages, so the sample that applies a queued pause
            # still carries the previous flag.  The driver's read-back discards that first sample.
            if self.pending_pause is not None:
                self.paused, self.pending_pause = self.pending_pause, None
            if not self.paused:
                self.iterations += 1  # placeholder
            return {"op": "publish", "topic": _WORLD + "/stats", "msg": sample}
        return super().recv(timeout_s=min(timeout_s or 0.01, 0.01))
