"""ROS-free recording fake for the swarm_sync_sim simulation clock endpoints.

The fake models the pinned wire contract of ``sss_sim_env``: a latched
rosgraph_msgs/Clock publication on ``/clock``, a latched std_msgs/Bool
publication on ``/sss_clock_is_online`` and the
sss_sim_env/srv/SimClockControl service on ``/sss_clock_control``.  Every
number and message below is test data (# placeholder), not a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeSwarmSyncSim(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.paused = False                   # placeholder state
        self.sim_secs = 12                    # placeholder
        self.sim_nsecs = 340000000            # placeholder
        self.online = True                    # placeholder
        self.max_sim_speed = 1.0              # placeholder
        self.fail_clock_service = False       # placeholder negative-path switch
        self.reject_clock_application = False # placeholder negative-path switch
        self.malformed_clock_response = False # placeholder negative-path switch

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            if topic == "/clock":
                # Event-driven stand-in for the running regulator: each clock
                # observation advances the placeholder sample while unpaused.
                # /clock is latched, so a paused observation returns the held
                # sample.  This is test data, not wall-clock pacing.
                if not self.paused:
                    self.sim_nsecs += 1000000        # placeholder step
                    if self.sim_nsecs >= 1000000000:  # placeholder normalization
                        self.sim_secs += self.sim_nsecs // 1000000000
                        self.sim_nsecs %= 1000000000
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": message.get("id"),
                    "msg": {"clock": {"secs": self.sim_secs, "nsecs": self.sim_nsecs}},  # placeholder
                }
            if topic == "/sss_clock_is_online":
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": message.get("id"),
                    "msg": {"data": self.online},  # placeholder
                }
            return None
        if operation == "call_service":
            return self._service(message)
        return None

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")
        if service != "/sss_clock_control":
            return {
                "op": "service_response",
                "service": service,
                "id": ident,
                "result": False,
                "values": {"success": False},  # placeholder
            }
        if self.fail_clock_service:
            return {
                "op": "service_response",
                "service": service,
                "id": ident,
                "result": False,
                "values": "clock control service unavailable",  # placeholder
            }
        args = message.get("args") if isinstance(message.get("args"), dict) else {}
        self.paused = not bool(args.get("proceed", True))          # placeholder default
        speed = float(args.get("max_sim_speed", 0.0))              # placeholder default
        if speed != 0.0:
            self.max_sim_speed = speed
        if self.malformed_clock_response:
            return {
                "op": "service_response",
                "service": service,
                "id": ident,
                "result": True,
                "values": "malformed",  # placeholder malformed reply
            }
        if self.reject_clock_application:
            # The transport answered but the application predicate is not met.
            return {
                "op": "service_response",
                "service": service,
                "id": ident,
                "result": True,
                "values": {"success": False},  # placeholder rejected application
            }
        return {
            "op": "service_response",
            "service": service,
            "id": ident,
            "result": True,
            "values": {"success": True},  # placeholder acknowledgement
        }
