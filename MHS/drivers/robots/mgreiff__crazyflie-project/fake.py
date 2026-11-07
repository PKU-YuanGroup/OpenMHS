"""ROS-free contract fake for the Crazyflie trajectory master endpoints.

The fake models the pinned upstream wire contract: publications on
/crazyflie/trajectory_packet, /crazyflie/synchronization_packet and
/crazyflie/cmd_vel, and the acknowledged /crazyflie/update_params and
/crazyflie/emergency services.  It contacts no ROS graph, rosbridge peer,
crazyflie_ros driver, Simulink model or UAV.  Every state value below is
placeholder test data, not a device fact and not a replay of captured
traffic.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeCrazyflieProject(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder recordings and state.  None of these values is a device
        # fact, a motion claim or a stop proof.
        self.trajectory_packets = []
        self.synchronization_packets = []
        self.twist_packets = []
        self.advertised_topics = []
        self.last_params = []
        self.emergency_requests = 0  # placeholder counter
        self.emergency_requested = False  # placeholder flag: request acknowledged, no motor claim
        self.log_ref_values = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder reference values
        # Negative-path switches used by the package tests.
        self.fail_update_params_service = False  # placeholder
        self.fail_emergency_service = False  # placeholder
        self.malformed_emergency_response = False  # placeholder

    def _respond(self, message):
        operation = message.get("op")
        if operation in ("advertise", "unadvertise"):
            if operation == "advertise":
                self.advertised_topics.append(message.get("topic"))
            return None
        if operation == "subscribe":
            if message.get("topic") == "/crazyflie/log_ref":
                return {"op": "publish", "topic": "/crazyflie/log_ref", "id": message.get("id"),
                        "msg": {"header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},
                                "values": list(self.log_ref_values)}}  # placeholder sample
            return None
        if operation == "publish":
            topic = message.get("topic")
            body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
            if topic == "/crazyflie/trajectory_packet":
                self.trajectory_packets.append(body)
                data = body.get("data")
                if isinstance(data, list) and len(data) == 6:
                    # Placeholder analytic effect only: copy the coefficients
                    # into the reference-values state so the resource changes.
                    # This is not dynamics, a measured pose or a reference pose.
                    self.log_ref_values = [float(value) for value in data]
            elif topic == "/crazyflie/synchronization_packet":
                self.synchronization_packets.append(body)
            elif topic == "/crazyflie/cmd_vel":
                self.twist_packets.append(body)
            return None
        if operation == "call_service":
            return self._service(message)
        return None

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")

        def reply(ok, values):
            return {"op": "service_response", "service": service, "id": ident,
                    "result": ok, "values": values}

        if service == "/crazyflie/update_params":
            if self.fail_update_params_service:
                return reply(False, {})
            args = message.get("args") if isinstance(message.get("args"), dict) else {}
            params = args.get("params") if isinstance(args, dict) else None
            if isinstance(params, list):
                self.last_params = list(params)
            return reply(True, {})
        if service == "/crazyflie/emergency":
            if self.fail_emergency_service:
                return reply(False, {})
            if self.malformed_emergency_response:
                # The transport answered, but the values are not a service
                # response object; the bridge must not report success.
                return reply(True, "not-a-service-values-object")  # placeholder malformed reply
            self.emergency_requests += 1  # placeholder counter
            self.emergency_requested = True  # placeholder acknowledgement flag
            return reply(True, {})
        return reply(False, {})
