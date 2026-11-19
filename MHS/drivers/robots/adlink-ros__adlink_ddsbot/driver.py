"""OpenMHS driver for gh.adlink-ros/adlink_ddsbot: the ADLINK DDSBot differential-drive base.

The device is the mobile base whose ROS 1 node is ``script/base_control.py:BaseControl``: it receives a body twist on
``cmd_vel``, converts it to left and right wheel speeds, writes the comma-separated frame ``left,right,checksum`` to an
Arduino over a serial port, and reads a ``left,right`` wheel-speed reply.  This is a direct Driver over that upstream
class: the fake backend implements the class's members and the hardware backend is a Python 3 port of its serial path
(the clone's node is Python 2 source and its serial I/O is interleaved with ROS timers and publishers, neither of which
this in-process driver needs).

* capability ``cap.motion.mobile_base.v1``: drive a commanded body twist for a bounded duration, then write a zero
  wheel-speed frame.  The reported distance and heading are integrated from the commanded twist and the command time;
  they are not measured odometry (the pinned motor firmware sets ``odom_pub = false``, see facts.md).
* reads: firmware-reported wheel speeds and the body twist derived from them. The pinned firmware reports
  placeholder zeros even during motion; these values are not measured odometry or a stop confirmation.
* the native stop writes a zero wheel-speed reference; the firmware's zero branch sets all four PWM outputs to 0.
  The frame is not acknowledged and the pinned firmware's ``odom_pub = false`` branch prints ``0,0`` instead of the
  measured wheel speeds, so this driver does not claim sensed quiescence from the reply.

No text file of the clone states a body linear or angular velocity range: the wheel separation and radius are ROS
parameters of the launch file and the firmware bounds wheel references, not body velocity.  Both inputs therefore use
``Limit.operator_required`` and every call is refused until the site supplies its envelope (site-limits.example.json
shows the overlay).  The package is model-authored and unreviewed; it is checked on the fake backend only.
"""

import math
import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: The upstream serial node and the motor firmware it talks to.
NODE = "script/base_control.py"
FIRMWARE = "document/arduino/motor_control/motor_control.ino"
LAUNCH = "launch/includes/adlink_ddsbot_base.launch.xml"


class AdlinkDdsbot(Driver):
    device_id = "adlink-ddsbot"
    device_kind = "robot.mobile_base"
    mode = "hardware"
    risk = "R2"
    native = "base_control:BaseControl"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeBaseControl"}
    vendor, model = "ADLINK Technology", "DDSBot differential-drive base"
    display_name = "ADLINK DDSBot mobile base"
    tags = ["mobile robot", "differential drive", "ros 1", "serial", "arduino"]
    facts = [
        Fact("The base node subscribes to cmd_vel (geometry_msgs/Twist) and publishes base_odom (nav_msgs/Odometry)",
             source="upstream_code", ref=f"{NODE}:43-44"),
        Fact("The node sends the motor command as left,right,checksum, where the checksum is the sum of the character "
             "lengths of the two wheel-speed strings", source="upstream_code", ref=f"{NODE}:121-125"),
        Fact("The node reads a reply line and splits it on ',' into two wheel speeds in deg/sec",
             source="upstream_code", ref=f"{NODE}:68-74"),
        Fact("The body twist is converted to wheel speeds with VR = vx + wheelSep/2.0*wz and VL = vx - wheelSep/2.0*wz, "
             "then to deg/sec with 180.0/math.pi/wheelRad", source="upstream_code", ref=f"{NODE}:117-120"),
        Fact("The node opens the serial port with a 10 s read timeout", source="upstream_code", ref=f"{NODE}:30"),
        Fact("The node uses string.split(line, ',') to split the reply line (the Python 2 module-level split API)",
             source="upstream_code", ref=f"{NODE}:69"),
        Fact("The shipped launch file configures the base node for /dev/uno at 57600 baud",
             source="upstream_code", ref=f"{LAUNCH}:7-8"),
        Fact("The launch file declares wheel_separation (0.15 m) and wheel_radius (0.0335 m) arguments",
             source="upstream_code", ref=f"{LAUNCH}:3-4"),
        Fact("The firmware parses the third field as the checksum and compares it with the command length minus 2 minus "
             "the checksum length", source="upstream_code", ref=f"{FIRMWARE}:109-118"),
        Fact("The firmware declares min_ref=110 and max_ref=350",
             source="upstream_code", ref=f"{FIRMWARE}:59-60"),
        Fact("The firmware adjusts nonzero wheel references using max_ref, min_ref and a steering correction",
             source="upstream_code", ref=f"{FIRMWARE}:120-158"),
        Fact("When the left wheel-speed reference is exactly zero, the firmware sets the left PWM outputs to 0",
             source="upstream_code", ref=f"{FIRMWARE}:281-286"),
        Fact("When the right wheel-speed reference is exactly zero, the firmware sets the right PWM outputs to 0",
             source="upstream_code", ref=f"{FIRMWARE}:337-342"),
        Fact("The firmware reports the two wheel speeds as integers in deg/sec with a CRLF terminator",
             source="upstream_code", ref=f"{FIRMWARE}:387-390"),
        Fact("The firmware declares timer_period=20 ms, odom_pub_period=40 ms and their ratio as odom_pub_thres",
             source="upstream_code", ref=f"{FIRMWARE}:31-33"),
        Fact("The firmware's odom_pub compile-time flag is false", source="upstream_code", ref=f"{FIRMWARE}:20"),
        Fact("When odom_pub is false the firmware prints '0,0' instead of the measured wheel speeds",
             source="upstream_code", ref=f"{FIRMWARE}:392-394"),
        Fact("The firmware sets the serial read timeout to 50 ms",
             source="upstream_code", ref=f"{FIRMWARE}:93"),
        Fact("On a bad checksum the firmware returns without zeroing the wheel references; the assignments are commented out",
             source="upstream_code", ref=f"{FIRMWARE}:109-118"),
        Fact("When no serial input is available, the firmware loop only delays 50 ms",
             source="upstream_code", ref=f"{FIRMWARE}:160-162"),
    ]
    safe_state = ("unconfirmed: the latch refuses new motion and a zero wheel-speed frame is requested, but no "
                  "stop acknowledgement is available; the robot may still move and the e-stop stays failed and latched")

    # -- observations -------------------------------------------------------------------------------------------
    @read("wheel_speed_left", unit="deg/s", description="Reported left speed; pinned odom_pub=false sends placeholder zero")
    def wheel_speed_left(self):
        return self._read_reply()[0]

    @read("wheel_speed_right", unit="deg/s", description="Reported right speed; pinned odom_pub=false sends placeholder zero")
    def wheel_speed_right(self):
        return self._read_reply()[1]

    @read("body_linear_velocity", unit="m/s",
          description="Derived from reported wheel speeds; pinned firmware zeros are not measured body velocity")
    def body_linear_velocity(self):
        return self._body_twist(*self._read_reply())[0]

    @read("body_angular_velocity", unit="rad/s",
          description="Derived from reported wheel speeds; pinned firmware zeros are not measured yaw rate")
    def body_angular_velocity(self):
        return self._body_twist(*self._read_reply())[1]

    # -- motion -------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.mobile_base.v1", long_running=True, cancellable=True,
            description="Drive a bounded body twist, then write a zero wheel-speed reference. distance_m and "
                        "heading_rad integrate the commanded twist over the command time; they are not measured "
                        "odometry.",
            input={
                "linear_velocity": Field(
                    description="Forward body velocity",
                    limit=Limit.operator_required(
                        "no text file of the clone states a body velocity range; the wheel radius and separation are "
                        "launch parameters and the firmware bounds wheel references, not body velocity, so the site "
                        "supplies the transit speed")),
                "angular_velocity": Field(
                    description="Yaw rate",
                    limit=Limit.operator_required(
                        "no text file of the clone states a body yaw-rate range; the wheel separation is a launch "
                        "parameter and the firmware bounds wheel references, not body velocity, so the site supplies "
                        "the turn rate")),
                "duration_s": Field(
                    description="Command duration; the class caps it at 300 s",
                    limit=Limit.operator_required(
                        "the class caps the duration at 300 s; the site supplies its own supervised-run maximum")),
            })
    def drive(self, linear_velocity, angular_velocity, duration_s):
        duration = max(0.0, float(duration_s))
        if duration == 0.0:
            self._command(0.0, 0.0)
            return {"distance_m": 0.0, "heading_rad": 0.0}
        distance = 0.0
        heading = 0.0
        started = time.monotonic()
        last = started
        try:
            while True:
                self.check_cancelled()
                self._command(linear_velocity, angular_velocity)
                now = time.monotonic()
                step = now - last
                last = now
                distance += abs(float(linear_velocity)) * step
                heading += float(angular_velocity) * step
                remaining = duration - (now - started)
                if remaining <= 0.0:
                    break
                time.sleep(min(0.1, remaining))
        finally:
            # The zero frame goes out even when the runtime cancels this action (the e-stop path also writes it).
            self._command(0.0, 0.0)
        return {"distance_m": distance, "heading_rad": heading}

    @action(name="x-cap.adlink-ros.stop_drive.v1",
            description="Request zero wheel speeds; this unacknowledged serial write does not confirm a stop",
            output={"zero_speed_reference": Field(
                "boolean", description="True once the zero wheel-speed frame has been written")})
    def stop_drive(self):
        self._command(0.0, 0.0)
        return {"zero_speed_reference": True}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Request zero speed, then refuse to certify an unacknowledged hardware stop."""
        self._command(0.0, 0.0)
        raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                           "zero-speed frame sent without an acknowledgement; odom_pub=false is not stop evidence")

    def setup(self):
        # The upstream object starts two ROS timers; this in-process driver owns the serial link, so stop them.
        for name in ("timer_odom", "timer_cmd"):
            timer = getattr(self.native, name, None)
            shutdown = getattr(timer, "shutdown", None)
            if callable(shutdown):
                shutdown()
        # The node's 10 s read timeout is too long for a bounded read; this is an execution bound, not a device limit.
        self.native.serial.timeout = 0.2

    def teardown(self):
        close = getattr(self.native.serial, "close", None)
        if callable(close):
            close()

    # -- helpers ------------------------------------------------------------------------------------------------
    def _command(self, linear_velocity, angular_velocity):
        """Set the body twist and run the upstream wheel-speed conversion and serial write."""
        self.native.trans_x = float(linear_velocity)
        self.native.rotat_z = float(angular_velocity)
        self.native.timerCmdCB(None)

    def _read_reply(self):
        """One fresh frame of the two firmware wheel speeds (deg/sec)."""
        line = self.native.serial.readline()
        text = line.decode("ascii", "replace") if isinstance(line, bytes) else str(line)
        parts = [part.strip() for part in text.split(",")]
        if len(parts) != 2:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the base did not answer with 'left,right' (got {text.strip()!r})")
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the base answered with non-numeric wheel speeds {text.strip()!r}") from None

    def _body_twist(self, left_deg_s, right_deg_s):
        """The upstream derivation (base_control.py:77-81): wheel deg/sec to body m/s and rad/s."""
        left = left_deg_s * math.pi / 180.0 * self.native.wheelRad
        right = right_deg_s * math.pi / 180.0 * self.native.wheelRad
        return (right + left) / 2.0, (right - left) / self.native.wheelSep
