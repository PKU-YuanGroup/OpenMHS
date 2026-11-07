"""ROS-free canned fake for the warehouse_simulation_toolkit command contract.

The fake models the only in-clone command endpoint, the teleop's
geometry_msgs/Twist publication on /cmd_vel, and the companion gazebo_ros
services ``/gazebo/pause_physics`` and ``/gazebo/get_physics_properties`` (the
e-stop and its read-back).  It records the outbound advertise and publish
messages and stores the most recent Twist, as the differential-drive plugin
stores its last command; a paused flag stands for the Gazebo world's: the
pause sets it, the read-back reports it, and a Twist received while it is set
is stored but drives no wheel.  It runs no Gazebo physics, differential-drive
controller, laser, IMU, gmapping or move_base.

No device number is invented here.  The initial record state is an empty
placeholder, not a fact or a limit; the GetPhysicsProperties numbers are
placeholders.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeWarehouseSimulationToolkit(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.last_cmd_vel = None       # placeholder: most recent recorded Twist (the plugin's stored command)
        self.driving_cmd_vel = None    # placeholder: the Twist a running world would turn into wheel speeds
        self.publish_count = 0         # placeholder: recorded publication count
        self.paused = False            # placeholder: the fake world starts running
        self.fail_pause = False        # placeholder negative-path switch: the pause is not answered
        self.fail_readback = False     # placeholder negative-path switch: a non-ODE engine
        self.ignore_pause = False      # placeholder negative-path switch: another client unpaused

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")
        if service == "/gazebo/pause_physics":
            if self.fail_pause:
                return None  # no answer: the e-stop's request times out
            self.paused = True
            return {"op": "service_response", "service": service, "id": ident, "result": True, "values": {}}
        if service == "/gazebo/get_physics_properties":
            if self.fail_readback:
                # A non-ODE engine: getPhysicsProperties returns false and does not report the flag.
                return {"op": "service_response", "service": service, "id": ident, "result": False,
                        "values": {}}  # placeholder
            return {"op": "service_response", "service": service, "id": ident, "result": True,
                    "values": {"time_step": 0.001, "pause": self.paused and not self.ignore_pause,  # placeholder
                               "max_update_rate": 1000.0, "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},  # placeholder
                               "ode_config": {}, "success": True,  # placeholder
                               "status_message": "GetPhysicsProperties: got properties"}}  # placeholder
        return {"op": "service_response", "service": service, "id": ident, "result": False,
                "values": {}}  # placeholder rejection

    def _respond(self, message):
        if message.get("op") == "publish" and message.get("topic") == "/cmd_vel":
            body = message.get("msg")
            if isinstance(body, dict):
                self.last_cmd_vel = body          # stored, paused or not (the plugin's queue thread runs)
                self.publish_count += 1
                if not self.paused:               # a paused world drives no wheel
                    self.driving_cmd_vel = body
            return None
        if message.get("op") == "call_service":
            return self._service(message)
        # A ROS topic publication is fire-and-forget: there is no service or
        # action response to synthesize, and the fake must not invent an
        # acknowledgement or a stopped state.
        return None
