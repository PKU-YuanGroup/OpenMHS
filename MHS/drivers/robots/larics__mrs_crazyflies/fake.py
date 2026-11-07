"""ROS-free contract fake for the mrs_crazyflies cf_1 endpoints.

The fake models the declared wire contract: a geometry_msgs/Twist publication
on /cf_1/cmd_vel, a PoseStamped observation on /cf_1/pose, and the acknowledged
std_srvs/Empty /all/emergency service.  It contacts no ROS graph, rosbridge
peer, Gazebo world, CrazySwarm2 node or Crazyflie.

This is an analytic ROS-free contract stand-in, not a recording of captured
traffic and not the upstream simulator.  Every number below is placeholder
test data, not a device fact or a motion claim.

The sensed-confirmation stop (SAFE-049) needs stamped samples: a pose
subscription is answered with a short burst whose ROS 2 stamps (sec,
nanosec) increase on a placeholder clock, each sample advancing a placeholder
fall by one tick; the first sample of a burst is the pose before that tick.
The fake starts hovering, so nothing satisfies the predicate before the
emergency request arrived; after it the motors stay cut.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_BURST = 16  # placeholder: samples per pose subscription
_TICK_NS = 100_000_000  # placeholder: 0.1 s of simulated time per sample


class FakeMrsCrazyflies(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder state and negative-path switches.  None of these values
        # is a device fact, a measured pose or a stop proof.
        self.pose = {"x": 0.0, "y": 0.0, "z": 1.0}  # placeholder: hovering as vel_mux leaves it
        self.twist_packets = []
        self.advertised_topics = []
        self.pose_requests = 0  # placeholder counter
        self.emergency_requests = 0  # placeholder counter
        self.emergency_requested = False  # placeholder acknowledgement flag
        self.fail_pose = False  # placeholder negative-path switch
        self.fail_emergency_service = False  # placeholder negative-path switch
        self.malformed_emergency_response = False  # placeholder negative-path switch
        self.motors_cut = False  # placeholder: the firmware emergency stop happened
        self.clock_ns = 1_000_000_000_000  # placeholder simulated clock
        self.no_fall = False  # placeholder: the emergency is acknowledged, the vehicle keeps hovering
        self.frozen_stamps = False  # placeholder: every sample repeats one stamp
        self.null_z = False  # placeholder: pose z is null in every sample
        self.drift = False  # placeholder: the pose keeps moving on the ground (never at rest)

    def _stamp(self):
        if not self.frozen_stamps:
            self.clock_ns += _TICK_NS
        return {"sec": self.clock_ns // 1_000_000_000, "nanosec": self.clock_ns % 1_000_000_000}

    def _tick(self):
        if self.motors_cut and not self.no_fall and self.pose["z"] > 0.0:
            # Placeholder fall per sample, not quadrotor dynamics.
            self.pose["z"] = 0.0 if self.pose["z"] <= 0.4 else round(self.pose["z"] - 0.4, 6)
        if self.drift:
            self.pose["x"] = round(self.pose["x"] + 0.5, 6)  # placeholder

    def _respond(self, message):
        operation = message.get("op")
        if operation == "advertise":
            self.advertised_topics.append(message.get("topic"))
            return None
        if operation in ("unadvertise", "unsubscribe"):
            return None
        if operation == "subscribe":
            return self._subscribe(message)
        if operation == "publish":
            return self._publish(message)
        if operation == "call_service":
            return self._service(message)
        return None

    def _subscribe(self, message):
        if message.get("topic") != "/cf_1/pose" or self.fail_pose:
            return None
        self.pose_requests += 1  # placeholder counter
        samples = []
        for _ in range(_BURST):
            samples.append({
                "op": "publish",
                "topic": "/cf_1/pose",
                "id": message.get("id"),
                "msg": {
                    # ROS 2 builtin_interfaces/Time fields (sec, nanosec) on a placeholder clock.
                    "header": {"stamp": self._stamp(), "frame_id": "world"},  # placeholder
                    "pose": {
                        "position": {
                            "x": self.pose["x"],
                            "y": self.pose["y"],
                            "z": None if self.null_z else self.pose["z"],
                        },
                        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                    },
                },
            })
            self._tick()
        return samples

    def _publish(self, message):
        topic = message.get("topic")
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        if topic == "/cf_1/cmd_vel":
            self.twist_packets.append(body)
            if self.motors_cut:
                return None  # placeholder: the motors stay cut after the firmware emergency stop
            linear = body.get("linear") if isinstance(body.get("linear"), dict) else {}
            # Placeholder analytic effect only: a fixed offset per publication,
            # not quadrotor dynamics, integration or a measured trajectory.
            self.pose["x"] = self.pose["x"] + 0.01 * float(linear.get("x", 0.0))  # placeholder
            self.pose["y"] = self.pose["y"] + 0.01 * float(linear.get("y", 0.0))  # placeholder
            self.pose["z"] = self.pose["z"] + 0.01 * float(linear.get("z", 0.0))  # placeholder
        return None

    def _service(self, message):
        service = message.get("service")
        ident = message.get("id")

        def reply(ok, values):
            return {"op": "service_response", "service": service, "id": ident,
                    "result": ok, "values": values}

        if service == "/all/emergency":
            if self.fail_emergency_service:
                return reply(False, {})
            if self.malformed_emergency_response:
                # The transport answered, but the values are not a service
                # response object; the bridge must not report success.
                return reply(True, "not-a-service-values-object")  # placeholder malformed reply
            self.emergency_requests += 1  # placeholder counter
            self.emergency_requested = True  # placeholder acknowledgement flag
            self.motors_cut = True  # placeholder: cflib's emergency stop packet cut the motors
            return reply(True, {})
        return reply(False, {})
