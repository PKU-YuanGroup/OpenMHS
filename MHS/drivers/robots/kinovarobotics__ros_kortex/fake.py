"""ROS-free recording fake for the Kinova Kortex ROS 1 base stop endpoints.

The fake models the pinned upstream wire contract: the relative ROS 1
services ``base/stop`` and ``base/apply_emergency_stop``, resolved here under
the explicit deployment namespace ``/my_gen3``.  Both services take the
generated request ``{input: Empty}`` and return ``{output: Empty}``.  The
failure switches and call record below are test data, not device facts; the
empty Empty payloads follow the pinned .srv definitions.  No ROS graph or
robot is contacted.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_STOP = "/my_gen3/base/stop"
_APPLY_EMERGENCY_STOP = "/my_gen3/base/apply_emergency_stop"
_TYPES = {_STOP: "kortex_driver/Stop", _APPLY_EMERGENCY_STOP: "kortex_driver/ApplyEmergencyStop"}


class FakeKortexRos1Stop(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.services_called = []                    # placeholder observation record
        self.fail_stop_service = False               # placeholder negative-path switch
        self.fail_stop_application = False           # placeholder negative-path switch
        self.wrong_stop_output = False               # placeholder negative-path switch
        self.fail_emergency_stop_service = False     # placeholder negative-path switch
        self.fail_emergency_stop_application = False  # placeholder negative-path switch
        self.wrong_emergency_stop_output = False     # placeholder negative-path switch

    def _respond(self, message):
        if message.get("op") != "call_service":
            return None
        service = message.get("service")
        if service not in _TYPES:
            return {"op": "service_response", "service": service, "id": message.get("id"), "result": False}
        self.services_called.append(service)  # placeholder
        # The real request nests an Empty message under "input"; a different
        # shape is answered with a response that fails the application
        # predicate rather than pretending the callback succeeded.
        if message.get("args") != {"input": {}} or message.get("type") != _TYPES[service]:
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": True, "values": {}}
        if service == _STOP:
            if self.fail_stop_service:
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": False, "values": {}}
            if self.fail_stop_application:
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": True, "values": {}}
            if self.wrong_stop_output:
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": True, "values": {"output": {"unexpected": True}}}
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": True, "values": {"output": {}}}
        if self.fail_emergency_stop_service:
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": False, "values": {}}
        if self.fail_emergency_stop_application:
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": True, "values": {}}
        if self.wrong_emergency_stop_output:
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": True, "values": {"output": {"unexpected": True}}}
        return {"op": "service_response", "service": service, "id": message.get("id"),
                "result": True, "values": {"output": {}}}
