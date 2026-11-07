"""ROS-free recording fake for the pinned ME5413 Gazebo world contract.

The fake models the rosbridge wire contract declared in ``driver.py``:

* publications on ``/rviz_panel/respawn_objects`` and ``/cmd_unblock``;
* subscriptions to ``/box_odom`` and ``/gazebo/ground_truth/box_markers``;
* the acknowledged ``/gazebo/delete_model`` service used by the plugin's delete
  path;
* the two services of the companion gazebo_ros API plugin the stop uses:
  ``/gazebo/pause_physics`` and ``/gazebo/get_physics_properties``.  It does
  not serve ``/gazebo/unpause_physics``: the package offers no unpause.  The
  fake keeps a paused flag the way ``World::SetPaused`` does: while it is set
  no model update runs, so ``/box_odom`` and the marker topic stay silent,
  while world edits (deletes) still apply.

It is an analytic contract stand-in, not a recording of captured traffic: it
answers canned observations and keeps the last publication/deletion in plain
attributes.  It runs no ROS, Gazebo physics, object spawner or plugin callback.
Every number below is test data and is marked ``# placeholder``; none is a
device fact or a safety limit.

The plugin's multi-step respawn and ten-second unblock callbacks are not
modelled, and deleting ``planar_box`` does not prove that a callback already
running in the live plugin has finished.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeMe5413FinalProject(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder scene state.  The live world starts it from the launch
        # file and the plugin's own callbacks, not from this fake.
        self.moving_obstacle_present = True   # placeholder
        self.objects_present = False          # placeholder
        self.exit_open = False                # placeholder
        self.last_respawn_command = None      # placeholder
        self.deleted_models = []              # recording helper, no device meaning
        self.published_topics = []            # recording helper, no device meaning
        self.fail_delete_service = False      # placeholder negative-path switch
        self.fail_delete_application = False  # placeholder negative-path switch
        # The world's paused flag (world.launch starts it unpaused).
        self.paused = False                   # placeholder state
        self.service_calls = []               # recording helper, no device meaning
        self.fail_pause = False               # placeholder negative-path switch
        self.fail_readback = False            # placeholder: a non-ODE engine answers false
        self.unpaused_by_other_client = False  # placeholder: the GUI or a client unpaused

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "advertise":
            return None
        if operation == "publish":
            self._record_publish(message)
            return None
        if operation == "call_service":
            return self._service(message)
        return None

    def _observation(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        if self.paused:
            return None  # no model update and no simulated-time timer while paused
        if topic == "/box_odom":
            if not self.moving_obstacle_present:
                # The live planar_move plugin stops publishing once the model
                # is deleted; a subscription then times out.
                return None
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "pose": {
                        "pose": {
                            "position": {"x": 6.0, "y": 0.0, "z": 3.5},             # placeholder
                            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                        }
                    },
                    "twist": {
                        "twist": {
                            "linear": {"x": 0.0, "y": 2.0, "z": 0.0},  # placeholder
                            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                        }
                    },
                },
            }
        if topic == "/gazebo/ground_truth/box_markers":
            # The 2526 plugin clears box_markers_msg_ and leaves the marker
            # construction commented out, so the published array is empty.
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {"markers": []},
            }
        return None

    def _record_publish(self, message):
        topic = message.get("topic")
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        self.published_topics.append(topic)
        if topic == "/rviz_panel/respawn_objects":
            self.last_respawn_command = body.get("data")  # placeholder echo
            if body.get("data") == 0:
                self.objects_present = False
            elif body.get("data") == 1:
                self.objects_present = True
        elif topic == "/cmd_unblock":
            if body.get("data") is True:
                self.exit_open = True  # placeholder one-time latch

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")
        self.service_calls.append(service)
        if service == "/gazebo/pause_physics":
            if self.fail_pause:
                return None  # no answer: the binding times out
            self.paused = True
            return {"op": "service_response", "service": service, "id": ident, "result": True, "values": {}}
        if service == "/gazebo/get_physics_properties":
            if self.fail_readback:
                return {"op": "service_response", "service": service, "id": ident, "result": False, "values": {}}
            if self.unpaused_by_other_client:
                self.paused = False
            return {"op": "service_response", "service": service, "id": ident, "result": True, "values": {
                "time_step": 0.001,                          # placeholder
                "pause": self.paused,
                "max_update_rate": 1000.0,                   # placeholder
                "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},  # placeholder
                "ode_config": {},                            # placeholder (fields not modelled)
                "success": True,
                "status_message": "GetPhysicsProperties: got properties",
            }}
        # No unpause. An /gazebo/unpause_physics call is refused below and the flag stays set.
        if service != "/gazebo/delete_model":
            return {"op": "service_response", "service": service, "id": ident,
                    "result": False, "values": {}}
        if self.fail_delete_service:
            return {"op": "service_response", "service": service, "id": ident,
                    "result": False, "values": {}}
        request = message.get("args") if isinstance(message.get("args"), dict) else {}
        model_name = request.get("model_name")
        if not isinstance(model_name, str):
            model_name = ""  # placeholder
        if self.fail_delete_application:
            return {"op": "service_response", "service": service, "id": ident,
                    "result": True,
                    "values": {"success": False, "status_message": "delete refused"}}  # placeholder
        if model_name == "planar_box" and not self.moving_obstacle_present:
            # gazebo_ros DeleteModel reports failure for an absent model
            # (companion gazebo_ros_api_plugin.cpp:824-830).
            return {"op": "service_response", "service": service, "id": ident,
                    "result": True,
                    "values": {"success": False,
                               "status_message": "model not found"}}  # placeholder
        if model_name == "planar_box":
            self.moving_obstacle_present = False
        self.deleted_models.append(model_name)
        return {"op": "service_response", "service": service, "id": ident,
                "result": True,
                "values": {"success": True,
                           "status_message": "deleted " + model_name}}  # placeholder echo
