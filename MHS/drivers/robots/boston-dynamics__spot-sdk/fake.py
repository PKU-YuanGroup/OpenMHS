"""Fake backend of the Spot driver: an in-memory stand-in for bosdyn.client.robot:Robot.

Gate G7: every public member defined here is a method of Robot (python/bosdyn-client/src/bosdyn/client/robot.py
at the pinned commit 04537ddafe0641d1751af3eb9e76cb785fc18594), with the upstream parameter names and defaults.
The canned state below is test data, not a fact: the real robot reports its own serial number, nickname, species,
usernames, frame tree, hardware configuration and power state.  The fake starts with the motors off and no E-Stop
active; the underscore hooks let a test change those states.

What it does not do: no network, no time sync, no lease, no motion over time.  ``power_on`` and ``power_off``
change the reported motor-power state immediately.  The commands it received are kept in ``_commands``.
"""


class _RobotId:
    """Stand-in for bosdyn.api.RobotId (protos/bosdyn/api/robot_id.proto:19-38)."""

    def __init__(self):
        self.serial_number = "fake-spot-0001"                # placeholder
        self.species = "spot"                                # placeholder
        self.version = "fake"                                # placeholder
        self.nickname = "fake-spot"                          # placeholder
        self.computer_serial_number = "fake-computer-0001"   # placeholder


class _HardwareConfiguration:
    """Stand-in for bosdyn.api.HardwareConfiguration (protos/bosdyn/api/robot_state.proto:49-64)."""

    def __init__(self):
        self.can_power_command_request_off_robot = True      # placeholder
        self.can_power_command_request_cycle_robot = False   # placeholder
        self.can_power_command_request_payload_ports = False # placeholder
        self.can_power_command_request_wifi_radio = False    # placeholder
        self.has_audio_visual_system = False                 # placeholder
        self.redundant_safety_stop_enabled = True            # placeholder


class _FrameTreeSnapshot:
    """Stand-in for bosdyn.api.FrameTreeSnapshot (protos/bosdyn/api/geometry.proto:110-187)."""

    def __init__(self):
        self.child_to_parent_edge_map = {"body": None, "odom": None, "vision": None}  # placeholder


class FakeRobot:
    """In-memory Robot with the upstream method signatures and a small canned state."""

    def __init__(self, **_options):
        self._robot_id = _RobotId()
        self._hardware_config = _HardwareConfiguration()
        self._frame_tree = _FrameTreeSnapshot()
        self._usernames = ["fake-user"]                      # placeholder
        self._powered_on = False                             # placeholder
        self._estopped = False                               # placeholder
        self._has_arm = True                                 # placeholder
        self._commands = []

    # -- cached identity and state ------------------------------------------------------------------------------
    def get_cached_robot_id(self, timeout=None):
        self._commands.append(("get_cached_robot_id", {"timeout": timeout}))
        return self._robot_id

    def get_cached_hardware_hardware_configuration(self, timeout=None):
        self._commands.append(("get_cached_hardware_hardware_configuration", {"timeout": timeout}))
        return self._hardware_config

    def get_cached_usernames(self):
        self._commands.append(("get_cached_usernames", {}))
        return list(self._usernames)

    def get_frame_tree_snapshot(self, timeout=None):
        self._commands.append(("get_frame_tree_snapshot", {"timeout": timeout}))
        return self._frame_tree

    def has_arm(self, timeout=None):
        self._commands.append(("has_arm", {"timeout": timeout}))
        return self._has_arm

    def is_estopped(self, timeout=None):
        self._commands.append(("is_estopped", {"timeout": timeout}))
        return self._estopped

    def is_powered_on(self, timeout=None):
        self._commands.append(("is_powered_on", {"timeout": timeout}))
        return self._powered_on

    # -- power ---------------------------------------------------------------------------------------------------
    def power_on(self, timeout_sec=20, update_frequency=1.0, timeout=None):
        self._commands.append(("power_on", {"timeout_sec": timeout_sec,
                                            "update_frequency": update_frequency, "timeout": timeout}))
        self._powered_on = True

    def power_off(self, cut_immediately=False, timeout_sec=20, update_frequency=1.0, timeout=None):
        self._commands.append(("power_off", {"cut_immediately": cut_immediately, "timeout_sec": timeout_sec,
                                             "update_frequency": update_frequency, "timeout": timeout}))
        self._powered_on = False

    # -- hooks for test_driver.py (not Robot members, never used by the driver) ---------------------------------
    def _set_powered_on(self, value):
        self._powered_on = bool(value)

    def _set_estopped(self, value):
        self._estopped = bool(value)

    def _set_has_arm(self, value):
        self._has_arm = bool(value)
