"""ROS-free recording fake for the pinned Care-O-bot Gazebo object tools.

The fake answers the endpoints the driver declares: the acknowledged
get_world_properties, get_model_state and delete_model services, the
set_model_state publication, and the two services of the companion
gazebo_ros API plugin the stop uses (/gazebo/pause_physics and
/gazebo/get_physics_properties).  It does not serve /gazebo/unpause_physics:
the package offers no unpause.  It keeps a paused flag the way World::SetPaused
does; world edits and the two service reads still act and answer while it is
set, as they do on a paused Gazebo world.  It
runs no Gazebo physics and does not replay captured traffic; every number and
status string below is test data, not a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeCobSimulation(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond, **_options)
        # Placeholder scene state: model names are shipped asset names, but
        # the poses and the model list are invented test data.
        self.poses = {
            "robot": {
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},          # placeholder
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            },
            "apple_juice_box": {
                "position": {"x": 1.0, "y": 0.0, "z": 0.0},          # placeholder
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            },
            "basmati_rice": {
                "position": {"x": -1.0, "y": 0.0, "z": 0.0},         # placeholder
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            },
        }
        self.twist = {
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},                 # placeholder
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},                # placeholder
        }
        self.sim_time = 0.0          # placeholder
        self.wall_time = 0.0         # placeholder
        self.fail_world_properties = False   # placeholder negative-path switch
        self.fail_get_model_state = False    # placeholder negative-path switch
        self.fail_delete_service = False     # placeholder negative-path switch
        self.reject_delete_application = False  # placeholder negative-path switch
        # The world's paused flag (world.launch starts it unpaused by default).
        self.paused = False                  # placeholder state
        self.service_calls = []              # recording helper, no device meaning
        self.fail_pause = False              # placeholder negative-path switch
        self.fail_readback = False           # placeholder: a non-ODE engine answers false
        self.unpaused_by_other_client = False  # placeholder: the GUI or a client unpaused

    @staticmethod
    def _service_response(message, *, result, values):
        return {
            "op": "service_response",
            "service": message.get("service"),
            "id": message.get("id"),
            "result": result,
            "values": values,
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation in ("advertise", "unadvertise"):
            return None
        if operation == "publish":
            if message.get("topic") != "/gazebo/set_model_state":
                return None
            body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
            name = body.get("model_name")
            pose = body.get("pose")
            if isinstance(name, str) and isinstance(pose, dict) and name in self.poses:
                self.poses[name] = pose
            return None
        if operation != "call_service":
            return None
        service = message.get("service")
        request = message.get("args") if isinstance(message.get("args"), dict) else {}
        self.service_calls.append(service)
        if service == "/gazebo/pause_physics":
            if self.fail_pause:
                return None  # no answer: the binding times out
            self.paused = True
            return self._service_response(message, result=True, values={})
        if service == "/gazebo/get_physics_properties":
            if self.fail_readback:
                return self._service_response(message, result=False, values={})
            if self.unpaused_by_other_client:
                self.paused = False
            return self._service_response(message, result=True, values={
                "time_step": 0.001,                           # placeholder
                "pause": self.paused,
                "max_update_rate": 1000.0,                    # placeholder
                "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},   # placeholder
                "ode_config": {},                             # placeholder (fields not modelled)
                "success": True,
                "status_message": "GetPhysicsProperties: got properties",
            })
        # No unpause. An /gazebo/unpause_physics call falls through and does not clear the flag.
        if service == "/gazebo/get_world_properties":
            if self.fail_world_properties:
                return self._service_response(message, result=False, values={})
            return self._service_response(message, result=True, values={
                "sim_time": self.sim_time,                    # placeholder
                "wall_time": self.wall_time,                  # placeholder
                "model_names": sorted(self.poses),
                "rendering_enabled": True,                    # placeholder
                "success": True,
                "status_message": "world properties",         # placeholder
            })
        if service == "/gazebo/get_model_state":
            if self.fail_get_model_state:
                return self._service_response(message, result=False, values={})
            name = request.get("model_name")
            pose = self.poses.get(name) if isinstance(name, str) else None
            if pose is None:
                return self._service_response(message, result=True, values={
                    "pose": {"position": {"x": 0.0, "y": 0.0, "z": 0.0},          # placeholder
                             "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}},  # placeholder
                    "twist": self.twist,
                    "success": False,
                    "status_message": "model not found",      # placeholder
                })
            return self._service_response(message, result=True, values={
                "pose": pose,
                "twist": self.twist,
                "success": True,
                "status_message": "model state",              # placeholder
            })
        if service == "/gazebo/delete_model":
            if self.fail_delete_service:
                return self._service_response(message, result=False, values={})
            if self.reject_delete_application:
                return self._service_response(message, result=True, values={
                    "success": False,
                    "status_message": "delete rejected",      # placeholder
                })
            name = request.get("model_name")
            if isinstance(name, str):
                # Placeholder: repeated deletion of an absent model is a no-op
                # success.  gazebo_ros 2.9.3 (the companion source) answers
                # success false, "DeleteModel: model does not exist"
                # (gazebo_ros_api_plugin.cpp:824-830); see the fidelity gaps.
                self.poses.pop(name, None)
            return self._service_response(message, result=True, values={
                "success": True,
                "status_message": "model deleted",            # placeholder
            })
        return self._service_response(message, result=False, values={})
