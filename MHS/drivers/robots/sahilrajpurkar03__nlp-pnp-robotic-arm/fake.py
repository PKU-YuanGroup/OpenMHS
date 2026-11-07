"""ROS-free analytic fake for the pinned SPARC pick-and-place topic contract.

The fake models only the two wire endpoints declared in ``driver.py``:

* a fresh subscription sample on ``/pick_place_status``
  (``std_msgs/msg/String``);
* an advertise and a publish on ``/target_point``
  (``std_msgs/msg/Float64MultiArray``).

It is an analytic contract stand-in, not a recording of captured traffic: it
answers a canned status and echoes the last target publication.  It runs no
ROS 2 graph, YOLOv8 detector, MoveIt move_group, controller, Isaac Sim scene
or UR5 physics.  Every number and status below is test data and is marked
``# placeholder``; none is a device fact, a sourced limit or a safety claim.

The clone exposes no ROS service or action that stops the upstream
pick-and-place sequence, so the fake models none and the package does not
claim an acknowledged stop.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeNlpPnpRoboticArm(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder status echo.  The real C++ node publishes current_status
        # every 200 ms from a timer (ur5_pick_place_cpp_r.cpp:394-400).
        self.status = "IDLE"  # placeholder
        self.last_target = [0.0, 0.0, 0.0, 0.0]  # placeholder
        self.published_targets = []  # recording helper, no device meaning
        self.reject_publish = False  # placeholder negative-path switch
        self.malformed_status = False  # placeholder negative-path switch
        self.silent_status = False  # placeholder negative-path switch
        # Model review (2026-11-05): in a real graph only clients publish /target_point, so a fresh
        # subscription is normally answered by nobody; this switch models that silence.
        self.silent_target = False  # placeholder negative-path switch

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
        if topic == "/target_point":
            if self.silent_target:
                return None
            return {"op": "publish", "topic": topic, "id": ident,
                    "msg": {"data": list(self.last_target)}}
        if topic != "/pick_place_status":
            return None
        if self.silent_status:
            return None
        if self.malformed_status:
            # A String message without data: the declared path cannot resolve.
            return {"op": "publish", "topic": topic, "id": ident,
                    "msg": {"not_data": "malformed-status-placeholder"}}  # placeholder
        return {"op": "publish", "topic": topic, "id": ident, "msg": {"data": self.status}}

    def _record_publish(self, message):
        if self.reject_publish:
            raise RuntimeError("fake rosbridge transport rejected the target publication")  # placeholder
        topic = message.get("topic")
        if topic != "/target_point":
            return
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        data = body.get("data") if isinstance(body.get("data"), list) else []
        self.published_targets.append(list(data))
        self.last_target = list(data)
        # The real node publishes ACTIVE when executePickAndPlace starts
        # (ur5_pick_place_cpp_r.cpp:297-298); this is a placeholder echo, not
        # evidence that this fake or the upstream node planned or moved.
        self.status = "ACTIVE"  # placeholder
