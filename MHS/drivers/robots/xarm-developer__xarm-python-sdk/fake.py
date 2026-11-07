"""Fake backend of the xArm driver: an in-memory stand-in for xarm.wrapper.xarm_api:XArmAPI.

Gate G7: every public member defined here is a method or property of XArmAPI (xarm/wrapper/xarm_api.py at the pinned
commit d911319cebc45142613e18086aabb8067b18ab7f), with the upstream parameter names and defaults.  Like the upstream
methods, the motion commands return an integer API code (0 is success, doc/api/xarm_api_code.md:15-58) and the
getters return ``(code, value)``.  The arm starts from the initial values the SDK keeps before it has talked to a
controller (xarm/x3/base.py:126-127: all joints at 0 rad and a tool pose of 201.5, 0, 140.5 mm with roll 3.1415926 rad),
enabled and in mode 0 and state 0 (the state the upstream examples prepare, example/wrapper/xarm7/2001-move_joint.py
:44-46).

What it does not do: no kinematics (a joint move does not change the reported tool pose and the reverse), no motion
over time (a move with wait=True or wait=False is finished when the call returns), no speed or acceleration, and none
of the SDK's own range checks.  The commands it received are kept in ``_commands`` and four underscore hooks let a test
put the arm in a state the SDK documents (a one-shot return code for a move or for a getter, a controller error, a
firmware version).  Nothing here talks to a device.
"""

import math

# xarm/x3/base.py:126-127 (initial tool pose in mm and rad, initial joint angles in rad)
_START_POSITION = (201.5, 0.0, 140.5, 3.1415926, 0.0, 0.0)
_START_ANGLES = (0.0,) * 7


def _radians(values, is_radian):
    return [float(value) if is_radian else math.radians(float(value)) for value in values]


class FakeXArmAPI:
    def __init__(self, port=None, is_radian=False, do_not_open=False, **kwargs):
        self._default_is_radian = bool(is_radian)
        self._angles = list(_START_ANGLES)                      # rad
        self._position = list(_START_POSITION)                  # x, y, z in mm and roll, pitch, yaw in rad
        self._state = 0
        self._mode = 0
        self._enabled = True
        self._error_code = 0
        self._warn_code = 0
        self._connected = True
        self._firmware = (2, 5, 0)                              # a stand-in value; the real arm reports its own
        self._forced = None                                     # one-shot API code for the next motion command
        self._forced_read = None                                # one-shot API code for the next getter
        self._forced_read_after_move = None                     # ... armed by the next move that finishes
        self._commands = []                                     # (name, keyword arguments) of every command received

    # -- properties of XArmAPI ---------------------------------------------------------------------------
    @property
    def state(self):
        return self._state

    @property
    def mode(self):
        return self._mode

    @property
    def error_code(self):
        return self._error_code

    @property
    def warn_code(self):
        return self._warn_code

    @property
    def connected(self):
        return self._connected

    @property
    def version_number(self):
        return self._firmware

    @property
    def axis(self):
        return 7

    @property
    def device_type(self):
        return 7

    # -- reads: (code, value) -----------------------------------------------------------------------------
    def get_servo_angle(self, servo_id=None, is_radian=None, is_real=False):
        radian = self._default_is_radian if is_radian is None else is_radian
        angles = [value if radian else math.degrees(value) for value in self._angles]
        if servo_id is None or servo_id == 8:
            return self._read_code(), angles
        return self._read_code(), angles[servo_id - 1]

    def get_position(self, is_radian=None):
        radian = self._default_is_radian if is_radian is None else is_radian
        x, y, z, roll, pitch, yaw = self._position
        return self._read_code(), [x, y, z] + [value if radian else math.degrees(value) for value in (roll, pitch, yaw)]

    # -- motion: an API code -------------------------------------------------------------------------------
    def set_servo_angle(self, servo_id=None, angle=None, speed=None, mvacc=None, mvtime=None, relative=False,
                        is_radian=None, wait=False, timeout=None, radius=None, **kwargs):
        radian = self._default_is_radian if is_radian is None else is_radian
        self._commands.append(("set_servo_angle", {"servo_id": servo_id, "angle": angle, "is_radian": radian,
                                                   "wait": wait, "timeout": timeout, "speed": speed}))
        code = self._motion_code()
        if code == 0:
            if servo_id is None or servo_id == 8:
                self._angles = _radians(angle, radian)
            else:
                self._angles[servo_id - 1] = _radians([angle], radian)[0]
        return code

    def set_position(self, x=None, y=None, z=None, roll=None, pitch=None, yaw=None, radius=None, speed=None,
                     mvacc=None, mvtime=None, relative=False, is_radian=None, wait=False, timeout=None, **kwargs):
        radian = self._default_is_radian if is_radian is None else is_radian
        self._commands.append(("set_position", {"x": x, "y": y, "z": z, "roll": roll, "pitch": pitch, "yaw": yaw,
                                                "is_radian": radian, "wait": wait, "timeout": timeout, "speed": speed}))
        code = self._motion_code()
        if code == 0:
            for index, value in enumerate((x, y, z)):
                if value is not None:
                    self._position[index] = float(value)
            for index, value in enumerate((roll, pitch, yaw), start=3):
                if value is not None:
                    self._position[index] = _radians([value], radian)[0]
        return code

    def vc_set_joint_velocity(self, speeds, is_radian=None, is_sync=True, duration=-1, **kwargs):
        radian = self._default_is_radian if is_radian is None else is_radian
        self._commands.append(("vc_set_joint_velocity", {"speeds": list(speeds), "is_radian": radian,
                                                         "is_sync": is_sync, "duration": duration}))
        return self._motion_code()

    def _motion_code(self):
        """The API code of a motion command now (xarm_api_code.md:15-58): 0, or why the arm refuses."""
        if self._forced is not None:
            code, self._forced = self._forced, None
            return code
        if self._error_code != 0:
            return 1            # there are errors that have not been cleared
        if not self._enabled:
            return -2           # not ready: motion is not enabled or the state is not set
        if self._state >= 3:
            return 9            # the state is not ready to move (paused or stopped)
        self._forced_read, self._forced_read_after_move = self._forced_read_after_move, None
        return 0

    # -- state: an API code (emergency_stop returns nothing, as upstream) -------------------------------------
    def emergency_stop(self):
        self._commands.append(("emergency_stop", {}))
        self._state = 4                                         # xarm/x3/xarm.py:1111-1115 (set_state(4))

    def motion_enable(self, enable=True, servo_id=None):
        self._commands.append(("motion_enable", {"enable": enable, "servo_id": servo_id}))
        self._enabled = bool(enable)
        return 0

    def set_mode(self, mode=0, detection_param=0):
        self._commands.append(("set_mode", {"mode": mode}))
        self._mode = mode
        return 0

    def set_state(self, state=0):
        self._commands.append(("set_state", {"state": state}))
        self._state = state
        return 0

    def clean_error(self):
        self._commands.append(("clean_error", {}))
        self._error_code = 0
        return 0

    def clean_warn(self):
        self._commands.append(("clean_warn", {}))
        self._warn_code = 0
        return 0

    def disconnect(self):
        self._commands.append(("disconnect", {}))
        self._connected = False

    def _read_code(self):
        """The API code of a getter now: 0, or the code ``_force_read_code`` set for this one call."""
        code, self._forced_read = (self._forced_read or 0), None
        return code

    # -- hooks for test_driver.py (not XArmAPI members, never used by the driver) ---------------------------
    def _force_code(self, code):
        """The next motion command returns ``code`` (and moves nothing)."""
        self._forced = code

    def _force_read_code(self, code):
        """The first get_servo_angle or get_position after the next finished move returns ``code``."""
        self._forced_read_after_move = code

    def _set_error(self, code):
        """The controller reports error ``code`` (1 is the Emergency Stop Button, xarm_api_code.md:68) until cleaned."""
        self._error_code = code

    def _set_firmware(self, version):
        self._firmware = tuple(version)
