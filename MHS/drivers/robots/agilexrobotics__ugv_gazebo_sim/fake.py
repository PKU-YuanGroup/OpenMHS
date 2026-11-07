"""ROS-free analytic fake for the Scout V2 empty-world wire contract.

The fake answers the absolute ``/cmd_vel`` publication (geometry_msgs/Twist)
and the companion gazebo_ros services ``/gazebo/pause_physics`` and
``/gazebo/get_physics_properties``.  A paused flag stands for the Gazebo
world's: the pause sets it and the read-back reports it.  A Twist publication
is recorded and is not applied to a wheel.  The fake implements no unpause.

It runs no Gazebo, ros_control controller or Scout physics, and it is not a
replay of captured ROS traffic.  Every number below is placeholder test data,
not a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeScoutV2EmptyWorld(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.received = []                     # placeholder recorded Twist components
        self.paused = False                    # placeholder: the fake starts running
        self.fail_pause = False                # placeholder negative-path switch: the pause is not answered
        self.fail_readback = False             # placeholder negative-path switch: a non-ODE engine
        self.ignore_pause = False              # placeholder negative-path switch: the read-back says not paused

    def _respond(self, message):
        operation = message.get("op")
        if operation == "publish":
            if message.get("topic") == "/cmd_vel":
                body = message.get("msg") or {}
                linear = body.get("linear") or {}
                angular = body.get("angular") or {}
                self.received.append({"linear_x": linear.get("x"), "angular_z": angular.get("z")})
            return None
        if operation == "call_service":
            service = message.get("service")
            if service == "/gazebo/pause_physics":
                if self.fail_pause:
                    return None
                self.paused = True
                return {"op": "service_response", "service": service, "id": message.get("id"), "result": True,
                        "values": {}}
            if service == "/gazebo/get_physics_properties":
                if self.fail_readback:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": False, "values": "get_physics_properties not supported"}
                return {"op": "service_response", "service": service, "id": message.get("id"), "result": True,
                        "values": {"time_step": 0.001, "pause": self.paused and not self.ignore_pause,
                                   "max_update_rate": 1000.0, "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},
                                   "ode_config": {}, "success": True, "status_message": "placeholder"}}
            # No unpause.  Any other service, including /gazebo/unpause_physics, is refused.
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": False, "values": {}}
        return None
