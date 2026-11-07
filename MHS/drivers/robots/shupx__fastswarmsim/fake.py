"""ROS-free canned-response fake for the FastSwarmSim time coordinator endpoints.

The fake models the pinned wire contract of ``fss_time``: a
rosgraph_msgs/msg/Clock publication on ``/clock``, a
fss_time_interfaces/msg/SimClockStatus publication on
``/fss/sim_clock_status`` and the fss_time_interfaces/srv/SimClockControl
service on ``/fss/clock_control``.  Every number and message below is test
data (# placeholder), not a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeFastSwarmSim(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.running = True                    # placeholder state
        self.max_real_time_factor = 0.5        # placeholder state
        self.observed_real_time_factor = 0.0   # placeholder
        self.participant_count = 1             # placeholder
        self.sim_sec = 12                      # placeholder
        self.sim_nanosec = 340000000           # placeholder
        self.fail_clock_service = False        # placeholder negative-path switch
        self.fail_clock_application = False    # placeholder negative-path switch

    def _status(self):
        return {
            "sim_time": {"sec": self.sim_sec, "nanosec": self.sim_nanosec},  # placeholder
            "running": self.running,
            "max_real_time_factor": self.max_real_time_factor,
            "observed_real_time_factor": self.observed_real_time_factor,    # placeholder
            "participant_count": self.participant_count,                    # placeholder
            "new_request_participant_count": 0,                             # placeholder
            "regulator_active": self.running and self.max_real_time_factor > 0.0,
            "debug_msg": "placeholder",                                     # placeholder
            "speed_regulator_step_ns": 10000000,                            # placeholder
            "min_operation_walltime": 100000,                               # placeholder
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            if topic == "/clock":
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": message.get("id"),
                    "msg": {"clock": {"sec": self.sim_sec, "nanosec": self.sim_nanosec}},  # placeholder
                }
            if topic == "/fss/sim_clock_status":
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": message.get("id"),
                    "msg": self._status(),
                }
            return None
        if operation == "call_service":
            service = message.get("service")
            if service == "/fss/clock_control":
                if self.fail_clock_service:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": False, "values": "clock_control unavailable"}  # placeholder
                args = message.get("args") or {}
                self.running = bool(args.get("running", self.running))
                self.max_real_time_factor = float(
                    args.get("max_real_time_factor", self.max_real_time_factor))
                if self.fail_clock_application:
                    # The transport answered but the application predicate is not met.
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": True, "values": {"success": False,
                                                       "message": "clock_control rejected"}}  # placeholder
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": True, "values": {"success": True,
                                                   "message": "time_coordinator updated"}}  # placeholder
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": False, "values": {}}
        return None
