"""ROS-free canned fake for the AutoRally Gazebo simulation topic contract.

The fake models the pinned upstream wire contract: fresh
``autorally_msgs/chassisState`` and ``autorally_msgs/wheelSpeeds`` publications,
an ``autorally_msgs/runstop`` publication on ``/runstop``, and a
``std_msgs/Float64`` publication on
``/constantSpeedController/speedCommand``.  It runs no Gazebo physics, no
constant-speed controller and no joystick node.

The runstop state mirrors ``getrunstop``: every recorded sender is ANDed and an
empty sender set means enabled.  Wheel speeds are a placeholder stream.  While
motion is enabled and the stored target is above 0.1 (the constant-speed
controller's own branch) the magnitude equals the absolute target, an echo and
not a plant.  They decay after a zero target or a false runstop AND, and they
settle at 0 so a later read does not move on its own.  A ``competing_speed``
switch keeps them at a coast magnitude.  Every number below is test data, not
a device fact.

The sensed-confirmation stop (SAFE-049) needs stamped samples.  A wheelSpeeds
subscription is answered with a short burst whose ROS 1 stamps (secs, nsecs)
increase on a placeholder clock.  The first sample is the pre-request state
the bridge discards.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_BURST = 12                 # placeholder: samples per wheelSpeeds subscription
_DT_NS = 100_000_000        # placeholder: 0.1 s of producer time between samples
_DECAY = 0.5                # placeholder decay of the wheel-speed magnitude per sample
_COAST = 2.0                # placeholder m/s while a target above 0.1 is stored
_STOP_SPEED = 0.1           # ConstantSpeedController.cpp:120 uses data > 0.1; not a device limit


class FakeAutorally(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.runstops = {}                       # placeholder sender -> bool map
        self.target_speed_mps = 3.0              # placeholder: README example target, already commanded
        self.wheel_speed = _COAST                # placeholder magnitude of all four wheels
        self.clock_ns = 100_000_000_000          # placeholder simulated clock; zero is an invalid stamp
        self.last_speed_command = None           # placeholder recording
        self.last_runstop = None                 # placeholder recording
        self.withhold_chassis_state = False      # placeholder negative-path switch
        self.withhold_wheel_speeds = False       # placeholder negative-path switch
        self.silent = False                      # placeholder: wheelSpeeds answers nothing
        self.frozen_stamps = False               # placeholder: every wheel sample repeats one stamp
        self.null_lf = False                     # placeholder: lfSpeed is null
        self.competing_speed = False             # placeholder: another publisher keeps the wheels fast
        self.drop_speed_zero = False             # placeholder: a data 0.0 speedCommand is not stored (lost delivery)
        self.chassis_placeholders = {            # placeholder state values
            "throttleRelayEnabled": False,
            "autonomousEnabled": False,
            "steeringCommander": "none",
            "steering": 0.0,
            "throttleCommander": "none",
            "throttle": 0.0,
            "frontBrakeCommander": "none",
            "frontBrake": 0.0,
        }

    def runstop_motion_enabled(self):
        """Mirror the controller's AND over every received sender."""
        if not self.runstops:
            return True
        return all(self.runstops.values())

    def _wheels_moving(self):
        """Placeholder: a false runstop AND forces the wheels down; a high target does not override it."""
        if self.competing_speed:
            return True
        if not self.runstop_motion_enabled():
            return False
        return self.target_speed_mps > _STOP_SPEED

    def chassis_message(self):
        message = {
            "header": {                          # placeholder header
                "seq": 0,
                "stamp": {"secs": 0, "nsecs": 0},
                "frame_id": "gazeboSim",
            },
            "runstopMotionEnabled": self.runstop_motion_enabled(),
        }
        message.update(self.chassis_placeholders)
        return message

    def _stamp(self):
        if self.frozen_stamps:
            return {"secs": 1, "nsecs": 0}       # placeholder repeated producer stamp
        seconds, nanos = divmod(self.clock_ns, 1_000_000_000)
        return {"secs": seconds, "nsecs": nanos}

    def _wheel_sample(self, topic, ident, speed):
        magnitude = float(speed)                 # placeholder: all four wheels share one magnitude
        return {
            "op": "publish",
            "topic": topic,
            "id": ident,
            "msg": {
                "header": {                      # placeholder header
                    "seq": 0,
                    "stamp": self._stamp(),
                    "frame_id": "gazeboSim",
                },
                "lfSpeed": None if self.null_lf else magnitude,
                "rfSpeed": magnitude,
                "lbSpeed": magnitude,
                "rbSpeed": magnitude,
            },
        }

    def _wheel_burst(self, topic, ident):
        moving = self._wheels_moving()
        if self.competing_speed:
            speed = _COAST                        # placeholder: another publisher keeps the wheels fast
        elif moving:
            speed = abs(self.target_speed_mps)    # placeholder echo of the stored target, not a plant
        else:
            speed = self.wheel_speed
        samples = []
        for _ in range(_BURST):
            samples.append(self._wheel_sample(topic, ident, speed))
            if not moving and not self.competing_speed:
                # Settle at 0 once inside the fake threshold so a later read does not change by itself.
                speed = 0.0 if speed <= 0.05 else round(speed * _DECAY, 9)
            if not self.frozen_stamps:
                self.clock_ns += _DT_NS
        self.wheel_speed = speed                 # the run-down, the echo, or the coast is stored (placeholder)
        return samples

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            if topic == "/chassisState" and not self.withhold_chassis_state:
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": message.get("id"),
                    "msg": self.chassis_message(),
                }
            if topic == "/wheelSpeeds" and not self.withhold_wheel_speeds and not self.silent:
                return self._wheel_burst(topic, message.get("id"))
            return None
        if operation == "publish":
            topic = message.get("topic")
            body = message.get("msg")
            if topic == "/constantSpeedController/speedCommand":
                self.last_speed_command = body
                if isinstance(body, dict):
                    value = body.get("data")
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        # A zero the controller never stores leaves the previous target (lost delivery).
                        if not (self.drop_speed_zero and float(value) == 0.0):
                            self.target_speed_mps = float(value)  # placeholder state effect
                return None
            if topic == "/runstop":
                self.last_runstop = body
                if isinstance(body, dict):
                    sender = body.get("sender")
                    if isinstance(sender, str) and sender:
                        self.runstops[sender] = bool(body.get("motionEnabled", False))
                return None
            return None
        return None
