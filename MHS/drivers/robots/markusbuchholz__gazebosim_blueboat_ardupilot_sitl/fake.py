"""Python stand-in for the pinned ``BlueboatROSInterface`` node class.

The fake exposes only the public methods the driver calls and the
``data``/``data_lock`` members the node's constructor creates.  It starts no
ROS node, MAVLink connection, ArduPilot SITL or Gazebo world.  Every value
below is test data, not a device fact.
"""

import threading


class FakeBlueboat:
    def __init__(self, **_options):
        self.data_lock = threading.Lock()
        # Placeholder MAVLink message snapshots in the shape the listener stores.
        self.data = {
            "HEARTBEAT": {"base_mode": 0},                       # placeholder: disarmed bitmask
            "VFR_HUD": {"heading": 90},                          # placeholder: degrees
            "ATTITUDE": {"roll": 0.05, "pitch": -0.02, "yaw": 1.2},  # placeholder: radians
            "SERVO_OUTPUT_RAW": {f"servo{index}_raw": 1500     # placeholder: PWM microseconds
                                 for index in range(1, 9)},  # placeholder: eight servo channels
        }
        self.sent = []                 # placeholder test log
        self.fail_disarm = False       # placeholder negative-path switch
        self.arm_value = 128           # placeholder: MAV_MODE_FLAG_SAFETY_ARMED bit

    def send_motor_thrust(self, motor_number, thrust_value):
        # Placeholder record only: no MAVLink frame, motor test or physics.
        self.sent.append(("motor", int(motor_number), int(thrust_value)))

    def arm_vehicle(self):
        if self.fail_disarm:
            raise RuntimeError("placeholder arm failure")
        with self.data_lock:
            base_mode = int(self.data["HEARTBEAT"].get("base_mode", 0))  # placeholder: default bitmask
            self.data["HEARTBEAT"]["base_mode"] = base_mode | self.arm_value
        self.sent.append(("arm",))

    def disarm_vehicle(self):
        if self.fail_disarm:
            raise RuntimeError("placeholder disarm failure")
        with self.data_lock:
            base_mode = int(self.data["HEARTBEAT"].get("base_mode", 0))  # placeholder: default bitmask
            self.data["HEARTBEAT"]["base_mode"] = base_mode & ~self.arm_value
        self.sent.append(("disarm",))
