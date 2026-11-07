"""ROS-free recording fake for the pinned ArduPilot SITL Gazebo ROS surface.

The fake models the wire contract this package declares: a
``mav_msgs/CommandMotorSpeed`` publication on ``/cessna/command/motor_speed``
and the acknowledged ``/fdmUDP/take_apm_lapseLock`` and
``/fdmUDP/release_apm_lapseLock`` services.  It contacts no ROS graph,
rosbridge peer, Gazebo world or ArduPilot SITL process.

The lapse lock is deliberately event-driven: it stays held until the release
service or a test resets it.  The real plugin also decrements the lock by the
loop's elapsed wall time and clears it automatically.  This limitation is
reported in the driver's fidelity gaps.  Every state value below is
synthesized placeholder data, not a device fact and not a replay of captured
ROS traffic.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeArdupilotSitlGazeboPlugin(RecordingRosTransport):
    """Deterministic stand-in for the plugin's declared ROS endpoints."""

    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder motor-speed command state.  The real array length follows
        # the SDF NB_SERVOS_MOTOR_SPEED setting (4 for iris, 5 for cessna); the
        # fake uses one array for the Cessna profile.
        self.motor_speed = [5.0, 5.0, 5.0, 5.0, 5.0]  # placeholder
        self.sequence = 0  # placeholder
        self.holders = 0  # placeholder
        self.paused = False  # placeholder
        self.publish_motor_speed = True  # placeholder negative-path switch
        self.fail_motor_topic = False  # placeholder negative-path switch
        self.fail_take_service = False  # placeholder negative-path switch
        self.malformed_take_response = False  # placeholder negative-path switch
        self.reject_take_application = False  # placeholder negative-path switch
        self.fail_release_service = False  # placeholder negative-path switch
        self.reject_release_application = False  # placeholder negative-path switch
        self.take_requests = []  # placeholder recording of take service args
        self.release_requests = []  # placeholder recording of release service args

    @staticmethod
    def _reply(service, ident, ok, values):
        return {"op": "service_response", "service": service, "id": ident,
                "result": ok, "values": values}

    def _motor_message(self):
        self.sequence += 1  # placeholder sequence
        return {
            "header": {
                "seq": self.sequence,
                "stamp": {"secs": 0, "nsecs": 0},  # placeholder
                "frame_id": "quad",
            },
            "motor_speed": list(self.motor_speed),
        }

    def _take(self, ident, values):
        service = "/fdmUDP/take_apm_lapseLock"
        self.take_requests.append(dict(values) if isinstance(values, dict) else {})
        if self.fail_take_service:
            return self._reply(service, ident, False, {})
        if self.malformed_take_response:
            return self._reply(service, ident, True, "not-a-service-values-object")
        if self.reject_take_application:
            # One external holder plus the caller's own increment leaves the
            # returned count above this driver's exact predicate.
            self.holders += 2  # placeholder
            self.paused = True
            return self._reply(service, ident, True, {"nb_holders": self.holders})
        self.holders += 1  # placeholder
        self.paused = True
        return self._reply(service, ident, True, {"nb_holders": self.holders})

    def _release(self, ident, values):
        service = "/fdmUDP/release_apm_lapseLock"
        self.release_requests.append(dict(values) if isinstance(values, dict) else {})
        if self.fail_release_service:
            return self._reply(service, ident, False, {})
        if self.reject_release_application:
            # A different holder remains, so this release does not free the loop.
            if self.holders > 0:
                self.holders -= 1  # placeholder
            if self.holders == 0:
                self.holders = 1  # placeholder: keep another holder
            return self._reply(service, ident, True, {"nb_holders": self.holders})
        if self.holders > 0:
            self.holders -= 1  # placeholder
        if self.holders == 0:
            self.paused = False
        return self._reply(service, ident, True, {"nb_holders": self.holders})

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            ident = message.get("id")
            if topic != "/cessna/command/motor_speed":
                return None
            if self.fail_motor_topic or self.paused or not self.publish_motor_speed:
                # The plugin publishes only from its stepping loop; a paused
                # loop produces no fresh sample for a new subscription.
                return None
            return {"op": "publish", "topic": topic, "id": ident, "msg": self._motor_message()}
        if operation == "call_service":
            service = message.get("service")
            ident = message.get("id")
            values = message.get("args") if isinstance(message.get("args"), dict) else {}
            if service == "/fdmUDP/take_apm_lapseLock":
                return self._take(ident, values)
            if service == "/fdmUDP/release_apm_lapseLock":
                return self._release(ident, values)
            return self._reply(str(service), ident, False, {})
        return None
