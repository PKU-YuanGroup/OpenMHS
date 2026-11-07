"""ROS-free scripted contract fake for the sjtu_drone ROS 2 topic surface.

The fake models the declared rosbridge endpoints of the pinned Gazebo model
plugin:

* publications on ``/simple_drone/takeoff``, ``/land``, ``/reset``,
  ``/posctrl``, ``/dronevel_mode`` and ``/cmd_vel``;
* subscriptions to ``/simple_drone/state``, ``/gt_pose`` and ``/cmd_mode``.

It keeps the last command and a placeholder state label so the package tests
can observe the publication effect.  Like the plugin's Reset(), neither the
``reset`` publication nor the acknowledged ``/reset_world`` call changes the
state label or the stored command.  It runs no ROS, no Gazebo, no PID
controller and no flight dynamics.  It also answers the companion gazebo_ros
services ``/pause_physics`` and ``/get_model_list`` (the e-stop and its stall
read-back): a paused flag stands for the Gazebo world's, ``get_model_list``
stamps each answer with a placeholder sim time that advances on every answer
unless the flag is set, and the plugin's outputs (state, gt_pose) are silent
while it is set.  It is a scripted stand-in, not captured traffic.  Every number below is test data, marked ``# placeholder``; none is
a device fact, measurement or safety limit.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_TAKEOFF = "/simple_drone/takeoff"
_LAND = "/simple_drone/land"
_RESET = "/simple_drone/reset"
_POSCTRL = "/simple_drone/posctrl"
_VEL_MODE = "/simple_drone/dronevel_mode"
_CMD_VEL = "/simple_drone/cmd_vel"
_STATE = "/simple_drone/state"
_POSE = "/simple_drone/gt_pose"
_MODE = "/simple_drone/cmd_mode"


class FakeSjtuDrone(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # The constants and values below are placeholders for the plugin's
        # LANDED_MODEL / FLYING_MODEL / TAKINGOFF_MODEL / LANDING_MODEL labels.
        self.state_value = 0                      # placeholder: LANDED_MODEL
        self.mode_value = "position"              # placeholder: no default publish in the clone
        self.position_control = False             # placeholder
        self.velocity_mode = False                # placeholder
        self.last_cmd_vel = {                     # placeholder zeros
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
        }
        self.pose_value = {                       # placeholder zeros
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        }
        self.malformed_state = False               # placeholder negative-path switch
        self.reject_publish = False                # placeholder negative-path switch
        self.fail_reset_world = False              # placeholder negative-path switch
        self.published_topics = []                 # recording helper, no device meaning
        self.world_resets = 0                      # recording helper, no device meaning
        self.paused = False                        # placeholder: the fake starts running
        self.sim_ns = 4_000_000_000                # placeholder sim time, advances 1 ms per answer while running
        self.fail_pause = False                    # placeholder negative-path switch: the pause is not answered
        self.ignore_pause = False                  # placeholder negative-path switch: the world keeps running
        self.fail_model_list = False               # placeholder negative-path switch: the read-back fails

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            if self.paused and topic in (_STATE, _POSE):
                return None  # the plugin publishes state and gt_pose only from its world update
            if topic == _STATE:
                if self.malformed_state:
                    return {"op": "publish", "topic": topic, "id": message.get("id"),
                            "msg": "malformed"}      # placeholder negative path
                return {"op": "publish", "topic": topic, "id": message.get("id"),
                        "msg": {"data": self.state_value}}
            if topic == _POSE:
                return {"op": "publish", "topic": topic, "id": message.get("id"),
                        "msg": _copy_pose(self.pose_value)}
            if topic == _MODE:
                return {"op": "publish", "topic": topic, "id": message.get("id"),
                        "msg": {"data": self.mode_value}}
            if topic == _CMD_VEL:
                return {"op": "publish", "topic": topic, "id": message.get("id"),
                        "msg": {
                            "linear": dict(self.last_cmd_vel["linear"]),
                            "angular": dict(self.last_cmd_vel["angular"]),
                        }}
            return None
        if operation in ("advertise", "unadvertise"):
            return None
        if operation == "publish":
            if self.reject_publish:
                raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder
            self._record(message)
            return None
        if operation == "call_service":
            if message.get("service") in ("/pause_physics", "/get_model_list"):
                return self._world_service(message)
            if message.get("service") == "/reset_world":
                if self.fail_reset_world:
                    return {"op": "service_response", "service": "/reset_world",
                            "id": message.get("id"), "result": False, "values": {}}
                self._reset_world()
                return {"op": "service_response", "service": "/reset_world",
                        "id": message.get("id"), "result": True, "values": {}}
            return {"op": "service_response", "service": message.get("service"),
                    "id": message.get("id"), "result": False, "values": {}}
        return None

    def _world_service(self, message):
        service = message.get("service")
        reply = {"op": "service_response", "service": service, "id": message.get("id"), "result": True}
        if service == "/pause_physics":
            if self.fail_pause:
                return None  # no answer: the e-stop's request times out
            self.paused = True
            return dict(reply, values={})
        if self.fail_model_list:
            return dict(reply, result=False, values="get_model_list failed")  # placeholder
        if not self.paused or self.ignore_pause:
            self.sim_ns += 1_000_000  # placeholder: a running world's sim time advances
        stamp = {"sec": self.sim_ns // 1_000_000_000, "nanosec": self.sim_ns % 1_000_000_000}
        return dict(reply, values={"header": {"stamp": stamp, "frame_id": ""},
                                   "model_names": ["ground_plane", "sjtu_drone"], "success": True})  # placeholder

    def _reset_world(self):
        # Model review 2026-11-04: the world reset is gazebo_ros code outside the
        # clone; the plugin's Reset() (plugin_drone_private.cpp:36-56) assigns
        # neither navi_state nor cmd_vel nor the mode flags, so the fake keeps its
        # state label, stored command and modes.  It only counts the call.
        self.world_resets += 1                    # recording helper, no device meaning

    def _record(self, message):
        topic = message.get("topic")
        body = message.get("msg")
        self.published_topics.append(topic)
        if topic == _TAKEOFF:
            if self.state_value == 0:             # placeholder LANDED_MODEL
                self.state_value = 2              # placeholder TAKINGOFF_MODEL
            return
        if topic == _LAND:
            if self.state_value in (1, 2):        # placeholder FLYING/TAKINGOFF
                self.state_value = 3              # placeholder LANDING_MODEL
            return
        if topic == _RESET:
            # ResetCallback -> Reset() resets PID controllers, force and torque but
            # not navi_state, cmd_vel or the mode flags (model review 2026-11-04).
            return
        if topic == _POSCTRL and isinstance(body, dict):
            self.position_control = bool(body.get("data", False))  # placeholder default
            return
        if topic == _VEL_MODE and isinstance(body, dict):
            self.velocity_mode = bool(body.get("data", False))     # placeholder default
            self.mode_value = "velocity" if self.velocity_mode else "position"
            return
        if topic == _CMD_VEL and isinstance(body, dict):
            linear = body.get("linear") if isinstance(body.get("linear"), dict) else {}
            angular = body.get("angular") if isinstance(body.get("angular"), dict) else {}
            self.last_cmd_vel = {
                "linear": {axis: float(linear.get(axis, 0.0)) for axis in ("x", "y", "z")},
                "angular": {axis: float(angular.get(axis, 0.0)) for axis in ("x", "y", "z")},
            }
            return


def _copy_pose(pose):
    return {
        "position": dict(pose["position"]),
        "orientation": dict(pose["orientation"]),
    }
