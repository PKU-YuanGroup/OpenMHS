"""ROS-free analytic fake for the UR5 vacuum-gripper ROS 1 endpoints.

The fake models the pinned wire contract only: the nine
``std_srvs/Empty`` on/off services declared by the gripper node, the first
plugin's ``/ur5/vacuum_gripper/grasping`` Bool topic, the ``/cxy``
``ur5_notebook/Tracker`` topic and the ``/blocks_poses``
``ur5_notebook/blocks_poses`` topic, and the companion gazebo_ros services
``/gazebo/pause_physics`` and ``/gazebo/get_physics_properties`` (the e-stop and
its read-back).  A paused flag stands for the Gazebo world's: the pause sets it,
the read-back reports it, and the three topics are silent while it is set; the
vacuum services still answer while paused (the plugin's queue thread runs on
the wall clock).  All values below are test data, not device facts.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

#: Channel order used by the pinned gripper node.
_ON = [
    "/ur5/vacuum_gripper/on",
    "/ur5/vacuum_gripper1/on",
    "/ur5/vacuum_gripper2/on",
    "/ur5/vacuum_gripper3/on",
    "/ur5/vacuum_gripper4/on",
    "/ur5/vacuum_gripper5/on",
    "/ur5/vacuum_gripper6/on",
    "/ur5/vacuum_gripper7/on",
    "/ur5/vacuum_gripper8/on",
]
_OFF = [
    "/ur5/vacuum_gripper/off",
    "/ur5/vacuum_gripper1/off",
    "/ur5/vacuum_gripper2/off",
    "/ur5/vacuum_gripper3/off",
    "/ur5/vacuum_gripper4/off",
    "/ur5/vacuum_gripper5/off",
    "/ur5/vacuum_gripper6/off",
    "/ur5/vacuum_gripper7/off",
    "/ur5/vacuum_gripper8/off",
]


class FakeUr5VacuumGripper(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        #: Placeholder vacuum state, one flag per channel.
        self.vacuum = [False] * 9
        #: Placeholder negative-path switches.
        self.fail_service = None
        self.fail_application = None
        #: Placeholder tracker sample.
        self.tracker = {
            "x": 400.0, "y": 400.0, "z": 0.0,                     # placeholder
            "error_x": 0.0, "error_y": 0.0, "error_z": 0.0,        # placeholder
            "flag1": True, "flag2": False, "flag3": False,         # placeholder
        }
        #: Placeholder block-pose sample.
        self.blocks = {"x": [0.0], "y": [0.0], "z": [0.0]}         # placeholder
        #: The Gazebo world's paused flag (the fake starts running) and its negative-path switches.
        self.paused = False         # placeholder
        self.fail_pause = False     # placeholder: the pause is not answered
        self.fail_readback = False  # placeholder: a non-ODE engine (success false, the call fails)
        self.ignore_pause = False   # placeholder: another client unpaused (the read-back reports pause false)

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if self.paused:
                return None  # a paused world runs no plugin update and no camera
            topic = message.get("topic")
            if topic == "/ur5/vacuum_gripper/grasping":
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": message.get("id"),
                    "msg": {"data": self.vacuum[0]},                # placeholder
                }
            if topic == "/cxy":
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": message.get("id"),
                    "msg": dict(self.tracker),
                }
            if topic == "/blocks_poses":
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": message.get("id"),
                    "msg": dict(self.blocks),
                }
            return None
        if operation == "call_service":
            service = message.get("service")
            if service == "/gazebo/pause_physics":
                if self.fail_pause:
                    return None  # no answer: the e-stop's request times out
                self.paused = True
                return {"op": "service_response", "service": service, "id": message.get("id"), "result": True,
                        "values": {}}
            if service == "/gazebo/get_physics_properties":
                if self.fail_readback:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": False, "values": "get_physics_properties not supported"}  # placeholder
                return {"op": "service_response", "service": service, "id": message.get("id"), "result": True,
                        "values": {"time_step": 0.001, "pause": self.paused and not self.ignore_pause,  # placeholder
                                   "max_update_rate": 1000.0, "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},
                                   "ode_config": {}, "success": True, "status_message": "placeholder"}}
            if service in _ON or service in _OFF:
                if service == self.fail_service:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": False, "values": "vacuum service unavailable"}  # placeholder
                if service == self.fail_application:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": True, "values": {"rejected": True}}             # placeholder
                index = (_ON if service in _ON else _OFF).index(service)
                self.vacuum[index] = service in _ON
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": True, "values": {}}
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": False, "values": {}}
        return None
