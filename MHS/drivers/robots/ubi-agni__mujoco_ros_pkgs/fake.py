"""ROS-free recording fake for the pinned mujoco_ros ROS 1 service contract.

The fake answers only the two rosbridge service calls this package declares:
``/mujoco_server/set_pause`` of type ``mujoco_ros_msgs/SetPause`` and
``/mujoco_server/get_sim_info`` of type ``mujoco_ros_msgs/GetSimInfo``.  It
runs no MuJoCo physics, no ROS node and no simulator process.  Every numeric
or boolean value below that is not derived from the request is placeholder
test data, not a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_SET_PAUSE = "/mujoco_server/set_pause"
_GET_SIM_INFO = "/mujoco_server/get_sim_info"


class FakeMujocoRos(RecordingRosTransport):
    """Package-local recording transport with the pinned service shapes."""

    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # placeholder simulator state, not a fact about a running MuJoCo model
        self.paused = False
        # placeholder negative-path switches for the package tests
        self.fail_pause_service = False
        self.fail_pause_application = False
        self.fail_info_service = False
        self.omit_paused = False

    def _respond(self, message):
        operation = message.get("op")
        if operation != "call_service":
            return None
        service = message.get("service")
        ident = message.get("id")
        if service == _SET_PAUSE:
            if self.fail_pause_service:
                return {"op": "service_response", "service": service, "id": ident,
                        "result": False, "values": "pause service unavailable"}  # placeholder
            arguments = message.get("args", {})
            accepted = (isinstance(arguments, dict)
                        and arguments.get("paused") is True
                        and arguments.get("admin_hash") == "")
            if not accepted:
                # The fake assumes an unauthenticated deployment outside eval
                # mode; it does not claim that every deployment accepts the
                # empty admin_hash.
                return {"op": "service_response", "service": service, "id": ident,
                        "result": True, "values": {"success": False}}
            if self.fail_pause_application:
                return {"op": "service_response", "service": service, "id": ident,
                        "result": True, "values": {"success": False}}  # placeholder rejection
            self.paused = True
            return {"op": "service_response", "service": service, "id": ident,
                    "result": True, "values": {"success": True}}
        if service == _GET_SIM_INFO:
            if self.fail_info_service:
                return {"op": "service_response", "service": service, "id": ident,
                        "result": False, "values": "get_sim_info service unavailable"}  # placeholder
            state = {} if self.omit_paused else {"paused": self.paused}
            return {"op": "service_response", "service": service, "id": ident,
                    "result": True, "values": {"state": state}}
        return {"op": "service_response", "service": service, "id": ident,
                "result": False, "values": "undeclared service"}  # placeholder
