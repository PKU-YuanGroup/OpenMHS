"""ROS-free recording fake for the Flatland simulator endpoints.

The fake models the pinned upstream wire contract: a rosgraph_msgs/Clock
publication on /clock and the std_srvs/Empty pause/resume services.  All
numbers below are test data, not device facts.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeFlatland(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.paused = False                  # placeholder state
        self.clock_secs = 12                 # placeholder
        self.clock_nsecs = 340000000         # placeholder
        self.fail_pause_service = False      # placeholder negative-path switch
        self.fail_pause_application = False  # placeholder negative-path switch

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == "/clock" and not self.paused:
                return {
                    "op": "publish",
                    "topic": "/clock",
                    "id": message.get("id"),
                    "msg": {"clock": {"secs": self.clock_secs, "nsecs": self.clock_nsecs}},  # placeholder
                }
            return None
        if operation == "call_service":
            service = message.get("service")
            if service == "/pause":
                if self.fail_pause_service:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": False, "values": "pause service unavailable"}  # placeholder
                self.paused = True
                if self.fail_pause_application:
                    # The transport answered but the application predicate is not met.
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": True, "values": {"rejected": True}}  # placeholder
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": True, "values": {}}
            if service == "/resume":
                self.paused = False
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": True, "values": {}}
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": False, "values": {}}
        return None
