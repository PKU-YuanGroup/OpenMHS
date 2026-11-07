"""OpenMHS driver for gh.boston-dynamics/spot-sdk: a Boston Dynamics Spot mobile robot through
bosdyn.client.robot:Robot.

The upstream SDK is a network client, so every method below is a plain ``def`` and every call is a gRPC round
trip to the robot.  The driver exposes identity and safety telemetry, a writable motor-power state, and the
native stop path:

* reads: the cached RobotId fields, the power and E-Stop state, the arm presence, the cached usernames, the
  frame names of the latest frame-tree snapshot, and two hardware-configuration flags;
* ``cap.device.configure.v1``: ``motors_on`` writes call ``Robot.power_on`` or ``Robot.power_off``; the latter
  uses the SDK's safe power-off path (``cut_immediately=False``), which sits the robot down before cutting
  motor power (docs/concepts/robot_services.md:45);
* the native stop is ``Robot.power_off`` with ``cut_immediately=True``.  The independent hardware stop is the
  physical E-Stop button (docs/python/quickstart.md:379); the software E-Stop service is a heartbeat service,
  not a replacement for it (docs/concepts/estop_service.md:11-19).

This package is model-authored and unreviewed: it is checked on the fake backend only, and the loader refuses
its hardware backend (R2) until a human signs ``reviewed_by``.  The pinned commit is
04537ddafe0641d1751af3eb9e76cb785fc18594.
"""

from mhs.driver import Driver, Fact, estop, read, write

ROBOT = "python/bosdyn-client/src/bosdyn/client/robot.py"
ROBOT_ID_PROTO = "protos/bosdyn/api/robot_id.proto"
ROBOT_STATE_PROTO = "protos/bosdyn/api/robot_state.proto"
QUICKSTART = "docs/python/quickstart.md"
ROBOT_SERVICES = "docs/concepts/robot_services.md"
ESTOP_SERVICE = "docs/concepts/estop_service.md"


class Spot(Driver):
    device_id = "spot"
    device_kind = "robot.mobile_base"
    mode = "hardware"
    risk = "R2"
    native = "bosdyn.client.robot:Robot"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeRobot"}
    vendor, model = "Boston Dynamics", "Spot quadruped mobile robot"
    display_name = "Boston Dynamics Spot (bosdyn.client.robot.Robot)"
    tags = ["mobile robot", "quadruped", "spot", "boston dynamics", "motor power", "robot state", "e-stop"]
    facts = [
        Fact("The quickstart tells the operator to push the E-Stop button and watch the robot do a glide-stop",
             source="vendor_doc", ref=f"{QUICKSTART}:379"),
        Fact("The E-Stop service is a heartbeat-based software service; its stop levels are CUT (actuator power "
             "is cut immediately), SETTLE_THEN_CUT (the robot stops, sits down, then cuts actuator power) and NONE",
             source="vendor_doc", ref=f"{ESTOP_SERVICE}:11-19"),
        Fact("The robot can have software and hardware E-Stops at the same time, and if any one E-Stop is activated "
             "the robot cannot power on its actuators", source="vendor_doc", ref=f"{ROBOT_SERVICES}:65"),
        Fact("Abruptly turning off motor power causes the robot to drop, so clients are encouraged to use "
             "SETTLE_THEN_CUT or SafePowerOffCommand; the safe power off sits the robot down before cutting motor "
             "power", source="vendor_doc", ref=f"{ROBOT_SERVICES}:34-45"),
        Fact("Robot.power_on blocks until the robot powers on", source="upstream_code", ref=f"{ROBOT}:625-626"),
        Fact("Robot.power_off(cut_immediately=True) cuts power immediately; cut_immediately=False issues a safe "
             "power off command", source="upstream_code", ref=f"{ROBOT}:642-648"),
        Fact("Robot.get_cached_robot_id returns the RobotId proto, querying it from the robot if it is not cached",
             source="upstream_code", ref=f"{ROBOT}:300-309"),
        Fact("Robot.get_cached_hardware_hardware_configuration returns the cached HardwareConfiguration proto",
             source="upstream_code", ref=f"{ROBOT}:311-320"),
        Fact("Robot.get_cached_usernames returns the sorted usernames matching the serial number in the token cache",
             source="upstream_code", ref=f"{ROBOT}:476-484"),
        Fact("Robot.get_frame_tree_snapshot returns the kinematic state's transforms_snapshot",
             source="upstream_code", ref=f"{ROBOT}:704-719"),
        Fact("HardwareConfiguration.redundant_safety_stop_enabled says the robot is configured with a redundant "
             "safety stop", source="upstream_code", ref=f"{ROBOT_STATE_PROTO}:63"),
        Fact("RobotId carries serial_number, species and nickname fields", source="upstream_code",
             ref=f"{ROBOT_ID_PROTO}:21-33"),
    ]
    safe_state = ("motor power is cut immediately with power_off(cut_immediately=True); the robot is not held up, "
                  "so the physical E-Stop button and the operator's exclusion zone are the protective functions")
    #: The physical E-Stop button the quickstart documents (SAFE-045 for this R2 hardware driver)
    estop_physical_ref = f"{QUICKSTART}:379"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("serial_number", type="string", description="Serial number reported by the robot-id service")
    def get_serial_number(self):
        return self.native.get_cached_robot_id().serial_number

    @read("nickname", type="string", description="Customer-supplied nickname reported by the robot-id service")
    def get_nickname(self):
        return self.native.get_cached_robot_id().nickname

    @read("species", type="string", description="Robot species reported by the robot-id service")
    def get_species(self):
        return self.native.get_cached_robot_id().species

    @read("motors_on", type="boolean", description="True when the robot reports motor power on")
    def get_motors_on(self):
        return self.native.is_powered_on()

    @read("estopped", type="boolean",
          description="True when the robot's E-Stop service reports an E-Stop")
    def get_estopped(self):
        return self.native.is_estopped()

    @read("has_arm", type="boolean", description="True when the robot reports an arm attached")
    def get_has_arm(self):
        return self.native.has_arm()

    @read("usernames", type="array", items="string",
          description="Usernames this client has cached for the robot")
    def get_usernames(self):
        return self.native.get_cached_usernames()

    @read("frame_names", type="array", items="string",
          description="Frame names in the latest frame-tree snapshot")
    def get_frame_names(self):
        return sorted(self.native.get_frame_tree_snapshot().child_to_parent_edge_map)

    @read("can_power_off_robot", type="boolean",
          description="Hardware configuration: the robot accepts a power-off request")
    def get_can_power_off_robot(self):
        return self.native.get_cached_hardware_hardware_configuration().can_power_command_request_off_robot

    @read("redundant_safety_stop_enabled", type="boolean",
          description="Hardware configuration: a redundant safety stop is installed")
    def get_redundant_safety_stop_enabled(self):
        return self.native.get_cached_hardware_hardware_configuration().redundant_safety_stop_enabled

    # -- configuration --------------------------------------------------------------------------------------------
    @write("motors_on", type="boolean", risk="R2",
           description="Power the motors on (True) or off (False); False uses the SDK's safe power-off path")
    def set_motors_on(self, value):
        if value:
            self.native.power_on()
        else:
            self.native.power_off(cut_immediately=False)

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="power_off")
    def stop(self):
        """The native stop: cut motor power immediately (the runtime latches first)."""
        self.native.power_off(cut_immediately=True)
