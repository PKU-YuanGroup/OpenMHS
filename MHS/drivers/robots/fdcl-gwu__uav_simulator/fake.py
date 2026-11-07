"""ROS-free contract fake for the FDCL-GWU UAV simulator endpoints.

The fake models only the pinned ROS 2 wire contract used by ``driver.py``:
subscriptions to ``/uav/states``, ``/uav/imu``, ``/uav/mode`` and
``/uav/motors_on``, a publication on ``/uav/mode`` and ``/uav/motors_on``, and
a burst of stamped ``/uav/gps`` samples for the sensed-confirmation stop.
It runs no Gazebo, physics, estimator, trajectory generator or controller.

Every value below is test data, not a device fact, and is marked
``# placeholder``.  The pose starts airborne and moving, so the predicate does
not hold before the motor-cut publication.  A Bool false (and no competing
publisher) is answered with a placeholder fall to a still pose, which is then
stored so a later reset subscription is already still.  The fall is not the
quadrotor model and does not also zero the wrench when the mode is below 2.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_BURST = 12            # placeholder: samples per /uav/gps subscription (under the bridge ring of 16)
_DT_NS = 100_000_000   # placeholder: 0.1 s, the URDF p3d update_rate of 10 written as a stamp step
_FLY_Z = 2.0           # placeholder metres, above the fixture landed band
_FLY_VX = 0.3          # placeholder m/s, so the pose is not still before the cut
_FALL_STEP = 0.4       # placeholder metres dropped per sample after the cut
_REST_Z = 0.15         # placeholder metres, at or below the fixture landed band and then held


class FakeUavSimulator(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.state = {
            "position": [0.0, 0.0, 0.2],              # placeholder
            "velocity": [0.0, 0.0, 0.0],              # placeholder
            "acceleration": [0.0, 0.0, 0.0],          # placeholder
            "attitude": [1.0, 0.0, 0.0,                # placeholder
                         0.0, 1.0, 0.0,                # placeholder
                         0.0, 0.0, 1.0],               # placeholder
            "angular_velocity": [0.0, 0.0, 0.0],      # placeholder
        }
        self.imu = {
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},      # placeholder
            "angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},           # placeholder
            "linear_acceleration": {"x": 0.0, "y": 0.0, "z": 9.81},       # placeholder
        }
        # The resource snapshot starts in flight: motors on, mode 0.  A live
        # /uav/motors_on read waits for a GUI event; the fake answers at once.
        self.last_mode = 0                       # placeholder
        self.last_mode_message = None            # placeholder observation for tests
        self.motors_on = True                    # placeholder: airborne until a Bool false
        self.last_motors_on = True               # placeholder
        self.last_motors_message = None          # placeholder observation for tests
        self.gps_x = 0.0                         # placeholder
        self.gps_y = 0.0                         # placeholder
        self.gps_z = _FLY_Z                      # placeholder
        self.gps_vx = _FLY_VX                    # placeholder
        self.clock_ns = 100_000_000_000          # placeholder simulated clock for /uav/gps stamps
        self.silent_state = False                # placeholder negative-path switch
        self.malformed_state = False             # placeholder negative-path switch
        self.silent_gps = False                  # placeholder: /uav/gps answers nothing
        self.frozen_stamps = False               # placeholder: every /uav/gps sample repeats one stamp
        self.null_position = False               # placeholder: pose.pose.position.x is null
        self.competing_publisher = False         # placeholder: a GUI event turns the motors back on

    def _state_message(self, ident):
        message = {
            "header": {"frame_id": "", "stamp": {"sec": 0, "nanosec": 0}},  # placeholder
        }
        if not self.malformed_state:
            message.update({
                "position": list(self.state["position"]),
                "velocity": list(self.state["velocity"]),
                "acceleration": list(self.state["acceleration"]),
                "attitude": list(self.state["attitude"]),
                "angular_velocity": list(self.state["angular_velocity"]),
            })
        return {"op": "publish", "topic": "/uav/states", "id": ident, "msg": message}

    def _imu_message(self, ident):
        return {
            "op": "publish",
            "topic": "/uav/imu",
            "id": ident,
            "msg": {
                "header": {"frame_id": "", "stamp": {"sec": 0, "nanosec": 0}},  # placeholder
                "orientation": dict(self.imu["orientation"]),
                "angular_velocity": dict(self.imu["angular_velocity"]),
                "linear_acceleration": dict(self.imu["linear_acceleration"]),
            },
        }

    def _gps_sample(self, ident, x, y, z, vx):
        return {
            "op": "publish",
            "topic": "/uav/gps",
            "id": ident,
            "msg": {
                "header": {
                    "stamp": {"sec": self.clock_ns // 1_000_000_000,
                              "nanosec": self.clock_ns % 1_000_000_000},
                    "frame_id": "world",  # placeholder
                },
                "pose": {
                    "pose": {
                        "position": {"x": None if self.null_position else x, "y": y, "z": z},  # placeholder
                        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                    }
                },
                "twist": {
                    "twist": {
                        "linear": {"x": vx, "y": 0.0, "z": 0.0},  # placeholder
                        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                    }
                },
            },
        }

    def _gps_burst(self, ident):
        if self.silent_gps:
            return None
        flying = bool(self.competing_publisher or self.motors_on)
        if self.competing_publisher:
            # A GUI motor event (gui.py publishes Bool only on a button or the M key) re-arms the cut.
            self.motors_on = True
            self.gps_z = _FLY_Z
            self.gps_vx = _FLY_VX
            flying = True
        x, y, z, vx = self.gps_x, self.gps_y, self.gps_z, self.gps_vx
        samples = []
        for _ in range(_BURST):
            samples.append(self._gps_sample(ident, x, y, z, vx))
            if flying:
                x = round(x + _FLY_VX * (_DT_NS / 1_000_000_000), 9)  # placeholder
                z = _FLY_Z                                             # placeholder
                vx = _FLY_VX                                           # placeholder
            elif z > _REST_Z:
                x = round(x + vx * (_DT_NS / 1_000_000_000), 9)        # placeholder
                z = round(z - _FALL_STEP, 9)                           # placeholder
                if z <= _REST_Z:
                    z = _REST_Z                                        # placeholder
                    vx = 0.0                                           # placeholder
            if not self.frozen_stamps:
                self.clock_ns += _DT_NS
        if not flying:
            # The cut's settle is stored.  A later reset subscription is already still.
            self.gps_x, self.gps_y, self.gps_z, self.gps_vx = x, y, z, vx
        return samples

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            ident = message.get("id")
            if topic == "/uav/states":
                if self.silent_state:
                    return None
                return self._state_message(ident)
            if topic == "/uav/imu":
                return self._imu_message(ident)
            if topic == "/uav/gps":
                return self._gps_burst(ident)
            if topic == "/uav/mode":
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": ident,
                    "msg": {
                        "header": {"frame_id": "", "stamp": {"sec": 0, "nanosec": 0}},  # placeholder
                        "mode": self.last_mode,
                        "x_offset": [0.0, 0.0, 0.0],  # placeholder
                        "yaw_offset": 0.0,           # placeholder
                    },
                }
            if topic == "/uav/motors_on":
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": ident,
                    "msg": {"data": self.motors_on},
                }
            return None
        if operation == "publish":
            topic = message.get("topic")
            body = message.get("msg") or {}
            if topic == "/uav/mode":
                self.last_mode_message = dict(body)
                mode = body.get("mode")
                if isinstance(mode, int) and not isinstance(mode, bool):
                    self.last_mode = mode
                return None
            if topic == "/uav/motors_on":
                self.last_motors_message = dict(body)
                data = body.get("data")
                if isinstance(data, bool):
                    self.motors_on = data
                    self.last_motors_on = data
                return None
            return None
        return None
