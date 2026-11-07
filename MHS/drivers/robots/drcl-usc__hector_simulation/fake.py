"""ROS-free event-driven fake for the pinned HECTOR Gazebo endpoints.

The fake models only the declared wire surface: one
``gazebo_msgs/ModelStates`` subscription on ``/gazebo/model_states``, ten
``unitree_legged_msgs/MotorCmd`` publications on the controller command topics,
and the two services of the companion gazebo_ros API plugin the stop uses
(``/gazebo/pause_physics`` and ``/gazebo/get_physics_properties``).  It does
not serve ``/gazebo/unpause_physics``: the package offers no unpause.  It keeps
a paused flag the way ``World::SetPaused`` does: while it is set no world
update runs, so ``/gazebo/model_states`` stays silent and a MotorCmd is only
stored (the controllers' callbacks still run).  It runs no Gazebo, no physics and no
hector_control loop, and it is not a replay of captured ROS traffic.  Every
state value and the tiny pose nudge below are test data, not device facts, and
are marked ``# placeholder``.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeHectorSimulation(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.model_names = ["ground_plane", "hector_gazebo"]  # placeholder
        self.model_poses = [
            {
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            },
            {
                "position": {"x": 0.0, "y": 0.0, "z": 0.545},  # placeholder
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            },
        ]
        self.model_twists = [
            {
                "linear": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
            },
            {
                "linear": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
            },
        ]
        self.last_commands = {}  # placeholder observation for tests
        self.silent_model_states = False  # placeholder negative-path switch
        # biped.launch starts the world paused (paused defaults to true); the fake starts it running so the
        # contract cases can publish and observe before an e-stop.
        self.paused = False  # placeholder state
        self.service_calls = []  # recording helper, no device meaning
        self.fail_pause = False  # placeholder negative-path switch
        self.fail_readback = False  # placeholder: a non-ODE engine answers false
        self.unpaused_by_other_client = False  # placeholder: the GUI or a client unpaused

    def _model_states_message(self, ident):
        return {
            "op": "publish",
            "topic": "/gazebo/model_states",
            "id": ident,
            "msg": {
                "name": list(self.model_names),  # placeholder
                "pose": [{"position": dict(pose["position"]),
                          "orientation": dict(pose["orientation"])}
                         for pose in self.model_poses],  # placeholder
                "twist": [{"linear": dict(twist["linear"]),
                           "angular": dict(twist["angular"])}
                          for twist in self.model_twists],  # placeholder
            },
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "call_service":
            return self._service(message)
        if operation == "subscribe":
            if message.get("topic") == "/gazebo/model_states":
                if self.silent_model_states or self.paused:
                    return None
                return self._model_states_message(message.get("id"))
            return None
        if operation == "publish":
            topic = message.get("topic")
            if isinstance(topic, str) and topic.endswith("/command"):
                # The controllers' command callbacks run paused or not: the MotorCmd is stored either way.
                self.last_commands[topic] = dict(message.get("msg") or {})  # placeholder
                if not self.paused:
                    self._nudge()
            return None
        return None

    def _nudge(self):
        # Placeholder effect only: nudge the canned robot pose so a subsequent
        # model-state sample is observably different.  This is not a physics or
        # controller model.
        self.model_poses[1]["position"]["x"] = round(
            self.model_poses[1]["position"]["x"] + 0.001, 6)  # placeholder

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")
        self.service_calls.append(service)
        if service == "/gazebo/pause_physics":
            if self.fail_pause:
                return None  # no answer: the binding times out
            self.paused = True
            return self._response(service, ident, True, {})
        if service == "/gazebo/get_physics_properties":
            if self.fail_readback:
                return self._response(service, ident, False, {})
            if self.unpaused_by_other_client:
                self.paused = False
            return self._response(service, ident, True, {
                "time_step": 0.001,  # placeholder
                "pause": self.paused,
                "max_update_rate": 1000.0,  # placeholder
                "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},  # placeholder
                "ode_config": {},  # placeholder (fields not modelled)
                "success": True,
                "status_message": "GetPhysicsProperties: got properties",
            })
        # No unpause. An /gazebo/unpause_physics call is refused and the flag stays set.
        return self._response(service, ident, False, {})

    @staticmethod
    def _response(service, ident, result, values):
        return {"op": "service_response", "service": service, "id": ident, "result": result, "values": values}
