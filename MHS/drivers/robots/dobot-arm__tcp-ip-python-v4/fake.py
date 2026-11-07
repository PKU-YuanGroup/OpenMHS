"""Fake backend of the Dobot V4 package: an in-memory stand-in for dobot_sdk.core.connection:DobotConnection.

The upstream driver talks to the arm through its TCP transport class, which sends one command line and reads one
text reply (dobot_sdk/core/connection.py:248-272, :357-369).  This fake replaces the socket with a model of the
controller's dashboard: ``send_receive_text`` records the command text, updates the arm state and answers with a
reply of the documented form ``ErrorID,{...},Command(...);`` (assets/SDK_API文档_完整版.md:1206-1218).  Gate G7: every
public member defined here is a member of DobotConnection at the pinned commit
55ec1ec82201aaf2e6d54aa47b6272bbaa14c815, with the upstream parameter names and defaults.

What it does not do: no motion over time (a queue command is finished when the call returns), no kinematics (a joint
move does not change the reported Cartesian pose and the reverse), no queue, and none of the controller's own range
checks.  The commands it received are kept in ``_commands`` and a few underscore hooks let a test put the arm in a
state the text documents (a one-shot command error, a controller error list, a robot mode).  Nothing here talks to
a device.

Every position in this file is placeholder test data, not a fact about an arm.
"""

import re

# placeholder: the joint angles the model starts at (an arm can be anywhere)
_START_ANGLES = (0.0, 0.0, 90.0, 0.0, 90.0, 0.0)
# placeholder: the Cartesian pose the model starts at (mm and degrees; an arm can be anywhere)
_START_POSE = (400.0, 0.0, 300.0, 180.0, 0.0, 0.0)
# placeholder: the robot mode number the model starts at
_START_MODE = 4
_COMMAND = re.compile(r"^(?P<name>[A-Za-z][A-Za-z0-9_]*)\((?P<args>.*)\)$")
_POINT = re.compile(r"(?:joint|pose)=\{(?P<values>[^}]*)\}")


def _floats(text):
    return [float(item) for item in text.replace(" ", "").split(",") if item]


class FakeDobotConnection:
    """A stand-in for DobotConnection: one command line in, one text reply out."""

    def __init__(self, ip="192.168.1.100", port=29999, buffer_size=144000, **_options):
        self.ip = ip
        self.port = port
        self.buffer_size = buffer_size
        self._connected = True                                  # placeholder: the fake stands for an open link
        self._auto_reconnect = False
        self._connect_timeout = None
        self._receive_timeout = None
        self._angles = list(_START_ANGLES)                       # degrees, placeholder
        self._pose = list(_START_POSE)                           # mm and degrees, placeholder
        self._mode = _START_MODE                                 # placeholder
        self._error_ids = []                                     # the controller reports no error
        self._estop_pressed = False
        self._stopped = False
        self._forced_error = None                                # one-shot ErrorID of the next command
        self._commands = []                                      # the text of every command received
        self._reply_text = ""                                    # what send_text queued for receive_text

    # -- the members of DobotConnection the driver may touch ---------------------------------------------------
    def connect(self, timeout=None):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def set_timeout(self, connect_timeout=None, receive_timeout=None):
        """The upstream class stores the two timeouts; the model has nothing to time out."""
        self._connect_timeout = connect_timeout
        self._receive_timeout = receive_timeout

    def enable_auto_reconnect(self, enable=True, callback=None):
        self._auto_reconnect = bool(enable)

    @property
    def is_connected(self):
        return self._connected

    @property
    def reconnect_enabled(self):
        return self._auto_reconnect

    def send_text(self, text):
        """Queue the reply ``send_receive_text`` would produce; the model answers immediately."""
        if not self._connected:
            raise ConnectionError(f"the fake connection to {self.ip}:{self.port} is not open")
        self._reply_text = self._answer(str(text))

    def receive_text(self, buffer_size=1024):
        if not self._connected:
            raise ConnectionError(f"the fake connection to {self.ip}:{self.port} is not open")
        reply, self._reply_text = self._reply_text, ""
        return reply

    def send_receive_text(self, text, recv_size=1024):
        """Record ``text``, apply it to the model and return the controller's reply line."""
        if not self._connected:
            raise ConnectionError(f"the fake connection to {self.ip}:{self.port} is not open")
        self._commands.append(str(text))
        return self._answer(str(text))

    # -- the controller's dashboard ---------------------------------------------------------------
    def _answer(self, text):
        if self._forced_error is not None:
            error_id, self._forced_error = self._forced_error, None
            return f"{error_id},{{}},{_name_of(text)}(...);"
        match = _COMMAND.match(text.strip())
        if match is None:
            return "-1,{},Unknown(...);"
        name, args = match.group("name"), match.group("args")
        if name == "RequestControl":
            return self._reply(name, "")
        if name == "GetAngle":
            return self._reply(name, ",".join(f"{value:.6f}" for value in self._angles))
        if name == "GetPose":
            return self._reply(name, ",".join(f"{value:.6f}" for value in self._pose))
        if name == "RobotMode":
            return self._reply(name, str(self._mode))
        if name == "GetErrorID":
            return self._reply(name, "[" + ",".join(str(item) for item in self._error_ids) + "]")
        if name in ("MovJ", "MovL"):
            point = _POINT.search(args)
            if point is None:
                return f"-1,{{}},{name}(...);"
            values = _floats(point.group("values"))
            if len(values) != 6:
                return f"-1,{{}},{name}(...);"
            self._stopped = False
            if name == "MovJ" and "joint={" in args:
                self._angles = values
            elif name == "MovL" or (name == "MovJ" and "pose={" in args):
                self._pose = values
            return self._reply(name, "1")
        if name == "Stop":
            self._stopped = True
            return self._reply(name, "")
        if name == "EmergencyStop":
            pressed = args.strip().startswith("1")
            self._estop_pressed = pressed
            if pressed:
                self._stopped = True
            return self._reply(name, "")
        return f"-1,{{}},{name}(...);"

    @staticmethod
    def _reply(name, payload):
        return f"0,{{{payload}}},{name}(...);"

    # -- hooks for test_driver.py (not DobotConnection members, never used by the driver) ----------------------
    def _force_error(self, error_id):
        """The next command answers ``error_id`` (and changes nothing)."""
        self._forced_error = error_id

    def _set_error_ids(self, error_ids):
        """The controller reports ``error_ids`` until a test changes them."""
        self._error_ids = list(error_ids)

    def _set_robot_mode(self, mode):
        """The controller reports robot mode ``mode``."""
        self._mode = int(mode)


def _name_of(text):
    match = _COMMAND.match(text.strip())
    return match.group("name") if match is not None else "Unknown"
