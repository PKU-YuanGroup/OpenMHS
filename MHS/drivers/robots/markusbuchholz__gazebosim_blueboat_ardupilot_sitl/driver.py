"""OpenMHS driver for the BlueBoat Gazebo/ArduPilot SITL ROS interface.

The pinned repository ships a Python ROS 2 node,
``BlueboatROSInterface``, that bridges ROS topics to a MAVLink ArduPilot
Rover and reads ``VFR_HUD``, ``ATTITUDE``, ``RAW_IMU`` and
``SERVO_OUTPUT_RAW`` into a shared ``data`` dictionary.  This package binds
that concrete node class directly: the ROS surface itself has no service or
action, so a configuration-only RosDriver cannot declare an acknowledged
native stop for the software e-stop the runtime requires at R2.  The driver
calls the class methods instead of inventing a ROS service.

The two motor commands use the node's ``send_motor_thrust`` path, whose
docstring states the 0-100 percent range.  The node offers no acknowledged
stop: ``send_motor_thrust`` and ``disarm_vehicle`` only transmit MAVLink
commands (a failed motor-test send is only logged) and read no COMMAND_ACK or
heartbeat.  The e-stop still sends zero motor-test thrust to both motors and
the disarm command, then reports ``MHS.SAFETY.SAFE_STATE_UNREACHED`` so the
latch stays held; the zero-thrust-and-disarm action is an ordinary
transmission-only command, not a safe-state action (model review,
2026-11-05).

The node's MAVLink endpoint defaults to ``udpin:0.0.0.0:14550``, where ArduPilot
SITL or a real BlueBoat can send; its constructor waits for a heartbeat without
a timeout and arms the vehicle.  The package declares only the fake backend.

Every fact cites the pinned clone at
96b01666d9f8e7ec19b25df3f8709c2aed2e1363.  The fake backend is a Python
stand-in for this node class: it starts no ROS, MAVLink or Gazebo process.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: The pinned ROS node class and its data/command paths.
_NODE = "gz_ws/extras_interface/ros2_blueboat_interface.py"

#: send_motor_thrust's docstring: thrust_value is 0-100 for percent.
_THRUST_REF = f"{_NODE}:392"
_THRUST_LIMIT = Limit(min=0, max=100, unit="%", source="upstream_code", ref=_THRUST_REF)

#: The constructor creates self.data and starts the MAVLink listener thread.
_DATA_REF = f"{_NODE}:173-177"

#: The observation accessors read VFR_HUD, ATTITUDE and SERVO_OUTPUT_RAW.
_COMPASS_REF = f"{_NODE}:413-429"
_SERVO_REF = f"{_NODE}:299-322"
_ATTITUDE_REF = f"{_NODE}:431-490"

#: set_stabilize_mode_and_arm checks base_mode for the armed flag.
_ARMED_REF = f"{_NODE}:252-261"


class BlueboatSitl(Driver):
    device_id = "blueboat-sitl"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    risk = "R2"
    native = "ros2_blueboat_interface:BlueboatROSInterface"
    backends = {"fake": ".fake:FakeBlueboat"}
    tags = ["ros", "ros2", "simulation", "gazebo", "blueboat", "usv", "mavlink", "thruster"]
    display_name = "BlueBoat Gazebo/ArduPilot SITL"
    vendor = "markusbuchholz"
    model = "BlueBoat"
    facts = [
        Fact("BlueboatROSInterface is an rclpy Node that subscribes to /blueboat/cmd_vel "
             "(geometry_msgs/Twist) and to the uuv_name-prefixed send_port_motor_0_100_thrust and "
             "send_stbd_motor_0_100_thrust topics (std_msgs/Float32), and publishes "
             "/blueboat/servo_outputs (std_msgs/Int32MultiArray), /compass (std_msgs/Float32), "
             "/imu (sensor_msgs/Imu) and the three Euler-angle Float32 topics.",
             source="upstream_code", ref=f"{_NODE}:86-170"),
        Fact("The node declares uuv_name with default 'blueboat'.",
             source="upstream_code", ref=f"{_NODE}:42"),
        Fact("The port and starboard motor callbacks cast the Float32 data to int and call "
             "send_motor_thrust with hard-coded motor numbers 3 and 4.",
             source="upstream_code", ref=f"{_NODE}:376-386"),
        Fact("send_motor_thrust sends MAV_CMD_DO_MOTOR_TEST with thrust_type 0 (percent) and "
             "duration 1.0 s; its docstring states thrust_value is 0-100 for percent.",
             source="upstream_code", ref=f"{_NODE}:388-408"),
        Fact("arm_vehicle sends MAV_CMD_COMPONENT_ARM_DISARM with param1 1; disarm_vehicle sends "
             "the same command with param1 0. Both methods only call command_long_send and do not "
             "read a heartbeat acknowledgement.",
             source="upstream_code", ref=f"{_NODE}:263-285"),
        Fact("send_motor_thrust wraps command_long_send in a try/except whose handler only logs the "
             "error.",
             source="upstream_code", ref=f"{_NODE}:397-411"),
        Fact("The constructor initialises self.data to an empty dictionary and starts a daemon "
             "MAVLink listener thread.",
             source="upstream_code", ref=_DATA_REF),
        Fact("mavlink_listener stores each received MAVLink message as a dict under its message type "
             "in self.data while rclpy.ok() is true.",
             source="upstream_code", ref=f"{_NODE}:285-297"),
        Fact("The node declares mavlink_connection with default udpin:0.0.0.0:14550.",
             source="upstream_code", ref=f"{_NODE}:39"),
        Fact("The constructor opens the MAVLink connection and calls wait_heartbeat.",
             source="upstream_code", ref=f"{_NODE}:35-52"),
        Fact("The constructor calls set_stabilize_mode_and_arm.",
             source="upstream_code", ref=f"{_NODE}:35-71"),
        Fact("set_stabilize_mode_and_arm sends MAV_CMD_COMPONENT_ARM_DISARM with param1 1.",
             source="upstream_code", ref=f"{_NODE}:232-250"),
        Fact("publish_compass reads the VFR_HUD heading, normalises it with heading % 360 and "
             "publishes it as a Float32 on /compass.",
             source="upstream_code", ref=_COMPASS_REF),
        Fact("_publish_servo_outputs reads servo1_raw through servo8_raw from the SERVO_OUTPUT_RAW "
             "snapshot, with 0 for a missing field, and publishes them as an Int32MultiArray.",
             source="upstream_code", ref=_SERVO_REF),
        Fact("publish_imu reads ATTITUDE roll, pitch and yaw in radians and RAW_IMU linear "
             "acceleration, publishes normalised Euler angles as Float32 degrees and builds a "
             "sensor_msgs/Imu message.",
             source="upstream_code", ref=_ATTITUDE_REF),
        Fact("set_stabilize_mode_and_arm waits for HEARTBEAT messages and checks "
             "base_mode & MAV_MODE_FLAG_SAFETY_ARMED; it raises when the vehicle did not arm.",
             source="upstream_code", ref=_ARMED_REF),
        Fact("JoystickNode publishes axis 4 and axis 1 times 100 times 0.5 as port and starboard thrust "
             "and calls arm_vehicle for button 7 and disarm_vehicle for button 6.",
             source="upstream_code", ref=f"{_NODE}:559-584"),
        Fact("main starts 'ros2 run joy joy_node' with subprocess.Popen before creating the nodes.",
             source="upstream_code", ref=f"{_NODE}:589-602"),
        Fact("changing_modes.py constructs BoatController on udpin:0.0.0.0:14550 and keeps a commented "
             "udpin:192.168.2.1:14550 alternative.",
             source="upstream_code", ref="gz_ws/src/extras_boat/changing_modes.py:119-120"),
    ]
    safe_state = (
        "No acknowledged stop: the e-stop sends zero motor-test thrust to motors 3 and 4 and a MAVLink "
        "disarm through the node, which only transmits them and reads no COMMAND_ACK or heartbeat, so it "
        "reports SAFE_STATE_UNREACHED with the latch held; ArduPilot SITL and Gazebo keep running, a "
        "joystick or other MAVLink client can re-arm, and nothing shows that the boat stopped."
    )
    fidelity = {
        "engine": "analytic:Python fake of BlueboatROSInterface (no ROS, MAVLink or physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "The fake is a stateful Python stand-in; it runs no ROS node, MAVLink "
                     "connection, Gazebo world or wall-clock timer, so it makes no trajectory "
                     "or state-hash replay claim.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake substitutes for the BlueboatROSInterface class only; it starts no ROS 2 "
            "node, MAVLink connection, ArduPilot SITL, Gazebo world or sensor",
            "the motor commands are recorded as percentages; the fake integrates no thrust, "
            "hydrodynamics, ArduPilot motor test or vehicle motion",
            "the observation values are placeholders and do not come from VFR_HUD, ATTITUDE, "
            "RAW_IMU or SERVO_OUTPUT_RAW traffic",
            "the fake's arm and disarm change the stored HEARTBEAT base_mode at once; upstream they only "
            "transmit the command, and base_mode changes only if ArduPilot's next HEARTBEAT reports it",
            "the e-stop and the zero-thrust-and-disarm action record the calls; upstream they are "
            "transmission-only MAVLink commands (no COMMAND_ACK, heartbeat or motor read-back), so the "
            "e-stop reports SAFE_STATE_UNREACHED and nothing proves that ArduPilot disarmed or that the "
            "boat stopped",
            "the reads return the node's last stored MAVLink message of each type with no age check, so "
            "after a link loss they keep serving stale values; the fake's snapshots never age",
            "live construction is not exercised: BlueboatROSInterface is an rclpy Node (it needs "
            "rclpy.init in the host process), waits for a MAVLink heartbeat on udpin:0.0.0.0:14550 "
            "without a timeout, arms the vehicle in its constructor and raises when arming fails, and "
            "starts a listener thread; a real BlueBoat sending MAVLink to that port would be armed and "
            "driven the same way (changing_modes.py keeps a commented 192.168.2.1 endpoint)",
            "the module's main() also starts joy_node and a JoystickNode that publishes -50..50 percent "
            "thrust on the same motor topics and arms or disarms from buttons 7 and 6; the 0-100 percent "
            "limit follows the send_motor_thrust docstring",
            "the ROS topic wiring, QoS, launch files, MAVLink connection and the ros_ign_bridge "
            "topics are outside this in-process fake",
        ],
    }

    @read("base_mode", type="integer", unit="1",
          description="MAVLink HEARTBEAT.base_mode bitmask as last received by the node")
    def base_mode(self):
        return self._heartbeat_field("base_mode")

    @read("heading_deg", unit="deg",
          description="VFR_HUD heading normalised to 0-360 degrees by the node")
    def heading_deg(self):
        vfr_hud = self._message("VFR_HUD")
        heading = vfr_hud.get("heading")
        if heading is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "VFR_HUD has no heading field")
        return float(heading) % 360.0

    @read("roll_rad", unit="rad", description="ATTITUDE roll in radians as last received")
    def roll_rad(self):
        return self._attitude_component("roll")

    @read("pitch_rad", unit="rad", description="ATTITUDE pitch in radians as last received")
    def pitch_rad(self):
        return self._attitude_component("pitch")

    @read("yaw_rad", unit="rad", description="ATTITUDE yaw in radians as last received")
    def yaw_rad(self):
        return self._attitude_component("yaw")

    @read("servo_outputs", type="array", items="integer", length=8, unit="us",
          description="SERVO_OUTPUT_RAW servo1_raw through servo8_raw in PWM microseconds")
    def servo_outputs(self):
        message = self._message("SERVO_OUTPUT_RAW")
        values = []
        for index in range(1, 9):
            value = message.get(f"servo{index}_raw")
            if value is None:
                raise DriverFailed("MHS.DEVICE.NOT_READY", f"SERVO_OUTPUT_RAW has no servo{index}_raw field")
            values.append(int(value))
        return values

    @action(name="x-cap.markusbuchholz.set_motor_thrust.v1", risk="R2",
            description="Command the port and starboard motor thrust percentages through the "
                        "node's MAV_CMD_DO_MOTOR_TEST path",
            input={
                "port_pct": Field("number", unit="%",
                                  description="Port motor (MAVLink motor 3) thrust in percent",
                                  limit=_THRUST_LIMIT),
                "stbd_pct": Field("number", unit="%",
                                  description="Starboard motor (MAVLink motor 4) thrust in percent",
                                  limit=_THRUST_LIMIT),
            },
            output={
                "port_pct": Field("number", unit="%", description="Port thrust value sent"),
                "stbd_pct": Field("number", unit="%", description="Starboard thrust value sent"),
            })
    def set_motor_thrust(self, port_pct, stbd_pct):
        self.native.send_motor_thrust(3, port_pct)
        self.native.send_motor_thrust(4, stbd_pct)
        return {"port_pct": port_pct, "stbd_pct": stbd_pct}

    @action(name="x-cap.markusbuchholz.arm.v1", risk="R2",
            description="Send the node's arm_vehicle MAVLink arm command",
            output={"requested": Field("boolean",
                                       description="True after the arm command was transmitted")})
    def arm(self):
        self.native.arm_vehicle()
        return {"requested": True}

    @action(name="x-cap.markusbuchholz.disarm.v1", risk="R2",
            description="Send the node's disarm_vehicle MAVLink disarm command",
            output={"requested": Field("boolean",
                                       description="True after the disarm command was transmitted")})
    def disarm(self):
        self.native.disarm_vehicle()
        return {"requested": True}

    @action(name="x-cap.markusbuchholz.stop.v1", risk="R2",
            description="Send zero motor-test thrust to both motors and the node's disarm command; "
                        "transmission only, not an acknowledged stop",
            output={"requested": Field("boolean",
                                       description="True after the zero-thrust and disarm commands "
                                                   "were transmitted")})
    def stop(self):
        self._command_zero_thrust_and_disarm()
        return {"requested": True}

    @estop
    def emergency_stop(self):
        """Send the zero-thrust and disarm commands, then refuse to certify them.

        The node only transmits MAV_CMD_DO_MOTOR_TEST and MAV_CMD_COMPONENT_ARM_DISARM and reads no
        acknowledgement, so the e-stop reports SAFE_STATE_UNREACHED and the latch stays held (model
        review, 2026-11-05).
        """
        self._command_zero_thrust_and_disarm()
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "zero motor-test thrust and a MAVLink disarm were transmitted without an acknowledgement; "
            "no acknowledged stop exists",
        )

    def _command_zero_thrust_and_disarm(self):
        self.native.send_motor_thrust(3, 0)
        self.native.send_motor_thrust(4, 0)
        self.native.disarm_vehicle()

    def _message(self, name):
        with self.native.data_lock:
            message = self.native.data.get(name)
        if not message:
            raise DriverFailed("MHS.DEVICE.NOT_READY",
                               f"the node has not received a {name} MAVLink message")
        return message

    def _heartbeat_field(self, name):
        heartbeat = self._message("HEARTBEAT")
        value = heartbeat.get(name)
        if value is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", f"HEARTBEAT has no {name} field")
        return int(value)

    def _attitude_component(self, name):
        attitude = self._message("ATTITUDE")
        value = attitude.get(name)
        if value is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", f"ATTITUDE has no {name} field")
        return float(value)
