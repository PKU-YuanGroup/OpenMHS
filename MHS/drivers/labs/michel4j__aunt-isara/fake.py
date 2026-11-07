"""Fake backend of the ISARA automounter driver: an in-memory stand-in for auntisara.ioc:AuntISARAApp.

Gate G7: every public method defined here exists on ``AuntISARAApp`` (``send_command``, ``set_mount_params``,
``wait_for_position``, ``is_idle`` and ``shutdown``).  The ``ioc`` attribute is the process-variable model the
upstream constructor assigns at ``auntisara/ioc.py:565``; the little ``_PV`` objects behind it only provide the
``get``/``put`` pairs the upstream PV classes have, and they are not part of this fake's class surface.  Nothing here
talks to a controller.  The starting values are placeholders, not facts about any ISARA unit.
"""

import re

_PORT = re.compile(r"^(1[A-F]|2[A-F]|3[A-E]|4[A-E]|5[A-E]|6[BD])([1-9]|1[0-6])$")

# placeholder: the puck prefixes are modelled after the upstream PUCK_LIST (auntisara/ioc.py:34-40)
_PUCKS = (
    "1A", "2A", "3A", "4A", "5A",
    "1B", "2B", "3B", "4B", "5B", "6B",
    "1C", "2C", "3C", "4C", "5C",
    "1D", "2D", "3D", "4D", "5D", "6D",
    "1E", "2E", "3E", "4E", "5E",
    "1F", "2F",
)


class _PV:
    """The get/put pair of one upstream process variable (auntisara/ioc.py:207-354)."""

    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def put(self, value):
        self._value = value


class _Ioc:
    """The process-variable model of the upstream ``AuntISARA`` class, reduced to the variables this driver reads."""

    def __init__(self):
        self.status = _PV(0)                 # placeholder: 0 is StatusType.IDLE
        self.action = _PV(0)                 # placeholder: no operation active
        self.position_fbk = _PV("SOAK")      # placeholder
        self.tool_fbk = _PV(4)               # placeholder: 4 is ToolType.DOUBLE
        self.emergency_ok = _PV(1)           # placeholder: 1 is GoodBad.GOOD
        self.collision_ok = _PV(1)           # placeholder: 1 is GoodBad.GOOD
        self.lid_fbk = _PV(0)                # placeholder: 0 is OpenClosed.CLOSED
        self.mounted_fbk = _PV("")           # placeholder: no sample on the goniometer
        self.next_port = _PV("")             # placeholder: no port selected
        self.tool_param = _PV(4)             # placeholder: 4 is ToolType.DOUBLE
        self.puck_param = _PV(0)             # placeholder
        self.sample_param = _PV(0)           # placeholder
        self.dewar_temp1_fbk = _PV(-185.0)   # placeholder
        self.dewar_temp2_fbk = _PV(-180.0)   # placeholder


class FakeAuntIsara:
    """An in-memory ``AuntISARAApp``: the methods the driver calls, with no controller behind them."""

    def __init__(self, **_options):
        self.ioc = _Ioc()
        self.last_command = None
        self.panicked = False
        self.ready = False

    def send_command(self, command, *args):
        """Queue one controller command; HOME makes the fake report the home position and idle state."""
        self.last_command = command
        if command == "home":
            self.ioc.position_fbk.put("HOME")   # placeholder
            self.ioc.status.put(0)              # placeholder: 0 is StatusType.IDLE
        elif command == "panic":
            self.panicked = True

    def do_next_port(self, pv, port, ioc):
        """The upstream next-port check (auntisara/ioc.py:2069-2073), reduced to the port shape."""
        text = str(port).strip()
        pv.put(text if text and _PORT.match(text) else "")

    def set_mount_params(self, port):
        """Apply the port-to-parameter conversion of the upstream ``port2args`` (auntisara/ioc.py:356-369)."""
        if not isinstance(port, str):
            return None
        match = _PORT.match(port)
        if match is None:
            return None
        self.ioc.tool_param.put(4)                                  # placeholder: 4 is ToolType.DOUBLE
        self.ioc.puck_param.put(_PUCKS.index(match.group(1)) + 1)   # placeholder: one-based puck number
        self.ioc.sample_param.put(int(match.group(2)))              # placeholder: the pin number
        return True

    def wait_for_position(self, *positions, timeout=30, invert=False, check_abort=True):
        """The upstream check, without waiting: the fake reaches HOME synchronously in ``send_command``."""
        hit = self.ioc.position_fbk.get() in positions
        return not hit if invert else hit

    def is_idle(self):
        return self.ioc.status.get() == 0   # placeholder: 0 is StatusType.IDLE

    def shutdown(self):
        self.ready = False
